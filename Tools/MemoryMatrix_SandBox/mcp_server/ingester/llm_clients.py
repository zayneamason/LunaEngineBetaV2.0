"""
LLM Client Adapters for the Extraction Pipeline

Provides a unified interface for LLM calls, whether using Anthropic's API
or local MLX inference (Qwen via Apple Silicon).

All clients implement the same contract:
    async def create(model: str, max_tokens: int, messages: list) -> LLMResponse

Usage:
    # Anthropic (cloud)
    client = AnthropicClient(api_key="sk-...")

    # Local MLX (offline)
    client = LocalMLXClient()

    # Either one works with the pipeline:
    extractor = TranscriptExtractor(llm_client=client, model="local-qwen")
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response shape (mirrors Anthropic SDK structure)
# ---------------------------------------------------------------------------

@dataclass
class Usage:
    """Token usage stats."""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ContentBlock:
    """Single content block in a response."""
    text: str


@dataclass
class LLMResponse:
    """
    Unified response object matching the Anthropic Messages API shape.

    Access pattern:
        response.content[0].text   -> generated text
        response.usage.input_tokens
        response.usage.output_tokens
    """
    content: list[ContentBlock]
    usage: Usage


# ---------------------------------------------------------------------------
# Client protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMClient(Protocol):
    """Interface that all LLM clients must satisfy."""

    async def create(
        self, model: str, max_tokens: int, messages: list
    ) -> LLMResponse: ...


# ---------------------------------------------------------------------------
# Anthropic Client
# ---------------------------------------------------------------------------

class AnthropicClient:
    """
    Wraps AsyncAnthropic for the extraction pipeline.

    Extracted from test scripts into a canonical, reusable adapter.
    """

    def __init__(self, api_key: Optional[str] = None):
        from anthropic import AsyncAnthropic

        self._client = AsyncAnthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
        )

    async def create(
        self, model: str, max_tokens: int, messages: list
    ) -> LLMResponse:
        """Pass through to Anthropic SDK (returns native response)."""
        response = await self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        # Anthropic's response already has .content[0].text and .usage —
        # return it directly since the pipeline accesses the same attrs.
        return response


# ---------------------------------------------------------------------------
# Local MLX Client
# ---------------------------------------------------------------------------

# JSON-forcing suffix appended to extraction prompts for local models
_JSON_SUFFIX = (
    "\n\nIMPORTANT: Respond with ONLY valid JSON. "
    "No markdown code fences. No explanation text before or after the JSON. "
    "Start your response with { or [ and end with } or ]."
)


class LocalMLXClient:
    """
    Adapts Luna's MLX + Qwen setup to the extraction pipeline's LLM client
    interface, enabling fully offline extraction.

    Composes a LocalInference instance from src/luna/inference/local.py
    but bypasses its generate() method to avoid double chat-template
    formatting. Instead, we format messages ourselves via the tokenizer's
    apply_chat_template() and call mlx_lm.generate() directly.

    Args:
        model_id: HuggingFace model ID (e.g. "Qwen/Qwen2.5-3B-Instruct").
                  Defaults to whatever LocalInference resolves.
        model_path: Explicit local path to a model directory. Takes
                    precedence over model_id.
        temperature: Sampling temperature (low = more deterministic JSON).
        repetition_penalty: Repetition penalty (mild to avoid JSON breakage).
        use_4bit: Use 4-bit quantization for speed.
        json_suffix: Whether to append a JSON-forcing instruction to prompts.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        model_path: Optional[str | Path] = None,
        temperature: float = 0.1,
        repetition_penalty: float = 1.05,
        use_4bit: bool = True,
        json_suffix: bool = True,
    ):
        # Lazy import to avoid hard dependency at module level
        import sys
        sys.path.insert(
            0,
            str(Path(__file__).resolve().parents[5] / "src"),
        )
        from luna.inference.local import LocalInference, InferenceConfig

        config = InferenceConfig(
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            use_4bit=use_4bit,
            adapter_path=None,  # No LoRA for extraction
        )
        if model_id:
            config.model_id = model_id

        self._inference = LocalInference(config=config)
        self._model_path = Path(model_path) if model_path else None
        self._json_suffix = json_suffix
        self._temperature = temperature
        self._repetition_penalty = repetition_penalty

    # -- public interface ---------------------------------------------------

    async def create(
        self, model: str, max_tokens: int, messages: list
    ) -> LLMResponse:
        """
        Generate a response from the local MLX model.

        Args:
            model: Ignored (we use the locally loaded model).
            max_tokens: Maximum tokens to generate.
            messages: Anthropic-style messages list.

        Returns:
            LLMResponse with .content[0].text and .usage.
        """
        # Ensure model is loaded
        if not self._inference.is_loaded:
            if self._model_path:
                # Override the model path before loading
                self._inference.config.model_id = str(self._model_path)
            success = await self._inference.load_model()
            if not success:
                raise RuntimeError(
                    f"Failed to load MLX model: {self._inference._load_error}"
                )

        # Format the messages into a prompt string
        prompt = self._format_messages(messages)

        # Count input tokens
        input_tokens = len(self._inference._tokenizer.encode(prompt))

        # Generate via MLX in executor (non-blocking)
        response_text = await self._generate_raw(prompt, max_tokens)

        # Count output tokens
        output_tokens = len(self._inference._tokenizer.encode(response_text))

        return LLMResponse(
            content=[ContentBlock(text=response_text)],
            usage=Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
        )

    # -- internals ----------------------------------------------------------

    def _format_messages(self, messages: list) -> str:
        """
        Convert Anthropic-style messages to a chat-template-formatted prompt.

        The extraction pipeline always sends:
            [{"role": "user", "content": "<big prompt>"}]

        We pass this through the tokenizer's apply_chat_template() for proper
        Qwen formatting (with <|im_start|> tokens etc.).
        """
        # Optionally append JSON-forcing suffix to the last user message
        if self._json_suffix:
            formatted = []
            for msg in messages:
                if msg["role"] == "user":
                    formatted.append({
                        "role": "user",
                        "content": msg["content"] + _JSON_SUFFIX,
                    })
                else:
                    formatted.append(msg)
            messages = formatted

        tokenizer = self._inference._tokenizer
        if hasattr(tokenizer, "apply_chat_template"):
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        # Fallback: manual Qwen format
        prompt = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"
        return prompt

    async def _generate_raw(self, prompt: str, max_tokens: int) -> str:
        """
        Call mlx_lm.generate() directly with a pre-formatted prompt string.

        Bypasses LocalInference.generate() to avoid double chat-template
        wrapping, but reuses the same run_in_executor pattern.
        """
        from mlx_lm import generate
        from mlx_lm.sample_utils import make_sampler, make_repetition_penalty

        sampler = make_sampler(
            temp=self._temperature,
            top_p=0.9,
        )
        rep_penalty = make_repetition_penalty(
            penalty=self._repetition_penalty,
            context_size=50,
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: generate(
                self._inference._model,
                self._inference._tokenizer,
                prompt=prompt,
                max_tokens=max_tokens,
                sampler=sampler,
                logits_processors=[rep_penalty],
            ),
        )
        return response

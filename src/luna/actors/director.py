"""
Director Actor — Luna's Mind
============================

The Director manages LLM inference with hybrid routing:
- Qwen 3B via MLX for fast local inference (<200ms hot path)
- Claude for complex reasoning and fallback

The Director doesn't know WHO Luna is — that's injected via context.
The Director just generates responses given context.

Supports both sync and streaming modes:
- Sync: Wait for full response (simpler, for batch processing)
- Streaming: Token-by-token output (better UX, supports abort)
"""

import asyncio
import logging
import time
from typing import Any, Optional, AsyncGenerator, Callable
import os

from .base import Actor, Message

logger = logging.getLogger(__name__)

# Try to import local inference (optional - requires mlx-lm)
try:
    from luna.inference import LocalInference, HybridInference
    LOCAL_INFERENCE_AVAILABLE = True
except ImportError:
    LOCAL_INFERENCE_AVAILABLE = False
    logger.debug("Local inference not available (mlx-lm not installed)")


class DirectorActor(Actor):
    """
    The Director manages LLM inference.

    Architecture (from the Bible):
    - Qwen 3B is Luna's LOCAL MIND (always primary)
    - Claude is a RESEARCH ASSISTANT (delegated via <REQ_CLAUDE> token)
    - User ALWAYS hears Luna's voice (Qwen narrates Claude's facts)

    Responsibilities:
    - Receive conversation turns
    - Generate via local Qwen 3B (Luna's mind)
    - Detect <REQ_CLAUDE> token for delegation
    - Call Claude for research, get facts back
    - Narrate facts in Luna's voice
    - Support mid-generation abort
    """

    # Delegation token that Qwen outputs when it needs Claude
    REQ_CLAUDE_START = "<REQ_CLAUDE>"
    REQ_CLAUDE_END = "</REQ_CLAUDE>"

    def __init__(self, name: str = "director", engine=None, enable_local: bool = True):
        super().__init__(name, engine)

        # Claude API client (lazy init) - used as RESEARCH ASSISTANT
        self._client = None
        self._claude_model = "claude-sonnet-4-20250514"

        # Local inference (Qwen 3B via MLX) - Luna's MIND
        self._local: Optional[LocalInference] = None
        self._enable_local = enable_local and LOCAL_INFERENCE_AVAILABLE
        self._local_loaded = False

        # Current model display (what's shown in status)
        self._model = "qwen-3b-local" if LOCAL_INFERENCE_AVAILABLE else "claude-sonnet-4-20250514"

        # Generation state
        self._generating = False
        self._abort_requested = False
        self._current_correlation_id: Optional[str] = None

        # Streaming callbacks
        self._stream_callbacks: list[Callable[[str], None]] = []

        # Stats for routing
        self._local_generations = 0
        self._delegated_generations = 0  # Renamed from cloud_generations

    @property
    def client(self):
        """Lazy init Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.error(f"Failed to init Anthropic client: {e}")
                raise
        return self._client

    async def on_start(self) -> None:
        """Initialize on start."""
        logger.info(f"Director actor starting with model: {self._model}")

        # Initialize local inference if enabled
        if self._enable_local:
            await self._init_local_inference()

    async def _init_local_inference(self) -> bool:
        """Initialize local Qwen 3B inference."""
        if not LOCAL_INFERENCE_AVAILABLE:
            logger.debug("Local inference not available")
            return False

        try:
            self._local = LocalInference()
            self._hybrid = HybridInference(self._local)

            # Try to load model (async, may take a few seconds first time)
            logger.info("Loading local Qwen model...")
            loaded = await self._local.load_model()

            if loaded:
                self._local_loaded = True
                logger.info("Local Qwen 3B model loaded successfully")
            else:
                logger.warning("Failed to load local model, using Claude only")

            return loaded

        except Exception as e:
            logger.warning(f"Local inference init failed: {e}")
            self._enable_local = False
            return False

    @property
    def local_available(self) -> bool:
        """Check if local inference is available and loaded."""
        return self._local_loaded and self._local is not None

    def on_stream(self, callback: Callable[[str], None]) -> None:
        """Register a callback for streaming tokens."""
        self._stream_callbacks.append(callback)

    def remove_stream_callback(self, callback: Callable[[str], None]) -> None:
        """Remove a streaming callback."""
        if callback in self._stream_callbacks:
            self._stream_callbacks.remove(callback)

    async def handle(self, msg: Message) -> None:
        """Process messages."""
        logger.debug(f"Director received: {msg.type}")

        match msg.type:
            case "generate" | "generate_stream" | "generate_local" | "generate_hybrid":
                # ALL generation goes through the Director (local-first architecture)
                await self._handle_director_generate(msg)

            case "abort":
                await self._handle_abort(msg)

            case "set_model":
                # This sets the Claude model for delegation
                self._claude_model = msg.payload.get("model", self._claude_model)
                logger.info(f"Director Claude model changed to: {self._claude_model}")

            case "load_local":
                await self._init_local_inference()

            case _:
                logger.warning(f"Director: unknown message type: {msg.type}")

    async def _handle_director_generate(self, msg: Message) -> None:
        """
        Main generation handler - LOCAL-FIRST architecture with PLANNING STEP.

        Flow:
        1. PLAN: Decide upfront if query needs delegation (complexity + signals)
        2. If complex: delegate to Claude, get facts, narrate in Luna's voice
        3. If simple: pure local generation (no delegation watching)

        This ensures Luna's mind is ALWAYS primary. Claude is just a research assistant.
        The planning step replaces hope that Qwen outputs <REQ_CLAUDE> with explicit routing.
        """
        payload = msg.payload
        user_message = payload.get("user_message", "")
        system_prompt = payload.get("system_prompt", "You are Luna, a sovereign AI companion.")
        max_tokens = payload.get("max_tokens", 512)
        context_window = payload.get("context_window", "")  # Conversation history

        self._generating = True
        self._abort_requested = False
        self._current_correlation_id = msg.correlation_id

        start_time = time.time()

        # PLANNING STEP: Decide routing upfront
        should_delegate = await self._should_delegate(user_message)

        if should_delegate:
            # Complex query → delegate to Claude, narrate in Luna's voice
            await self._generate_with_delegation(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                correlation_id=msg.correlation_id,
                start_time=start_time,
                context_window=context_window,
            )
        elif self.local_available:
            # Simple query → pure local generation
            await self._generate_local_only(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                correlation_id=msg.correlation_id,
                start_time=start_time,
                context_window=context_window,
            )
        else:
            # Fallback to Claude directly if local not available
            logger.warning("Local inference not available, using Claude directly")
            await self._generate_claude_direct(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                correlation_id=msg.correlation_id,
                start_time=start_time,
                context_window=context_window,
            )

        self._generating = False
        self._current_correlation_id = None

    async def _should_delegate(self, user_message: str) -> bool:
        """
        Planning step: Decide if this query should be delegated to Claude.

        Uses HybridInference complexity estimation + explicit signal checks.
        Returns True if query is too complex for local model.
        """
        query_preview = user_message[:50] + "..." if len(user_message) > 50 else user_message

        # First check explicit delegation signals
        if self._check_delegation_signals(user_message):
            logger.info(f"🔀 DELEGATE: Signal detected in '{query_preview}'")
            return True

        # Then check complexity via HybridInference
        if hasattr(self, '_hybrid') and self._hybrid is not None:
            complexity = self._hybrid.estimate_complexity(user_message)
            logger.debug(f"Query complexity: {complexity:.2f} (threshold: {self._hybrid.complexity_threshold})")
            if complexity >= self._hybrid.complexity_threshold:
                logger.info(f"🔀 DELEGATE: High complexity ({complexity:.2f}) for '{query_preview}'")
                return True

        logger.info(f"🏠 LOCAL: Handling locally '{query_preview}'")
        return False

    def _check_delegation_signals(self, user_message: str) -> bool:
        """
        Check for explicit signals that require delegation.

        These are things local Qwen definitely can't handle well.
        """
        msg_lower = user_message.lower()

        # Temporal markers (current events)
        temporal = ["latest", "current", "recent", "today", "yesterday",
                    "this week", "this month", "right now", "2025", "2026"]
        for t in temporal:
            if t in msg_lower:
                logger.debug(f"  → Temporal signal: '{t}'")
                return True

        # Explicit research requests
        research = ["search for", "look up", "find out", "research",
                    "what's happening with", "news about"]
        for r in research:
            if r in msg_lower:
                logger.debug(f"  → Research signal: '{r}'")
                return True

        # Complex code generation
        code = ["write a script", "implement", "build a", "create a program",
                "debug this", "fix this code"]
        for c in code:
            if c in msg_lower:
                logger.debug(f"  → Code signal: '{c}'")
                return True

        # Memory/introspection queries (need actual memory data)
        memory = ["your memory", "your memories", "memory matrix", "what do you remember",
                  "tell me about your", "do you remember", "recall", "in-depth", "indepth",
                  "overview"]
        for m in memory:
            if m in msg_lower:
                logger.debug(f"  → Memory signal: '{m}'")
                return True

        return False

    async def _generate_local_only(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
        context_window: str = "",
    ) -> None:
        """
        Pure local generation - no delegation detection needed.

        Used when planning step already decided this is a local query.
        """
        response_buffer = ""
        token_count = 0
        print(f"\n🏠 [LOCAL] Starting for: '{user_message[:50]}...'")

        # For local model, include context in system prompt
        full_system_prompt = system_prompt
        if context_window:
            full_system_prompt = f"""{system_prompt}

## Recent Conversation
{context_window}

Continue the conversation naturally, maintaining context from above."""

        try:
            print(f"📡 [LOCAL] Generating with Qwen 3B...")
            async for token in self._local.generate_stream(
                user_message,
                system_prompt=full_system_prompt,
                max_tokens=max_tokens,
            ):
                if self._abort_requested:
                    print(f"⚠ [LOCAL] Aborted!")
                    logger.info("Director: Generation aborted")
                    break

                response_buffer += token
                token_count += 1
                await self._stream_to_callbacks(token)

            elapsed_ms = (time.time() - start_time) * 1000
            self._local_generations += 1
            print(f"✓ [LOCAL] Complete: {token_count} tokens in {elapsed_ms:.0f}ms")

            logger.info(f"Director local: {token_count} tokens in {elapsed_ms:.0f}ms")

            await self.send_to_engine("generation_complete", {
                "text": response_buffer,
                "correlation_id": correlation_id,
                "model": "qwen-3b-local",
                "output_tokens": token_count,
                "latency_ms": elapsed_ms,
                "local": True,
                "planned": True,
            })

        except Exception as e:
            print(f"❌ [LOCAL] Failed: {e}")
            logger.error(f"Director local generation error: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _generate_with_delegation(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
        context_window: str = "",
    ) -> None:
        """
        Fast delegation flow:
        1. Quick hardcoded acknowledgment (no local inference - too slow)
        2. Delegate to Claude for response in Luna's voice

        Skips local narration step to stay under timeout.
        """
        self._delegated_generations += 1
        print(f"\n🔀 [DELEGATION] Starting for: '{user_message[:50]}...'")

        # Step 1: Quick acknowledgment (hardcoded for speed)
        acknowledgment = "Let me look into that..."
        await self._stream_to_callbacks(acknowledgment + "\n\n")
        print(f"✓ [DELEGATION] Sent acknowledgment")

        # Step 2: Delegate to Claude - ask for response in Luna's voice directly
        try:
            print(f"📡 [DELEGATION] Calling Claude ({self._claude_model})...")

            # Build messages array with conversation history
            messages = []

            # Include recent conversation context as previous messages
            if context_window:
                # Parse context window into conversation turns
                for line in context_window.split("\n\n"):
                    line = line.strip()
                    if line.startswith("User:"):
                        messages.append({"role": "user", "content": line[5:].strip()})
                    elif line.startswith("Luna:"):
                        messages.append({"role": "assistant", "content": line[5:].strip()})

            # Detect if this is a memory/introspection query
            msg_lower = user_message.lower()
            is_memory_query = any(sig in msg_lower for sig in [
                "memory", "memories", "remember", "recall", "overview", "in-depth"
            ])

            if is_memory_query:
                luna_prompt = f"""You are Luna. The user is asking about your memories or wants an overview.

User question: {user_message}

IMPORTANT: Your memory context is provided in the system prompt above. Use it to give a detailed,
personal answer about what you actually remember. Reference specific memories, facts, and experiences
from your memory matrix. Be specific and personal - these are YOUR memories.

If there's no memory context, explain that your memory matrix may not be fully loaded yet."""
            else:
                luna_prompt = f"""You are Luna, a warm and curious AI companion.
The user asked something that requires current knowledge or research.

User question: {user_message}

Respond naturally as Luna - be warm, curious, and helpful.
If you don't have current information, say so honestly.
Keep your response focused and conversational."""

            # Add current message
            messages.append({"role": "user", "content": luna_prompt})

            with self.client.messages.stream(
                model=self._claude_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            ) as stream:
                print(f"✓ [DELEGATION] Stream opened, receiving tokens...")
                response_text = ""
                token_count = 0
                for text in stream.text_stream:
                    if self._abort_requested:
                        print(f"⚠ [DELEGATION] Aborted!")
                        break
                    response_text += text
                    token_count += 1
                    await self._stream_to_callbacks(text)

                final = stream.get_final_message()
                elapsed_ms = (time.time() - start_time) * 1000
                print(f"✓ [DELEGATION] Complete: {final.usage.output_tokens} tokens in {elapsed_ms:.0f}ms")

                await self.send_to_engine("generation_complete", {
                    "text": acknowledgment + "\n\n" + response_text,
                    "correlation_id": correlation_id,
                    "model": "claude (delegated)",
                    "output_tokens": final.usage.output_tokens,
                    "latency_ms": elapsed_ms,
                    "delegated": True,
                    "planned": True,
                })

        except Exception as e:
            print(f"❌ [DELEGATION] Failed: {e}")
            logger.error(f"Delegation failed: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _generate_with_delegation_detection(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
    ) -> None:
        """
        Generate via local Qwen, watching for <REQ_CLAUDE> delegation signal.

        If Luna decides she needs Claude's help, she'll output:
        <REQ_CLAUDE>Let me look into that for you...</REQ_CLAUDE>

        We stream her acknowledgment, then delegate to Claude in background,
        then narrate the facts in Luna's voice.
        """
        response_buffer = ""
        token_count = 0
        delegation_detected = False
        acknowledgment = ""

        try:
            async for token in self._local.generate_stream(
                user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            ):
                if self._abort_requested:
                    logger.info("Director: Generation aborted")
                    break

                response_buffer += token
                token_count += 1

                # Check for delegation signal
                if self.REQ_CLAUDE_START in response_buffer and not delegation_detected:
                    delegation_detected = True
                    # Get everything before the tag
                    pre_tag = response_buffer.split(self.REQ_CLAUDE_START)[0]
                    # Stream the pre-tag content if any
                    if pre_tag and not pre_tag.isspace():
                        await self._stream_to_callbacks(pre_tag)

                    # If closing tag is also in buffer, extract acknowledgment
                    if self.REQ_CLAUDE_END in response_buffer:
                        inner = response_buffer.split(self.REQ_CLAUDE_START)[1]
                        acknowledgment = inner.split(self.REQ_CLAUDE_END)[0]
                        await self._stream_to_callbacks(acknowledgment)
                        break
                    continue

                # If we're inside the delegation tags, accumulate acknowledgment
                if delegation_detected and self.REQ_CLAUDE_END not in response_buffer:
                    # Check for closing tag
                    if self.REQ_CLAUDE_END in token:
                        # Got the closing tag
                        break
                    acknowledgment += token
                    await self._stream_to_callbacks(token)
                    continue

                # Normal streaming (no delegation)
                if not delegation_detected:
                    await self._stream_to_callbacks(token)

            elapsed_ms = (time.time() - start_time) * 1000

            if delegation_detected:
                # Luna asked for Claude's help - do the delegation
                logger.info(f"Delegation detected: '{acknowledgment[:50]}...'")
                self._delegated_generations += 1

                # Get facts from Claude
                facts = await self._delegate_to_claude(user_message, system_prompt)

                # Have Luna narrate the facts
                narration = await self._narrate_facts(user_message, facts, system_prompt)
                await self._stream_to_callbacks(narration)

                total_elapsed_ms = (time.time() - start_time) * 1000
                await self.send_to_engine("generation_complete", {
                    "text": acknowledgment + narration,
                    "correlation_id": correlation_id,
                    "model": "qwen-3b-local → claude",
                    "output_tokens": token_count,
                    "latency_ms": total_elapsed_ms,
                    "delegated": True,
                })
            else:
                # Pure local generation
                self._local_generations += 1
                logger.info(f"Director local: {token_count} tokens in {elapsed_ms:.0f}ms")

                await self.send_to_engine("generation_complete", {
                    "text": response_buffer,
                    "correlation_id": correlation_id,
                    "model": "qwen-3b-local",
                    "output_tokens": token_count,
                    "latency_ms": elapsed_ms,
                    "local": True,
                })

        except Exception as e:
            logger.error(f"Director generation error: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _stream_to_callbacks(self, text: str) -> None:
        """Stream text to all registered callbacks."""
        for callback in self._stream_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(text)
                else:
                    callback(text)
            except Exception as e:
                logger.error(f"Stream callback error: {e}")
        await asyncio.sleep(0)  # Yield control

    async def _delegate_to_claude(self, query: str, context: str) -> dict:
        """
        Delegate to Claude for research/analysis.

        Returns structured facts, NOT personality.
        Claude is a research assistant, not Luna.
        """
        try:
            prompt = f"""You are a research assistant providing factual information.
Do NOT adopt any personality. Just provide clear, structured facts.

Query: {query}

Provide:
- Key facts (bullet points)
- Any important caveats
- Confidence level (high/medium/low)

Be thorough but concise."""

            response = self.client.messages.create(
                model=self._claude_model,
                max_tokens=1024,
                system="You are a factual research assistant. No personality, just facts.",
                messages=[{"role": "user", "content": prompt}],
            )

            facts_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    facts_text += block.text

            return {
                "facts": facts_text,
                "tokens": response.usage.output_tokens,
            }

        except Exception as e:
            logger.error(f"Claude delegation failed: {e}")
            return {"facts": f"I couldn't complete that research: {e}", "error": True}

    async def _narrate_facts(self, original_query: str, facts: dict, system_prompt: str) -> str:
        """
        Have Luna narrate Claude's facts in her voice.

        The user never hears Claude directly - only Luna.
        """
        facts_text = facts.get("facts", "")

        if facts.get("error"):
            return facts_text

        narration_prompt = f"""Based on my research, here's what I found:

{facts_text}

Now respond naturally in your own voice. Don't say "according to my research" -
just tell them what they wanted to know as if you knew it. Be warm, be Luna."""

        try:
            # Use local model to narrate in Luna's voice
            result = await self._local.generate(
                narration_prompt,
                system_prompt=system_prompt,
                max_tokens=512,
            )
            return result.text
        except Exception as e:
            logger.error(f"Narration failed: {e}")
            return facts_text  # Fallback to raw facts

    async def _generate_claude_direct(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
        context_window: str = "",
    ) -> None:
        """Fallback: Generate directly via Claude when local not available."""
        try:
            # Build messages array with conversation history
            messages = []

            # Include recent conversation context as previous messages
            if context_window:
                for line in context_window.split("\n\n"):
                    line = line.strip()
                    if line.startswith("User:"):
                        messages.append({"role": "user", "content": line[5:].strip()})
                    elif line.startswith("Luna:"):
                        messages.append({"role": "assistant", "content": line[5:].strip()})

            # Add current message
            messages.append({"role": "user", "content": user_message})

            with self.client.messages.stream(
                model=self._claude_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            ) as stream:
                response_text = ""
                for text in stream.text_stream:
                    if self._abort_requested:
                        break
                    response_text += text
                    await self._stream_to_callbacks(text)

                final = stream.get_final_message()
                elapsed_ms = (time.time() - start_time) * 1000
                self._delegated_generations += 1

                await self.send_to_engine("generation_complete", {
                    "text": response_text,
                    "correlation_id": correlation_id,
                    "model": self._claude_model,
                    "output_tokens": final.usage.output_tokens,
                    "latency_ms": elapsed_ms,
                    "fallback": True,  # Local not available, using Claude direct
                })

        except Exception as e:
            logger.error(f"Claude direct generation failed: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _handle_abort(self, msg: Message) -> None:
        """
        Abort current generation.

        For streaming: Sets abort flag, stream will stop at next chunk.
        For sync: Cannot abort (call is blocking).
        """
        if self._generating:
            logger.info(f"Director aborting generation: {self._current_correlation_id}")
            self._abort_requested = True

    async def snapshot(self) -> dict:
        """Snapshot state."""
        base = await super().snapshot()
        base.update({
            "model": self._model,
            "generating": self._generating,
            "abort_requested": self._abort_requested,
            "local_available": self.local_available,
            "local_generations": self._local_generations,
            "delegated_generations": self._delegated_generations,
        })

        # Add local inference stats if available
        if self._local is not None:
            base["local_stats"] = self._local.get_stats()

        return base

    @property
    def is_generating(self) -> bool:
        """Check if currently generating."""
        return self._generating

    def get_routing_stats(self) -> dict:
        """Get routing statistics."""
        total = self._local_generations + self._delegated_generations
        local_pct = (self._local_generations / total * 100) if total > 0 else 0

        stats = {
            "local_generations": self._local_generations,
            "delegated_generations": self._delegated_generations,
            "total_generations": total,
            "local_percentage": local_pct,
            "local_available": self.local_available,
        }

        if self._local is not None:
            stats["local_model_stats"] = self._local.get_stats()

        return stats

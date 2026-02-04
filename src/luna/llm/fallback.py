"""
Inference Fallback Chain.

Provides resilient LLM inference by trying providers in order
until one succeeds. Prevents Luna from hanging on API failures.

Usage:
    from luna.llm.fallback import FallbackChain, get_fallback_chain

    chain = get_fallback_chain()
    result = await chain.generate(messages, system="You are Luna...")

    # Reorder at runtime
    chain.set_chain(["groq", "local", "claude"])
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, AsyncGenerator, TYPE_CHECKING

if TYPE_CHECKING:
    from .registry import ProviderRegistry
    from luna.inference.local import LocalInference

logger = logging.getLogger(__name__)


class AllProvidersFailedError(Exception):
    """Raised when all providers in the fallback chain fail."""

    def __init__(self, message: str, attempts: list["AttemptRecord"]):
        super().__init__(message)
        self.attempts = attempts


@dataclass
class AttemptRecord:
    """Record of a single provider attempt."""
    provider: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    status_code: Optional[int] = None


@dataclass
class FallbackResult:
    """Result from fallback chain inference."""
    content: str
    provider_used: str
    providers_tried: list[str]
    attempts: list[AttemptRecord]
    total_latency_ms: float


@dataclass
class ProviderStats:
    """Statistics for a single provider."""
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.attempts if self.attempts > 0 else 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts > 0 else 0.0


@dataclass
class FallbackStats:
    """Global fallback chain statistics."""
    total_requests: int = 0
    fallback_events: int = 0
    by_provider: dict[str, ProviderStats] = field(default_factory=dict)
    last_fallback: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dict for API response."""
        return {
            "total_requests": self.total_requests,
            "fallback_events": self.fallback_events,
            "by_provider": {
                name: {
                    "attempts": stats.attempts,
                    "successes": stats.successes,
                    "failures": stats.failures,
                    "avg_latency_ms": stats.avg_latency_ms,
                    "success_rate": stats.success_rate,
                }
                for name, stats in self.by_provider.items()
            },
            "last_fallback": self.last_fallback,
        }


class FallbackChain:
    """
    Inference fallback chain.

    Tries providers in configured order until one succeeds.
    Supports both registry providers (groq, gemini, claude) and
    local inference (Qwen via MLX).
    """

    def __init__(
        self,
        registry: Optional["ProviderRegistry"] = None,
        local_inference: Optional["LocalInference"] = None,
        chain: Optional[list[str]] = None,
        per_provider_timeout_ms: int = 30000,
        max_retries_per_provider: int = 1,
    ):
        """
        Initialize fallback chain.

        Args:
            registry: LLM provider registry (for groq, gemini, claude)
            local_inference: Local inference instance (for Qwen)
            chain: Ordered list of provider names to try
            per_provider_timeout_ms: Timeout per provider attempt
            max_retries_per_provider: Retries before moving to next
        """
        self._registry = registry
        self._local = local_inference
        self._chain = chain or ["local", "groq", "claude"]
        self._timeout_ms = per_provider_timeout_ms
        self._max_retries = max_retries_per_provider
        self._stats = FallbackStats()

        logger.info(f"FallbackChain initialized: chain={self._chain}")

    def set_chain(self, providers: list[str]) -> list[str]:
        """
        Update chain order at runtime.

        Args:
            providers: New ordered list of provider names

        Returns:
            List of warnings (unknown providers, unavailable, etc)
        """
        warnings = []

        # Validate providers
        valid_providers = []
        for name in providers:
            if name == "local":
                if self._local is None:
                    warnings.append(f"local: LocalInference not configured")
                else:
                    valid_providers.append(name)
            elif self._registry and self._registry.get(name):
                valid_providers.append(name)
            else:
                warnings.append(f"{name}: Provider not found in registry")

        if valid_providers:
            self._chain = valid_providers
            logger.info(f"[FALLBACK] Chain updated: {self._chain}")
        else:
            warnings.append("No valid providers - keeping existing chain")

        return warnings

    def get_chain(self) -> list[str]:
        """Return current chain order."""
        return list(self._chain)

    def get_stats(self) -> dict:
        """Return attempt statistics."""
        return self._stats.to_dict()

    def _ensure_provider_stats(self, provider: str) -> ProviderStats:
        """Get or create stats for a provider."""
        if provider not in self._stats.by_provider:
            self._stats.by_provider[provider] = ProviderStats()
        return self._stats.by_provider[provider]

    async def _try_local(
        self,
        messages: list[dict],
        system: str,
        max_tokens: int,
    ) -> tuple[str, Optional[str]]:
        """
        Try local inference.

        Returns:
            (response_text, error) - error is None on success
        """
        if self._local is None:
            return "", "LocalInference not configured"

        if not self._local.is_available:
            return "", "MLX not available on this system"

        try:
            # Ensure model is loaded
            if not self._local.is_loaded:
                await self._local.load_model()

            # Local inference expects user message, not messages array
            # Extract the last user message
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

            if not user_message:
                return "", "No user message found"

            result = await asyncio.wait_for(
                self._local.generate(
                    user_message,
                    system_prompt=system,
                    max_tokens=max_tokens,
                ),
                timeout=self._timeout_ms / 1000,
            )

            return result.text, None

        except asyncio.TimeoutError:
            return "", "timeout"
        except Exception as e:
            return "", str(e)

    async def _try_provider(
        self,
        provider_name: str,
        messages: list[dict],
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, Optional[str], Optional[int]]:
        """
        Try a registry provider.

        Returns:
            (response_text, error, status_code)
        """
        if self._registry is None:
            return "", "Registry not configured", None

        provider = self._registry.get(provider_name)
        if provider is None:
            return "", f"Provider {provider_name} not found", None

        if not provider.is_available:
            return "", f"Provider {provider_name} not available", None

        try:
            # Import Message type from base
            from .base import Message as LLMMessage

            # Convert messages dict to Message objects
            # Provider expects system as first message or separate
            llm_messages = [LLMMessage(role="system", content=system)]
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ["user", "assistant"]:
                    llm_messages.append(LLMMessage(role=role, content=content))

            result = await asyncio.wait_for(
                provider.complete(
                    llm_messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self._timeout_ms / 1000,
            )

            return result.content, None, None

        except asyncio.TimeoutError:
            return "", "timeout", None
        except Exception as e:
            # Try to extract status code from common API errors
            status_code = None
            error_msg = str(e)

            # Common patterns
            if "credit" in error_msg.lower():
                status_code = 402  # Payment required
            elif "rate" in error_msg.lower():
                status_code = 429
            elif hasattr(e, "status_code"):
                status_code = getattr(e, "status_code")

            return "", error_msg, status_code

    async def generate(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> FallbackResult:
        """
        Generate response using fallback chain.

        Tries providers in order until one succeeds.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system: System prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            FallbackResult with response and telemetry

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        self._stats.total_requests += 1
        start_time = time.perf_counter()
        attempts: list[AttemptRecord] = []
        providers_tried: list[str] = []

        for idx, provider_name in enumerate(self._chain):
            attempt_start = time.perf_counter()
            providers_tried.append(provider_name)

            # Attempt generation
            if provider_name == "local":
                content, error = await self._try_local(
                    messages, system, max_tokens
                )
                status_code = None
            else:
                content, error, status_code = await self._try_provider(
                    provider_name, messages, system, max_tokens, temperature
                )

            latency_ms = (time.perf_counter() - attempt_start) * 1000
            success = error is None and content

            # Record attempt
            attempt = AttemptRecord(
                provider=provider_name,
                success=success,
                latency_ms=latency_ms,
                error=error,
                status_code=status_code,
            )
            attempts.append(attempt)

            # Update stats
            stats = self._ensure_provider_stats(provider_name)
            stats.attempts += 1
            stats.total_latency_ms += latency_ms
            if success:
                stats.successes += 1
            else:
                stats.failures += 1

            # Log attempt
            if success:
                logger.info(
                    f"[INFERENCE] provider={provider_name} status=success "
                    f"latency_ms={latency_ms:.0f}"
                )
            else:
                logger.warning(
                    f"[INFERENCE] provider={provider_name} status=failed "
                    f"error=\"{error}\" latency_ms={latency_ms:.0f}"
                )

            if success:
                # Log fallback if not first provider
                if idx > 0:
                    self._stats.fallback_events += 1
                    prev_provider = self._chain[idx - 1]
                    prev_error = attempts[-2].error if len(attempts) > 1 else "unknown"
                    self._stats.last_fallback = {
                        "from": prev_provider,
                        "to": provider_name,
                        "reason": prev_error,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    logger.info(
                        f"[FALLBACK] from={prev_provider} to={provider_name} "
                        f"reason=\"{prev_error}\""
                    )

                total_latency = (time.perf_counter() - start_time) * 1000
                return FallbackResult(
                    content=content,
                    provider_used=provider_name,
                    providers_tried=providers_tried,
                    attempts=attempts,
                    total_latency_ms=total_latency,
                )

        # All providers failed
        total_latency = (time.perf_counter() - start_time) * 1000
        error_summary = "; ".join(
            f"{a.provider}: {a.error}" for a in attempts
        )
        logger.error(f"[FALLBACK] All providers failed: {error_summary}")

        raise AllProvidersFailedError(
            f"All {len(attempts)} providers failed: {error_summary}",
            attempts=attempts,
        )

    async def stream(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response using fallback chain.

        Tries providers in order. If streaming fails mid-way,
        discards partial output and retries with next provider.

        Args:
            messages: List of message dicts
            system: System prompt
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Yields:
            Response tokens

        Raises:
            AllProvidersFailedError: If all providers fail
        """
        self._stats.total_requests += 1
        start_time = time.perf_counter()
        attempts: list[AttemptRecord] = []

        for idx, provider_name in enumerate(self._chain):
            attempt_start = time.perf_counter()

            try:
                # For now, fall back to non-streaming with full retry
                # TODO: Implement true streaming with mid-stream retry
                if provider_name == "local":
                    content, error = await self._try_local(
                        messages, system, max_tokens
                    )
                    if error:
                        raise RuntimeError(error)
                else:
                    content, error, status_code = await self._try_provider(
                        provider_name, messages, system, max_tokens, temperature
                    )
                    if error:
                        raise RuntimeError(error)

                latency_ms = (time.perf_counter() - attempt_start) * 1000
                attempts.append(AttemptRecord(
                    provider=provider_name,
                    success=True,
                    latency_ms=latency_ms,
                ))

                stats = self._ensure_provider_stats(provider_name)
                stats.attempts += 1
                stats.successes += 1
                stats.total_latency_ms += latency_ms

                logger.info(
                    f"[INFERENCE] provider={provider_name} status=success "
                    f"latency_ms={latency_ms:.0f} (streamed)"
                )

                # Yield content token by token for streaming effect
                # Real streaming would yield as tokens arrive
                for token in content.split():
                    yield token + " "

                return

            except Exception as e:
                latency_ms = (time.perf_counter() - attempt_start) * 1000
                error_msg = str(e)
                attempts.append(AttemptRecord(
                    provider=provider_name,
                    success=False,
                    latency_ms=latency_ms,
                    error=error_msg,
                ))

                stats = self._ensure_provider_stats(provider_name)
                stats.attempts += 1
                stats.failures += 1
                stats.total_latency_ms += latency_ms

                logger.warning(
                    f"[INFERENCE] provider={provider_name} status=failed "
                    f"error=\"{error_msg}\" latency_ms={latency_ms:.0f}"
                )

                # Log fallback
                if idx < len(self._chain) - 1:
                    next_provider = self._chain[idx + 1]
                    logger.info(
                        f"[FALLBACK] from={provider_name} to={next_provider} "
                        f"reason=\"{error_msg}\""
                    )
                    self._stats.fallback_events += 1

        # All providers failed
        error_summary = "; ".join(f"{a.provider}: {a.error}" for a in attempts)
        logger.error(f"[FALLBACK] All providers failed: {error_summary}")

        raise AllProvidersFailedError(
            f"All {len(attempts)} providers failed: {error_summary}",
            attempts=attempts,
        )


# Global fallback chain instance
_fallback_chain: Optional[FallbackChain] = None


def get_fallback_chain() -> Optional[FallbackChain]:
    """Get the global fallback chain instance."""
    return _fallback_chain


def init_fallback_chain(
    registry: Optional["ProviderRegistry"] = None,
    local_inference: Optional["LocalInference"] = None,
    chain: Optional[list[str]] = None,
) -> FallbackChain:
    """
    Initialize the global fallback chain.

    Args:
        registry: LLM provider registry
        local_inference: Local inference instance
        chain: Initial chain order

    Returns:
        The initialized FallbackChain
    """
    global _fallback_chain
    _fallback_chain = FallbackChain(
        registry=registry,
        local_inference=local_inference,
        chain=chain,
    )
    return _fallback_chain

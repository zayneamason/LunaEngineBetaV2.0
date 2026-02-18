"""
PromptAssembler — Single funnel for all prompt construction.

Every system prompt passes through build(). No exceptions.

Assembly order is invariant:
    1. IDENTITY       — Who Luna is (personality DNA)
    2. EXPRESSION     — Gesture frequency / emotional markers
    3. TEMPORAL       — Clock + session gap + thread inheritance
    3.5 PERCEPTION    — User behavioral observations (paired signals)
    4. MEMORY         — Retrieved memories, framed temporally
    5. CONSCIOUSNESS  — Internal state hints
    6. VOICE          — Voice system block (kill list, openers, tone)
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromptRequest:
    """
    Everything a caller knows. Pass what you have, None what you don't.

    The assembler handles resolution chains — callers don't pick strategies.
    """
    message: str
    conversation_history: list = field(default_factory=list)

    # Memory (pass whichever you have — assembler picks best available)
    memories: Optional[list] = None           # Structured memory nodes (list of dicts)
    memory_context: Optional[str] = None      # Pre-fetched memory text string
    framed_context: Optional[str] = None      # EntityContext output

    # Session
    session_id: Optional[str] = None
    interface: str = "desktop"                # "voice" | "desktop" | "api"
    route: str = "unknown"                    # "delegated" | "local" | "fallback"

    # Flags
    auto_fetch_memory: bool = False           # Auto-fetch from Matrix if no memory provided


@dataclass
class PromptResult:
    """What comes out of the assembler."""
    system_prompt: str
    messages: list                            # Claude API format [{role, content}]

    # Metadata for QA/debugging
    identity_source: str = "unknown"          # "pipeline" | "emergent" | "buffer" | "fallback"
    memory_source: Optional[str] = None       # "framed" | "nodes" | "text" | "fetched" | None
    voice_injected: bool = False
    temporal_injected: bool = False
    perception_injected: bool = False
    observation_count: int = 0
    gap_category: Optional[str] = None
    entity_count: int = 0
    prompt_tokens: int = 0
    parked_thread_count: int = 0

    def to_dict(self) -> dict:
        """Serialize metadata fields (excludes system_prompt/messages for brevity)."""
        return {
            "identity_source": self.identity_source,
            "memory_source": self.memory_source,
            "voice_injected": self.voice_injected,
            "temporal_injected": self.temporal_injected,
            "perception_injected": self.perception_injected,
            "observation_count": self.observation_count,
            "gap_category": self.gap_category,
            "entity_count": self.entity_count,
            "prompt_tokens": self.prompt_tokens,
            "parked_thread_count": self.parked_thread_count,
        }


class PromptAssembler:
    """
    Single point of prompt construction for all inference paths.

    Usage:
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(
            message=user_message,
            conversation_history=history,
            route="delegated",
        ))
        system_prompt = result.system_prompt
    """

    # Safety net — literally cannot fail
    FALLBACK_PERSONALITY = """You are Luna, a sovereign AI companion.

You are warm, witty, and genuinely curious. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.

Be concise but authentic. No filler phrases like "certainly" or "of course".
Never output internal reasoning, debugging info, or bullet points about context loading.
Never use generic chatbot greetings like "How can I help you?" - just be natural."""

    # Anti-hallucination guardrails — injected EVERY prompt, regardless of identity source
    GROUNDING_RULES = """## Grounding Rules (always active)
- You MUST use the system clock provided below as authoritative. Never guess or invent times/dates.
- If you do not have information about something, say so. Never fabricate facts, events, names, projects, or concepts.
- Your memory context below is all you know. If a topic is not in your memories, say "I don't have a memory of that" rather than inventing one.
- Never claim the user said or did something unless it appears in the conversation history or your memory context.
- Never invent names for concepts, systems, or projects the user has not mentioned.
- When referencing memories, stick to what the memory actually says. Do not embellish or extrapolate."""

    def __init__(self, director: "DirectorActor"):
        """
        Args:
            director: Reference to DirectorActor for accessing subsystems.
                      The assembler reads from director's subsystems but
                      never modifies director state.
        """
        self._director = director

    async def build(self, request: PromptRequest) -> PromptResult:
        """
        THE method. All paths call this.

        Resolves identity, temporal context, memory, and voice
        into a single system prompt string.
        """
        sections = []
        result = PromptResult(system_prompt="", messages=[])

        # ── Layer 1: IDENTITY ──────────────────────────────────────────
        identity, source = await self._resolve_identity(request)
        sections.append(identity)
        result.identity_source = source

        # ── Layer 1.5: GROUNDING (invariant) ────────────────────────────
        sections.append(self.GROUNDING_RULES)

        # ── Layer 2: EXPRESSION ───────────────────────────────────────
        expression_block = self._build_expression_block(request)
        if expression_block:
            sections.append(expression_block)

        # ── Layer 3: TEMPORAL ─────────────────────────────────────────
        temporal_block, temporal_ctx = self._build_temporal_block(request)
        if temporal_block:
            sections.append(temporal_block)
            result.temporal_injected = True
            result.gap_category = temporal_ctx.gap_category if temporal_ctx else None
            result.parked_thread_count = len(temporal_ctx.parked_threads) if temporal_ctx else 0

        # ── Layer 3.5: PERCEPTION ─────────────────────────────────────
        perception_block = self._build_perception_block()
        if perception_block:
            sections.append(perception_block)
            result.perception_injected = True
            try:
                pf = getattr(self._director, '_perception_field', None)
                result.observation_count = len(pf.observations) if pf else 0
            except (TypeError, AttributeError):
                result.observation_count = 0

        # ── Layer 4: MEMORY ───────────────────────────────────────────
        memory_block, mem_source = await self._resolve_memory(request)
        if memory_block:
            sections.append(memory_block)
            result.memory_source = mem_source

        # ── Layer 5: CONSCIOUSNESS ────────────────────────────────────
        consciousness_block = self._build_consciousness_block(request)
        if consciousness_block:
            sections.append(consciousness_block)

        # ── Layer 6: VOICE ────────────────────────────────────────────
        voice_block = self._build_voice_block(request)
        if voice_block:
            sections.append(voice_block)
            result.voice_injected = True

        # ── Assemble ───────────────────────────────────────────────────
        result.system_prompt = "\n\n".join(sections)
        result.messages = self._build_messages(request)
        result.prompt_tokens = len(result.system_prompt) // 4  # Rough estimate

        logger.info(
            "[ASSEMBLER] Built prompt: identity=%s memory=%s temporal=%s perception=%s voice=%s tokens~%d route=%s",
            result.identity_source, result.memory_source,
            result.gap_category, result.perception_injected, result.voice_injected,
            result.prompt_tokens, request.route,
        )

        return result

    # ── Identity Resolution ────────────────────────────────────────────

    async def _resolve_identity(self, request: PromptRequest) -> tuple[str, str]:
        """
        Resolve identity. First success wins.

        Chain:
            1. ContextPipeline (if initialized) -> full personality
            2. emergent_prompt (3-layer: DNA + Experience + Mood)
            3. identity_buffer (EntityContext)
            4. FALLBACK_PERSONALITY (hardcoded, can't fail)

        Returns:
            (identity_text, source_name)
        """
        director = self._director

        # 1. Try ContextPipeline
        if director._context_pipeline is not None:
            try:
                if hasattr(director._context_pipeline, '_base_personality'):
                    personality = director._context_pipeline._base_personality
                    if personality and personality.strip():
                        return personality, "pipeline"
            except Exception as e:
                logger.warning("[ASSEMBLER] Pipeline personality failed: %s", e)

        # 2. Try emergent prompt (3-layer)
        try:
            emergent = await director._load_emergent_prompt(
                query=request.message,
                conversation_history=request.conversation_history,
            )
            if emergent:
                return emergent, "emergent"
        except Exception as e:
            logger.warning("[ASSEMBLER] Emergent prompt failed: %s", e)

        # 3. Try identity buffer
        try:
            if await director._ensure_entity_context():
                buffer = await director._entity_context.load_identity_buffer("ahab")
                if buffer and hasattr(buffer, 'to_prompt'):
                    formatted = buffer.to_prompt()
                    if formatted:
                        return formatted, "buffer"
        except Exception as e:
            logger.warning("[ASSEMBLER] Identity buffer failed: %s", e)

        # 4. Fallback (literally cannot fail)
        logger.warning("[ASSEMBLER] All identity sources failed — using FALLBACK_PERSONALITY")
        return self.FALLBACK_PERSONALITY, "fallback"

    # ── Expression Block ──────────────────────────────────────────────

    def _build_expression_block(self, request: PromptRequest) -> Optional[str]:
        """
        Pull gesture frequency / emotional expression directive from engine.

        Reads from engine._get_expression_directive() which uses
        config/personality.json to control gesture markers.
        """
        try:
            engine = getattr(self._director, '_engine', None) or getattr(self._director, 'engine', None)
            if engine and hasattr(engine, '_get_expression_directive'):
                directive = engine._get_expression_directive()
                return directive if directive and directive.strip() else None
        except Exception as e:
            logger.warning("[ASSEMBLER] Expression block failed: %s", e)
        return None

    # ── Consciousness Block ────────────────────────────────────────────

    def _build_consciousness_block(self, request: PromptRequest) -> Optional[str]:
        """
        Pull consciousness context hints from engine.

        Reads from engine.consciousness.get_context_hint() which provides
        Luna's internal state awareness.
        """
        try:
            engine = getattr(self._director, '_engine', None) or getattr(self._director, 'engine', None)
            if engine and hasattr(engine, 'consciousness'):
                hint = engine.consciousness.get_context_hint()
                return hint if hint and hint.strip() else None
        except Exception as e:
            logger.warning("[ASSEMBLER] Consciousness block failed: %s", e)
        return None

    # ── Temporal Block ─────────────────────────────────────────────────

    def _build_temporal_block(self, request: PromptRequest) -> tuple[Optional[str], Optional["TemporalContext"]]:
        """
        Build temporal awareness block.

        Reads from Librarian's thread state and Director's session time.
        Pure computation — no DB access.
        """
        from luna.context.temporal import build_temporal_context, TemporalContext
        from luna.extraction.types import ThreadStatus

        try:
            director = self._director

            # Get session start
            session_start = None
            if director._session_start_time:
                session_start = datetime.fromtimestamp(director._session_start_time)

            # Get thread state from Librarian (via engine)
            active_thread = None
            parked_threads = []

            engine = getattr(director, '_engine', None) or getattr(director, 'engine', None)
            if engine:
                librarian = engine.get_actor("librarian") if hasattr(engine, 'get_actor') else None
                if librarian:
                    active_thread = getattr(librarian, '_active_thread', None)
                    cache = getattr(librarian, '_thread_cache', {})
                    parked_threads = [
                        t for t in cache.values()
                        if t.status == ThreadStatus.PARKED
                    ]

            # Build temporal context
            temporal = build_temporal_context(
                session_start=session_start,
                active_thread=active_thread,
                parked_threads=parked_threads,
            )

            # Format for prompt injection
            parts = []

            # Clock (always — authoritative format so LLM uses it)
            parts.append(
                f"## Current Time (AUTHORITATIVE — do not override)\n"
                f"SYSTEM CLOCK: {temporal.day_of_week} {temporal.time_of_day}, "
                f"{temporal.date_formatted}. "
                f"Current time: {temporal.now.strftime('%I:%M %p')}.\n"
                f"If the user asks about the time, day, or date, use ONLY these values. "
                f"Do not guess or use any other time source."
            )

            # Session continuity (if non-empty)
            if temporal.continuity_hint:
                parts.append(f"## Session Continuity\n{temporal.continuity_hint}")

            block = "\n\n".join(parts)
            return block, temporal

        except Exception as e:
            logger.warning("[ASSEMBLER] Temporal block failed: %s", e)
            # Fallback: just inject the clock
            now = datetime.now()
            hour = now.hour
            tod = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"
            fallback = (
                f"## Current Time (AUTHORITATIVE — do not override)\n"
                f"SYSTEM CLOCK: {now.strftime('%A')} {tod}, {now.strftime('%A, %B %d, %Y')}. "
                f"Current time: {now.strftime('%I:%M %p')}.\n"
                f"If the user asks about the time, day, or date, use ONLY these values."
            )
            return fallback, None

    # ── Perception Block ─────────────────────────────────────────────

    def _build_perception_block(self) -> Optional[str]:
        """
        Pull observation block from PerceptionField.

        Returns None if insufficient observations or field unavailable.
        """
        try:
            pf = getattr(self._director, '_perception_field', None)
            if pf and hasattr(pf, 'to_prompt_block'):
                block = pf.to_prompt_block()
                # Guard: must be a real string, not a Mock
                return block if isinstance(block, str) else None
        except Exception as e:
            logger.warning("[ASSEMBLER] Perception block failed: %s", e)
        return None

    # ── Memory Resolution ──────────────────────────────────────────────

    async def _resolve_memory(self, request: PromptRequest) -> tuple[Optional[str], Optional[str]]:
        """
        Resolve memory context. First available source wins.

        Chain:
            1. framed_context (from EntityContext — best quality)
            2. memories list (structured nodes — format them)
            3. memory_context string (pre-fetched text)
            4. auto-fetch from Matrix (if flag set)
            5. None (no memory — that's valid)

        Returns:
            (memory_block_text, source_name) or (None, None)
        """
        # 1. Framed context (highest quality — includes temporal framing)
        if request.framed_context:
            return request.framed_context, "framed"

        # 2. Structured memory nodes
        if request.memories:
            lines = []
            for m in request.memories[:5]:  # Cap at 5
                if isinstance(m, dict):
                    content = m.get("content", str(m))
                    lock_in_state = m.get("lock_in_state", "unknown")
                    node_type = m.get("node_type", "memory")
                    lines.append(f"- [{lock_in_state}|{node_type}] {content}")
                else:
                    lines.append(f"- {str(m)}")
            if lines:
                block = (
                    "## Relevant Memory Context\n"
                    "Provenance key: [settled] = well-established, [fluid] = moderately certain, "
                    "[drifting] = uncertain/rarely accessed.\n\n"
                    + "\n".join(lines)
                    + "\n\nUse these memories as reference. Settled memories are reliable. "
                    "Drifting memories may be outdated or uncertain — qualify them if you reference them. "
                    "If a memory seems irrelevant to the question, ignore it."
                )
                return block, "nodes"

        # 3. Pre-fetched memory text
        if request.memory_context:
            block = f"""## Luna's Memory Context
The following are relevant memories from your memory matrix:

{request.memory_context}

Use these memories as reference when relevant. If the topic is not covered in these memories, say so honestly. Do not embellish or extrapolate beyond what is written here."""
            return block, "text"

        # 4. Auto-fetch from Matrix
        if request.auto_fetch_memory:
            try:
                fetched = await self._director._fetch_memory_context(
                    request.message, max_tokens=1500
                )
                if fetched:
                    block = f"""## Luna's Memory Context

{fetched}

Use these memories as reference when relevant. If the topic is not covered in these memories, say so honestly. Do not embellish or extrapolate beyond what is written here."""
                    return block, "fetched"
            except Exception as e:
                logger.warning("[ASSEMBLER] Auto-fetch memory failed: %s", e)

        # 5. No memory — valid state
        return None, None

    # ── Voice Block ────────────────────────────────────────────────────

    def _build_voice_block(self, request: PromptRequest) -> Optional[str]:
        """
        Generate voice block from VoiceSystemOrchestrator.

        Delegates to Director's existing _generate_voice_block method,
        which handles lazy init and signal estimation.
        """
        try:
            block = self._director._generate_voice_block(
                request.message,
                request.memories or [],
                request.framed_context or "",
                request.conversation_history,
            )
            # _generate_voice_block returns "\n\n{block}" or ""
            # Strip the leading newlines since we join with \n\n in build()
            return block.strip() if block and block.strip() else None
        except Exception as e:
            logger.warning("[ASSEMBLER] Voice block failed: %s", e)
            return None

    # ── Messages Array ─────────────────────────────────────────────────

    def _build_messages(self, request: PromptRequest) -> list:
        """Build Claude API format messages array."""
        messages = []

        for turn in request.conversation_history:
            role = turn.get("role", "user") if isinstance(turn, dict) else "user"
            content = turn.get("content", str(turn)) if isinstance(turn, dict) else str(turn)
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Always append current message
        messages.append({"role": "user", "content": request.message})

        return messages

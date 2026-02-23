"""
PromptAssembler — Single funnel for all prompt construction.

Every system prompt passes through build(). No exceptions.

Assembly order is invariant:
    1.0  IDENTITY       — Who Luna is (personality DNA)
    1.5  GROUNDING      — Anti-hallucination guardrails
    1.55 ACCESS         — Data room permission constraints (identity-gated)
    1.6  MODE           — Response mode enum (L2 prompt control)
    1.75 CONSTRAINTS    — Confidence signals (L1 prompt control)
    2.0  EXPRESSION     — Gesture frequency / emotional markers
    3.0  TEMPORAL       — Clock + session gap + thread inheritance
    3.5  PERCEPTION     — User behavioral observations (paired signals)
    4.0  MEMORY         — Retrieved memories, framed temporally
    5.0  CONSCIOUSNESS  — Internal state hints
    6.0  VOICE          — Voice system block (kill list, openers, tone)
"""

from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING
from datetime import datetime
import logging

if TYPE_CHECKING:
    from luna.context.modes import IntentClassification
    from luna.identity.bridge import BridgeResult

logger = logging.getLogger(__name__)


@dataclass
class MemoryConfidence:
    """Structured confidence metadata from memory retrieval (L1 prompt control)."""
    match_count: int           # Total nodes returned
    relevant_count: int        # Nodes with lock_in > 0.3
    avg_similarity: float      # Mean similarity score (0-1), 0 if no matches
    best_lock_in: str          # Highest lock-in state: "settled" | "fluid" | "drifting" | "none"
    has_entity_match: bool     # Whether any detected entity appears in memory results
    query: str                 # Original query (for debugging)

    @property
    def level(self) -> str:
        """Compute confidence level from metrics."""
        if self.match_count == 0:
            return "NONE"
        if self.relevant_count >= 2 and self.best_lock_in == "settled":
            return "HIGH"
        if self.relevant_count >= 1 or self.avg_similarity > 0.5:
            return "MEDIUM"
        return "LOW"

    @property
    def directive(self) -> str:
        """Behavioral directive for this confidence level."""
        directives = {
            "NONE": (
                'Say "i don\'t have a memory of that" or "that doesn\'t ring a bell."\n'
                'Do NOT guess, invent, or bridge gaps with plausible-sounding information.\n'
                'Ask what specifically they\'re thinking of.'
            ),
            "LOW": (
                'You have thin memories on this topic. Reference what you find but qualify it.\n'
                'Say "from what i recall..." or "i have a vague memory of..."\n'
                'Do NOT fill gaps with invented details.'
            ),
            "MEDIUM": (
                'Reference memories naturally. Note if any feel outdated (drifting state).\n'
                'Stick to what the memories actually say.'
            ),
            "HIGH": (
                'Reference memories confidently. Cite specifics.\n'
                'You can build on these — they\'re well-established.'
            ),
        }
        return directives.get(self.level, directives["NONE"])

    def to_dict(self) -> dict:
        return {
            "match_count": self.match_count,
            "relevant_count": self.relevant_count,
            "avg_similarity": self.avg_similarity,
            "best_lock_in": self.best_lock_in,
            "has_entity_match": self.has_entity_match,
            "level": self.level,
            "query": self.query,
        }


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

    # L2 Prompt Control: Intent classification (from Director._classify_intent)
    intent: Optional["IntentClassification"] = None

    # Identity-gated access (from FaceID → AccessBridge)
    bridge_result: Optional[Any] = None    # BridgeResult or None


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

    # L1/L2 prompt control metadata
    mode_injected: bool = False
    response_mode: Optional[str] = None
    constraints_injected: bool = False
    memory_confidence_level: Optional[str] = None

    # Identity-gated access metadata
    access_injected: bool = False
    access_entity_id: Optional[str] = None
    access_luna_tier: Optional[str] = None
    access_dataroom_tier: Optional[int] = None
    access_denied_count: int = 0

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
            "mode_injected": self.mode_injected,
            "response_mode": self.response_mode,
            "constraints_injected": self.constraints_injected,
            "memory_confidence_level": self.memory_confidence_level,
            "access_injected": self.access_injected,
            "access_entity_id": self.access_entity_id,
            "access_luna_tier": self.access_luna_tier,
            "access_dataroom_tier": self.access_dataroom_tier,
            "access_denied_count": self.access_denied_count,
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

        Layer ordering:
            1.0  IDENTITY
            1.5  GROUNDING
            1.55 ACCESS (identity-gated data room permissions)
            1.6  MODE (L2 — response mode enum)
            1.75 CONSTRAINTS (L1 — confidence signals)
            2.0  EXPRESSION
            3.0  TEMPORAL
            3.5  PERCEPTION
            4.0  MEMORY
            5.0  CONSCIOUSNESS
            6.0  VOICE
        """
        sections = []
        result = PromptResult(system_prompt="", messages=[])

        # ── Layer 1.0: IDENTITY ────────────────────────────────────────
        identity, source = await self._resolve_identity(request)
        sections.append(identity)
        result.identity_source = source

        # ── Layer 1.5: GROUNDING (invariant) ──────────────────────────
        sections.append(self.GROUNDING_RULES)

        # ── Layer 1.55: ACCESS (identity-gated permissions) ──────────
        access_block = self._build_access_block(request)
        if access_block:
            sections.append(access_block)
            result.access_injected = True
            if request.bridge_result:
                result.access_entity_id = request.bridge_result.entity_id
                result.access_luna_tier = request.bridge_result.luna_tier
                result.access_dataroom_tier = request.bridge_result.dataroom_tier

        # ── Layer 1.6: MODE (L2 — response mode) ─────────────────────
        if request.intent is not None:
            mode_block = self._build_mode_block(request.intent)
            sections.append(mode_block)
            result.mode_injected = True
            result.response_mode = request.intent.mode.value

        # ── Resolve memory EARLY (need confidence for L1.75) ──────────
        memory_block, mem_source, mem_confidence = await self._resolve_memory_with_confidence(request)

        # ── Layer 1.75: CONSTRAINTS (L1 — confidence signals) ─────────
        if mem_confidence is not None:
            constraints_block = self._build_constraints_block(
                confidence=mem_confidence,
                intent=request.intent,
            )
            sections.append(constraints_block)
            result.constraints_injected = True
            result.memory_confidence_level = mem_confidence.level

        # ── Layer 2.0: EXPRESSION ─────────────────────────────────────
        expression_block = self._build_expression_block(request)
        if expression_block:
            sections.append(expression_block)

        # ── Layer 3.0: TEMPORAL ───────────────────────────────────────
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

        # ── Layer 4.0: MEMORY ─────────────────────────────────────────
        # (already resolved above for confidence — just inject the block)
        if memory_block:
            sections.append(memory_block)
            result.memory_source = mem_source

        # ── Layer 5.0: CONSCIOUSNESS ──────────────────────────────────
        consciousness_block = self._build_consciousness_block(request)
        if consciousness_block:
            sections.append(consciousness_block)

        # ── Layer 6.0: VOICE ──────────────────────────────────────────
        voice_block = self._build_voice_block(request)
        if voice_block:
            sections.append(voice_block)
            result.voice_injected = True

        # ── Assemble ───────────────────────────────────────────────────
        result.system_prompt = "\n\n".join(sections)
        result.messages = self._build_messages(request)
        result.prompt_tokens = len(result.system_prompt) // 4  # Rough estimate

        logger.info(
            "[ASSEMBLER] Built prompt: identity=%s memory=%s mode=%s confidence=%s "
            "temporal=%s perception=%s voice=%s tokens~%d route=%s",
            result.identity_source, result.memory_source,
            result.response_mode, result.memory_confidence_level,
            result.gap_category, result.perception_injected, result.voice_injected,
            result.prompt_tokens, request.route,
        )

        return result

    # ── L2: Mode Block ──────────────────────────────────────────────────

    def _build_mode_block(self, intent: "IntentClassification") -> str:
        """Build response mode block for prompt injection (L2)."""
        from luna.context.modes import MODE_CONTRACTS

        contract = MODE_CONTRACTS[intent.mode]
        rules = "\n".join(f"  - {r}" for r in contract["rules"])

        lines = [
            "## Response Mode (system-assigned — do not override)",
            f"[RESPONSE_MODE: {intent.mode.value}]",
            f"[MODE_CONFIDENCE: {intent.confidence:.1f}]",
            f"[IS_CONTINUATION: {intent.is_continuation}]",
            "",
            f"You are in {intent.mode.value} mode: {contract['description']}",
            "",
            f"Rules for {intent.mode.value}:",
            rules,
        ]

        if intent.is_continuation:
            lines.append("")
            lines.append("NOTE: This is a continuation of the previous topic. Maintain the thread.")

        return "\n".join(lines)

    # ── L1: Constraints Block ─────────────────────────────────────────

    def _build_constraints_block(
        self,
        confidence: "MemoryConfidence",
        intent: Optional["IntentClassification"] = None,
    ) -> str:
        """Build structured constraints block for prompt injection (L1)."""
        lines = [
            "## Response Constraints (auto-generated — do not override)",
            f"[MEMORY_MATCH: {confidence.level} — {confidence.match_count} nodes found, {confidence.relevant_count} relevant]",
            f"[ENTITY_MATCH: {'YES' if confidence.has_entity_match else 'NONE'}]",
            f"[CONFIDENCE: {confidence.level}]",
            "",
            f"For this response (CONFIDENCE={confidence.level}):",
            confidence.directive,
        ]
        return "\n".join(lines)

    # ── Access Block (Identity-Gated Permissions) ──────────────────────

    CATEGORY_NAMES = {
        1: "Company Overview", 2: "Financials", 3: "Legal",
        4: "Product", 5: "Market & Competition", 6: "Team",
        7: "Go-to-Market", 8: "Partnerships & Impact", 9: "Risk & Mitigation",
    }

    def _build_access_block(self, request: PromptRequest) -> Optional[str]:
        """
        Build data room access constraint block (Layer 1.55).

        Uses the BridgeResult passed via PromptRequest to tell the LLM
        what this person can and cannot see. The hard filter happens in
        the Director (denied docs never reach the context), but this
        block sets behavioral guardrails for how Luna handles denials.
        """
        bridge = request.bridge_result
        if bridge is None:
            # No identity — check if IdentityActor has a current face
            try:
                engine = getattr(self._director, '_engine', None) or getattr(self._director, 'engine', None)
                if engine:
                    identity_actor = engine.get_actor("identity")
                    if identity_actor and identity_actor.current.is_present:
                        # IdentityActor has a face but no bridge was passed —
                        # build a minimal block from what we know
                        current = identity_actor.current
                        return (
                            f"## Data Room Access\n"
                            f"Speaker: **{current.entity_name}** "
                            f"(luna tier: {current.luna_tier}, "
                            f"data room tier: {current.dataroom_tier})\n\n"
                            f"If asked about documents outside their access, "
                            f"do NOT acknowledge the document exists."
                        )
            except Exception as e:
                logger.warning("[ASSEMBLER] Access block identity fallback failed: %s", e)
            # Degraded mode: no face recognized, no bridge — restrict document access
            return (
                "## Identity Status — Degraded Mode\n"
                "No face recognized. Operating in degraded mode.\n"
                "You may chat freely but CANNOT discuss, reference, or acknowledge "
                "any data room documents, files, or their contents.\n"
                "If the user asks about documents, inform them that FaceID "
                "verification is required to access the data room.\n"
                "Never reveal document names, categories, or Google Drive links."
            )

        # Admin/Sovereign — no restrictions needed
        if bridge.luna_tier == "admin" and bridge.dataroom_tier <= 1:
            return None

        # Build access description
        lines = [
            "## Data Room Access Rules",
            f"Speaker: **{bridge.entity_id}** "
            f"(luna tier: {bridge.luna_tier}, data room tier: {bridge.dataroom_tier})",
        ]

        if bridge.can_see_all:
            lines.append(
                "\nThis person has full document access (Tier 1-2). "
                "No content restrictions apply."
            )
        else:
            # List accessible categories
            cat_names = [
                f"{c} ({self.CATEGORY_NAMES.get(c, '?')})"
                for c in sorted(bridge.dataroom_categories)
            ]
            lines.append(f"\nAccessible categories: {', '.join(cat_names) or 'none'}")
            lines.append("")
            lines.append("CRITICAL: You may ONLY discuss documents from the categories listed above.")
            lines.append("If asked about documents outside their access:")

            if bridge.luna_tier in ("trusted", "friend"):
                lines.append(
                    "- Acknowledge the boundary warmly, suggest they contact Ahab or Tarcila"
                )
            elif bridge.luna_tier == "guest":
                lines.append("- State that additional permissions are needed")
            else:
                lines.append("- Do NOT acknowledge the document exists at all")

            lines.append("")
            lines.append("Never reveal the existence of documents the current speaker cannot access.")

        return "\n".join(lines)

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

    async def _resolve_memory_with_confidence(
        self, request: PromptRequest
    ) -> tuple[Optional[str], Optional[str], Optional[MemoryConfidence]]:
        """
        Resolve memory context with confidence metadata (L1).

        Chain:
            1. framed_context (from EntityContext — best quality)
            2. memories list (structured nodes — format them)
            3. memory_context string (pre-fetched text)
            4. auto-fetch from Matrix (if flag set)
            5. None (no memory — that's valid)

        Returns:
            (memory_block_text, source_name, MemoryConfidence) or (None, None, confidence)
        """
        # 1. Framed context (highest quality — includes temporal framing)
        if request.framed_context:
            # Framed context from EntityContext — entity match is implicit
            confidence = MemoryConfidence(
                match_count=1,
                relevant_count=1,
                avg_similarity=0.0,
                best_lock_in="fluid",
                has_entity_match=True,
                query=request.message,
            )
            return request.framed_context, "framed", confidence

        # 2. Structured memory nodes
        if request.memories:
            lines = []
            lock_in_order = {"settled": 3, "fluid": 2, "drifting": 1, "none": 0, "unknown": 0}
            best_lock_in = "none"

            for m in request.memories[:5]:  # Cap at 5
                if isinstance(m, dict):
                    content = m.get("content", str(m))
                    lock_in_state = m.get("lock_in_state", "unknown")
                    node_type = m.get("node_type", "memory")
                    lines.append(f"- [{lock_in_state}|{node_type}] {content}")
                    # Track best lock-in
                    if lock_in_order.get(lock_in_state, 0) > lock_in_order.get(best_lock_in, 0):
                        best_lock_in = lock_in_state
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
                confidence = MemoryConfidence(
                    match_count=len(request.memories),
                    relevant_count=sum(
                        1 for m in request.memories
                        if isinstance(m, dict) and m.get("lock_in", 0) > 0.3
                    ),
                    avg_similarity=0.0,
                    best_lock_in=best_lock_in,
                    has_entity_match=False,
                    query=request.message,
                )
                return block, "nodes", confidence

        # 3. Pre-fetched memory text
        if request.memory_context:
            block = f"""## Luna's Memory Context
The following are relevant memories from your memory matrix:

{request.memory_context}

Use these memories as reference when relevant. If the topic is not covered in these memories, say so honestly. Do not embellish or extrapolate beyond what is written here."""
            confidence = MemoryConfidence(
                match_count=1,
                relevant_count=1,
                avg_similarity=0.0,
                best_lock_in="fluid",
                has_entity_match=False,
                query=request.message,
            )
            return block, "text", confidence

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
                    # Use Director's cached confidence if available
                    confidence = getattr(self._director, '_last_memory_confidence', None)
                    if confidence is None:
                        confidence = MemoryConfidence(
                            match_count=1,
                            relevant_count=1,
                            avg_similarity=0.0,
                            best_lock_in="fluid",
                            has_entity_match=False,
                            query=request.message,
                        )
                    return block, "fetched", confidence
            except Exception as e:
                logger.warning("[ASSEMBLER] Auto-fetch memory failed: %s", e)

        # 5. No memory — valid state, but still produce confidence (NONE)
        confidence = MemoryConfidence(
            match_count=0,
            relevant_count=0,
            avg_similarity=0.0,
            best_lock_in="none",
            has_entity_match=False,
            query=request.message,
        )
        return None, None, confidence

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

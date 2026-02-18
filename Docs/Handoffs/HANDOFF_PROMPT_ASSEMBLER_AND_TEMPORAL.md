# HANDOFF: Prompt Assembly Funnel + Temporal Awareness Layer

**Created:** 2026-02-17
**Author:** The Dude (Architecture)
**For:** Claude Code Execution
**Complexity:** M (4-8 hours across 2 phases)
**Depends on:** Voice system integration (complete), Thread management Layer 3 (complete)

---

## 1. CONTEXT

Director.py (3001 lines) builds system prompts in **5 separate locations** with 3 different identity-loading strategies and 3 different memory-loading strategies. Every cross-cutting concern (voice, entity context, session identity) requires patching all 5 paths individually. The recent voice system integration demonstrated this — it took finding the hot path through trial and error, then patching each location.

Additionally, Luna has **no temporal awareness**. Thread timestamps exist (`started_at`, `parked_at`, `resumed_at`), session start time is tracked, memory nodes have `created_at` — but none of this flows into the prompt. Luna can't distinguish "we were just talking" from "it's been 5 days."

This handoff addresses both problems as a single coherent change.

---

## 2. THE PROBLEM: 5 PROMPT PATHS

### Current prompt assembly locations in `director.py`:

| # | Method / Path | Line | Identity Source | Memory Source |
|---|--------------|------|----------------|---------------|
| 1 | `process()` → delegated | ~L830 | Hardcoded preamble + `framed_context` OR `emergent_prompt` OR `FALLBACK_PERSONALITY` | `memories[]` from caller |
| 2 | `process()` → local | ~L1020 | `ContextPipeline.build()` OR fallback chain | Pipeline or `context_window` |
| 3 | `process()` → fallback delegated | ~L1083 | Hardcoded preamble + `framed_context` OR `emergent_prompt` | None explicit |
| 4 | `_generate_with_delegation()` | ~L1930 | `emergent_prompt` → `identity_buffer` → `FALLBACK_PERSONALITY` | `_fetch_memory_context()` |
| 5 | `_generate_local_only()` | ~L1420 | `ContextPipeline.build()` OR legacy fallback | Pipeline handles it |

Each path independently:
- Chooses an identity source (with different fallback chains)
- Loads or skips memory
- Builds the system prompt string
- Sets `_last_system_prompt` for QA/debugging
- Has voice block injection (recently patched into each one)

**The smell:** Shotgun surgery. Every new prompt concern = 5 locations to patch.

### What already exists and works well

`ContextPipeline._build_system_prompt()` in `src/luna/context/pipeline.py` (line ~332) already does it right — single method, structured sections (personality → session → entities → memory), clear priority. But Director bypasses it in most paths.

---

## 3. THE PROBLEM: TEMPORAL BLINDNESS

Luna has timestamps everywhere but is blind at inference time:

- **No clock** — can't say "good evening" or "happy weekend"
- **No session gap** — first message after a week gets same context as a follow-up 30 seconds later
- **No thread inheritance** — parked threads with open tasks never surface in prompts

### What already exists

The Thread system (Layer 3) tracks everything needed:
- `Thread.started_at`, `Thread.parked_at`, `Thread.resumed_at`, `Thread.closed_at`
- `Thread.open_tasks[]`, `Thread.entities[]`, `Thread.turn_count`, `Thread.resume_count`
- `Librarian._active_thread`, `Librarian._thread_cache` (parked threads in memory)
- `Director._session_start_time` (float timestamp)

**No new storage is needed.** The most recently parked thread's `parked_at` timestamp IS the last interaction boundary.

---

## 4. PHASE 1: PROMPT ASSEMBLER

### 4.1 Create `src/luna/context/assembler.py`

This is the single funnel. All prompt-building paths call it.

```python
"""
PromptAssembler — Single funnel for all prompt construction.

Every system prompt passes through build(). No exceptions.
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
    gap_category: Optional[str] = None
    entity_count: int = 0
    prompt_tokens: int = 0
    parked_thread_count: int = 0
```

### 4.2 The `build()` method

Assembly order is **invariant** — every prompt follows this exact section order:

```
1. IDENTITY        — Who Luna is (personality DNA)
2. TEMPORAL         — Clock + session gap + thread inheritance (NEW)
3. MEMORY          — Retrieved memories, framed temporally
4. CONVERSATION    — Ring buffer / recent history
5. VOICE           — Voice system block (kill list, openers, tone)
```

```python
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

    def __init__(self, director: "DirectorActor"):
        """
        Args:
            director: Reference to DirectorActor for accessing subsystems.
                      The assembler reads from director's subsystems but
                      never modifies director state.
        """
        self._director = director
        self._voice_orchestrator = None  # Lazy init
    
    async def build(self, request: PromptRequest) -> PromptResult:
        """
        THE method. All paths call this.
        
        Resolves identity, temporal context, memory, conversation, and voice
        into a single system prompt string.
        """
        sections = []
        result = PromptResult(system_prompt="", messages=[])
        
        # ── Layer 1: IDENTITY ──────────────────────────────────────────
        identity, source = await self._resolve_identity(request)
        sections.append(identity)
        result.identity_source = source
        
        # ── Layer 2: TEMPORAL ──────────────────────────────────────────
        temporal_block, temporal_ctx = self._build_temporal_block(request)
        if temporal_block:
            sections.append(temporal_block)
            result.temporal_injected = True
            result.gap_category = temporal_ctx.gap_category if temporal_ctx else None
            result.parked_thread_count = len(temporal_ctx.parked_threads) if temporal_ctx else 0
        
        # ── Layer 3: MEMORY ────────────────────────────────────────────
        memory_block, mem_source = await self._resolve_memory(request)
        if memory_block:
            sections.append(memory_block)
            result.memory_source = mem_source
        
        # ── Layer 4: CONVERSATION ──────────────────────────────────────
        conv_block = self._build_conversation_block(request)
        if conv_block:
            sections.append(conv_block)
        
        # ── Layer 5: VOICE ─────────────────────────────────────────────
        voice_block = self._build_voice_block(request)
        if voice_block:
            sections.append(voice_block)
            result.voice_injected = True
        
        # ── Assemble ───────────────────────────────────────────────────
        result.system_prompt = "\n\n".join(sections)
        result.messages = self._build_messages(request)
        result.prompt_tokens = len(result.system_prompt) // 4  # Rough estimate
        
        logger.info(
            "[ASSEMBLER] Built prompt: identity=%s memory=%s temporal=%s voice=%s tokens≈%d",
            result.identity_source, result.memory_source,
            result.gap_category, result.voice_injected, result.prompt_tokens,
        )
        
        return result
```

### 4.3 Identity Resolution Chain

```python
    async def _resolve_identity(self, request: PromptRequest) -> tuple[str, str]:
        """
        Resolve identity. First success wins.
        
        Chain:
            1. ContextPipeline (if initialized) → full personality
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
                # Pipeline builds its own system prompt — extract just personality
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
                if buffer and hasattr(buffer, 'format_for_prompt'):
                    formatted = buffer.format_for_prompt()
                    if formatted:
                        return formatted, "buffer"
        except Exception as e:
            logger.warning("[ASSEMBLER] Identity buffer failed: %s", e)
        
        # 4. Fallback (literally cannot fail)
        logger.warning("[ASSEMBLER] All identity sources failed — using FALLBACK_PERSONALITY")
        return self.FALLBACK_PERSONALITY, "fallback"
```

### 4.4 Memory Resolution Chain

```python
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
                content = m.get("content", str(m)) if isinstance(m, dict) else str(m)
                lines.append(f"- {content}")
            if lines:
                block = "## Relevant Memory Context\n\n" + "\n".join(lines)
                block += "\n\nWhen answering, reference these memories naturally as your own experiences and knowledge."
                return block, "nodes"
        
        # 3. Pre-fetched memory text
        if request.memory_context:
            block = f"""## Luna's Memory Context
The following are relevant memories from your memory matrix:

{request.memory_context}

When answering, reference these memories naturally as your own experiences and knowledge."""
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

When answering, reference these memories naturally as your own experiences and knowledge."""
                    return block, "fetched"
            except Exception as e:
                logger.warning("[ASSEMBLER] Auto-fetch memory failed: %s", e)
        
        # 5. No memory — valid state
        return None, None
```

### 4.5 Voice Block

```python
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
            return block if block and block.strip() else None
        except Exception as e:
            logger.warning("[ASSEMBLER] Voice block failed: %s", e)
            return None
```

### 4.6 Messages Array

```python
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
```

---

## 5. PHASE 2: TEMPORAL AWARENESS LAYER

### 5.1 Create `src/luna/context/temporal.py`

```python
"""
Temporal Awareness — Clock injection, session gap detection, thread inheritance.

Pure functions. No DB writes. No side effects.
Called once per prompt assembly.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import logging

# Import Thread type from extraction types
from luna.extraction.types import Thread, ThreadStatus

logger = logging.getLogger(__name__)


@dataclass
class TemporalContext:
    """Computed temporal state for a single prompt assembly."""
    
    # Clock
    now: datetime = field(default_factory=datetime.now)
    time_of_day: str = "day"              # morning | afternoon | evening | night
    day_of_week: str = "Monday"
    date_formatted: str = ""              # "Tuesday, February 18, 2026"
    
    # Session gap
    session_start: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    gap_duration: Optional[timedelta] = None
    gap_category: str = "first_ever"      # continuation | short_break | new_day
                                           # | multi_day | long_absence | first_ever
    
    # Thread inheritance
    active_thread: Optional[Thread] = None
    parked_threads: list = field(default_factory=list)
    resumable_summary: Optional[str] = None
    
    # Derived
    is_greeting_appropriate: bool = True
    continuity_hint: str = ""


def build_temporal_context(
    session_start: Optional[datetime] = None,
    active_thread: Optional[Thread] = None,
    parked_threads: Optional[list] = None,
    last_interaction: Optional[datetime] = None,
) -> TemporalContext:
    """
    Pure function. Computes temporal context from clock + thread state.
    
    Args:
        session_start: When this session began
        active_thread: Currently active thread (from Librarian)
        parked_threads: Parked threads (from Librarian._thread_cache)
        last_interaction: Last message timestamp from any session.
                         If None, falls back to most recent parked_at.
    
    Returns:
        TemporalContext ready for prompt injection.
    """
    now = datetime.now()
    parked = parked_threads or []
    
    # ── Clock ──
    hour = now.hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"
    
    # ── Gap detection ──
    # If no explicit last_interaction, derive from most recent parked thread
    effective_last = last_interaction
    if effective_last is None and parked:
        # Most recently parked thread's parked_at IS the last interaction boundary
        parked_with_times = [t for t in parked if t.parked_at is not None]
        if parked_with_times:
            most_recent = max(parked_with_times, key=lambda t: t.parked_at)
            effective_last = most_recent.parked_at
    
    gap = None
    gap_category = "first_ever"
    
    if effective_last:
        gap = now - effective_last
        minutes = gap.total_seconds() / 60
        
        if minutes < 5:
            gap_category = "continuation"
        elif minutes < 120:
            gap_category = "short_break"
        elif gap.days < 1:
            gap_category = "new_day"
        elif gap.days <= 7:
            gap_category = "multi_day"
        else:
            gap_category = "long_absence"
    
    # ── Thread inheritance ──
    continuity = _build_continuity_hint(
        gap_category, active_thread, parked, time_of_day
    )
    
    resumable = None
    with_tasks = [t for t in parked if t.open_tasks and t.status == ThreadStatus.PARKED]
    if with_tasks:
        resumable = f"{len(with_tasks)} parked thread{'s' if len(with_tasks) != 1 else ''} with open tasks"
    
    return TemporalContext(
        now=now,
        time_of_day=time_of_day,
        day_of_week=now.strftime("%A"),
        date_formatted=now.strftime("%A, %B %d, %Y"),
        session_start=session_start,
        last_interaction=effective_last,
        gap_duration=gap,
        gap_category=gap_category,
        active_thread=active_thread,
        parked_threads=parked,
        resumable_summary=resumable,
        is_greeting_appropriate=gap_category not in ("continuation",),
        continuity_hint=continuity,
    )


def _build_continuity_hint(
    gap_category: str,
    active_thread: Optional[Thread],
    parked_threads: list,
    time_of_day: str,
) -> str:
    """Format thread state into natural prompt language based on gap."""
    
    sections = []
    
    if gap_category == "continuation":
        # No injection needed — mid-conversation
        return ""
    
    if gap_category == "short_break":
        if active_thread:
            sections.append(f"You were discussing: {active_thread.topic}")
        return "\n".join(sections)
    
    if gap_category in ("new_day", "multi_day"):
        # Surface parked threads with open tasks
        with_tasks = [
            t for t in parked_threads
            if t.open_tasks and t.status == ThreadStatus.PARKED
        ]
        without_tasks = [
            t for t in parked_threads
            if not t.open_tasks and t.status == ThreadStatus.PARKED
        ][:2]  # Cap
        
        if with_tasks:
            sections.append("## Parked Threads (with open tasks)")
            for t in with_tasks[:3]:
                age = _humanize_age(t.parked_at)
                sections.append(
                    f'- "{t.topic}" — parked {age} '
                    f'({t.turn_count} turns, {len(t.open_tasks)} open)'
                )
        
        if without_tasks:
            topics = ", ".join(f'"{t.topic}"' for t in without_tasks)
            sections.append(f"Also parked (no open tasks): {topics}")
        
        if gap_category == "multi_day":
            sections.append(
                "\nDon't dump thread context unprompted. "
                "Let Ahab lead — surface these only if relevant."
            )
        
        return "\n".join(sections)
    
    if gap_category == "long_absence":
        total = len(parked_threads)
        with_tasks = sum(1 for t in parked_threads if t.open_tasks)
        if total > 0:
            sections.append(
                f"You have {total} parked thread{'s' if total != 1 else ''} "
                f"({with_tasks} with open tasks)."
            )
        sections.append(
            "Don't info-dump. Let Ahab set the pace. "
            "Surface threads only when directly relevant."
        )
        return "\n".join(sections)
    
    # first_ever
    return ""


def _humanize_age(dt: Optional[datetime]) -> str:
    """Convert a datetime to a human-readable age string."""
    if dt is None:
        return "some time ago"
    
    delta = datetime.now() - dt
    minutes = delta.total_seconds() / 60
    
    if minutes < 60:
        return f"{int(minutes)} minutes ago"
    
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    
    days = delta.days
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    
    weeks = days // 7
    if weeks == 1:
        return "last week"
    
    return f"{weeks} weeks ago"
```

### 5.2 Wire temporal into PromptAssembler

Add this method to the `PromptAssembler` class:

```python
    def _build_temporal_block(self, request: PromptRequest) -> tuple[Optional[str], Optional[TemporalContext]]:
        """
        Build temporal awareness block.
        
        Reads from Librarian's thread state and Director's session time.
        Pure computation — no DB access.
        """
        from luna.context.temporal import build_temporal_context, TemporalContext
        
        try:
            director = self._director
            
            # Get session start
            session_start = None
            if director._session_start_time:
                session_start = datetime.fromtimestamp(director._session_start_time)
            
            # Get thread state from Librarian (via engine)
            active_thread = None
            parked_threads = []
            
            engine = director._engine
            if engine:
                librarian = engine.get_actor("librarian")
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
            
            # Clock (always)
            parts.append(
                f"## Current Time\n"
                f"It is {temporal.day_of_week} {temporal.time_of_day}, "
                f"{temporal.date_formatted}."
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
            fallback = f"## Current Time\nIt is {now.strftime('%A')} {tod}, {now.strftime('%A, %B %d, %Y')}."
            return fallback, None
```

---

## 6. WIRING INTO DIRECTOR

### 6.1 Replace prompt assembly in each path

Each of the 5 prompt-building locations in `director.py` gets replaced with a call to the assembler.

**Create the assembler in `__init__`:**

```python
# In DirectorActor.__init__, after existing initialization:
from luna.context.assembler import PromptAssembler
self._assembler = PromptAssembler(self)
```

**Pattern for each path — example for `_generate_with_delegation()` (~L1930):**

BEFORE (50+ lines of inline prompt assembly):
```python
enhanced_system_prompt = system_prompt
if identity_context:
    enhanced_system_prompt = f"""{enhanced_system_prompt}\n{identity_context}"""
enhanced_system_prompt = f"""{enhanced_system_prompt}\n## Current Session\nYou are currently talking to Ahab..."""
if memory_context:
    enhanced_system_prompt = f"""{enhanced_system_prompt}\n## Luna's Memory Context\n{memory_context}\nWhen answering..."""
mem_list = [{"content": memory_context}] if memory_context else []
enhanced_system_prompt += self._generate_voice_block(user_message, mem_list, identity_context, conversation_history)
self._last_system_prompt = enhanced_system_prompt
```

AFTER (6 lines):
```python
result = await self._assembler.build(PromptRequest(
    message=user_message,
    conversation_history=conversation_history,
    memory_context=memory_context,
    route="delegated",
    auto_fetch_memory=not bool(memory_context),
))
enhanced_system_prompt = result.system_prompt
self._last_system_prompt = result.system_prompt
self._last_route_decision = "delegated"
```

### 6.2 All 5 paths to update

**Path 1: `process()` → delegated (~L830)**
```python
result = await self._assembler.build(PromptRequest(
    message=message,
    conversation_history=conversation_history,
    memories=memories,
    framed_context=framed_context,
    route="delegated",
))
system_prompt = result.system_prompt
```

**Path 2: `process()` → local (~L1020)**

Note: When ContextPipeline is available and succeeds, continue using it (it has its own prompt builder that handles entity detection inline). Only use the assembler as fallback when pipeline fails or is unavailable.

```python
if self._context_pipeline is not None:
    try:
        packet = await self._context_pipeline.build(message)
        system_prompt = packet.system_prompt
        # TODO Phase 3: Merge ContextPipeline with PromptAssembler
    except Exception as e:
        logger.warning(f"[PROCESS-LOCAL] Pipeline failed, using assembler: {e}")
        result = await self._assembler.build(PromptRequest(
            message=message,
            conversation_history=conversation_history,
            memories=memories,
            framed_context=framed_context,
            route="local",
        ))
        system_prompt = result.system_prompt
else:
    result = await self._assembler.build(PromptRequest(
        message=message,
        conversation_history=conversation_history,
        memories=memories,
        framed_context=framed_context,
        route="local",
    ))
    system_prompt = result.system_prompt
```

**Path 3: `process()` → fallback delegated (~L1083)**
```python
result = await self._assembler.build(PromptRequest(
    message=message,
    conversation_history=conversation_history,
    framed_context=framed_context,
    route="fallback",
    auto_fetch_memory=True,
))
system_prompt = result.system_prompt
```

**Path 4: `_generate_with_delegation()` (~L1930)**
```python
result = await self._assembler.build(PromptRequest(
    message=user_message,
    conversation_history=conversation_history,
    memory_context=memory_context,
    route="delegated",
    auto_fetch_memory=not bool(memory_context),
))
enhanced_system_prompt = result.system_prompt
```

**Path 5: `_generate_local_only()` (~L1420)**

Same note as Path 2 — ContextPipeline takes priority when available. Use assembler as fallback.

### 6.3 Remove inline prompt assembly code

After wiring the assembler calls, **remove** the following from each path:
- Identity fallback chains (emergent → buffer → FALLBACK_PERSONALITY)
- Manual memory formatting
- Voice block injection calls (`_generate_voice_block`)
- Hardcoded preambles ("You are Luna, a sovereign AI companion...")
- Hardcoded session context ("You are currently talking to Ahab...")

Keep:
- `_last_system_prompt` assignment (from `result.system_prompt`)
- `_last_route_decision` assignment
- The actual LLM call (FallbackChain, Claude API, local inference)
- Context audit logging (but update to use `result.metadata`)

---

## 7. FILES

| File | Action | Description |
|------|--------|-------------|
| `src/luna/context/assembler.py` | **NEW** | PromptAssembler class, PromptRequest/PromptResult dataclasses |
| `src/luna/context/temporal.py` | **NEW** | TemporalContext, build_temporal_context(), gap categories, thread formatting |
| `src/luna/actors/director.py` | **MODIFY** | Wire assembler into 5 paths, remove inline prompt assembly |
| `tests/test_assembler.py` | **NEW** | Identity chain, memory chain, assembly order, voice injection |
| `tests/test_temporal.py` | **NEW** | Gap categories, thread formatting, clock injection, edge cases |

---

## 8. TESTING

### 8.1 PromptAssembler Tests

```python
# Identity chain: fallback fires when all else fails
async def test_identity_fallback():
    assembler = PromptAssembler(mock_director_no_subsystems())
    result = await assembler.build(PromptRequest(message="hello"))
    assert "Luna" in result.system_prompt
    assert result.identity_source == "fallback"

# Memory chain: framed_context takes priority over memories list
async def test_memory_priority():
    result = await assembler.build(PromptRequest(
        message="test",
        framed_context="framed memory content",
        memories=[{"content": "node memory"}],
    ))
    assert "framed memory content" in result.system_prompt
    assert result.memory_source == "framed"

# Assembly order: identity before temporal before memory before voice
async def test_assembly_order():
    result = await assembler.build(PromptRequest(message="hello"))
    prompt = result.system_prompt
    # Identity should come before temporal
    identity_pos = prompt.find("Luna")
    temporal_pos = prompt.find("Current Time")
    assert identity_pos < temporal_pos
    
# Voice block is always last
async def test_voice_always_last():
    result = await assembler.build(PromptRequest(message="hello"))
    if result.voice_injected:
        voice_pos = result.system_prompt.find("<luna_voice")
        memory_pos = result.system_prompt.find("Memory Context")
        if memory_pos > -1:
            assert voice_pos > memory_pos

# No memory is valid
async def test_no_memory_valid():
    result = await assembler.build(PromptRequest(message="hello"))
    assert result.system_prompt  # Not empty
    assert result.memory_source is None  # Fine

# Metadata populated
async def test_metadata():
    result = await assembler.build(PromptRequest(message="hello"))
    assert result.identity_source in ("pipeline", "emergent", "buffer", "fallback")
    assert result.prompt_tokens > 0
```

### 8.2 Temporal Awareness Tests

```python
from luna.context.temporal import build_temporal_context, TemporalContext
from luna.extraction.types import Thread, ThreadStatus
from datetime import datetime, timedelta

# Gap categories
def test_continuation_gap():
    ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(minutes=2))
    assert ctx.gap_category == "continuation"
    assert ctx.continuity_hint == ""  # No injection

def test_multi_day_gap():
    ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(days=3))
    assert ctx.gap_category == "multi_day"
    assert ctx.is_greeting_appropriate

def test_first_ever():
    ctx = build_temporal_context()  # No last_interaction
    assert ctx.gap_category == "first_ever"

# Thread inheritance
def test_parked_threads_surface_on_multi_day():
    thread = Thread(
        id="t1", topic="voice system",
        status=ThreadStatus.PARKED,
        open_tasks=["task1"],
        turn_count=8,
        parked_at=datetime.now() - timedelta(days=2),
    )
    ctx = build_temporal_context(
        last_interaction=datetime.now() - timedelta(days=3),
        parked_threads=[thread],
    )
    assert "voice system" in ctx.continuity_hint
    assert "open" in ctx.continuity_hint

def test_last_interaction_derived_from_parked_thread():
    """No explicit last_interaction → derive from most recent parked_at."""
    thread = Thread(
        id="t1", topic="test",
        status=ThreadStatus.PARKED,
        parked_at=datetime.now() - timedelta(hours=6),
    )
    ctx = build_temporal_context(parked_threads=[thread])
    assert ctx.gap_category == "new_day"  # 6 hours → new_day

# Clock
def test_time_of_day():
    ctx = build_temporal_context()
    assert ctx.time_of_day in ("morning", "afternoon", "evening", "night")
    assert ctx.day_of_week  # Non-empty
    assert ctx.date_formatted  # Non-empty

# Restraint instructions
def test_long_absence_restraint():
    ctx = build_temporal_context(
        last_interaction=datetime.now() - timedelta(days=14),
        parked_threads=[
            Thread(id="t1", topic="a", status=ThreadStatus.PARKED, parked_at=datetime.now() - timedelta(days=14)),
            Thread(id="t2", topic="b", status=ThreadStatus.PARKED, open_tasks=["x"], parked_at=datetime.now() - timedelta(days=10)),
        ],
    )
    assert "Don't info-dump" in ctx.continuity_hint
```

### 8.3 Integration Test

```python
# End-to-end: assembler produces valid prompt with all layers
async def test_full_assembly_with_temporal():
    """Verify complete prompt has identity → temporal → memory → voice ordering."""
    assembler = PromptAssembler(real_director)
    result = await assembler.build(PromptRequest(
        message="good morning",
        memory_context="Ahab likes coffee",
        route="delegated",
    ))
    
    prompt = result.system_prompt
    
    # All layers present
    assert "Luna" in prompt                    # Identity
    assert "Current Time" in prompt            # Temporal
    assert "Ahab likes coffee" in prompt       # Memory
    
    # Temporal before memory
    assert prompt.index("Current Time") < prompt.index("coffee")
    
    # Metadata correct
    assert result.temporal_injected is True
    assert result.gap_category is not None
```

---

## 9. SUCCESS CRITERIA

Phase 1 (Assembler) is complete when:
1. All 5 prompt paths call `PromptAssembler.build()`
2. Inline prompt assembly removed from director.py (identity chains, memory formatting, voice injection)
3. `PromptResult.metadata` captures identity source, memory source, voice state for QA
4. `/slash/prompt` still works (reads from `_last_system_prompt`)
5. All existing tests pass (no behavioral regression)
6. Voice block still present in prompts (verified via `/slash/prompt`)

Phase 2 (Temporal) is complete when:
7. Clock injected into every prompt (`## Current Time` section)
8. Gap category correctly computed from thread timestamps
9. Parked threads with open tasks surface in multi_day/long_absence gaps
10. Restraint instructions present for long_absence (no info-dump)
11. `continuation` gap injects nothing (no redundant context)
12. `/slash/prompt` shows temporal block between identity and memory

---

## 10. WHAT THIS DOES NOT DO

- **Does not merge ContextPipeline with PromptAssembler** — that's Phase 3 (future). For now, ContextPipeline still handles the local path when available. The assembler is a parallel system that covers all paths.
- **Does not add timestamps to ConversationRing turns** — the ring stays role+content. Temporal framing comes from the temporal layer, not per-turn timestamps.
- **Does not create new DB tables or storage** — all temporal data derived from existing thread timestamps and session start time.
- **Does not change thread lifecycle** — threads still create/park/resume/close the same way. The temporal layer is read-only.

---

## 11. EXECUTION ORDER

1. Create `src/luna/context/temporal.py` (standalone, no dependencies beyond `extraction/types.py`)
2. Create `src/luna/context/assembler.py` (depends on `temporal.py` and director subsystems)
3. Create `tests/test_temporal.py` — run and verify
4. Create `tests/test_assembler.py` — run and verify
5. Wire assembler into `DirectorActor.__init__`
6. Replace Path 4 (`_generate_with_delegation`) first — this is the hot path
7. Verify via `/slash/prompt` that prompt has identity + temporal + memory + voice
8. Replace remaining paths (1, 2, 3, 5)
9. Remove dead inline assembly code
10. Run full test suite
11. Restart server, send test messages, verify end-to-end

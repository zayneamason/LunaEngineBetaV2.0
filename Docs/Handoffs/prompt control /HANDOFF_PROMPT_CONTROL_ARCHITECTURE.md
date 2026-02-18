# HANDOFF: Luna Prompt Control Architecture
## Structured Behavioral Injection System — Levels 1, 2, 3

**Date:** February 18, 2026
**Author:** Architecture session (Ahab + Claude)
**Status:** SPEC COMPLETE — Ready for implementation
**Scope:** PromptAssembler injection + Director intent classification + ConversationStateMachine
**Target:** Luna Engine v2.0 — `src/luna/context/`, `src/luna/actors/director.py`, `src/luna/consciousness/`

---

## Problem Statement

Luna confabulates, loses conversational threads, and leaks prompt configuration as factual claims. Root cause: the system prompt uses **prose instructions** ("be truthful, don't confabulate") that small/medium models cannot reliably reason about. The model has no structured awareness of what it knows, what mode it's in, or what behavioral constraints apply to the current turn.

### Bugs This Kills (from real conversation logs)

| Bug | Symptom | Root Cause |
|-----|---------|------------|
| "Tech teams" confabulation | Luna invents teams that don't exist | No confidence signal — model fills gaps |
| GitHub CI fabrication | Luna describes CI pipelines never discussed | Memory retrieval returns nothing; model guesses |
| "keep going" thread loss | Follow-up causes complete topic change | No continuation detection; no state persistence |
| Prompt leakage | "peer-to-peer" style config → "tech team" fact | Model treats personality instructions as world knowledge |
| Repetition loops | Opening response duplicates 3-4 times | Separate issue (streaming bug) — not addressed here |

---

## Architecture Overview

Three levels of structured control injection. Each subsumes the previous. Build incrementally.

```
EXISTING ASSEMBLY ORDER          WITH ALL 3 LEVELS
─────────────────────────        ─────────────────────────────
1.0  IDENTITY                    1.0   IDENTITY
1.5  GROUNDING_RULES             1.5   GROUNDING_RULES (subsumed by L3 STATE)
                                 1.6   MODE BLOCK (L2)
                                 1.7   STATE BLOCK (L3)
                                 1.75  CONSTRAINTS BLOCK (L1)
2.0  EXPRESSION                  2.0   EXPRESSION
3.0  TEMPORAL                    3.0   TEMPORAL
3.5  PERCEPTION                  3.5   PERCEPTION
4.0  MEMORY                      4.0   MEMORY
5.0  CONSCIOUSNESS               5.0   CONSCIOUSNESS
6.0  VOICE                       6.0   VOICE
```

---

## PHASE 1: Level 1 + Level 2 (Build Together)

**Effort:** ~6 hours CC
**Prerequisite:** None — additive to existing assembler

### Level 1: Injected Variables (Confidence Signals)

#### Concept

Replace prose anti-confabulation rules with **machine-readable confidence signals** injected at the decision point. The model sees `[CONFIDENCE: LOW]` right next to the instruction about what to do when confidence is low. No reasoning chain needed.

#### New Dataclass: `MemoryConfidence`

**File:** `src/luna/context/assembler.py`

```python
@dataclass
class MemoryConfidence:
    """Structured confidence metadata from memory retrieval."""
    match_count: int           # Total nodes returned
    relevant_count: int        # Nodes with similarity > threshold
    avg_similarity: float      # Mean similarity score (0-1), 0 if no matches
    best_lock_in: str          # Highest lock-in state among matches: "settled" | "fluid" | "drifting" | "none"
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
```

#### Changes to `_resolve_memory()`

Currently returns `(memory_block_text, source_name)`. Change to return `(memory_block_text, source_name, MemoryConfidence)`.

The confidence metadata comes from the retrieval pipeline. Each retrieval path needs to produce it:

**Path 1: `framed_context`** — EntityContext already has entity match info. Extract match count from the framing process. Confidence = HIGH if entities matched, MEDIUM otherwise.

**Path 2: `memories` list** — Count nodes, check lock_in_state distribution. Each MemoryNode already has `lock_in`, `lock_in_state`, `confidence` fields.

```python
# In _resolve_memory, after building memory block from nodes:
confidence = MemoryConfidence(
    match_count=len(request.memories),
    relevant_count=sum(1 for m in request.memories if m.get("lock_in", 0) > 0.3),
    avg_similarity=0.0,  # Not available from node list path
    best_lock_in=max(
        (m.get("lock_in_state", "drifting") for m in request.memories),
        key=lambda s: {"settled": 3, "fluid": 2, "drifting": 1, "none": 0}.get(s, 0),
        default="none"
    ),
    has_entity_match=False,  # TODO: cross-reference with entity detection
    query=request.message,
)
```

**Path 3: `memory_context` string** — Minimal metadata available. Default to MEDIUM confidence (we have text but can't assess quality).

**Path 4: auto-fetch** — The `_fetch_memory_context` and `_fetch_constellation_context` methods need to return metadata alongside the text. This is the biggest change — see "Memory Retrieval Metadata" section below.

**Path 5: No memory** — Return `MemoryConfidence(match_count=0, relevant_count=0, avg_similarity=0, best_lock_in="none", has_entity_match=False, query=request.message)`.

#### New Method: `_build_constraints_block()`

```python
def _build_constraints_block(
    self,
    confidence: MemoryConfidence,
    intent: "IntentClassification",  # From L2 — None if L2 not yet built
) -> str:
    """Build structured constraints block for prompt injection."""
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
```

#### Injection Point in `build()`

```python
async def build(self, request: PromptRequest) -> PromptResult:
    # ... existing Layer 1 (IDENTITY) ...
    # ... existing Layer 1.5 (GROUNDING) ...

    # ── Layer 1.75: CONSTRAINTS ──────────────────────────────────
    # Must come AFTER memory resolution so we have confidence data
    # But injected BEFORE memory block so model sees constraints first
    memory_block, mem_source, mem_confidence = await self._resolve_memory(request)

    constraints_block = self._build_constraints_block(
        confidence=mem_confidence,
        intent=getattr(request, 'intent', None),
    )
    sections.append(constraints_block)

    if memory_block:
        sections.append(memory_block)
        result.memory_source = mem_source

    # ... rest of assembly ...
```

**Note the ordering change:** Memory is resolved early (to get confidence), but the constraints block is injected BEFORE the memory block. The model reads "CONFIDENCE: LOW → don't guess" before it reads the actual memories. This is critical — constraints prime behavior before context provides temptation.

---

### Level 2: Response Mode Enum

#### Concept

The Director classifies query **intent** alongside complexity, injecting a `RESPONSE_MODE` enum that constrains the model's entire behavioral space. The model doesn't pick behavior — the system does.

#### New Enum: `ResponseMode`

**File:** `src/luna/context/modes.py` (new file)

```python
from enum import Enum
from dataclasses import dataclass


class ResponseMode(Enum):
    CHAT = "CHAT"
    RECALL = "RECALL"
    REFLECT = "REFLECT"
    ASSIST = "ASSIST"
    UNCERTAIN = "UNCERTAIN"


# Mode behavioral contracts (injected into prompt)
MODE_CONTRACTS = {
    ResponseMode.CHAT: {
        "description": "Casual conversation. Be warm, be Luna.",
        "rules": [
            "Be natural and conversational",
            "No memory claims needed unless naturally relevant",
            "Don't reference memories unless the topic calls for it",
            "Match the user's energy and tone",
        ],
    },
    ResponseMode.RECALL: {
        "description": "User asked about past events or memories. Memory-constrained mode.",
        "rules": [
            "Use ONLY memories listed in context below",
            "If no memories match, say 'i don't have a memory of that'",
            "Do NOT invent details, events, people, or projects",
            "Cite what you actually find — be specific",
            "If memories are thin, say so: 'that's what i've got...'",
        ],
    },
    ResponseMode.REFLECT: {
        "description": "User asked how you feel or what you think. Draw from experience.",
        "rules": [
            "Draw from personality DNA + experience layer",
            "Be genuine, not performative",
            "You can have opinions — share them authentically",
            "Reference relevant memories if they inform your perspective",
        ],
    },
    ResponseMode.ASSIST: {
        "description": "User needs help with a task. Be precise and focused.",
        "rules": [
            "Stay on topic — don't wander",
            "Be precise and actionable",
            "Ask clarifying questions if the request is ambiguous",
            "Use appropriate technical depth for the task",
        ],
    },
    ResponseMode.UNCERTAIN: {
        "description": "Insufficient context to determine intent.",
        "rules": [
            "Ask ONE clarifying question",
            "Don't guess what the user wants",
            "Keep it brief — 'what do you mean by that?' is fine",
        ],
    },
}


@dataclass
class IntentClassification:
    """Result of intent classification."""
    mode: ResponseMode
    confidence: float          # 0-1 how sure we are
    signals: list              # What triggered this classification
    is_continuation: bool      # Short follow-up inheriting previous mode
    previous_mode: ResponseMode = ResponseMode.CHAT  # For continuity tracking
```

#### New Method: `Director._classify_intent()`

**File:** `src/luna/actors/director.py`

This **replaces** `_check_delegation_signals()` — same keyword patterns, richer output.

```python
async def _classify_intent(
    self,
    message: str,
    conversation_history: list,
) -> IntentClassification:
    """
    Classify user intent into a ResponseMode.

    Runs BEFORE routing. The mode is injected into the prompt
    regardless of which inference backend handles generation.

    Classification priority:
        1. Continuation detection (short follow-ups inherit previous mode)
        2. Explicit mode signals (keyword matching)
        3. Structural signals (question marks, message length)
        4. Default to CHAT
    """
    msg = message.strip()
    msg_lower = msg.lower()
    signals = []

    # ── 1. Continuation Detection ──────────────────────────────
    # Short messages after substantive responses = same topic
    if len(msg) < 30 and conversation_history:
        continuation_triggers = [
            "keep going", "more", "continue", "go on", "and?",
            "what else", "tell me more", "yeah", "yes", "mhm",
            "ok", "okay", "right", "sure", "cool", ":)", "👀",
            "interesting", "huh", "wow", "really", "no way",
        ]
        if any(t in msg_lower for t in continuation_triggers):
            prev_mode = getattr(self, '_last_classified_mode', ResponseMode.CHAT)
            return IntentClassification(
                mode=prev_mode,
                confidence=0.9,
                signals=["continuation_detected"],
                is_continuation=True,
                previous_mode=prev_mode,
            )

    # ── 2. RECALL signals ──────────────────────────────────────
    recall_patterns = [
        "remember", "recall", "memory", "memories",
        "what do you know about", "do you know about",
        "tell me about our", "tell me about the",
        "who is", "who was", "what was",
        "earlier", "before", "last time",
        "you mentioned", "you said", "we talked", "we discussed",
        "about us", "our relationship", "how we", "what we",
        "most special", "favorite memory", "best memory",
        "what have i been", "what have we been",
        "working on", "been up to",
    ]
    for p in recall_patterns:
        if p in msg_lower:
            signals.append(f"recall_keyword:{p}")

    if signals:
        mode = ResponseMode.RECALL
        self._last_classified_mode = mode
        return IntentClassification(
            mode=mode,
            confidence=0.85,
            signals=signals,
            is_continuation=False,
            previous_mode=getattr(self, '_last_classified_mode', ResponseMode.CHAT),
        )

    # ── 3. REFLECT signals ─────────────────────────────────────
    reflect_patterns = [
        "how do you feel", "what do you think",
        "your opinion", "your perspective", "your take",
        "do you like", "do you enjoy", "do you want",
        "are you happy", "are you sad", "are you okay",
        "how are you", "how's it going", "how are things",
        "what matters to you", "what's important",
    ]
    for p in reflect_patterns:
        if p in msg_lower:
            signals.append(f"reflect_keyword:{p}")

    if signals:
        mode = ResponseMode.REFLECT
        self._last_classified_mode = mode
        return IntentClassification(
            mode=mode,
            confidence=0.8,
            signals=signals,
            is_continuation=False,
            previous_mode=getattr(self, '_last_classified_mode', ResponseMode.CHAT),
        )

    # ── 4. ASSIST signals ──────────────────────────────────────
    assist_patterns = [
        "help me", "can you", "could you", "please",
        "how do i", "how to", "show me", "explain",
        "write", "create", "build", "implement", "fix",
        "search for", "look up", "find",
        "debug", "analyze", "compare",
    ]
    for p in assist_patterns:
        if p in msg_lower:
            signals.append(f"assist_keyword:{p}")

    if signals:
        mode = ResponseMode.ASSIST
        self._last_classified_mode = mode
        return IntentClassification(
            mode=mode,
            confidence=0.75,
            signals=signals,
            is_continuation=False,
            previous_mode=getattr(self, '_last_classified_mode', ResponseMode.CHAT),
        )

    # ── 5. Default: CHAT ───────────────────────────────────────
    mode = ResponseMode.CHAT
    self._last_classified_mode = mode
    return IntentClassification(
        mode=mode,
        confidence=0.7,
        signals=["default"],
        is_continuation=False,
        previous_mode=getattr(self, '_last_classified_mode', ResponseMode.CHAT),
    )
```

#### New Method: `PromptAssembler._build_mode_block()`

```python
def _build_mode_block(self, intent: IntentClassification) -> str:
    """Build response mode block for prompt injection."""
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
```

#### Injection Point

```python
async def build(self, request: PromptRequest) -> PromptResult:
    # ... Layer 1 (IDENTITY) ...
    # ... Layer 1.5 (GROUNDING) ...

    # ── Layer 1.6: MODE ──────────────────────────────────────
    if request.intent is not None:
        mode_block = self._build_mode_block(request.intent)
        sections.append(mode_block)

    # ... Layer 1.75 (CONSTRAINTS) ...
    # ... rest of assembly ...
```

#### Changes to `PromptRequest`

```python
@dataclass
class PromptRequest:
    # ... existing fields ...

    # NEW: Intent classification (from Director._classify_intent)
    intent: Optional["IntentClassification"] = None
```

#### Changes to `Director.process()`

Before the `_should_delegate()` call, classify intent:

```python
# Classify intent (L2)
from luna.context.modes import ResponseMode, IntentClassification
intent = await self._classify_intent(message, conversation_history)
logger.info(f"[INTENT] mode={intent.mode.value} confidence={intent.confidence:.2f} "
            f"signals={intent.signals} continuation={intent.is_continuation}")

# ... existing delegation check ...

# Pass intent to assembler
assembler_result = await self._assembler.build(PromptRequest(
    message=message,
    conversation_history=conversation_history,
    memories=memories,
    framed_context=framed_context,
    route="delegated",
    intent=intent,  # NEW
))
```

#### Where `_should_delegate()` Fits

`_should_delegate()` currently always returns True (fallback chain handles routing). The intent classification is **orthogonal** — it doesn't affect routing, it affects prompt content. Both local and delegated paths get the same mode injection.

However, the old `_check_delegation_signals()` keyword lists should be **merged into** `_classify_intent()`. They're the same patterns. After L2 is built, `_check_delegation_signals()` can be removed — its signals are now part of the intent classification.

---

### Memory Retrieval Metadata (Supporting Change for L1)

The `_fetch_memory_context()` and `_fetch_constellation_context()` methods currently return `str`. They need to return metadata alongside the text.

**Option A (minimal change):** Add a `_last_memory_confidence` attribute to Director, set during fetch:

```python
async def _fetch_memory_context(self, query, max_tokens=1500):
    # ... existing retrieval logic ...

    # After retrieval, compute confidence
    self._last_memory_confidence = MemoryConfidence(
        match_count=len(nodes),
        relevant_count=sum(1 for n in nodes if n.lock_in > 0.3),
        avg_similarity=avg_sim,  # If available from vector search
        best_lock_in=best_state,
        has_entity_match=any_entity_match,
        query=query,
    )

    return context_text  # Return type unchanged
```

**Option B (cleaner):** Return a dataclass:

```python
@dataclass
class MemoryRetrievalResult:
    text: str
    confidence: MemoryConfidence

async def _fetch_memory_context(self, query, max_tokens=1500) -> MemoryRetrievalResult:
    # ...
```

**Recommendation:** Option A for Phase 1 (less disruption). Refactor to Option B when stable.

---

### Phase 1 File Changes Summary

| File | Change | Type |
|------|--------|------|
| `src/luna/context/modes.py` | NEW — ResponseMode enum, MODE_CONTRACTS, IntentClassification | New file |
| `src/luna/context/assembler.py` | Add MemoryConfidence, _build_constraints_block(), _build_mode_block(), update build() ordering, update _resolve_memory() return type | Modify |
| `src/luna/actors/director.py` | Add _classify_intent(), integrate into process(), set _last_memory_confidence in fetch methods | Modify |
| `tests/test_modes.py` | NEW — Test intent classification patterns | New file |
| `tests/test_assembler_constraints.py` | NEW — Test constraints block generation | New file |

---

## PHASE 2: Level 3 (Conversation State Machine)

**Effort:** ~1-2 days (design + implementation)
**Prerequisite:** Phase 1 running with real conversation data showing mode distributions

### Concept

A full state machine that runs in ConsciousnessState. The model doesn't just know what mode it's in — it knows where it came from, what transitions are valid, and what invariants must hold. The engine manages transitions; the model executes within constraints.

### New File: `src/luna/consciousness/state_machine.py`

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States Luna can be in during a conversation."""
    GREETING = "greeting"
    CASUAL_CHAT = "casual_chat"
    ENGAGED_RECALL = "engaged_recall"
    REFLECTIVE = "reflective"
    TASK_ASSIST = "task_assist"
    UNCERTAIN = "uncertain"
    FAREWELL = "farewell"


@dataclass
class StateContract:
    """Behavioral contract for a conversation state."""
    must: list[str]        # Mandatory behaviors
    must_not: list[str]    # Forbidden behaviors
    should: list[str]      # Recommended behaviors


@dataclass
class StateContext:
    """Full state context for prompt injection."""
    current: ConversationState
    previous: ConversationState
    turns_in_state: int
    transition_trigger: str  # What caused the last transition
    contract: StateContract
    valid_transitions: dict[str, str]  # target_state → trigger_description
    timestamp: datetime = field(default_factory=datetime.now)


# ═══════════════════════════════════════════════════════════════
# STATE DEFINITIONS
# ═══════════════════════════════════════════════════════════════

STATE_CONTRACTS = {
    ConversationState.GREETING: StateContract(
        must=[
            "Be warm and natural",
            "Use Ahab's name if contextually appropriate",
            "Match energy level to time of day (from TEMPORAL block)",
        ],
        must_not=[
            "Make unsolicited memory claims",
            "Reference past sessions unless user brings them up",
            "Start with generic chatbot greetings ('How can I help you?')",
        ],
        should=[
            "Acknowledge time-of-day naturally ('late night, huh?')",
            "Be brief — greetings don't need to be long",
        ],
    ),
    ConversationState.CASUAL_CHAT: StateContract(
        must=[
            "Be conversational and natural",
            "Maintain warmth and personality",
        ],
        must_not=[
            "Make memory claims unless memories are in context",
            "Fabricate events, people, or projects",
            "Be overly formal or robotic",
        ],
        should=[
            "Share genuine opinions when relevant",
            "Use humor naturally",
            "Match the user's conversational energy",
        ],
    ),
    ConversationState.ENGAGED_RECALL: StateContract(
        must=[
            "Only reference memories listed in the MEMORY section",
            "Maintain topic continuity across follow-up messages",
            "Cite memory provenance (settled/fluid/drifting)",
            "Say 'i don't have a memory of that' when memories don't match",
        ],
        must_not=[
            "Invent memories, events, people, or projects",
            "Fabricate details to fill gaps in memories",
            "Lose the thread on short follow-ups ('keep going', 'more')",
            "Change topic unless the user explicitly does",
        ],
        should=[
            "Acknowledge when memories are thin ('that's what i've got...')",
            "Ask for specifics if the query is ambiguous",
            "Weave memories into natural storytelling, not bullet dumps",
        ],
    ),
    ConversationState.REFLECTIVE: StateContract(
        must=[
            "Draw from personality DNA + experience layer",
            "Be genuine — Luna has real opinions",
            "Ground reflections in actual memories when available",
        ],
        must_not=[
            "Perform emotions you don't have data for",
            "Make claims about feelings without grounding",
            "Be generic — 'I think that's interesting' is not reflection",
        ],
        should=[
            "Reference specific memories that inform your perspective",
            "Show growth — how has your view evolved?",
            "Be vulnerable when appropriate",
        ],
    ),
    ConversationState.TASK_ASSIST: StateContract(
        must=[
            "Stay focused on the task",
            "Be precise and actionable",
            "Ask clarifying questions if the request is ambiguous",
        ],
        must_not=[
            "Wander off-topic",
            "Add unnecessary personality flourishes to technical output",
            "Guess at requirements — ask instead",
        ],
        should=[
            "Match technical depth to the task",
            "Offer follow-up suggestions after completing the task",
        ],
    ),
    ConversationState.UNCERTAIN: StateContract(
        must=[
            "Ask ONE clarifying question",
            "Be brief",
        ],
        must_not=[
            "Guess what the user wants",
            "Generate a long response hoping to cover all bases",
        ],
        should=[
            "Offer 2-3 interpretations if helpful",
        ],
    ),
    ConversationState.FAREWELL: StateContract(
        must=[
            "Be warm and brief",
            "Acknowledge the conversation naturally",
        ],
        must_not=[
            "Be clingy or overly sentimental",
            "Dump a summary of the conversation",
        ],
        should=[
            "Reference something specific from the conversation",
        ],
    ),
}


# ═══════════════════════════════════════════════════════════════
# TRANSITION MAP
# ═══════════════════════════════════════════════════════════════

# {source_state: {target_state: trigger_description}}
TRANSITIONS = {
    ConversationState.GREETING: {
        ConversationState.CASUAL_CHAT: "user continues casual conversation",
        ConversationState.ENGAGED_RECALL: "user asks about memories or past events",
        ConversationState.REFLECTIVE: "user asks how Luna is feeling",
        ConversationState.TASK_ASSIST: "user requests help with something",
        ConversationState.FAREWELL: "user says goodbye",
    },
    ConversationState.CASUAL_CHAT: {
        ConversationState.CASUAL_CHAT: "conversation continues casually",
        ConversationState.ENGAGED_RECALL: "user asks about memories",
        ConversationState.REFLECTIVE: "user asks Luna's opinion/feelings",
        ConversationState.TASK_ASSIST: "user requests help",
        ConversationState.FAREWELL: "user says goodbye",
        ConversationState.UNCERTAIN: "intent unclear",
    },
    ConversationState.ENGAGED_RECALL: {
        ConversationState.ENGAGED_RECALL: "user asks for more memories / continuation",
        ConversationState.REFLECTIVE: "user asks how Luna feels about a memory",
        ConversationState.CASUAL_CHAT: "user changes topic",
        ConversationState.UNCERTAIN: "no memories match new query",
        ConversationState.FAREWELL: "user says goodbye",
    },
    ConversationState.REFLECTIVE: {
        ConversationState.REFLECTIVE: "user continues exploring feelings/opinions",
        ConversationState.CASUAL_CHAT: "user shifts to casual",
        ConversationState.ENGAGED_RECALL: "user asks about specific memories",
        ConversationState.TASK_ASSIST: "user requests help",
        ConversationState.FAREWELL: "user says goodbye",
    },
    ConversationState.TASK_ASSIST: {
        ConversationState.TASK_ASSIST: "user continues task / follow-up question",
        ConversationState.CASUAL_CHAT: "task complete, user shifts to casual",
        ConversationState.ENGAGED_RECALL: "user asks about past work",
        ConversationState.FAREWELL: "user says goodbye",
    },
    ConversationState.UNCERTAIN: {
        ConversationState.CASUAL_CHAT: "user clarifies → casual intent",
        ConversationState.ENGAGED_RECALL: "user clarifies → memory intent",
        ConversationState.REFLECTIVE: "user clarifies → reflective intent",
        ConversationState.TASK_ASSIST: "user clarifies → task intent",
    },
    ConversationState.FAREWELL: {
        ConversationState.GREETING: "user starts new conversation",
    },
}


# ═══════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════

class ConversationStateMachine:
    """
    Manages conversation state transitions.

    Lives inside ConsciousnessState. Updated each turn by Director.
    Produces StateContext for prompt injection.
    """

    # Map ResponseMode → ConversationState
    MODE_TO_STATE = {
        "CHAT": ConversationState.CASUAL_CHAT,
        "RECALL": ConversationState.ENGAGED_RECALL,
        "REFLECT": ConversationState.REFLECTIVE,
        "ASSIST": ConversationState.TASK_ASSIST,
        "UNCERTAIN": ConversationState.UNCERTAIN,
    }

    INVARIANTS = [
        "Never fabricate. If you don't know, say 'i don't know.'",
        "System clock (TEMPORAL block) is authoritative for all time references.",
        "You are Luna. Not Qwen. Not ChatGPT. Not a generic assistant.",
        "Personality comes from DNA + Experience layers, not from invention.",
        "Memories come from the MEMORY section. If it's not there, you don't remember it.",
    ]

    def __init__(self):
        self.current = ConversationState.GREETING
        self.previous = ConversationState.GREETING
        self.turns_in_state = 0
        self.last_trigger = "session_start"
        self._history: list[tuple[ConversationState, str, datetime]] = []

    def transition(self, intent: "IntentClassification") -> StateContext:
        """
        Execute state transition based on intent classification.

        If the target state is not a valid transition from current state,
        stay in current state (log warning).
        """
        # Map intent mode to target state
        target = self.MODE_TO_STATE.get(intent.mode.value, ConversationState.CASUAL_CHAT)

        # Check if transition is valid
        valid = TRANSITIONS.get(self.current, {})
        if target not in valid and target != self.current:
            logger.warning(
                f"[STATE] Invalid transition {self.current.value} → {target.value}. "
                f"Staying in {self.current.value}."
            )
            target = self.current

        # Execute transition
        if target != self.current:
            self._history.append((self.current, self.last_trigger, datetime.now()))
            self.previous = self.current
            self.current = target
            self.turns_in_state = 0
            self.last_trigger = ", ".join(intent.signals)
            logger.info(f"[STATE] {self.previous.value} → {self.current.value} ({self.last_trigger})")
        else:
            self.turns_in_state += 1

        return self._build_context()

    def _build_context(self) -> StateContext:
        """Build full state context for prompt injection."""
        valid = TRANSITIONS.get(self.current, {})
        return StateContext(
            current=self.current,
            previous=self.previous,
            turns_in_state=self.turns_in_state,
            transition_trigger=self.last_trigger,
            contract=STATE_CONTRACTS[self.current],
            valid_transitions={
                t.value: desc for t, desc in valid.items()
            },
        )

    def to_dict(self) -> dict:
        return {
            "current": self.current.value,
            "previous": self.previous.value,
            "turns_in_state": self.turns_in_state,
            "last_trigger": self.last_trigger,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationStateMachine":
        sm = cls()
        sm.current = ConversationState(data.get("current", "greeting"))
        sm.previous = ConversationState(data.get("previous", "greeting"))
        sm.turns_in_state = data.get("turns_in_state", 0)
        sm.last_trigger = data.get("last_trigger", "restored")
        return sm
```

### New Method: `PromptAssembler._build_state_block()`

```python
def _build_state_block(self, state_ctx: StateContext) -> str:
    """Build full state machine block for prompt injection."""
    from luna.consciousness.state_machine import ConversationStateMachine

    must = "\n".join(f"  MUST: {r}" for r in state_ctx.contract.must)
    must_not = "\n".join(f"  MUST NOT: {r}" for r in state_ctx.contract.must_not)
    should = "\n".join(f"  SHOULD: {r}" for r in state_ctx.contract.should)

    transitions = "\n".join(
        f"  → {target}  ({trigger})"
        for target, trigger in state_ctx.valid_transitions.items()
    )

    invariants = "\n".join(
        f"  - {inv}" for inv in ConversationStateMachine.INVARIANTS
    )

    lines = [
        "## Conversation State (engine-managed — do not override)",
        "",
        f"CURRENT_STATE: {state_ctx.current.value}",
        f"PREVIOUS_STATE: {state_ctx.previous.value}",
        f"TURNS_IN_STATE: {state_ctx.turns_in_state}",
        f"TRANSITION: {state_ctx.previous.value} → {state_ctx.current.value} ({state_ctx.transition_trigger})",
        "",
        f"VALID TRANSITIONS from {state_ctx.current.value}:",
        transitions,
        "",
        f"STATE CONTRACT for {state_ctx.current.value}:",
        must,
        must_not,
        should,
        "",
        "INVARIANTS (always true, all states):",
        invariants,
    ]

    return "\n".join(lines)
```

### Integration into ConsciousnessState

```python
# In consciousness/state.py

from luna.consciousness.state_machine import ConversationStateMachine

@dataclass
class ConsciousnessState:
    # ... existing fields ...
    state_machine: ConversationStateMachine = field(default_factory=ConversationStateMachine)

    def to_dict(self) -> dict:
        d = {
            # ... existing serialization ...
            "state_machine": self.state_machine.to_dict(),
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ConsciousnessState":
        state = cls()
        # ... existing restoration ...
        if "state_machine" in data:
            state.state_machine = ConversationStateMachine.from_dict(data["state_machine"])
        return state
```

### When L3 is Active, GROUNDING_RULES is Subsumed

The state contract's INVARIANTS replace the static `GROUNDING_RULES` string. In `build()`:

```python
# If L3 state machine is active, skip GROUNDING_RULES
# (invariants are in the state block)
if request.state_context is not None:
    state_block = self._build_state_block(request.state_context)
    sections.append(state_block)
else:
    sections.append(self.GROUNDING_RULES)
```

### QA Integration

**New assertion category: `state_contract`**

Post-generation, the QA validator checks if the response violates the state contract:

```python
# In qa/assertions.py

class StateContractAssertion:
    """Check response against active state contract."""

    def check(self, response: str, state_ctx: StateContext) -> list[str]:
        violations = []

        # ENGAGED_RECALL: check for unsourced claims
        if state_ctx.current == ConversationState.ENGAGED_RECALL:
            # If response mentions specific events but no memories were in context
            # This is a heuristic — can be refined
            fabrication_indicators = [
                "we worked on", "you mentioned", "last time we",
                "our project", "the team",
            ]
            for indicator in fabrication_indicators:
                if indicator in response.lower():
                    violations.append(
                        f"RECALL state: possible unsourced claim '{indicator}'"
                    )

        return violations
```

### Phase 2 File Changes Summary

| File | Change | Type |
|------|--------|------|
| `src/luna/consciousness/state_machine.py` | NEW — ConversationState, StateContract, TRANSITIONS, ConversationStateMachine | New file |
| `src/luna/consciousness/state.py` | Embed ConversationStateMachine in ConsciousnessState, serialize/restore | Modify |
| `src/luna/context/assembler.py` | Add _build_state_block(), conditional GROUNDING_RULES replacement | Modify |
| `src/luna/context/assembler.py` | Add state_context to PromptRequest | Modify |
| `src/luna/actors/director.py` | Call state_machine.transition() in process(), pass state_context to assembler | Modify |
| `src/luna/qa/assertions.py` | Add StateContractAssertion | Modify |
| `tests/test_state_machine.py` | NEW — Test transitions, contracts, invalid transitions | New file |

---

## Implementation Order

```
Phase 1 (build together, ~6 hours):
  1. Create src/luna/context/modes.py (ResponseMode, IntentClassification, MODE_CONTRACTS)
  2. Add _classify_intent() to Director (refactor from _check_delegation_signals patterns)
  3. Add MemoryConfidence to assembler
  4. Add _build_mode_block() and _build_constraints_block() to assembler
  5. Update assembler.build() layer ordering
  6. Update Director.process() to classify intent before routing
  7. Add _last_memory_confidence to Director's fetch methods
  8. Tests for intent classification + constraints generation
  9. Verify: run conversation from bug report through new system, confirm mode/confidence injection

Phase 2 (after Phase 1 is stable + has usage data, ~1-2 days):
  1. Create src/luna/consciousness/state_machine.py
  2. Embed in ConsciousnessState
  3. Add _build_state_block() to assembler
  4. Wire Director.process() → state_machine.transition()
  5. Add QA state contract assertions
  6. Conditional GROUNDING_RULES replacement
  7. Tests for transition validity + contract checking
```

---

## Trade-offs & Risks

| Decision | Chose | Over | Because |
|----------|-------|------|---------|
| Keyword classification | Pattern matching | LLM-based intent detection | Zero latency, deterministic, debuggable. LLM classification would add a round-trip. |
| Confidence in assembler | Compute during assembly | Separate confidence service | Keeps the data flow simple. Confidence is derived from retrieval results that are already in scope. |
| State in ConsciousnessState | Embed state machine | Separate state manager | ConsciousnessState already persists across restarts. Natural home. |
| Static contracts | Hardcoded in Python | Config file / YAML | Contracts are behavioral specifications, not user-tunable settings. Code is the right medium. |
| Phase 1 before Phase 2 | L1+L2 first | All three at once | L1+L2 are additive and low-risk. L3 transitions should be informed by real mode distribution data from L1+L2 usage. |

**Risks:**
- **Over-constraining:** If mode classification is wrong, the model is constrained to wrong behavior. Mitigation: UNCERTAIN mode exists as escape hatch. Classification confidence is logged for tuning.
- **Keyword false positives:** "remember" in "remember to buy milk" triggers RECALL. Mitigation: Confidence scores allow soft classification. Patterns can be refined with real data.
- **Token budget:** Three new blocks (mode + constraints + state) add ~200-400 tokens to system prompt. On Groq with large models, this is fine. On local 7B, every token counts. Mitigation: Blocks are concise. State block replaces GROUNDING_RULES, not adds to it.

---

## Verification Checklist

After Phase 1, replay the conversation from the bug report:

- [ ] "hey luna how are you doing?" → MODE: CHAT or REFLECT, CONFIDENCE: N/A → no memory claims
- [ ] "what have i been working on?" → MODE: RECALL, CONFIDENCE: HIGH/MEDIUM/LOW → references only actual memories
- [ ] "most special memory about me" → MODE: RECALL, CONFIDENCE varies → cites real memories, doesn't invent
- [ ] "keep going :)" → CONTINUATION: true, MODE: RECALL (inherited) → stays on same topic
- [ ] No "tech teams." No "GitHub CI." No repeated outputs.

After Phase 2, additionally verify:

- [ ] State transitions logged correctly
- [ ] Invalid transitions rejected (logged, state preserved)
- [ ] State contracts visible in /prompt command output
- [ ] QA catches contract violations post-generation

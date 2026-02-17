# Flow Awareness System — Layer 2 Specification

## Luna Engine Conversation State Architecture

**Depends on:** Pipeline Fix (Layer 1) — all turns reaching Scribe in real-time
**Produces:** Flow signals that enable Librarian thread management (Layer 3)

---

## 1. The Problem

Luna processes every turn identically. A greeting, a deep technical exchange, a topic pivot, a correction — all get the same extraction pass, the same routing, the same context assembly. There's no awareness that a conversation has *shape* — that it flows, shifts, and sometimes backtracks.

The user experiences this as Luna having no conversational continuity. She can't say "we were deep into Kozmo and you just shifted to Kinoni" because she doesn't know she was deep into anything.

## 2. Conversation Modes

Three modes describe what's happening in any conversation at the turn level:

### FLOW
Back-to-back turns on the same topic cluster. Entities are consistent, vocabulary is stable, the conversation is building. This is the *default* state — conversation starts here and stays here until something breaks it.

Characteristics:
- Entity overlap between current and recent turns is high (>0.6)
- Vocabulary/topic drift is low
- No explicit redirect signals
- Attention should be *deepening* on the active topic cluster

### RECALIBRATION
A topic shift has occurred. The user has introduced a new subject, new entities, or explicitly redirected. Luna needs to:
1. Snapshot the current flow (topic, entities, accumulated context, open tasks)
2. Park it as a resumable thread
3. Retrieve context for the new direction
4. Begin a new flow

Characteristics:
- Entity overlap drops below threshold (<0.3)
- New entities appear that weren't in recent turns
- Explicit redirect language ("anyway", "switching gears", "what about...")
- OR a question about a completely different domain

### AMEND
The user is correcting or redirecting *within* the current flow. Not a new topic — a course correction. "Actually no, I meant...", "Go back to...", "That's not what I was asking."

Characteristics:
- Same entity cluster as current flow
- Correction/negation language detected
- Backward reference to earlier point in current flow
- Does NOT require a new thread — adjusts the current one

---

## 3. Where Flow Detection Lives

### Scribe (Ben) — the detector

Ben already receives every turn and runs semantic chunking. He already has a `stack` (deque of 5 chunks) that represents recent conversational context. He already detects topic shifts in the chunker via `_is_topic_shift()`.

**What changes:** Ben compares each incoming turn against his stack to produce a `FlowSignal` alongside every extraction. This is metadata on the extraction output, not a separate message.

### Key insight: Ben doesn't decide what to *do* about the signal. He just names what he sees.

The Librarian decides how to act on it. Ben's job is observation. The Dude's job is filing.

---

## 4. New Types

### File: `src/luna/extraction/types.py`

```python
class ConversationMode(str, Enum):
    """The current conversational mode detected by Scribe."""
    FLOW = "FLOW"                     # Continuing on-topic
    RECALIBRATION = "RECALIBRATION"   # Topic shift detected
    AMEND = "AMEND"                   # Course correction within flow


@dataclass
class FlowSignal:
    """
    Scribe's assessment of conversational continuity.
    
    Emitted with every extraction. Consumed by Librarian
    for thread management decisions.
    """
    mode: ConversationMode
    
    # Topic tracking
    current_topic: str              # Brief label for what's being discussed
    topic_entities: list[str]       # Entities active in this topic
    
    # Continuity metrics
    continuity_score: float         # 0.0 (total shift) to 1.0 (same thread)
    entity_overlap: float           # Jaccard similarity of entities vs recent turns
    
    # Open threads detected
    open_threads: list[str]         # Brief descriptions of unresolved items
    
    # Amend specifics (only populated in AMEND mode)
    correction_target: str = ""     # What's being corrected/redirected
    
    # Debug
    signals_detected: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "current_topic": self.current_topic,
            "topic_entities": self.topic_entities,
            "continuity_score": self.continuity_score,
            "entity_overlap": self.entity_overlap,
            "open_threads": self.open_threads,
            "correction_target": self.correction_target,
            "signals_detected": self.signals_detected,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FlowSignal":
        return cls(
            mode=ConversationMode(data["mode"]),
            current_topic=data.get("current_topic", ""),
            topic_entities=data.get("topic_entities", []),
            continuity_score=data.get("continuity_score", 1.0),
            entity_overlap=data.get("entity_overlap", 1.0),
            open_threads=data.get("open_threads", []),
            correction_target=data.get("correction_target", ""),
            signals_detected=data.get("signals_detected", []),
        )
```

### Add to ExtractionOutput

```python
@dataclass
class ExtractionOutput:
    objects: list[ExtractedObject] = field(default_factory=list)
    edges: list[ExtractedEdge] = field(default_factory=list)
    source_id: str = ""
    extraction_time_ms: int = 0
    flow_signal: Optional[FlowSignal] = None  # NEW
```

---

## 5. Scribe Changes

### File: `src/luna/actors/scribe.py`

#### New state on ScribeActor

```python
class ScribeActor(Actor):
    def __init__(self, ...):
        # ... existing init ...
        
        # Flow tracking state
        self._current_topic: str = ""
        self._current_entities: set[str] = set()
        self._recent_entities: deque[set[str]] = deque(maxlen=5)  # Entity sets from last 5 extractions
        self._turn_count_in_flow: int = 0
        self._open_actions: list[dict] = []  # ACTIONs without matching OUTCOMEs
```

#### New method: `_assess_flow()`

Called after every extraction, before sending to Librarian. Uses the extraction results (entities, types) plus the stack history to determine conversational mode.

```python
def _assess_flow(
    self, 
    extraction: ExtractionOutput,
    raw_text: str,
) -> FlowSignal:
    """
    Assess conversational flow state from current extraction.
    
    Uses three signals:
    1. Entity overlap — are we talking about the same things?
    2. Explicit language — did the user signal a shift or correction?
    3. Extraction type distribution — ACTIONs without OUTCOMEs = open threads
    """
    
    # 1. Gather current entities from extraction
    current_entities = set()
    for obj in extraction.objects:
        current_entities.update(obj.entities)
    
    # 2. Calculate entity overlap with recent history
    if self._recent_entities:
        # Union of all recent entity sets
        recent_union = set()
        for entity_set in self._recent_entities:
            recent_union.update(entity_set)
        
        # Jaccard similarity
        if current_entities or recent_union:
            intersection = current_entities & recent_union
            union = current_entities | recent_union
            entity_overlap = len(intersection) / len(union) if union else 0.0
        else:
            entity_overlap = 1.0  # No entities either way = neutral
    else:
        entity_overlap = 1.0  # First turn = flow by default
    
    # 3. Detect explicit signals in raw text
    signals = []
    mode = ConversationMode.FLOW
    
    # Recalibration signals
    recal_patterns = [
        r"(?i)^(anyway|so|moving on|switching|let'?s talk about)",
        r"(?i)(different topic|change of subject|other thing)",
        r"(?i)^(what about|how about|tell me about)\b(?!.*\b(this|that|it)\b)",
    ]
    for pattern in recal_patterns:
        if re.search(pattern, raw_text):
            signals.append(f"recal_language: {pattern}")
    
    # Amend signals  
    amend_patterns = [
        r"(?i)^(actually|wait|no|sorry|i mean)",
        r"(?i)(go back|back to|not what i|that'?s wrong)",
        r"(?i)(i meant|let me rephrase|correction)",
    ]
    for pattern in amend_patterns:
        if re.search(pattern, raw_text):
            signals.append(f"amend_language: {pattern}")
    
    # 4. Determine mode
    has_recal_language = any("recal_language" in s for s in signals)
    has_amend_language = any("amend_language" in s for s in signals)
    
    if has_amend_language and entity_overlap > 0.3:
        mode = ConversationMode.AMEND
    elif has_recal_language or entity_overlap < 0.3:
        mode = ConversationMode.RECALIBRATION
    else:
        mode = ConversationMode.FLOW
    
    # 5. Track open threads (ACTIONs without OUTCOMEs)
    for obj in extraction.objects:
        if obj.type == ExtractionType.ACTION:
            self._open_actions.append({
                "content": obj.content,
                "entities": obj.entities,
                "timestamp": time.time(),
            })
        elif obj.type == ExtractionType.OUTCOME:
            # Try to match and close an open action
            # Simple: remove first action with overlapping entities
            for i, action in enumerate(self._open_actions):
                if set(action["entities"]) & set(obj.entities):
                    self._open_actions.pop(i)
                    break
    
    # 6. Generate topic label from highest-confidence extraction
    current_topic = self._current_topic
    if extraction.objects:
        best = max(extraction.objects, key=lambda o: o.confidence)
        # Use entities as topic label, or first few words of content
        if best.entities:
            current_topic = ", ".join(best.entities[:3])
        else:
            current_topic = best.content[:50]
    
    # 7. Update state
    if mode == ConversationMode.RECALIBRATION:
        self._turn_count_in_flow = 0
    else:
        self._turn_count_in_flow += 1
    
    self._recent_entities.append(current_entities)
    self._current_entities = current_entities
    self._current_topic = current_topic
    
    # 8. Build signal
    open_thread_descriptions = [a["content"][:80] for a in self._open_actions[-5:]]
    
    return FlowSignal(
        mode=mode,
        current_topic=current_topic,
        topic_entities=list(current_entities),
        continuity_score=entity_overlap,
        entity_overlap=entity_overlap,
        open_threads=open_thread_descriptions,
        correction_target=raw_text[:80] if mode == ConversationMode.AMEND else "",
        signals_detected=signals,
    )
```

#### Modified: `_process_stack()` 

Attach flow signal to extraction before sending to Librarian:

```python
async def _process_stack(self) -> None:
    if not self.stack:
        return

    chunks = list(self.stack)
    self.stack.clear()
    
    # Get raw text for flow assessment
    raw_text = "\n".join(chunk.content for chunk in chunks)

    extraction, entity_updates = await self._extract_chunks(chunks)

    # NEW: Assess conversational flow
    flow_signal = self._assess_flow(extraction, raw_text)
    extraction.flow_signal = flow_signal
    
    logger.info(
        f"Ben: Flow={flow_signal.mode.value} "
        f"continuity={flow_signal.continuity_score:.2f} "
        f"topic='{flow_signal.current_topic[:30]}' "
        f"open_threads={len(flow_signal.open_threads)}"
    )

    if not extraction.is_empty():
        await self._send_to_librarian(extraction)
    
    for update in entity_updates:
        await self._send_entity_update_to_librarian(update)
```

---

## 6. Librarian Changes (Preview — Full Spec in Layer 3)

The Librarian receives `flow_signal` on every extraction. For Layer 2, the Dude just *logs* the signal and begins tracking thread state. The actual snapshot/park/resume mechanics come in Layer 3.

### What the Dude does in Layer 2:

```python
async def _handle_file(self, msg: Message) -> None:
    payload = msg.payload or {}
    extraction = ExtractionOutput.from_dict(payload)
    
    # NEW: Read flow signal
    flow_signal = extraction.flow_signal
    if flow_signal:
        logger.info(
            f"The Dude: Flow signal received — {flow_signal.mode.value} "
            f"(continuity={flow_signal.continuity_score:.2f})"
        )
        
        # Track for Layer 3
        if flow_signal.mode == ConversationMode.RECALIBRATION:
            logger.info(
                f"The Dude: Topic shift detected. "
                f"Previous: '{self._current_thread_topic}' → "
                f"New: '{flow_signal.current_topic}'"
            )
            # Layer 3 will add: snapshot current flow, park thread
        
        self._current_thread_topic = flow_signal.current_topic
        self._current_thread_entities = set(flow_signal.topic_entities)
    
    # ... existing filing logic unchanged ...
```

---

## 7. Consciousness Integration (Preview — Full Spec in Layer 5)

Flow signals feed directly into consciousness state:

- **FLOW** → attention weight on current topic *increases* per turn
- **RECALIBRATION** → attention on old topic *decays*, new topic enters at base weight
- **AMEND** → attention stays on same topic, coherence temporarily dips (uncertainty)

This is the bridge between "what Ben observes" and "how Luna feels" — but the wiring comes after the detection is proven.

---

## 8. Sequencing Guarantee

Flow detection requires **turns to arrive in order**. The pipeline fix (Layer 1) handles this for the frontend stream path. For MCP, the auto-session buffer already sequences turns before flushing.

**Risk:** If `_trigger_extraction()` is async and non-blocking, fast sequential turns could arrive at Ben out of order. 

**Mitigation:** Scribe's stack (deque) provides natural ordering — chunks are appended in arrival order. The flow assessment compares current vs. stack, so as long as the stack reflects true temporal order, the signal is valid.

**Monitor:** Add a sequence counter to extraction payloads. If Ben ever receives a turn with a lower sequence number than his last processed turn, log a warning. This is a canary, not a blocker.

---

## 9. What This Does NOT Do (Yet)

- **Thread parking/resuming** — Layer 3 (Librarian)
- **Task ledger persistence** — Layer 4 (Matrix schema)
- **Consciousness wiring** — Layer 5
- **Router adaptation** — Layer 6
- **Proactive thread surfacing** ("we left off discussing X") — Layer 7

Each layer depends on the one before it. This spec is strictly: **Ben learns to see conversational shape.**

---

## 10. Testing

### Unit: Flow detection accuracy

```python
# FLOW: same entities, no redirect language
signal = scribe._assess_flow(
    extraction_with_entities(["Kozmo", "pipeline"]),
    "how's the kozmo pipeline looking?"
)
assert signal.mode == ConversationMode.FLOW
assert signal.continuity_score > 0.5

# RECALIBRATION: new entities, redirect language  
signal = scribe._assess_flow(
    extraction_with_entities(["Kinoni", "Uganda"]),
    "anyway, what about the Kinoni research?"
)
assert signal.mode == ConversationMode.RECALIBRATION
assert signal.continuity_score < 0.3

# AMEND: same entities, correction language
signal = scribe._assess_flow(
    extraction_with_entities(["Kozmo", "pipeline"]),  
    "actually no, I meant the asset indexing part"
)
assert signal.mode == ConversationMode.AMEND
```

### Unit: Sovereignty invariants

```python
# Flow detection NEVER calls cloud, regardless of config
scribe.config.backend = "sonnet"  # Cloud enabled for extraction
signal = await scribe._assess_flow(extraction, text)
# Flow signal must still be produced locally
assert signal.detection_method in ("regex", "local_model")  # Never "cloud"

# Local extraction doesn't fall back to cloud
scribe.config.backend = "local"
scribe._local_model = None  # Simulate missing model
extraction, _ = await scribe._extract_chunks(chunks)
assert extraction.is_empty()  # Skipped, not fell back
# Check logs for sovereignty warning
```

### Integration: End-to-end flow signal emission

1. Send 3 turns about Kozmo through `record_conversation_turn()`
2. Verify Scribe emits FLOW signals with increasing continuity
3. Send 1 turn about Kinoni
4. Verify Scribe emits RECALIBRATION signal
5. Send 1 turn "actually go back to the kozmo thing"
6. Verify Scribe emits AMEND signal
7. Verify all signals have `detection_method != "cloud"`

### Open thread tracking

1. Send turn: "we need to fix the eden integration" (ACTION extracted)
2. Verify `open_threads` includes this item
3. Send turn: "eden integration is working now" (OUTCOME extracted)
4. Verify `open_threads` no longer includes it
5. Send turn with ACTION, wait 25 hours (or mock time)
6. Verify stale action aged out of `open_actions`

### Local model extraction quality

1. Run extraction on 20 representative conversation turns using local model
2. Compare entity extraction recall against Haiku baseline
3. Acceptable: >70% entity recall, >60% type accuracy
4. If below threshold: simplify `LOCAL_EXTRACTION_PROMPT` further, don't enable cloud

---

## 15. Files Modified

| File | Change |
|------|--------|
| `src/luna/extraction/types.py` | Add `ConversationMode`, `FlowSignal`, update `ExtractionOutput` |
| `src/luna/actors/scribe.py` | Add flow tracking state, tiered detection methods, `LOCAL_EXTRACTION_PROMPT`, modify `_process_stack()` |
| `src/luna/actors/librarian.py` | Read and log flow signals, thread state tracking (prep for Layer 3) |
| `tests/test_flow_detection.py` | New — flow signal accuracy tests |
| `tests/test_sovereignty.py` | New — verify no cloud calls in flow detection path |

---

## 16. Success Criteria

Layer 2 is complete when:

1. Every extraction includes a `FlowSignal`
2. Flow signals accurately reflect conversational continuity (>80% accuracy on test cases)
3. Flow detection runs entirely on-device — zero cloud calls in the detection path
4. Extraction defaults to local model, cloud only via explicit config override
5. Open thread tracking catches ACTION→OUTCOME gaps
6. Librarian logs confirm signal reception
7. No regression in extraction quality or latency (flow assessment adds <10ms for regex, <200ms for local model)
8. Sequential delivery is verified (no out-of-order warnings in logs)
9. `detection_method` field provides full transparency on how each signal was produced

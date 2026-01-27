# Part IV: The Scribe (Ben Franklin) — v2.1

**Status:** CURRENT
**Replaces:** BIBLE-PART-IV-THE-SCRIBE-v2.0.md
**Last Updated:** January 25, 2026
**Implementation:** `src/luna/actors/scribe.py`

---

## 4.1 The Scribe: Benjamin Franklin

The Scribe is the **sensory cortex** — turning the messy stream of experience into structured data the Substrate can understand.

**Persona:** Benjamin Franklin. Colonial gravitas, meticulous attention, practical wisdom. Ben monitors the conversation stream, extracts wisdom, and classifies it with scholarly precision.

> "An investment in knowledge pays the best interest." — Ben Franklin

The Scribe doesn't just transcribe; it **distills**.

### The Separation Principle

**Critical Design Rule:** Ben has personality in his PROCESS (logs can be witty and colonial), but his OUTPUTS are NEUTRAL (clean structured data). Luna's memories stay unpolluted by processing artifacts.

```
┌─────────────────────────────────────────────────────────────┐
│  PROCESS (Ben's Domain)          OUTPUT (Neutral)           │
│                                                              │
│  "Ahoy! A decision most weighty  →  Decision(              │
│   hath been rendered..."              choice="Actor model", │
│                                       confidence=0.9        │
│  Colonial personality OK here        )                      │
│                                                              │
│                                      No colonial flavor     │
│                                      in the data itself     │
└─────────────────────────────────────────────────────────────┘
```

Why? Luna's voice should be Luna's. Not a patchwork of processing personas.

---

## 4.2 Two-Gear Operation

### Reflexive Gear (Real-time, <200ms)

```
Audio → Whisper → Text → Local Classifier → Label
```

The local classifier (Director 3B) doesn't understand everything. It just labels:

| Label | Signal | Action |
|-------|--------|--------|
| **COMMAND** | "Luna, do X" | Route to Director |
| **QUESTION** | "What is X?" | Route to Director + Retrieval |
| **STATEMENT** | Declarative, no action | Queue for extraction |
| **NOISE** | Filler, incomplete | Ignore |

```python
class ReflexiveGear:
    async def classify(self, text: str) -> Intent:
        """<200ms classification using Director 3B."""
        # Single forward pass, no generation
        logits = self.model.classify(text)
        return Intent(
            type=logits.argmax(),
            confidence=logits.max(),
            requires_response=logits.argmax() in (COMMAND, QUESTION)
        )
```

### Deep Gear (Background, async)

If the Reflexive pass detects extractable content, it queues for full extraction:

```
Text → Claude (via Shadow Reasoner) → Structured Extraction → Queue for Librarian
```

The Deep Gear runs asynchronously — Luna has already responded before extraction completes.

---

## 4.3 The Stack of Benjamins

Conversations don't arrive as neat packets. They stream. Ben handles this with stacking:

```
         Conversation Stream
                 │
                 ▼
        ┌─────────────────┐
        │     CHUNKER     │  Split into semantic units
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │      STACK      │  Accumulate chunks with context window
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │  BEN REVIEWS    │  Process stacked chunks together
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ "MAKE IT RAIN"  │  Extractions flow to The Dude
        └─────────────────┘
```

### Chunking Strategy

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Target size | 200-500 tokens | Fits in single extraction call |
| Overlap | 50 tokens | Context continuity |
| Boundaries | Topic shifts, speaker changes | Semantic coherence |

```python
class SemanticChunker:
    def chunk(self, conversation: list[Turn]) -> list[Chunk]:
        chunks = []
        current_chunk = []
        current_tokens = 0

        for turn in conversation:
            turn_tokens = count_tokens(turn.text)

            # Topic shift detection
            if self.is_topic_shift(current_chunk, turn):
                if current_chunk:
                    chunks.append(self.finalize_chunk(current_chunk))
                current_chunk = []
                current_tokens = 0

            current_chunk.append(turn)
            current_tokens += turn_tokens

            # Size limit
            if current_tokens >= 500:
                chunks.append(self.finalize_chunk(current_chunk))
                # Overlap: keep last turn for context
                current_chunk = [turn]
                current_tokens = turn_tokens

        if current_chunk:
            chunks.append(self.finalize_chunk(current_chunk))

        return chunks
```

### Stacking Strategy

Ben doesn't process chunks in isolation. He sees context:

```python
class BenStack:
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.stack: deque[Chunk] = deque(maxlen=window_size)

    def push(self, chunk: Chunk):
        self.stack.append(chunk)

    def get_context_window(self) -> list[Chunk]:
        """Ben sees 3-5 recent chunks for context."""
        return list(self.stack)

    async def process(self) -> list[Extraction]:
        """Process current stack, return extractions."""
        context = self.get_context_window()
        extractions = await self.extract_with_context(context)
        return extractions  # "Make it rain"
```

---

## 4.4 Extraction Types

Ben classifies into eleven categories (defined in `src/luna/extraction/types.py`):

| Type | Description | Example | Signal Words |
|------|-------------|---------|--------------|
| **FACT** | Something known to be true | "Alex lives in Berlin" | is, lives, has, works at |
| **DECISION** | A choice that was made | "We chose Actor model" | decided, chose, going with |
| **PROBLEM** | An unresolved issue | "Voice latency is too high" | issue, problem, bug, broken |
| **ASSUMPTION** | Believed but unverified | "Users will want voice-first" | assume, probably, likely |
| **CONNECTION** | Relationship between entities | "Alex and Sarah are teammates" | knows, works with, related to |
| **ACTION** | Something done or to be done | "Need to implement RRF" | did, need to, should, will |
| **OUTCOME** | Result of action or decision | "Switching to NetworkX saved 45ms" | resulted in, improved, fixed |
| **QUESTION** | A question asked | "What is the best approach?" | what, how, why, when |
| **PREFERENCE** | User preference stated | "I prefer dark mode" | prefer, like, want, favor |
| **OBSERVATION** | Something noticed | "The API seems slow today" | notice, seems, appears |
| **MEMORY** | A memory shared | "Remember when we debugged that?" | remember, recall, back when |

### Confidence Scoring

| Evidence Level | Confidence Range | Example |
|---------------|------------------|---------|
| Explicit statement | 0.9-1.0 | "Alex definitely lives in Berlin" |
| Strong implication | 0.7-0.9 | "Alex mentioned his Berlin apartment" |
| Weak inference | 0.5-0.7 | "Alex seems to be in Germany" |
| Speculation | 0.3-0.5 | "Alex might be European" |

```python
@dataclass
class ExtractedFact:
    type: ExtractionType
    content: str
    confidence: float
    source_chunk: str
    entities: list[str]

    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.7
```

---

## 4.5 Interface Contract

### Input

```python
@dataclass
class ExtractionInput:
    raw_content: str
    source_type: str  # 'conversation', 'document', 'voice'
    source_id: str
    context: dict  # Additional metadata
    preceding_chunks: list[str]  # For context window
```

### Output

```python
@dataclass
class ExtractedObject:
    type: ExtractionType  # FACT, DECISION, PROBLEM, QUESTION, PREFERENCE, etc.
    content: str  # The distilled content
    confidence: float  # 0.0-1.0
    entities: list[str]  # Mentioned entities
    source_id: str = ""  # Source reference
    metadata: dict = field(default_factory=dict)  # Additional structured fields

@dataclass
class ExtractedEdge:
    from_ref: str  # Source entity name
    to_ref: str  # Target entity name
    edge_type: str  # "works_on", "decided", "caused", etc.
    confidence: float = 1.0  # Edge confidence
    source_id: str = ""  # Source conversation

@dataclass
class ExtractionOutput:
    objects: list[ExtractedObject]
    edges: list[ExtractedEdge]
    source_id: str = ""
    extraction_time_ms: int = 0

    def is_empty(self) -> bool:
        """Check if extraction produced no results."""
        return len(self.objects) == 0 and len(self.edges) == 0

    def to_dict(self) -> dict:
        """Serialize for message passing."""
        ...
```

### Entity Updates (v2.1 Addition)

Ben also extracts entity updates for the Entity System:

```python
@dataclass
class EntityUpdate:
    update_type: ChangeType  # CREATE, UPDATE, SYNTHESIZE
    entity_id: str | None  # Existing ID (for updates)
    name: str  # Entity name
    entity_type: EntityType  # PERSON, PERSONA, PLACE, PROJECT
    facts: dict[str, str]  # Facts to add/update
    source: str = ""  # Source of update
```

This enables Ben to file biographical facts directly to entity profiles.

---

## 4.6 Scheduling Model

Ben is **event-driven**, not scheduled:

| Trigger | Action | Priority |
|---------|--------|----------|
| Conversation turn completed | Queue for extraction | Normal |
| Document uploaded | Parse + extract | High |
| Silence > 30s | Flush pending stack | Normal |
| User says "remember that" | Immediate extraction | High |

```python
class ScribeScheduler:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.stack = BenStack(window_size=5)

    async def on_turn(self, turn: Turn):
        """Event: conversation turn completed."""
        chunk = self.chunker.process_turn(turn)
        self.stack.push(chunk)

        # Queue for background extraction
        await self.queue.put(ExtractionTask(
            chunks=self.stack.get_context_window(),
            priority=Priority.NORMAL
        ))

    async def on_document(self, doc: Document):
        """Event: document uploaded."""
        chunks = self.chunker.chunk_document(doc)
        await self.queue.put(ExtractionTask(
            chunks=chunks,
            priority=Priority.HIGH
        ))

    async def on_silence(self, duration_s: float):
        """Event: conversation went quiet."""
        if duration_s > 30 and self.stack:
            await self.flush_stack()

    async def worker(self):
        """Background worker processes queue."""
        while True:
            task = await self.queue.get()
            extractions = await self.extract(task.chunks)
            await self.librarian.file(extractions)  # Make it rain
```

**Why event-driven?**
- CPU usage minimal during idle periods
- Extractions queue naturally as conversation flows
- No wasted cycles polling for work

**Contrast with The Dude:** The Librarian runs on a hybrid schedule (event-driven for urgent filing, periodic for maintenance tasks like pruning).

---

## 4.7 Technical Stack

| Component | Model | Purpose | Latency |
|-----------|-------|---------|---------|
| Transcription | Whisper V3 Turbo (local) | Audio → Text | ~200ms |
| Reflexive labeling | Director 3B (local) | Fast classification | ~50ms |
| Deep extraction | Claude via Shadow Reasoner | Full semantic extraction | Async |
| Embedding | Sentence Transformers (local) | Vector representation | ~10ms |

### Resource Budget

```
┌────────────────────────────────────────────────────────────────┐
│  REFLEXIVE PATH (must complete <200ms)                         │
│                                                                 │
│  Whisper Turbo: 150ms                                          │
│  Director 3B classify: 40ms                                    │
│  Queue for extraction: 5ms                                      │
│  ────────────────────────────────                              │
│  Total: ~195ms ✓                                               │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  DEEP PATH (async, user already has response)                  │
│                                                                 │
│  Stack processing: 10ms                                        │
│  Claude extraction: 500-2000ms                                 │
│  Embedding generation: 50ms                                    │
│  Queue for Librarian: 5ms                                      │
│  ────────────────────────────────                              │
│  Total: ~600-2100ms (non-blocking)                             │
└────────────────────────────────────────────────────────────────┘
```

---

## 4.8 Implementation (Actor Pattern)

The actual implementation uses the Actor pattern with mailbox-based communication:

```python
class ScribeActor(Actor):
    """
    Benjamin Franklin: The extraction system.

    Extracts structured knowledge from conversations and sends
    to Librarian for filing in Memory Matrix.
    """

    def __init__(
        self,
        config: Optional[ExtractionConfig] = None,
        engine: Optional["LunaEngine"] = None,
    ):
        super().__init__("scribe", engine)

        self.config = config or ExtractionConfig()
        self.chunker = SemanticChunker()
        self.stack: deque[Chunk] = deque(maxlen=5)  # Context window

        # Anthropic client (lazy init)
        self._client = None

        # Stats
        self._extractions_count = 0
        self._objects_extracted = 0
        self._edges_extracted = 0
        self._entity_updates_extracted = 0
```

### Message Types (Mailbox Interface)

| Message Type | Purpose | Payload |
|--------------|---------|---------|
| `extract_turn` | Extract from conversation turn | `{role, content, session_id, immediate}` |
| `extract_text` | Extract from raw text | `{text, source_id, immediate}` |
| `entity_note` | Direct entity update command | `{entity_name, entity_type, facts}` |
| `flush_stack` | Process pending chunks | None |
| `compress_turn` | Compress for history tier | `{turn_id, content, role}` |
| `get_stats` | Return extraction statistics | None |

### Extraction Backend Configuration

```python
@dataclass
class ExtractionConfig:
    backend: str = "haiku"  # "haiku", "opus", "local", "disabled"
    batch_size: int = 3
    min_content_length: int = 20
    max_tokens: int = 1000
    temperature: float = 0.3
```

### Turn Compression (v2.1 Feature)

Ben also handles turn compression for the HistoryManager:

```python
async def compress_turn(self, content: str, role: str = "user") -> str:
    """
    Compress a conversation turn into a one-sentence summary.

    Used by HistoryManager when rotating turns from Active to Recent tier.

    Returns:
        Compressed summary (<50 words)
    """
```

### Extraction Statistics

```python
{
    "backend": "claude-opus",
    "extractions_count": 15,
    "objects_extracted": 234,
    "edges_extracted": 89,
    "entity_updates_extracted": 45,
    "avg_extraction_time_ms": 2345,
    "stack_size": 2,
    "batch_size": 3
}
```

---

## 4.9 Ben's Principles

| Principle | Implementation |
|-----------|----------------|
| **Separation** | Personality in process, neutrality in output |
| **Context Window** | Never extract in isolation; see surrounding chunks |
| **Confidence Tagging** | Every extraction carries uncertainty signal |
| **Event-Driven** | React to events, don't poll |
| **Non-Blocking** | Deep extraction never delays response |

> "By failing to prepare, you are preparing to fail." — Ben Franklin

Ben prepares Luna's memories so they're ready when needed.

---

*End of Part IV (v2.1)*

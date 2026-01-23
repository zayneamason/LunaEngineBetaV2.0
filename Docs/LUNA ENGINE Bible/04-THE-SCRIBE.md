# Part IV: The Scribe (Ben Franklin) — v2.0

**Status:** CURRENT
**Replaces:** BIBLE-PART-IV-THE-SCRIBE-v1.md
**Date:** December 29, 2025

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

Ben classifies into seven categories:

| Type | Description | Example | Signal Words |
|------|-------------|---------|--------------|
| **FACT** | Something known to be true | "Alex lives in Berlin" | is, lives, has, works at |
| **DECISION** | A choice that was made | "We chose Actor model" | decided, chose, going with |
| **PROBLEM** | An unresolved issue | "Voice latency is too high" | issue, problem, bug, broken |
| **ASSUMPTION** | Believed but unverified | "Users will want voice-first" | assume, probably, likely |
| **CONNECTION** | Relationship between entities | "Alex and Sarah are teammates" | knows, works with, related to |
| **ACTION** | Something done or to be done | "Need to implement RRF" | did, need to, should, will |
| **OUTCOME** | Result of action or decision | "Switching to rustworkx saved 45ms" | resulted in, improved, fixed |

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
    type: ExtractionType  # FACT, DECISION, PROBLEM, etc.
    subtype: str | None  # Further classification
    content: str  # The distilled content
    properties: dict  # Structured fields
    confidence: float  # 0.0-1.0
    entities: list[str]  # Mentioned entities
    embedding: np.ndarray | None  # Pre-computed if available

@dataclass
class ExtractedEdge:
    from_ref: str  # ID or content reference
    to_ref: str
    type: str  # "works_on", "decided", "caused", etc.
    role: str | None  # "author", "subject", etc.
    context_ref: str | None  # Source conversation

@dataclass
class ExtractionOutput:
    objects: list[ExtractedObject]
    edges: list[ExtractedEdge]
    source_id: str
    extraction_time_ms: int
```

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

## 4.8 Implementation

```python
class Scribe:
    """Benjamin Franklin: The extraction system."""

    def __init__(self, director: Director, librarian: Librarian):
        self.transcriber = WhisperTurboLocal()
        self.classifier = director.model  # Share with Director
        self.extractor = ShadowReasonerClient()
        self.chunker = SemanticChunker()
        self.stack = BenStack(window_size=5)
        self.librarian = librarian

    async def process_audio(self, audio_chunk: bytes) -> ScribeOutput:
        """Hot path: Audio → Classification → Route."""
        # 1. Transcribe (~150ms)
        text = await self.transcriber.transcribe(audio_chunk)

        # 2. Reflexive classification (~40ms)
        intent = await self.classifier.classify(text)

        # 3. Route based on intent
        if intent.type == IntentType.COMMAND:
            return ScribeOutput(text=text, intent=intent, routed_to="director")

        elif intent.type == IntentType.QUESTION:
            return ScribeOutput(text=text, intent=intent, routed_to="director")

        elif intent.type == IntentType.STATEMENT:
            # Queue for deep extraction (async)
            asyncio.create_task(self.deep_extract(text))
            return ScribeOutput(text=text, intent=intent, routed_to="extraction_queue")

        else:  # NOISE
            return ScribeOutput(text=text, intent=intent, routed_to="ignore")

    async def deep_extract(self, text: str):
        """Cold path: Full semantic extraction via Shadow Reasoner."""
        # 1. Chunk
        chunk = self.chunker.chunk_text(text)
        self.stack.push(chunk)

        # 2. Extract with context
        context_window = self.stack.get_context_window()
        extraction = await self.extractor.extract(
            text=text,
            context=context_window,
            extraction_types=list(ExtractionType)
        )

        # 3. Hand off to Librarian ("Make it rain")
        await self.librarian.file(extraction)

@dataclass
class ScribeOutput:
    text: str
    intent: Intent
    routed_to: str
    extraction_queued: bool = False
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

*End of Part IV (v2.0)*

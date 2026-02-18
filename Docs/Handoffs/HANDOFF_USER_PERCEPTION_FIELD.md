# HANDOFF: UserPerceptionField — Luna's Observation Layer

**Created:** 2026-02-18
**Author:** The Dude (Architecture), Benjamin Franklin (Philosophy), Luna (Self-Advocacy)
**For:** Claude Code Execution
**Complexity:** S-M (2-4 hours)
**Depends on:** PromptAssembler (HANDOFF_PROMPT_ASSEMBLER_AND_TEMPORAL.md) — can be implemented before or after, but wires into it

---

## 1. CONTEXT

Luna currently has zero model of the user's state. Her entire perception stack is self-referential:

| Component | What it reads | What it senses | About whom |
|-----------|--------------|----------------|------------|
| VoiceLock | Current query text | Query *type* (greeting/technical/emotional) | The *query* |
| ConfidenceSignals | Memory score, turn #, entity depth | System health / context richness | Luna's *own readiness* |
| ContextType | Query keywords + turn count | Conversation *category* | The *situation* |
| Mood Layer | Last 5 messages | Conversational *momentum* | The *conversation* |

**What's missing:** Any perception of the *user's* current behavioral state.

Luna reads the query. Luna reads her own context quality. But she never reads *Ahab*.

---

## 2. THE PHILOSOPHY

### The Principle: "Feed the mind, don't bypass it."

This is an **observation layer**, NOT a state machine or classifier.

**Wrong approach** (classifier → behavior change):
```
signals → state_machine → "frustrated" → inject "Be gentle, keep it brief"
```

**Right approach** (perception → awareness):
```
signals → observations → inject paired facts → Luna interprets herself
```

### Why Not a State Machine

A classifier that decides "user is frustrated" and injects behavioral instructions:
- **Misreads confidently** — short messages could be frustration, or driving, or rapid iteration mode
- **Bypasses Luna's judgment** — she's told what to think instead of seeing and deciding
- **Labels humans** — reduces complex behavioral patterns to enum values

### Why Paired Observations

Every observation carries its **trigger context** — what Luna did or what happened right before the signal changed. This is Luna's key insight:

Not "messages getting shorter" but "messages shortened **after Luna gave a long technical explanation**."

The pairing makes raw signals interpretable without pre-digesting them into conclusions.

---

## 3. DATA MODEL

### Create `src/luna/context/perception.py`

```python
"""
UserPerceptionField — Luna's observation layer for reading the room.

NOT a classifier. NOT a state machine. An observation accumulator.
Extracts behavioral signals from user messages, pairs each observation
with its trigger context (what Luna did right before), and formats
them for prompt injection.

Zero LLM calls. Pure signal extraction.
Session-scoped. Resets each session.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    """A single thing Luna noticed about the user."""
    
    signal: str          # What changed
                         # e.g. "length_shift", "correction_detected", "question_density"
    
    value: str           # The observation in natural language
                         # e.g. "Messages shortened from ~140 chars to ~35 chars"
    
    trigger: str         # What preceded / caused this
                         # e.g. "after Luna's 400-word technical explanation"
    
    turn: int            # When (turn number in session)
    confidence: float    # How clear is this signal (0.0-1.0)
    
    @property
    def paired(self) -> str:
        """Natural language: observation + trigger."""
        return f"{self.value} ({self.trigger})"


@dataclass
class PerceptionField:
    """
    Luna's observations about the current user, this session.
    
    NOT a state machine. NOT a classifier.
    An accumulator of paired observations.
    
    Resets each session. Does not persist to Matrix.
    (Future: Librarian could extract patterns across sessions)
    """
    
    observations: list[Observation] = field(default_factory=list)
    
    # Running signal state (for delta detection)
    _msg_lengths: list[int] = field(default_factory=list)
    _user_messages: list[str] = field(default_factory=list)
    _question_flags: list[bool] = field(default_factory=list)
    _terse_count: int = 0
    _correction_count: int = 0
    _last_luna_action: str = ""      # What Luna did last (for trigger context)
    _baseline_energy: Optional[dict] = None  # Energy markers from first 3 messages
    
    # Limits
    MAX_OBSERVATIONS: int = 8        # Cap what gets injected into prompt
    MIN_OBSERVATIONS_TO_INJECT: int = 2  # Need minimum signal before injecting
    
    def observe(self, obs: Observation) -> None:
        """Add an observation. Oldest drop when over limit."""
        self.observations.append(obs)
        if len(self.observations) > self.MAX_OBSERVATIONS:
            self.observations.pop(0)
        logger.debug("[PERCEPTION] %s (conf=%.2f, turn=%d)", obs.paired, obs.confidence, obs.turn)
    
    def to_prompt_block(self) -> Optional[str]:
        """
        Format for injection into system prompt.
        
        Returns None if insufficient observations.
        Returns formatted observation block if enough signal.
        """
        if len(self.observations) < self.MIN_OBSERVATIONS_TO_INJECT:
            return None  # Not enough signal yet
        
        recent = self.observations[-5:]  # Last 5 observations
        lines = [obs.paired for obs in recent]
        
        return (
            "## User Observation (this session)\n\n"
            + "\n".join(f"- {line}" for line in lines)
            + "\n\nThese are observations, not conclusions. "
            "Interpret them in context of what you know about Ahab."
        )
    
    def reset(self) -> None:
        """Reset for new session."""
        self.observations.clear()
        self._msg_lengths.clear()
        self._user_messages.clear()
        self._question_flags.clear()
        self._terse_count = 0
        self._correction_count = 0
        self._last_luna_action = ""
        self._baseline_energy = None
```

---

## 4. SIGNAL EXTRACTION

### The `ingest()` method

Called once per user turn, before prompt assembly. Extracts all signals and generates observations.

```python
    def ingest(self, user_message: str, turn_number: int) -> None:
        """
        Process a user message and extract observations.
        
        Called once per turn, before prompt assembly.
        Zero LLM calls. Pure signal extraction.
        """
        msg_text = user_message.strip()
        msg_len = len(msg_text)
        msg_lower = msg_text.lower()
        
        self._msg_lengths.append(msg_len)
        self._user_messages.append(msg_text)
        
        # Detect if this is a question
        question_starters = ("what", "who", "where", "when", "why", "how", "is ", "are ", "can ", "do ", "does ")
        is_question = msg_text.endswith("?") or msg_lower.startswith(question_starters)
        self._question_flags.append(is_question)
        
        trigger = self._last_luna_action or "start of session"
        
        # ── Signal 1: Message Length Trajectory ──
        self._check_length_trajectory(trigger, turn_number)
        
        # ── Signal 2: Correction / Repetition ──
        self._check_corrections(msg_text, trigger, turn_number)
        
        # ── Signal 3: Question Density ──
        self._check_question_density(trigger, turn_number)
        
        # ── Signal 4: Brevity Signals ──
        self._check_brevity(msg_lower, trigger, turn_number)
        
        # ── Signal 5: Energy Markers ──
        self._check_energy_markers(msg_text, trigger, turn_number)
    
    # ── Signal Extractors ──────────────────────────────────────
    
    def _check_length_trajectory(self, trigger: str, turn: int) -> None:
        """Detect sustained message length changes."""
        if len(self._msg_lengths) < 4:
            return
        
        recent_avg = sum(self._msg_lengths[-3:]) / 3
        earlier_avg = sum(self._msg_lengths[:-3]) / max(len(self._msg_lengths) - 3, 1)
        
        if earlier_avg <= 0:
            return
        
        ratio = recent_avg / earlier_avg
        
        if ratio < 0.4:  # Dropped to less than 40%
            self.observe(Observation(
                signal="length_shift",
                value=f"Messages shortened from ~{int(earlier_avg)} to ~{int(recent_avg)} chars over last 3 turns",
                trigger=trigger,
                turn=turn,
                confidence=0.8,
            ))
        elif ratio > 2.0:  # Doubled
            self.observe(Observation(
                signal="length_shift",
                value=f"Messages expanding — ~{int(recent_avg)} chars, up from ~{int(earlier_avg)}",
                trigger=trigger,
                turn=turn,
                confidence=0.7,
            ))
    
    def _check_corrections(self, msg_text: str, trigger: str, turn: int) -> None:
        """
        Detect when user repeats or corrects something.
        
        Heuristic: >40% word overlap with user's message from 2-3 turns ago
        indicates restating/correcting. Excludes common stop words.
        """
        if len(self._user_messages) < 3:
            return
        
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "can", "shall", "to", "of",
            "in", "for", "on", "with", "at", "by", "from", "it", "its",
            "this", "that", "these", "those", "i", "you", "we", "they",
            "me", "him", "her", "us", "them", "my", "your", "our", "and",
            "or", "but", "not", "no", "yes", "so", "if", "then", "just",
            "also", "about", "up", "out", "what", "how", "when", "where",
        }
        
        current_words = set(
            w.lower() for w in re.findall(r'\b\w+\b', msg_text)
            if len(w) > 2 and w.lower() not in stop_words
        )
        
        if not current_words:
            return
        
        # Check against messages from 2-3 turns ago
        for offset in [2, 3]:
            if len(self._user_messages) <= offset:
                continue
            
            prior_msg = self._user_messages[-(offset + 1)]  # +1 because current is already appended
            prior_words = set(
                w.lower() for w in re.findall(r'\b\w+\b', prior_msg)
                if len(w) > 2 and w.lower() not in stop_words
            )
            
            if not prior_words:
                continue
            
            overlap = len(current_words & prior_words)
            overlap_ratio = overlap / min(len(current_words), len(prior_words))
            
            if overlap_ratio > 0.4:
                self._correction_count += 1
                
                if self._correction_count == 1:
                    self.observe(Observation(
                        signal="correction_detected",
                        value="User rephrased or repeated a prior point",
                        trigger=trigger,
                        turn=turn,
                        confidence=0.75,
                    ))
                elif self._correction_count >= 2:
                    self.observe(Observation(
                        signal="correction_detected",
                        value=f"User has restated/corrected {self._correction_count} times this session",
                        trigger="Luna's responses may not be addressing the core ask",
                        turn=turn,
                        confidence=0.9,
                    ))
                break  # Only fire once per turn
    
    def _check_question_density(self, trigger: str, turn: int) -> None:
        """Detect sustained high question density."""
        if len(self._question_flags) < 4:
            return
        
        recent_q = sum(self._question_flags[-4:])
        
        if recent_q >= 3:
            self.observe(Observation(
                signal="question_density",
                value=f"High question density — {recent_q} of last 4 messages are questions",
                trigger=trigger,
                turn=turn,
                confidence=0.7,
            ))
        
        # Detect shift from questions to statements
        if len(self._question_flags) >= 6:
            earlier_q = sum(self._question_flags[-6:-3])
            recent_q_3 = sum(self._question_flags[-3:])
            if earlier_q >= 2 and recent_q_3 == 0:
                self.observe(Observation(
                    signal="question_density",
                    value="Shifted from questions to statements",
                    trigger=trigger,
                    turn=turn,
                    confidence=0.65,
                ))
    
    def _check_brevity(self, msg_lower: str, trigger: str, turn: int) -> None:
        """Detect terse acknowledgment patterns."""
        terse_markers = {
            "ok", "sure", "thanks", "got it", "yep", "yeah",
            "sounds good", "cool", "k", "fine", "right",
            "makes sense", "understood", "noted",
        }
        
        # Strip trailing punctuation for matching
        cleaned = msg_lower.rstrip(".!?,")
        
        if cleaned in terse_markers:
            self._terse_count += 1
            
            if self._terse_count >= 2:
                self.observe(Observation(
                    signal="terse_response",
                    value=f"{self._terse_count} terse acknowledgments in this session",
                    trigger=trigger,
                    turn=turn,
                    confidence=0.7 if self._terse_count == 2 else 0.85,
                ))
        else:
            # Non-terse message resets the counter (not accumulative across gaps)
            if self._terse_count > 0 and len(msg_lower) > 40:
                self._terse_count = 0
    
    def _check_energy_markers(self, msg_text: str, trigger: str, turn: int) -> None:
        """Detect energy changes via punctuation, caps, emoji."""
        exclamation_count = msg_text.count("!")
        caps_words = sum(1 for w in msg_text.split() if w.isupper() and len(w) > 1)
        # Simple emoji detection (common unicode ranges)
        emoji_count = sum(
            1 for c in msg_text
            if ord(c) > 0x1F300  # Rough emoji range start
        )
        
        energy = {
            "exclamations": exclamation_count,
            "caps": caps_words,
            "emoji": emoji_count,
        }
        
        # Establish baseline from first 3 messages
        if len(self._msg_lengths) <= 3:
            if self._baseline_energy is None:
                self._baseline_energy = {"exclamations": 0, "caps": 0, "emoji": 0}
            for k in energy:
                self._baseline_energy[k] = max(self._baseline_energy.get(k, 0), energy[k])
            return
        
        if self._baseline_energy is None:
            return
        
        # Detect significant changes from baseline
        baseline_total = sum(self._baseline_energy.values())
        current_total = sum(energy.values())
        
        if baseline_total == 0 and current_total >= 2:
            self.observe(Observation(
                signal="energy_markers",
                value="Energy markers appeared — exclamation marks, emoji, or emphasis",
                trigger=trigger,
                turn=turn,
                confidence=0.6,
            ))
        elif baseline_total >= 2 and current_total == 0 and turn > 8:
            self.observe(Observation(
                signal="energy_markers",
                value="Energy markers dropped — flat punctuation, no emoji",
                trigger=f"late in session (turn {turn})",
                turn=turn,
                confidence=0.5,
            ))
```

---

## 5. LUNA ACTION TRACKING

After each LLM response, record what Luna did for trigger context on the next turn.

```python
    def record_luna_action(self, luna_response: str) -> None:
        """
        Record a brief summary of Luna's response for trigger context.
        Called after LLM generation, before next turn.
        
        NOT an LLM call. Simple heuristic classification.
        """
        length = len(luna_response)
        has_question = "?" in luna_response
        has_code = "```" in luna_response
        
        if length < 100:
            action = "gave brief response"
        elif length < 300:
            action = "gave moderate response"
        elif has_code:
            action = f"gave {(length // 100) * 100}+ char technical response with code"
        else:
            action = f"gave {(length // 100) * 100}+ char explanation"
        
        if has_question:
            action += " and asked a question"
        
        self._last_luna_action = action
```

---

## 6. WIRING

### 6.1 Data Flow (each turn)

```
User Message ──→ PerceptionField.ingest(message, turn_number)
     │              │
     │              ├─ compute message length
     │              ├─ detect corrections (word overlap)
     │              ├─ count questions
     │              ├─ check brevity markers
     │              ├─ check energy markers
     │              ├─ compare against running baselines
     │              │
     │              ├─ for each signal that changed:
     │              │    create Observation(
     │              │      signal = what changed
     │              │      value  = the observation
     │              │      trigger = _last_luna_action
     │              │    )
     │              │
     │              └─ update running state
     │
     ▼
PromptAssembler.build()
     │
     ├─ Layer 1: Identity
     ├─ Layer 2: Temporal
     ├─ Layer 3: perception_field.to_prompt_block() ◄── HERE
     ├─ Layer 4: Memory
     ├─ Layer 5: Conversation
     └─ Layer 6: Voice
     │
     ▼
LLM generates response
     │
     ▼
PerceptionField.record_luna_action(response)
```

### 6.2 Create PerceptionField in Director

```python
# In DirectorActor.__init__, after other initialization:
from luna.context.perception import PerceptionField
self._perception_field = PerceptionField()
self._perception_turn_count = 0
```

### 6.3 Ingest before prompt assembly

In every path that processes a user message (the process() method and its sub-paths), add the ingest call **before** prompt assembly:

```python
# Before building the prompt:
self._perception_turn_count += 1
self._perception_field.ingest(message, self._perception_turn_count)
```

This should go in ONE location — wherever the user message first enters the Director's processing pipeline, before any branching into delegated/local/fallback paths. Find the earliest common point.

### 6.4 Record Luna's action after response

After the LLM response is generated but before it's returned to the user:

```python
# After LLM generates response:
self._perception_field.record_luna_action(response_text)
```

### 6.5 Wire into PromptAssembler (Layer 3)

**If PromptAssembler exists** (HANDOFF_PROMPT_ASSEMBLER_AND_TEMPORAL has been implemented):

Add to `PromptAssembler.build()`, between Layer 2 (TEMPORAL) and Layer 4 (MEMORY):

```python
        # ── Layer 3: PERCEPTION ────────────────────────────────────
        perception_block = None
        if hasattr(self._director, '_perception_field') and self._director._perception_field:
            perception_block = self._director._perception_field.to_prompt_block()
        
        if perception_block:
            sections.append(perception_block)
            result.perception_injected = True
            result.observation_count = len(self._director._perception_field.observations)
```

Add to `PromptResult` dataclass:
```python
    perception_injected: bool = False
    observation_count: int = 0
```

**If PromptAssembler does NOT yet exist** (this handoff is implemented first):

Wire directly into wherever the system prompt is being assembled. Find where `enhanced_system_prompt` or `system_prompt` is being built and add:

```python
# After identity/temporal, before memory:
perception_block = self._perception_field.to_prompt_block()
if perception_block:
    system_prompt = f"{system_prompt}\n\n{perception_block}"
```

### 6.6 Reset on session start

When a new session starts (however that's currently detected):

```python
self._perception_field.reset()
self._perception_turn_count = 0
```

---

## 7. PROMPT INJECTION EXAMPLES

### Scenario: Deep Focus

Turn 14. Sustained architecture discussion, long messages, high question density.

```
## User Observation (this session)

- Topic sustained for 12 turns — deep technical focus (on temporal awareness architecture)
- Messages expanding — ~180 chars, up from ~90 (since topic shifted to implementation details)
- High question density — 4 of last 4 messages are questions (in sustained architecture discussion)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.
```

Luna reads this and matches the intensity — stays thorough, stays technical.

### Scenario: Losing Patience

Turn 10. Luna missed the point, user corrected, messages shortened.

```
## User Observation (this session)

- User corrected Luna's interpretation (after Luna's 500+ char explanation)
- Messages shortened from ~160 to ~55 chars over last 3 turns (after Luna's 500+ char explanation)
- User rephrased or repeated a prior point (Luna's responses may not be addressing the core ask)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.
```

Luna reads this and gets to the point — addresses exactly what was asked, shorter response.

### Scenario: Winding Down

Turn 18. Late in session, terse acknowledgments.

```
## User Observation (this session)

- 3 terse acknowledgments in this session (during implementation wrap-up)
- Messages shortened from ~120 to ~25 chars over last 3 turns (after productive deep dive)
- Energy markers dropped — flat punctuation, no emoji (late in session, turn 18+)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.
```

Luna reads this and wraps up gracefully.

### Scenario: Early Session

Turn 2. Insufficient data.

```
[No perception block injected — fewer than 2 observations]
```

The PerceptionField stays silent until it has enough signal. No observation is better than premature observation.

---

## 8. FILES

| File | Action | Description |
|------|--------|-------------|
| `src/luna/context/perception.py` | **NEW** | ~220 lines. Observation, PerceptionField, signal extractors, prompt formatting |
| `src/luna/context/assembler.py` | **MODIFY** | ~10 lines. Add Layer 3 perception injection (if assembler exists) |
| `src/luna/actors/director.py` | **MODIFY** | ~20 lines. Create PerceptionField, call ingest(), call record_luna_action() |
| `tests/test_perception.py` | **NEW** | ~180 lines. Signal detection, observation pairing, prompt formatting |

---

## 9. TESTING

### 9.1 Signal Detection Tests

```python
from luna.context.perception import PerceptionField, Observation


def test_length_shift_detection():
    """Messages shortening triggers observation."""
    pf = PerceptionField()
    # Simulate 3 long messages then 3 short ones
    for i, msg in enumerate(["x" * 150, "x" * 140, "x" * 160, "x" * 40, "x" * 35, "x" * 30]):
        pf.ingest(msg, i + 1)
    
    signals = [o.signal for o in pf.observations]
    assert "length_shift" in signals
    
    length_obs = [o for o in pf.observations if o.signal == "length_shift"][0]
    assert "shortened" in length_obs.value.lower()


def test_correction_detection():
    """Repeating similar content triggers correction observation."""
    pf = PerceptionField()
    pf.ingest("I want the thread timestamps not the session timestamps", 1)
    pf.ingest("can you explain more about threads", 2)
    pf._last_luna_action = "gave 500+ char explanation about session timestamps"
    pf.ingest("no I mean the thread timestamps not session", 3)
    
    signals = [o.signal for o in pf.observations]
    assert "correction_detected" in signals


def test_question_density():
    """High question rate triggers observation."""
    pf = PerceptionField()
    pf.ingest("what about the temporal layer?", 1)
    pf.ingest("how does the gap detection work?", 2)
    pf.ingest("what are the thread inheritance rules?", 3)
    pf.ingest("where does the clock get injected?", 4)
    
    signals = [o.signal for o in pf.observations]
    assert "question_density" in signals


def test_brevity_detection():
    """Terse acknowledgments trigger observation."""
    pf = PerceptionField()
    pf.ingest("This is a normal length message about architecture", 1)
    pf.ingest("ok", 2)
    pf.ingest("sure", 3)
    
    signals = [o.signal for o in pf.observations]
    assert "terse_response" in signals


def test_energy_markers_appear():
    """Energy increase triggers observation."""
    pf = PerceptionField()
    # Flat baseline
    pf.ingest("normal message here", 1)
    pf.ingest("another normal message", 2)
    pf.ingest("still normal", 3)
    # Energy spike
    pf.ingest("YES! That's exactly it!! 🎯🎯", 4)
    
    signals = [o.signal for o in pf.observations]
    assert "energy_markers" in signals
```

### 9.2 Observation Pairing Tests

```python
def test_trigger_context_captured():
    """Observations carry what Luna did before."""
    pf = PerceptionField()
    pf._last_luna_action = "gave 400+ char explanation"
    
    pf.ingest("x" * 150, 1)
    pf.ingest("x" * 140, 2)
    pf.ingest("x" * 160, 3)
    pf._last_luna_action = "gave 500+ char technical response with code"
    pf.ingest("x" * 30, 4)
    pf.ingest("x" * 25, 5)
    pf.ingest("x" * 20, 6)
    
    length_obs = [o for o in pf.observations if o.signal == "length_shift"]
    if length_obs:
        assert "500+" in length_obs[-1].trigger or "technical" in length_obs[-1].trigger


def test_paired_output_format():
    """Observation.paired combines value and trigger."""
    obs = Observation(
        signal="length_shift",
        value="Messages shortened from ~140 to ~35 chars",
        trigger="after Luna's 400-word explanation",
        turn=8,
        confidence=0.8,
    )
    assert "Messages shortened" in obs.paired
    assert "after Luna's" in obs.paired
    assert "(" in obs.paired  # Trigger in parentheses
```

### 9.3 Prompt Formatting Tests

```python
def test_no_injection_with_insufficient_observations():
    """Fewer than 2 observations → no prompt block."""
    pf = PerceptionField()
    pf.observe(Observation("test", "one observation", "trigger", 1, 0.5))
    assert pf.to_prompt_block() is None


def test_injection_with_sufficient_observations():
    """2+ observations → formatted prompt block."""
    pf = PerceptionField()
    pf.observe(Observation("a", "first thing", "trigger1", 1, 0.7))
    pf.observe(Observation("b", "second thing", "trigger2", 2, 0.8))
    
    block = pf.to_prompt_block()
    assert block is not None
    assert "User Observation" in block
    assert "first thing" in block
    assert "observations, not conclusions" in block


def test_max_observations_cap():
    """Only last MAX_OBSERVATIONS survive."""
    pf = PerceptionField()
    for i in range(12):
        pf.observe(Observation(f"sig_{i}", f"obs {i}", "trigger", i, 0.5))
    
    assert len(pf.observations) == pf.MAX_OBSERVATIONS


def test_reset_clears_everything():
    """Reset wipes all state."""
    pf = PerceptionField()
    pf.ingest("test message", 1)
    pf.observe(Observation("test", "obs", "trigger", 1, 0.5))
    pf._last_luna_action = "something"
    
    pf.reset()
    
    assert len(pf.observations) == 0
    assert len(pf._msg_lengths) == 0
    assert pf._last_luna_action == ""
```

### 9.4 Luna Action Recording Tests

```python
def test_record_brief_response():
    pf = PerceptionField()
    pf.record_luna_action("Sure, here you go.")
    assert "brief" in pf._last_luna_action


def test_record_long_explanation():
    pf = PerceptionField()
    pf.record_luna_action("x" * 500)
    assert "500" in pf._last_luna_action or "char" in pf._last_luna_action


def test_record_code_response():
    pf = PerceptionField()
    pf.record_luna_action("Here's the code:\n```python\ndef hello():\n    pass\n```\nThat should work." + "x" * 400)
    assert "code" in pf._last_luna_action


def test_record_question():
    pf = PerceptionField()
    pf.record_luna_action("That's interesting. What made you think of that approach?")
    assert "question" in pf._last_luna_action
```

### 9.5 Integration Test

```python
async def test_perception_end_to_end():
    """Full flow: ingest → observe → format → inject."""
    pf = PerceptionField()
    
    # Simulate a conversation arc
    messages = [
        ("Tell me about the memory architecture", "gave 400+ char explanation"),
        ("How does the vector search work?", "gave 300+ char explanation"),
        ("What about the graph traversal?", "gave 500+ char technical response with code"),
        ("And the FTS5 integration?", "gave 400+ char explanation"),
        # Now user gets terse
        ("ok", "gave brief response"),
        ("sure", "gave brief response"),
    ]
    
    for i, (msg, luna_action) in enumerate(messages):
        pf.ingest(msg, i + 1)
        pf.record_luna_action("x" * (int(luna_action.split("+")[0].split()[-1]) if "+" in luna_action else 50))
    
    block = pf.to_prompt_block()
    assert block is not None
    assert "User Observation" in block
    assert "observations, not conclusions" in block
```

---

## 10. SUCCESS CRITERIA

Implementation is complete when:

1. `PerceptionField` class exists in `src/luna/context/perception.py`
2. Six signal extractors work: length trajectory, correction detection, question density, brevity, energy markers, and topic persistence (reuse existing `topic_continuity`)
3. Every observation carries trigger context (`_last_luna_action`)
4. `to_prompt_block()` returns None for < 2 observations
5. `to_prompt_block()` returns formatted block with paired observations for >= 2
6. Observation cap works (oldest drop at MAX_OBSERVATIONS)
7. `ingest()` called before prompt assembly on every user turn
8. `record_luna_action()` called after every LLM response
9. Perception block injected into prompt between TEMPORAL and MEMORY (Layer 3)
10. Session reset clears all perception state
11. All tests pass
12. `/slash/prompt` shows perception block when observations exist
13. Zero LLM calls in the perception pipeline
14. No new dependencies

---

## 11. WHAT THIS DOES NOT DO

- **Does not classify user mood/state** — observations only, never labels like "frustrated" or "happy"
- **Does not persist across sessions** — session-scoped, resets on new session. Future work for Librarian to extract cross-session patterns.
- **Does not use LLM calls** — pure Python string operations and heuristics
- **Does not modify Luna's behavior directly** — injects observations into prompt for Luna's inference layer to interpret
- **Does not replace VoiceLock** — VoiceLock reads query type, PerceptionField reads user behavioral patterns. Complementary, not overlapping.
- **Does not track topic_continuity** — reuses the existing `_calculate_topic_continuity()` in Director if available. Does not reimplement.

---

## 12. EXECUTION ORDER

1. Create `src/luna/context/perception.py` (standalone, no dependencies)
2. Create `tests/test_perception.py` — run unit tests
3. Wire `PerceptionField` into `DirectorActor.__init__`
4. Add `ingest()` call at earliest common point before prompt assembly
5. Add `record_luna_action()` call after LLM response generation
6. Wire `to_prompt_block()` into prompt assembly (Layer 3 if assembler exists, or inline)
7. Add `reset()` call on session start
8. Run full test suite
9. Restart server, send test conversation, verify:
   - First 2 messages: no perception block in prompt
   - Turn 4+: perception block appears with observations
   - Observations include trigger context
10. Verify via `/slash/prompt` that perception block visible between temporal and memory

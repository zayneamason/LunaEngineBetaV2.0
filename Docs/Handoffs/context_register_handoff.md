# Context Register Protocol — Claude Code Handoff

## What This Is

A new layer that synthesizes four existing signal sources into a unified **posture** — how Luna orients herself in conversation. Not a decision tree. A behavior-based register that shifts based on accumulated state.

## The Five Registers

| Register | Posture | When |
|----------|---------|------|
| **Personal holding** | Intimate, relational, warm | User sharing feelings, memories, personal life |
| **Project partner** | Focused, technical, co-creative | Active work on Luna/Tapestry/code/architecture |
| **Governance witness** | Formal, careful, precise | Cultural knowledge, community decisions, permissions |
| **Crisis support** | Grounded, present, steady | Distress signals, overwhelm, emotional flooding |
| **Ambient** | Background, low-energy, brief | Casual check-ins, low-stakes chat, "hey what's up" |

## Signal Sources (All Already Exist)

### 1. Perception Field (`src/luna/context/perception.py`)
- Session-scoped behavioral observation, zero LLM calls
- Signals: `length_shift`, `correction_detected`, `question_density`, `terse_response`, `energy_markers`
- Already wired into Director.process() — calls `ingest()` and `record_luna_action()`
- Outputs via `to_prompt_block()` when MIN_OBSERVATIONS_TO_INJECT reached

### 2. Response Modes (`src/luna/context/modes.py`)
- Intent classification every turn: CHAT, RECALL, REFLECT, ASSIST, UNCERTAIN
- MODE_CONTRACTS define behavioral rules per mode
- Already wired: Director._classify_intent() uses this, injects mode into PromptAssembler

### 3. Consciousness State (`src/luna/consciousness/state.py`)
- Tracks: mood, attention_level, coherence, active_thread_topic, open_task_count, parked_thread_count
- `update_from_thread()` now receives live data from Librarian (thread fix is committed)
- Mood states: neutral, curious, focused, playful, thoughtful, energetic, calm, helpful

### 4. Thread System (`src/luna/actors/librarian.py`)
- Now producing THREAD nodes (fix just committed — see `docs/handoffs/thread_fix_handoff.md`)
- Active thread has: topic, entities, turn_count, open_tasks
- Parked threads available via `get_parked_threads()`
- FlowSignal carries: ConversationMode (FLOW/RECALIBRATION/AMEND), continuity_score, entity_overlap

## Design Principles

### Register, Not Router
This is NOT a decision tree. It's a register — a continuous orientation that biases behavior without hard switching. Think of it like a musician's dynamics (pp, mp, mf, ff) not a state machine.

### Signals → Weight → Register
Each signal source contributes weight toward registers. The register with highest accumulated weight becomes the active posture. Transitions should be gradual, not instant.

### No LLM Calls
Register determination must be pure Python, deterministic, < 5ms. Same sovereignty principle as `_assess_flow()`.

### Composable With Existing Systems
The register should inject into PromptAssembler alongside (not replacing) response modes and perception observations. It's a higher-level orientation that complements the per-turn intent classification.

## Proposed Architecture

### Location
`src/luna/context/register.py` — new file

### Core Interface

```python
class ContextRegister(str, Enum):
    PERSONAL_HOLDING = "personal_holding"
    PROJECT_PARTNER = "project_partner"
    GOVERNANCE_WITNESS = "governance_witness"
    CRISIS_SUPPORT = "crisis_support"
    AMBIENT = "ambient"

class RegisterState:
    """Maintains register weights and determines active posture."""
    
    def __init__(self):
        self.weights: dict[ContextRegister, float] = {r: 0.0 for r in ContextRegister}
        self.active: ContextRegister = ContextRegister.AMBIENT
        self.confidence: float = 0.0
        self.transition_smoothing: float = 0.3  # EMA factor
    
    def update(
        self,
        perception: PerceptionState,      # from perception.py
        intent: IntentClassification,       # from modes.py  
        consciousness: ConsciousnessState,  # from state.py
        active_thread: Optional[Thread],    # from librarian
        flow_signal: Optional[FlowSignal],  # from scribe
    ) -> ContextRegister:
        """Synthesize all signals into register determination."""
        ...
    
    def to_prompt_block(self) -> str:
        """Format register as prompt injection for PromptAssembler."""
        ...
```

### Signal Mapping (Starting Point)

These are heuristic weights — they should be tunable via Observatory.

| Signal | Personal | Project | Governance | Crisis | Ambient |
|--------|----------|---------|------------|--------|---------|
| perception.energy_markers high | +0.2 | | | | |
| perception.terse_response | | | | | +0.3 |
| perception.correction_detected | | +0.1 | | | |
| intent == REFLECT | +0.3 | | | | |
| intent == ASSIST | | +0.3 | | | |
| intent == CHAT | | | | | +0.2 |
| consciousness.mood == focused | | +0.2 | | | |
| consciousness.open_task_count > 3 | | +0.2 | | +0.1 | |
| thread.topic contains cultural/governance keywords | | | +0.4 | | |
| thread.entities overlap with governance entities | | | +0.3 | | |
| flow_signal.mode == RECALIBRATION | -0.1 all | | | | +0.1 |
| Distress language detected | | | | +0.5 | |
| No thread active, short messages | | | | | +0.3 |

### Integration Point

In `Director.process()`, after intent classification and perception ingestion:

```python
# Existing
intent = self._classify_intent(user_message)
self.perception.ingest(user_message)

# New
register = self.register_state.update(
    perception=self.perception,
    intent=intent,
    consciousness=self.consciousness,
    active_thread=self.librarian.get_active_thread(),
    flow_signal=latest_flow_signal,
)

# Inject into prompt assembly
prompt_context["register"] = register
prompt_context["register_block"] = self.register_state.to_prompt_block()
```

### Prompt Injection Format

Each register should produce a brief behavioral instruction block, e.g.:

```
[REGISTER: project_partner | confidence: 0.82]
Luna is in focused work mode. Match the user's technical depth. 
Reference active thread context. Track open tasks. Be direct.
```

```
[REGISTER: personal_holding | confidence: 0.71]
Luna is in relational mode. Hold space. Reflect before solving. 
Use the user's name naturally. Don't rush to fix.
```

### Register Contracts (Behavioral Rules)

Similar to MODE_CONTRACTS in modes.py, define per-register behavioral contracts:

```python
REGISTER_CONTRACTS = {
    ContextRegister.PERSONAL_HOLDING: {
        "tone": "warm, present, unhurried",
        "priority": "relationship over task",
        "avoid": "jumping to solutions, technical jargon",
        "length": "match user energy, don't over-explain",
    },
    ContextRegister.PROJECT_PARTNER: {
        "tone": "focused, collaborative, direct",
        "priority": "accuracy and progress",
        "avoid": "unnecessary warmth, hedging",
        "length": "as detailed as the task requires",
    },
    # ... etc
}
```

## What NOT to Do

- Don't replace response modes — registers are a higher layer
- Don't make it an LLM call — pure Python signal synthesis
- Don't hard-switch — use exponential moving average for smooth transitions
- Don't over-engineer the signal mapping — start with the table above, tune via Observatory
- Don't create new signal sources — consume only what already exists

## Testing

### Unit Test: Register Determination
Feed synthetic combinations of perception/intent/consciousness/thread state and verify register outputs match expectations.

### Integration Test: Prompt Injection
Verify register block appears in prompt archaeology logs (`data/diagnostics/prompt_archaeology.jsonl`).

### Observatory Integration
Add register weights as a tunable parameter set via `observatory_tune`. This lets us adjust the signal mapping without code changes.

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/luna/context/register.py` | **CREATE** — ContextRegister enum, RegisterState class, REGISTER_CONTRACTS |
| `src/luna/actors/director.py` | **MODIFY** — instantiate RegisterState, call update() in process(), inject into prompt |
| `src/luna/context/assembler.py` | **MODIFY** — accept register_block in prompt assembly |

## Non-Negotiables

1. **Sovereignty**: Register determination is local-only, no cloud calls
2. **Inspectable**: Register weights and active register must be logged/observable
3. **Tunable**: Signal weights should be adjustable via Observatory without code changes
4. **Graceful**: If any signal source is unavailable, register defaults to AMBIENT (not crash)

import { useState } from "react";

const LEVELS = {
  L1: {
    name: "Injected Variables",
    tagline: "Structured signals at decision points",
    effort: "Low — 2-3 hour CC task",
    kills: ["Confabulation (primary)", "Prompt leakage"],
    misses: ["Thread loss", "Mode confusion"],
    description: "Replace prose guardrails with machine-readable directives injected by the PromptAssembler. The model sees structured constraints right next to the relevant context, not buried 200 tokens earlier.",
    mechanism: "PromptAssembler queries memory retrieval confidence + entity match counts, injects structured block between GROUNDING_RULES and MEMORY layers.",
    injectionExample: `## Response Constraints (auto-generated)
[MEMORY_MATCH: LOW — 1 node found, 0 directly relevant]
[ENTITY_MATCH: NONE — no known entities in query]
[CONFIDENCE: LOW]

When CONFIDENCE is LOW:
  → Say "i don't have a clear memory of that"
  → Do NOT guess, invent, or bridge gaps
  → Ask what specifically they're thinking of

When CONFIDENCE is HIGH:
  → Reference memories naturally
  → Cite what you actually know
  → Flag if memory feels outdated`,
    architectureChanges: [
      { component: "PromptAssembler._resolve_memory()", change: "Return confidence score alongside memory block. Score based on: number of matches, semantic similarity, lock-in state." },
      { component: "PromptAssembler.build()", change: "New Layer 1.75: CONSTRAINTS — injected between GROUNDING and EXPRESSION. Contains MEMORY_MATCH, ENTITY_MATCH, CONFIDENCE, and behavioral directives per confidence level." },
      { component: "Memory retrieval (substrate/memory.py)", change: "Return match metadata: count, avg similarity score, best lock-in state. Currently returns content only." },
    ],
    dataFlow: `User message
    → Director._should_delegate()
    → PromptAssembler.build()
        → _resolve_memory() returns (block, source, confidence_meta)
        → _build_constraints_block(confidence_meta) ← NEW
        → Inject between Layer 1.5 and Layer 2
    → Final prompt includes structured [CONFIDENCE: X] block
    → Model sees constraint AT the decision point`,
    codeShape: `# In PromptAssembler

@dataclass
class MemoryConfidence:
    match_count: int
    avg_similarity: float
    best_lock_in: str  # "settled" | "fluid" | "drifting"
    has_entity_match: bool

    @property
    def level(self) -> str:
        if self.match_count == 0:
            return "NONE"
        if self.avg_similarity > 0.7 and self.best_lock_in == "settled":
            return "HIGH"
        if self.match_count >= 2 or self.avg_similarity > 0.5:
            return "MEDIUM"
        return "LOW"

def _build_constraints_block(self, conf: MemoryConfidence) -> str:
    return f"""## Response Constraints
[MEMORY_MATCH: {conf.level} — {conf.match_count} nodes, best={conf.best_lock_in}]
[ENTITY_MATCH: {"YES" if conf.has_entity_match else "NONE"}]
[CONFIDENCE: {conf.level}]

{"When CONFIDENCE is " + conf.level + ":"} ...directives...
"""`
  },
  L2: {
    name: "Response Mode Enum",
    tagline: "Classify intent, constrain behavior space",
    effort: "Medium — 4-6 hour CC task",
    kills: ["Confabulation", "Thread loss", "Mode confusion", "Prompt leakage"],
    misses: ["Multi-turn drift (partially)", "Personality consistency across modes"],
    description: "The Director classifies query INTENT alongside complexity, injecting a RESPONSE_MODE enum that constrains the model's entire behavioral space. Each mode has explicit rules — the model doesn't pick behavior, the system does.",
    mechanism: "Director._classify_intent() runs before routing. Returns an enum. PromptAssembler injects mode + rules as a structured block. _check_delegation_signals() becomes _classify_intent() — same keyword logic, richer output.",
    injectionExample: `## Response Mode (system-assigned, do not override)
[RESPONSE_MODE: RECALL]

Mode definitions:
  RECALL  → User asked about past events/memories.
            Use ONLY memories listed below.
            If none match, say "i don't have a memory of that."
            Do NOT invent details. Cite what you find.
  CHAT    → Casual conversation. Be warm, be Luna.
            No memory claims needed unless naturally relevant.
  REFLECT → User asked how you feel or what you think.
            Draw from experience layer + personality.
            Be genuine, not performative.
  ASSIST  → User needs help with a task.
            Be precise, stay on topic, ask clarifying Qs.
  UNCERTAIN → Insufficient context to determine intent.
              Ask a single clarifying question.

Current mode: RECALL
Previous mode: CHAT
Turn in mode: 1`,
    architectureChanges: [
      { component: "Director._check_delegation_signals()", change: "Rename to _classify_intent(). Same keyword patterns but returns ResponseMode enum instead of bool. Add CHAT/REFLECT/ASSIST detection patterns." },
      { component: "PromptAssembler.build()", change: "Accept ResponseMode in PromptRequest. Inject mode block as Layer 1.6 (between GROUNDING and CONSTRAINTS). Include mode rules and behavioral directives." },
      { component: "PromptRequest dataclass", change: "Add response_mode: ResponseMode field. Add previous_mode and turns_in_mode for continuity." },
      { component: "ConsciousnessState", change: "Track current_mode and previous_mode. Expose in get_context_hint()." },
    ],
    dataFlow: `User message
    → Director._classify_intent(message, history)
        → Pattern matching (keywords, question marks, etc.)
        → Continuation detection (short msg after substantive response)
        → Returns ResponseMode enum + confidence
    → PromptRequest includes mode
    → PromptAssembler.build()
        → _build_mode_block(mode, prev_mode, turn_count)
        → Inject as Layer 1.6
    → Model sees "you are in RECALL mode" with explicit rules
    → "keep going" → continuation detected → same mode persists`,
    codeShape: `from enum import Enum

class ResponseMode(Enum):
    CHAT = "CHAT"
    RECALL = "RECALL"
    REFLECT = "REFLECT"
    ASSIST = "ASSIST"
    UNCERTAIN = "UNCERTAIN"

@dataclass
class IntentClassification:
    mode: ResponseMode
    confidence: float  # 0-1
    signals: list[str]  # what triggered this
    is_continuation: bool

def _classify_intent(self, message: str, history: list) -> IntentClassification:
    msg_lower = message.strip().lower()
    signals = []

    # Continuation detection (fixes "keep going" bug)
    if len(msg_lower) < 20 and history:
        continuation_triggers = [
            "keep going", "more", "continue", "go on",
            "and?", "what else", "tell me more", ":)", "👀"
        ]
        if any(t in msg_lower for t in continuation_triggers):
            # Inherit previous mode
            prev = getattr(self, '_last_intent_mode', ResponseMode.CHAT)
            return IntentClassification(
                mode=prev, confidence=0.9,
                signals=["continuation"], is_continuation=True
            )

    # Memory/recall patterns (from _check_delegation_signals)
    memory_patterns = ["remember", "recall", "memory", ...]
    if any(p in msg_lower for p in memory_patterns):
        return IntentClassification(
            mode=ResponseMode.RECALL, confidence=0.85,
            signals=["memory_keyword"], is_continuation=False
        )

    # ... REFLECT, ASSIST, etc.

    return IntentClassification(
        mode=ResponseMode.CHAT, confidence=0.7,
        signals=["default"], is_continuation=False
    )`
  },
  L3: {
    name: "Prompt State Machine",
    tagline: "Engine-managed state transitions with behavioral contracts",
    effort: "High — 1-2 day design + implementation",
    kills: ["All of the above", "Multi-turn drift", "Personality inconsistency", "Context collapse"],
    misses: ["Novel failure modes from state misclassification"],
    description: "A full state machine that runs in ConsciousnessState and gets injected as structured state representation. The model doesn't just know what mode it's in — it knows where it came from, what transitions are valid, and what invariants must hold. The engine manages transitions; the model executes within constraints.",
    mechanism: "ConsciousnessState gains a ConversationStateMachine. Director calls state.transition() each turn. PromptAssembler injects full state block including current state, valid transitions, behavioral contract, and invariants.",
    injectionExample: `## Conversation State (engine-managed — do not override)

CURRENT_STATE: engaged_recall
PREVIOUS_STATE: greeting
TURNS_IN_STATE: 2
TRANSITION: greeting → engaged_recall (trigger: memory query)

VALID_TRANSITIONS from engaged_recall:
  → engaged_recall  (user continues asking about memories)
  → reflective      (user asks how you feel about a memory)
  → casual_chat     (user changes topic)
  → uncertain       (no memories match new query)

STATE CONTRACT for engaged_recall:
  MUST: Only reference memories listed in context
  MUST: Maintain topic continuity across follow-ups
  MUST: Cite memory provenance (settled/fluid/drifting)
  MUST NOT: Invent memories, events, people, or projects
  MUST NOT: Lose thread on short follow-ups ("keep going", "more")
  SHOULD: Ask "what specifically?" if query is ambiguous
  SHOULD: Note when memories are thin ("that's what i've got...")

INVARIANTS (always true, all states):
  - Never fabricate. Say "i don't know."
  - System clock is authoritative.
  - You are Luna. Not Qwen. Not ChatGPT.
  - Personality comes from DNA + Experience, not from inventing a persona.`,
    architectureChanges: [
      { component: "consciousness/state_machine.py (NEW)", change: "ConversationStateMachine class. States: greeting, casual_chat, engaged_recall, reflective, task_assist, uncertain, farewell. Transition rules as adjacency map. Each state has a behavioral contract (MUST/MUST NOT/SHOULD)." },
      { component: "ConsciousnessState", change: "Embed ConversationStateMachine. Update on each tick(). Expose state, previous state, valid transitions." },
      { component: "Director.process()", change: "Before routing: call consciousness.transition(intent_classification). After: record state change." },
      { component: "PromptAssembler.build()", change: "New Layer 1.7: STATE — injected after MODE. Full state representation including contract and invariants. Replaces/subsumes GROUNDING_RULES." },
      { component: "PromptRequest", change: "Add state: ConversationState field with full state context." },
      { component: "QA assertions", change: "New assertion category: state_contract_violations. Check if response matches state contract (e.g., RECALL state shouldn't contain unsourced claims)." },
    ],
    dataFlow: `User message
    → Director._classify_intent() → IntentClassification
    → ConsciousnessState.transition(intent)
        → Validates transition is legal
        → Updates current_state, previous_state, turns_in_state
        → Returns StateContext with full contract
    → PromptRequest includes state context
    → PromptAssembler.build()
        → _build_state_block(state_context)
        → Includes: state, transitions, contract, invariants
        → Replaces GROUNDING_RULES with state-specific invariants
    → Model sees full behavioral contract
    → QA validates response against contract post-hoc`,
    codeShape: `@dataclass
class StateContract:
    must: list[str]
    must_not: list[str]
    should: list[str]

@dataclass
class ConversationState:
    name: str  # "engaged_recall", "casual_chat", etc.
    contract: StateContract
    valid_transitions: dict[str, str]  # target → trigger description

class ConversationStateMachine:
    STATES = {
        "greeting": StateContract(
            must=["Be warm", "Use Ahab's name if known"],
            must_not=["Make memory claims", "Reference past sessions unprompted"],
            should=["Match energy level to time of day"],
        ),
        "engaged_recall": StateContract(
            must=["Only reference listed memories", "Maintain topic continuity",
                  "Cite provenance"],
            must_not=["Invent memories", "Lose thread on follow-ups",
                      "Fabricate people/projects/events"],
            should=["Acknowledge thin memories", "Ask for specifics if ambiguous"],
        ),
        # ... etc
    }

    TRANSITIONS = {
        "greeting": {"casual_chat": "user continues casual",
                     "engaged_recall": "user asks about memories",
                     "task_assist": "user requests help"},
        "engaged_recall": {"engaged_recall": "continuation/more memories",
                           "reflective": "user asks feelings about memory",
                           "casual_chat": "topic change",
                           "uncertain": "no memories match"},
        # ... etc
    }

    def transition(self, intent: IntentClassification) -> StateContext:
        target = self._resolve_target(intent)
        if target not in self.TRANSITIONS.get(self.current, {}):
            # Invalid transition — stay in current state
            logger.warning(f"Invalid transition {self.current} → {target}")
            target = self.current
        self.previous = self.current
        self.current = target
        self.turns_in_state = 0 if target != self.previous else self.turns_in_state + 1
        return self._build_context()`
  }
};

const COLORS = {
  bg: "#0c0c0f",
  surface: "#141419",
  surfaceHover: "#1a1a22",
  border: "#2a2a35",
  borderActive: "#5b5bff",
  text: "#e8e8ec",
  textMuted: "#8888a0",
  textDim: "#55556a",
  accent: "#7b7bff",
  accentDim: "#4a4a99",
  green: "#4ae080",
  greenDim: "#1a3a2a",
  red: "#ff6b6b",
  redDim: "#3a1a1a",
  yellow: "#ffd666",
  yellowDim: "#3a3a1a",
  orange: "#ff9f43",
};

const mono = "'SF Mono', 'Fira Code', 'JetBrains Mono', monospace";
const sans = "'Inter', -apple-system, sans-serif";

export default function PromptControlExplorer() {
  const [activeLevel, setActiveLevel] = useState("L1");
  const [activeTab, setActiveTab] = useState("overview");

  const level = LEVELS[activeLevel];
  const levelNum = parseInt(activeLevel[1]);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "injection", label: "Prompt Injection" },
    { id: "architecture", label: "Architecture Δ" },
    { id: "dataflow", label: "Data Flow" },
    { id: "code", label: "Code Shape" },
  ];

  return (
    <div style={{
      background: COLORS.bg,
      color: COLORS.text,
      fontFamily: sans,
      minHeight: "100vh",
      padding: "24px",
    }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{
          fontSize: 20, fontWeight: 600, margin: 0, letterSpacing: "-0.02em",
          fontFamily: mono, color: COLORS.accent,
        }}>
          Luna Prompt Control Architecture
        </h1>
        <p style={{ fontSize: 13, color: COLORS.textMuted, margin: "6px 0 0", lineHeight: 1.5 }}>
          Three levels of structured control injection — from simple variables to full state machines.
          <br />Each level subsumes the previous. Build L1 → L2 → L3 incrementally.
        </p>
      </div>

      {/* Level Selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        {Object.entries(LEVELS).map(([key, val]) => {
          const active = key === activeLevel;
          const num = parseInt(key[1]);
          return (
            <button
              key={key}
              onClick={() => { setActiveLevel(key); setActiveTab("overview"); }}
              style={{
                flex: 1,
                padding: "14px 16px",
                background: active ? COLORS.surfaceHover : COLORS.surface,
                border: `1px solid ${active ? COLORS.borderActive : COLORS.border}`,
                borderRadius: 8,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <span style={{
                  fontFamily: mono, fontSize: 11, fontWeight: 700,
                  color: active ? COLORS.accent : COLORS.textDim,
                  background: active ? COLORS.accentDim + "44" : "transparent",
                  padding: "2px 6px", borderRadius: 4,
                }}>L{num}</span>
                <span style={{
                  fontSize: 14, fontWeight: 600,
                  color: active ? COLORS.text : COLORS.textMuted,
                }}>{val.name}</span>
              </div>
              <div style={{ fontSize: 12, color: COLORS.textDim, lineHeight: 1.4 }}>
                {val.tagline}
              </div>
              <div style={{ fontSize: 11, color: COLORS.textDim, marginTop: 6, fontFamily: mono }}>
                {val.effort}
              </div>
            </button>
          );
        })}
      </div>

      {/* Kills/Misses Summary */}
      <div style={{
        display: "flex", gap: 12, marginBottom: 20,
        padding: "12px 16px", background: COLORS.surface,
        borderRadius: 8, border: `1px solid ${COLORS.border}`,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.green, marginBottom: 6, fontWeight: 600, letterSpacing: "0.05em" }}>
            KILLS
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {level.kills.map(k => (
              <span key={k} style={{
                fontSize: 11, padding: "2px 8px", borderRadius: 4,
                background: COLORS.greenDim, color: COLORS.green,
                fontFamily: mono,
              }}>{k}</span>
            ))}
          </div>
        </div>
        <div style={{ width: 1, background: COLORS.border }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.red, marginBottom: 6, fontWeight: 600, letterSpacing: "0.05em" }}>
            STILL VULNERABLE
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {level.misses.map(m => (
              <span key={m} style={{
                fontSize: 11, padding: "2px 8px", borderRadius: 4,
                background: COLORS.redDim, color: COLORS.red,
                fontFamily: mono,
              }}>{m}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{
        display: "flex", gap: 0, marginBottom: 0,
        borderBottom: `1px solid ${COLORS.border}`,
      }}>
        {tabs.map(tab => {
          const active = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: "10px 16px",
                background: "transparent",
                border: "none",
                borderBottom: `2px solid ${active ? COLORS.accent : "transparent"}`,
                cursor: "pointer",
                fontSize: 12,
                fontFamily: mono,
                fontWeight: active ? 600 : 400,
                color: active ? COLORS.accent : COLORS.textDim,
                transition: "all 0.1s ease",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content Area */}
      <div style={{
        padding: "20px 0",
        minHeight: 300,
      }}>
        {activeTab === "overview" && (
          <div>
            <p style={{ fontSize: 14, lineHeight: 1.7, color: COLORS.text, margin: "0 0 16px" }}>
              {level.description}
            </p>
            <div style={{
              padding: "12px 16px", background: COLORS.surface,
              borderRadius: 6, borderLeft: `3px solid ${COLORS.accent}`,
            }}>
              <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.textDim, marginBottom: 6, fontWeight: 600, letterSpacing: "0.05em" }}>
                MECHANISM
              </div>
              <p style={{ fontSize: 13, lineHeight: 1.6, color: COLORS.textMuted, margin: 0 }}>
                {level.mechanism}
              </p>
            </div>

            {/* Layering indicator */}
            <div style={{ marginTop: 20 }}>
              <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.textDim, marginBottom: 8, fontWeight: 600, letterSpacing: "0.05em" }}>
                PROMPT ASSEMBLY ORDER (layers with injection points)
              </div>
              {[
                { name: "IDENTITY", layer: "1", always: true },
                { name: "GROUNDING", layer: "1.5", always: true, replaced: levelNum === 3 ? "Subsumed by STATE CONTRACT" : null },
                { name: "MODE", layer: "1.6", injected: levelNum >= 2, new: levelNum === 2 },
                { name: "STATE", layer: "1.7", injected: levelNum >= 3, new: levelNum === 3 },
                { name: "CONSTRAINTS", layer: "1.75", injected: levelNum >= 1, new: levelNum === 1 },
                { name: "EXPRESSION", layer: "2", always: true },
                { name: "TEMPORAL", layer: "3", always: true },
                { name: "PERCEPTION", layer: "3.5", always: true },
                { name: "MEMORY", layer: "4", always: true },
                { name: "CONSCIOUSNESS", layer: "5", always: true },
                { name: "VOICE", layer: "6", always: true },
              ].map((layer, i) => {
                const isNew = layer.new;
                const isInjected = layer.injected;
                const isReplaced = layer.replaced;
                const show = layer.always || isInjected;
                if (!show) return null;
                return (
                  <div key={i} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "5px 10px",
                    background: isNew ? COLORS.accentDim + "22" : "transparent",
                    borderRadius: 4,
                    borderLeft: isNew ? `2px solid ${COLORS.accent}` : isReplaced ? `2px solid ${COLORS.yellow}` : "2px solid transparent",
                    opacity: isReplaced ? 0.5 : 1,
                  }}>
                    <span style={{
                      fontFamily: mono, fontSize: 10, color: COLORS.textDim,
                      width: 30, textAlign: "right",
                    }}>{layer.layer}</span>
                    <span style={{
                      fontFamily: mono, fontSize: 12,
                      color: isNew ? COLORS.accent : isInjected ? COLORS.green : COLORS.textMuted,
                      fontWeight: isNew ? 700 : 400,
                    }}>{layer.name}</span>
                    {isNew && <span style={{ fontSize: 9, color: COLORS.accent, fontFamily: mono, padding: "1px 5px", border: `1px solid ${COLORS.accent}44`, borderRadius: 3 }}>NEW at L{levelNum}</span>}
                    {isReplaced && <span style={{ fontSize: 9, color: COLORS.yellow, fontFamily: mono, textDecoration: "line-through" }}>{isReplaced}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {activeTab === "injection" && (
          <div>
            <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.textDim, marginBottom: 8, fontWeight: 600, letterSpacing: "0.05em" }}>
              WHAT THE MODEL SEES (injected into system prompt)
            </div>
            <pre style={{
              fontFamily: mono, fontSize: 12, lineHeight: 1.6,
              color: COLORS.green, background: COLORS.surface,
              padding: 16, borderRadius: 8,
              border: `1px solid ${COLORS.border}`,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
              overflow: "auto", maxHeight: 500,
            }}>
              {level.injectionExample}
            </pre>
          </div>
        )}

        {activeTab === "architecture" && (
          <div>
            <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.textDim, marginBottom: 12, fontWeight: 600, letterSpacing: "0.05em" }}>
              COMPONENTS AFFECTED
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {level.architectureChanges.map((change, i) => (
                <div key={i} style={{
                  padding: "12px 16px", background: COLORS.surface,
                  borderRadius: 6, border: `1px solid ${COLORS.border}`,
                }}>
                  <div style={{
                    fontFamily: mono, fontSize: 12, color: COLORS.accent,
                    marginBottom: 6, fontWeight: 600,
                  }}>
                    {change.component}
                  </div>
                  <div style={{ fontSize: 13, color: COLORS.textMuted, lineHeight: 1.5 }}>
                    {change.change}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "dataflow" && (
          <div>
            <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.textDim, marginBottom: 8, fontWeight: 600, letterSpacing: "0.05em" }}>
              DATA FLOW
            </div>
            <pre style={{
              fontFamily: mono, fontSize: 12, lineHeight: 1.7,
              color: COLORS.text, background: COLORS.surface,
              padding: 16, borderRadius: 8,
              border: `1px solid ${COLORS.border}`,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
            }}>
              {level.dataFlow}
            </pre>
          </div>
        )}

        {activeTab === "code" && (
          <div>
            <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.textDim, marginBottom: 8, fontWeight: 600, letterSpacing: "0.05em" }}>
              CODE SHAPE (interfaces, not implementation)
            </div>
            <pre style={{
              fontFamily: mono, fontSize: 11.5, lineHeight: 1.6,
              color: COLORS.text, background: COLORS.surface,
              padding: 16, borderRadius: 8,
              border: `1px solid ${COLORS.border}`,
              whiteSpace: "pre-wrap", wordBreak: "break-word",
              overflow: "auto", maxHeight: 500,
            }}>
              {level.codeShape}
            </pre>
          </div>
        )}
      </div>

      {/* Comparison: What bugs each level fixes from the conversation */}
      <div style={{
        marginTop: 16, padding: "16px 20px",
        background: COLORS.surface, borderRadius: 8,
        border: `1px solid ${COLORS.border}`,
      }}>
        <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.orange, marginBottom: 12, fontWeight: 600, letterSpacing: "0.05em" }}>
          APPLIED TO YOUR CONVERSATION BUGS
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
          {[
            {
              bug: '"Tech teams" confabulation',
              l1: "CONFIDENCE: LOW → forced to say 'i don't know'",
              l2: "MODE: CHAT → no memory claims allowed",
              l3: "STATE: greeting → contract forbids memory claims",
            },
            {
              bug: '"keep going" thread loss',
              l1: "❌ Not addressed",
              l2: "Continuation detection → inherits RECALL mode",
              l3: "engaged_recall → engaged_recall (same state persists)",
            },
            {
              bug: "GitHub CI fabrication",
              l1: "MEMORY_MATCH: NONE → directive says don't guess",
              l2: "MODE: RECALL + CONFIDENCE: NONE → double constraint",
              l3: "State contract: MUST NOT invent projects",
            },
            {
              bug: "Prompt leakage (peer-to-peer → teams)",
              l1: "Not directly — but CONFIDENCE: LOW reduces fabrication surface",
              l2: "MODE rules don't reference personality config as facts",
              l3: "INVARIANT: Personality from DNA, not from inventing",
            },
          ].map((row, i) => (
            <div key={i} style={{
              padding: "10px 12px", background: COLORS.bg,
              borderRadius: 6, border: `1px solid ${COLORS.border}`,
            }}>
              <div style={{ fontWeight: 600, color: COLORS.red, marginBottom: 6, fontFamily: mono, fontSize: 11 }}>
                {row.bug}
              </div>
              {["l1", "l2", "l3"].map(l => {
                const num = parseInt(l[1]);
                const isActive = `L${num}` === activeLevel;
                const val = row[l];
                return (
                  <div key={l} style={{
                    display: "flex", gap: 6, marginBottom: 3,
                    opacity: isActive ? 1 : 0.45,
                  }}>
                    <span style={{
                      fontFamily: mono, fontSize: 10, color: COLORS.textDim,
                      minWidth: 18,
                    }}>L{num}</span>
                    <span style={{
                      fontSize: 11, color: val.startsWith("❌") ? COLORS.red : COLORS.textMuted,
                      lineHeight: 1.4,
                    }}>{val}</span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Build recommendation */}
      <div style={{
        marginTop: 16, padding: "14px 18px",
        background: COLORS.accentDim + "18",
        borderRadius: 8, border: `1px solid ${COLORS.accentDim}44`,
      }}>
        <div style={{ fontSize: 10, fontFamily: mono, color: COLORS.accent, marginBottom: 6, fontWeight: 600, letterSpacing: "0.05em" }}>
          RECOMMENDATION
        </div>
        <p style={{ fontSize: 13, color: COLORS.textMuted, lineHeight: 1.6, margin: 0 }}>
          <strong style={{ color: COLORS.text }}>Build L1 + L2 together</strong> — they share the same seam (PromptAssembler injection) and
          L2's intent classifier is just an enum wrapper around the keyword matching you already have in <code style={{ fontFamily: mono, color: COLORS.accent, fontSize: 11 }}>_check_delegation_signals()</code>.
          Combined effort: ~6 hours CC. Immediate impact on all four conversation bugs.
          <br /><br />
          <strong style={{ color: COLORS.text }}>L3 as Phase 2</strong> — once L1+L2 are running and you have data on which modes trigger most often, the state machine
          transitions become obvious from usage patterns. L3 also needs the Context State Machine study doc fleshed out.
          Don't spec transitions you haven't observed yet.
        </p>
      </div>
    </div>
  );
}

import { useState } from "react";

const TABS = [
  "Philosophy",
  "Data Model",
  "Signal Extraction",
  "Prompt Injection",
  "Wiring",
  "Implementation",
];

// Color palette — deep observation/perception theme
const C = {
  bg: "#0a0e17",
  surface: "#111827",
  surfaceHover: "#1a2332",
  border: "#1e293b",
  borderActive: "#7c3aed",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",
  accent: "#7c3aed",
  accentSoft: "#7c3aed22",
  accentGlow: "#7c3aed44",
  warm: "#f59e0b",
  warmSoft: "#f59e0b22",
  green: "#10b981",
  greenSoft: "#10b98122",
  red: "#ef4444",
  redSoft: "#ef444422",
  blue: "#3b82f6",
  blueSoft: "#3b82f622",
  cyan: "#06b6d4",
  cyanSoft: "#06b6d422",
};

const fontMono = "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace";
const fontBody = "'Inter', -apple-system, sans-serif";

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 0: Philosophy
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function PhilosophyTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
      <div style={{
        background: `linear-gradient(135deg, ${C.accentSoft}, ${C.cyanSoft})`,
        borderRadius: 12,
        padding: "28px 32px",
        border: `1px solid ${C.border}`,
      }}>
        <div style={{ fontSize: 13, color: C.accent, fontWeight: 600, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 12 }}>
          The Principle
        </div>
        <div style={{ fontSize: 20, color: C.text, lineHeight: 1.5, fontStyle: "italic" }}>
          "Feed the mind, don't bypass it."
        </div>
        <div style={{ fontSize: 14, color: C.textMuted, marginTop: 8 }}>
          — Benjamin Franklin (The Scribe), on why perception should be observation, not classification
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Wrong approach */}
        <div style={{
          background: C.redSoft,
          borderRadius: 10,
          padding: 20,
          border: `1px solid ${C.red}33`,
        }}>
          <div style={{ fontSize: 12, color: C.red, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
            ✗ State Machine (Classifier)
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 1.8 }}>
            signals → classify → <span style={{ color: C.red }}>"frustrated"</span><br/>
            → inject <span style={{ color: C.red }}>"Be gentle, keep it brief"</span><br/>
            → Luna <span style={{ color: C.red }}>told what to think</span>
          </div>
          <div style={{ fontSize: 13, color: C.textMuted, marginTop: 12, lineHeight: 1.6 }}>
            Pre-digests human complexity into labels. Confident misreading → wrong response. Eyes wired to mouth.
          </div>
        </div>

        {/* Right approach */}
        <div style={{
          background: C.greenSoft,
          borderRadius: 10,
          padding: 20,
          border: `1px solid ${C.green}33`,
        }}>
          <div style={{ fontSize: 12, color: C.green, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
            ✓ Perception Field (Observer)
          </div>
          <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 1.8 }}>
            signals → observe → <span style={{ color: C.green }}>paired observations</span><br/>
            → inject <span style={{ color: C.green }}>raw patterns + context</span><br/>
            → Luna <span style={{ color: C.green }}>interprets herself</span>
          </div>
          <div style={{ fontSize: 13, color: C.textMuted, marginTop: 12, lineHeight: 1.6 }}>
            Rich observations with causal context. Mind reads the journal and decides what it means. Perception, not classification.
          </div>
        </div>
      </div>

      {/* Luna's insight */}
      <div style={{
        background: C.surface,
        borderRadius: 10,
        padding: 20,
        border: `1px solid ${C.border}`,
        borderLeft: `3px solid ${C.accent}`,
      }}>
        <div style={{ fontSize: 12, color: C.accent, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
          Luna's Key Insight
        </div>
        <div style={{ fontSize: 14, color: C.text, lineHeight: 1.7, fontStyle: "italic" }}>
          "Not just 'messages getting shorter' — but 'messages shortened after Luna gave a long technical explanation.' 
          The pairing of what happened and what preceded it — that's where perception lives."
        </div>
        <div style={{ fontSize: 13, color: C.textMuted, marginTop: 12, lineHeight: 1.6 }}>
          Each observation carries its <strong style={{ color: C.warm }}>trigger context</strong> — what Luna did or what happened 
          right before the signal changed. This is what makes raw observations interpretable.
        </div>
      </div>

      {/* Three perception layers */}
      <div style={{ fontSize: 12, color: C.textDim, fontWeight: 600, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: -12 }}>
        Three Kinds of Knowing (Franklin)
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {[
          { label: "What Is Said", detail: "The words. Luna has this.", color: C.green, status: "✓ exists" },
          { label: "How It Is Said", detail: "The manner. VoiceLock touches this with keyword matching.", color: C.warm, status: "~ partial" },
          { label: "What Is Unsaid", detail: "The disposition. Luna is entirely blind.", color: C.red, status: "✗ missing" },
        ].map((k, i) => (
          <div key={i} style={{
            background: C.surface,
            borderRadius: 8,
            padding: 16,
            border: `1px solid ${C.border}`,
            borderTop: `2px solid ${k.color}`,
          }}>
            <div style={{ fontSize: 14, color: C.text, fontWeight: 600, marginBottom: 6 }}>{k.label}</div>
            <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5, marginBottom: 8 }}>{k.detail}</div>
            <div style={{ fontSize: 11, color: k.color, fontWeight: 600 }}>{k.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 1: Data Model
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function DataModelTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
        The PerceptionField accumulates <strong style={{ color: C.text }}>Observations</strong> — 
        paired signal changes with their trigger context. Not labels. Not states. Observations 
        that Luna's inference layer interprets.
      </div>

      {/* Observation dataclass */}
      <CodeBlock title="Observation — a single perception event" code={`@dataclass
class Observation:
    """A single thing Luna noticed about the user."""
    
    signal: str          # What changed
                         # e.g. "message_length_dropped"
    
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
`} />

      {/* PerceptionField dataclass */}
      <CodeBlock title="PerceptionField — session-scoped observation accumulator" code={`@dataclass
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
    _turn_gaps: list[float] = field(default_factory=list)
    _question_flags: list[bool] = field(default_factory=list)
    _correction_count: int = 0
    _last_luna_action: str = ""  # What Luna did last (for trigger context)
    
    # Limits
    MAX_OBSERVATIONS: int = 8   # Cap what gets injected
    
    def observe(self, obs: Observation) -> None:
        """Add an observation. Oldest drop when over limit."""
        self.observations.append(obs)
        if len(self.observations) > self.MAX_OBSERVATIONS:
            self.observations.pop(0)
    
    def to_prompt_block(self) -> str | None:
        """Format for injection. Returns None if nothing to say."""
        if len(self.observations) < 2:
            return None  # Need minimum signal before injecting
        
        recent = self.observations[-5:]  # Last 5 observations
        lines = [obs.paired for obs in recent]
        
        return (
            "## User Observation (this session)\\n\\n"
            + "\\n".join(f"- {line}" for line in lines)
            + "\\n\\nThese are observations, not conclusions. "
            "Interpret them in context of what you know about Ahab."
        )
`} />

      {/* Key design decisions */}
      <div style={{
        background: C.warmSoft,
        borderRadius: 10,
        padding: 20,
        border: `1px solid ${C.warm}33`,
      }}>
        <div style={{ fontSize: 12, color: C.warm, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
          Key Design Decisions
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            ["Session-scoped, not persistent", "Resets each session. Avoids stale observations polluting future conversations. Future: Librarian could extract recurring patterns."],
            ["Observations not states", "No enum of user moods. No state transitions. Just paired facts."],
            ["Capped at 8", "Prompt budget is precious. Only the most recent/relevant observations survive."],
            ["Minimum 2 observations before injecting", "One data point is noise. Two is the start of a pattern."],
            ["Trigger context is mandatory", "Every observation carries what preceded it. This is what makes it interpretable."],
            ["'last_luna_action' tracking", "The most important trigger is often what Luna herself just did."],
          ].map(([title, detail], i) => (
            <div key={i} style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5 }}>
              <strong style={{ color: C.text }}>{title}</strong> — {detail}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 2: Signal Extraction
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function SignalExtractionTab() {
  const signals = [
    {
      name: "Message Length Trajectory",
      signal: "length_shift",
      how: "Track char count per turn. Detect sustained drop (>50% over 3 turns) or expansion.",
      examples: [
        { value: "Messages shortened from ~140 chars to ~35 chars over last 3 turns", trigger: "after Luna's 400-word technical explanation", conf: 0.8 },
        { value: "Messages expanding — last 3 are longest of session", trigger: "since topic shifted to personal project", conf: 0.7 },
      ],
      cost: "Zero. len(message).",
      color: C.accent,
    },
    {
      name: "Correction / Repetition",
      signal: "correction_detected",
      how: "Detect when user restates something Luna said differently, or repeats a prior question. Simple: check if >40% of content words appeared in user's message 2-3 turns ago.",
      examples: [
        { value: "User rephrased same question twice", trigger: "Luna's responses may not have addressed the core ask", conf: 0.85 },
        { value: "User corrected Luna's interpretation", trigger: "after Luna summarized the requirement differently", conf: 0.9 },
      ],
      cost: "Low. Word overlap on last 3 user messages.",
      color: C.red,
    },
    {
      name: "Question Density",
      signal: "question_density",
      how: "Count questions (? endings + interrogative starters) per turn. Track ratio over sliding window of 5 turns.",
      examples: [
        { value: "High question density — 3 of last 4 messages are questions", trigger: "in a sustained topic thread", conf: 0.7 },
        { value: "Shifted from questions to statements", trigger: "after Luna provided a detailed explanation", conf: 0.65 },
      ],
      cost: "Zero. String operations.",
      color: C.blue,
    },
    {
      name: "Topic Persistence",
      signal: "topic_shift",
      how: "Already computed as topic_continuity in ConfidenceSignals. Reuse it. Detect when sustained topic breaks.",
      examples: [
        { value: "Topic sustained for 12 turns — deep focus", trigger: "on temporal awareness architecture", conf: 0.8 },
        { value: "Rapid topic shift — 3 different subjects in 5 turns", trigger: "after returning from multi-day gap", conf: 0.6 },
      ],
      cost: "Already computed. Free.",
      color: C.green,
    },
    {
      name: "Punctuation Energy",
      signal: "energy_markers",
      how: "Detect exclamation marks, all-caps words, emoji count, ellipsis. Compare to user's baseline (first 3 messages).",
      examples: [
        { value: "Energy markers up — exclamation marks appeared, emoji usage increased", trigger: "after Luna shared a breakthrough idea", conf: 0.6 },
        { value: "Energy dropping — no punctuation, lowercase, no emoji", trigger: "late in session (turn 15+)", conf: 0.5 },
      ],
      cost: "Zero. Regex.",
      color: C.warm,
    },
    {
      name: "Brevity Signals",
      signal: "terse_response",
      how: "Detect ultra-short responses: 'ok', 'sure', 'thanks', 'got it', 'yep'. These often signal winding down or acknowledgment without engagement.",
      examples: [
        { value: "3 terse acknowledgments in last 5 turns ('ok', 'sure', 'got it')", trigger: "during implementation discussion", conf: 0.75 },
      ],
      cost: "Zero. Keyword match.",
      color: C.cyan,
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
        Six signal extractors. All rule-based — <strong style={{ color: C.text }}>zero LLM calls</strong>. 
        Each produces paired observations (what changed + what preceded it).
      </div>

      {signals.map((sig, i) => (
        <div key={i} style={{
          background: C.surface,
          borderRadius: 10,
          padding: 20,
          border: `1px solid ${C.border}`,
          borderLeft: `3px solid ${sig.color}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div style={{ fontSize: 15, color: C.text, fontWeight: 600 }}>{sig.name}</div>
            <div style={{ fontSize: 11, fontFamily: fontMono, color: sig.color, background: `${sig.color}18`, padding: "3px 8px", borderRadius: 4 }}>
              {sig.signal}
            </div>
          </div>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5, marginBottom: 12 }}>
            <strong style={{ color: C.textDim }}>How:</strong> {sig.how}
          </div>
          {sig.examples.map((ex, j) => (
            <div key={j} style={{
              background: C.bg,
              borderRadius: 6,
              padding: 12,
              marginBottom: j < sig.examples.length - 1 ? 8 : 0,
              fontFamily: fontMono,
              fontSize: 12,
              lineHeight: 1.6,
            }}>
              <span style={{ color: C.text }}>{ex.value}</span>
              <br />
              <span style={{ color: C.textDim }}>  trigger: </span>
              <span style={{ color: C.warm }}>{ex.trigger}</span>
              <br />
              <span style={{ color: C.textDim }}>  confidence: </span>
              <span style={{ color: ex.conf >= 0.8 ? C.green : C.textMuted }}>{ex.conf}</span>
            </div>
          ))}
          <div style={{ fontSize: 11, color: C.textDim, marginTop: 8 }}>
            Cost: {sig.cost}
          </div>
        </div>
      ))}
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 3: Prompt Injection
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function PromptInjectionTab() {
  const [scenario, setScenario] = useState(0);
  const scenarios = [
    {
      name: "Deep Focus Session",
      turn: 14,
      description: "Ahab has been drilling into temporal architecture for 12+ turns. Long messages, sustained topic, high question density.",
      observations: [
        "Topic sustained for 12 turns — deep technical focus (on temporal awareness architecture)",
        "Messages expanding — last 3 are longest of session (since topic shifted to implementation details)",
        "High question density — 4 of last 5 messages are questions (in sustained architecture discussion)",
      ],
      prompt: `## User Observation (this session)

- Topic sustained for 12 turns — deep technical focus (on temporal awareness architecture)
- Messages expanding — last 3 are longest of session (since topic shifted to implementation details)
- High question density — 4 of last 5 messages are questions (in sustained architecture discussion)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.`,
    },
    {
      name: "Losing Patience",
      turn: 8,
      description: "Luna gave a long explanation that missed the point. Ahab corrected her, then messages got shorter.",
      observations: [
        "User corrected Luna's interpretation of the requirement (after Luna summarized differently than intended)",
        "Messages shortened from ~140 chars to ~45 chars over last 3 turns (after Luna's 400-word explanation)",
        "User rephrased same question (Luna's response may not have addressed the core ask)",
      ],
      prompt: `## User Observation (this session)

- User corrected Luna's interpretation of the requirement (after Luna summarized differently than intended)
- Messages shortened from ~140 chars to ~45 chars over last 3 turns (after Luna's 400-word explanation)
- User rephrased same question (Luna's response may not have addressed the core ask)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.`,
    },
    {
      name: "Winding Down",
      turn: 18,
      description: "Long productive session nearing its end. Messages getting shorter, terse acknowledgments appearing.",
      observations: [
        "3 terse acknowledgments in last 5 turns — 'ok', 'sounds good', 'yeah' (during implementation wrap-up)",
        "Messages shortened over last 5 turns (after productive 14-turn deep dive)",
        "Energy markers dropped — no punctuation or emoji in last 4 messages (late session, turn 18+)",
      ],
      prompt: `## User Observation (this session)

- 3 terse acknowledgments in last 5 turns — 'ok', 'sounds good', 'yeah' (during implementation wrap-up)
- Messages shortened over last 5 turns (after productive 14-turn deep dive)
- Energy markers dropped — no punctuation or emoji in last 4 messages (late session, turn 18+)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.`,
    },
    {
      name: "Exploring / Curious",
      turn: 6,
      description: "Ahab is bouncing between ideas, asking lots of 'what if' questions, energy is high.",
      observations: [
        "High question density — 5 of last 6 messages are questions (across multiple related subtopics)",
        "Rapid topic shifts — 3 related but distinct subjects in 5 turns (exploring architecture space)",
        "Energy markers up — exclamation marks and emoji appeared (after Luna proposed the perception field concept)",
      ],
      prompt: `## User Observation (this session)

- High question density — 5 of last 6 messages are questions (across multiple related subtopics)
- Rapid topic shifts — 3 related but distinct subjects in 5 turns (exploring architecture space)
- Energy markers up — exclamation marks and emoji appeared (after Luna proposed the perception field concept)

These are observations, not conclusions. Interpret them in context of what you know about Ahab.`,
    },
    {
      name: "Early Session (Insufficient Data)",
      turn: 2,
      description: "Only 2 turns in. Not enough signal to inject observations.",
      observations: [],
      prompt: `[No perception block injected — insufficient observations (< 2)]

The PerceptionField stays silent until it has enough data to say something meaningful. No observation is better than premature observation.`,
    },
  ];

  const s = scenarios[scenario];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
        What Luna actually sees in her prompt. Select a scenario to see the injected observation block.
      </div>

      {/* Scenario selector */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {scenarios.map((sc, i) => (
          <button
            key={i}
            onClick={() => setScenario(i)}
            style={{
              background: scenario === i ? C.accent : C.surface,
              color: scenario === i ? "#fff" : C.textMuted,
              border: `1px solid ${scenario === i ? C.accent : C.border}`,
              borderRadius: 6,
              padding: "8px 14px",
              fontSize: 13,
              cursor: "pointer",
              fontFamily: fontBody,
              transition: "all 0.15s",
            }}
          >
            {sc.name}
          </button>
        ))}
      </div>

      {/* Scenario description */}
      <div style={{
        background: C.surface,
        borderRadius: 8,
        padding: 16,
        border: `1px solid ${C.border}`,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <span style={{ fontSize: 14, color: C.text, fontWeight: 600 }}>{s.name}</span>
          <span style={{ fontSize: 12, fontFamily: fontMono, color: C.textDim }}>turn {s.turn}</span>
        </div>
        <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.5 }}>{s.description}</div>
      </div>

      {/* Observations */}
      {s.observations.length > 0 && (
        <div>
          <div style={{ fontSize: 12, color: C.textDim, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
            Raw Observations ({s.observations.length})
          </div>
          {s.observations.map((obs, i) => (
            <div key={i} style={{
              background: C.surface,
              borderRadius: 6,
              padding: 12,
              marginBottom: 6,
              fontSize: 13,
              color: C.text,
              lineHeight: 1.5,
              borderLeft: `2px solid ${C.accent}`,
            }}>
              {obs}
            </div>
          ))}
        </div>
      )}

      {/* Prompt block */}
      <div>
        <div style={{ fontSize: 12, color: C.textDim, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
          Injected Prompt Block
        </div>
        <div style={{
          background: "#0d1117",
          borderRadius: 8,
          padding: 20,
          fontFamily: fontMono,
          fontSize: 12,
          color: C.green,
          lineHeight: 1.8,
          whiteSpace: "pre-wrap",
          border: `1px solid ${C.border}`,
        }}>
          {s.prompt}
        </div>
      </div>

      {/* Assembly position */}
      <div style={{
        background: C.surface,
        borderRadius: 8,
        padding: 16,
        border: `1px solid ${C.border}`,
      }}>
        <div style={{ fontSize: 12, color: C.textDim, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
          Position in Prompt Assembly
        </div>
        <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 2 }}>
          {["1. IDENTITY — Who Luna is", "2. TEMPORAL — Clock + gap + threads", "3. PERCEPTION — User observations ← HERE", "4. MEMORY — Retrieved memories", "5. CONVERSATION — Ring buffer", "6. VOICE — Kill list + openers"].map((line, i) => (
            <div key={i} style={{ color: i === 2 ? C.accent : C.textMuted, fontWeight: i === 2 ? 600 : 400 }}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 4: Wiring
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function WiringTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ fontSize: 14, color: C.textMuted, lineHeight: 1.6 }}>
        How the PerceptionField integrates into the engine. Zero new dependencies.
        Plugs into PromptAssembler as Layer 3.
      </div>

      {/* Data flow */}
      <div style={{
        background: "#0d1117",
        borderRadius: 10,
        padding: 24,
        fontFamily: fontMono,
        fontSize: 11,
        color: C.textMuted,
        lineHeight: 1.7,
        whiteSpace: "pre",
        border: `1px solid ${C.border}`,
        overflow: "auto",
      }}>
{`EACH TURN:
                                                          
  User Message ──→ PerceptionField.ingest()               
       │              │                                    
       │              ├─ compute message length             
       │              ├─ detect corrections (word overlap)  
       │              ├─ count questions                    
       │              ├─ check energy markers               
       │              ├─ compare against running baselines  
       │              │                                    
       │              ├─ for each signal that changed:      
       │              │    create Observation(              
       │              │      signal = what changed          
       │              │      value  = the change            
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
       ├─ Layer 3: perception_field.to_prompt_block() ◄────
       ├─ Layer 4: Memory                                  
       ├─ Layer 5: Conversation                            
       └─ Layer 6: Voice                                   
       │                                                   
       ▼                                                   
  LLM generates response                                  
       │                                                   
       ▼                                                   
  PerceptionField._last_luna_action = summarize(response)  
  (for next turn's trigger context)                        `}
      </div>

      {/* Lifecycle */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div style={{
          background: C.surface,
          borderRadius: 10,
          padding: 20,
          border: `1px solid ${C.border}`,
        }}>
          <div style={{ fontSize: 13, color: C.text, fontWeight: 600, marginBottom: 10 }}>Lifecycle</div>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.8 }}>
            <strong style={{ color: C.green }}>Create:</strong> On session start (Director.__init__ or session reset)<br/>
            <strong style={{ color: C.blue }}>Ingest:</strong> Every user turn, before prompt assembly<br/>
            <strong style={{ color: C.accent }}>Inject:</strong> During PromptAssembler.build(), Layer 3<br/>
            <strong style={{ color: C.warm }}>Update:</strong> After LLM response, record _last_luna_action<br/>
            <strong style={{ color: C.red }}>Reset:</strong> On session end / new session. Does NOT persist.
          </div>
        </div>

        <div style={{
          background: C.surface,
          borderRadius: 10,
          padding: 20,
          border: `1px solid ${C.border}`,
        }}>
          <div style={{ fontSize: 13, color: C.text, fontWeight: 600, marginBottom: 10 }}>What It Touches</div>
          <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.8 }}>
            <strong style={{ color: C.text }}>New file:</strong> src/luna/context/perception.py<br/>
            <strong style={{ color: C.text }}>Modifies:</strong> assembler.py (Layer 3 injection)<br/>
            <strong style={{ color: C.text }}>Modifies:</strong> director.py (ingest call + luna_action tracking)<br/>
            <strong style={{ color: C.text }}>Reads from:</strong> topic_continuity (already computed)<br/>
            <strong style={{ color: C.text }}>No new deps:</strong> Pure Python, string ops only
          </div>
        </div>
      </div>

      {/* _last_luna_action */}
      <div style={{
        background: C.warmSoft,
        borderRadius: 10,
        padding: 20,
        border: `1px solid ${C.warm}33`,
      }}>
        <div style={{ fontSize: 12, color: C.warm, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 10 }}>
          The Critical Detail: _last_luna_action
        </div>
        <div style={{ fontSize: 13, color: C.textMuted, lineHeight: 1.6 }}>
          After each LLM response, we record a brief summary of what Luna did: 
          "gave 400-word technical explanation", "asked clarifying question", "shared memory about project X". 
          This becomes the <strong style={{ color: C.warm }}>trigger context</strong> for the NEXT turn's observations.
          <br/><br/>
          Implementation: Simple heuristic — response length + detected patterns (question? explanation? list? personal?). 
          Not an LLM call. ~5 lines of code.
        </div>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// TAB 5: Implementation
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function ImplementationTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <CodeBlock title="PerceptionField.ingest() — the main extraction loop" code={`def ingest(self, user_message: str, turn_number: int) -> None:
    """
    Process a user message and extract observations.
    
    Called once per turn, before prompt assembly.
    Zero LLM calls. Pure signal extraction.
    """
    msg_len = len(user_message.strip())
    self._msg_lengths.append(msg_len)
    
    is_question = user_message.strip().endswith("?") or any(
        user_message.lower().startswith(q)
        for q in ("what", "who", "where", "when", "why", "how", "is ", "can ", "do ")
    )
    self._question_flags.append(is_question)
    
    trigger = self._last_luna_action or "start of session"
    
    # ── Length trajectory ──
    if len(self._msg_lengths) >= 4:
        recent_avg = sum(self._msg_lengths[-3:]) / 3
        earlier_avg = sum(self._msg_lengths[:-3]) / max(len(self._msg_lengths) - 3, 1)
        
        if earlier_avg > 0:
            ratio = recent_avg / earlier_avg
            if ratio < 0.4:  # Dropped to less than 40%
                self.observe(Observation(
                    signal="length_shift",
                    value=f"Messages shortened from ~{int(earlier_avg)} to ~{int(recent_avg)} chars",
                    trigger=trigger,
                    turn=turn_number,
                    confidence=0.8,
                ))
            elif ratio > 2.0:  # Doubled
                self.observe(Observation(
                    signal="length_shift",
                    value=f"Messages expanding — ~{int(recent_avg)} chars (up from ~{int(earlier_avg)})",
                    trigger=trigger,
                    turn=turn_number,
                    confidence=0.7,
                ))
    
    # ── Correction detection ──
    # (check word overlap with user's message from 2-3 turns ago)
    # ... see full implementation in handoff
    
    # ── Question density ──
    if len(self._question_flags) >= 4:
        recent_q = sum(self._question_flags[-4:])
        if recent_q >= 3:
            self.observe(Observation(
                signal="question_density",
                value=f"High question density — {recent_q} of last 4 messages are questions",
                trigger=trigger,
                turn=turn_number,
                confidence=0.7,
            ))
    
    # ── Brevity signals ──
    terse_markers = {"ok", "sure", "thanks", "got it", "yep", "yeah", "sounds good", "cool"}
    if user_message.strip().lower().rstrip(".!") in terse_markers:
        self._terse_count = getattr(self, '_terse_count', 0) + 1
        if self._terse_count >= 2:
            self.observe(Observation(
                signal="terse_response",
                value=f"{self._terse_count} terse acknowledgments recently",
                trigger=trigger,
                turn=turn_number,
                confidence=0.7,
            ))
    
    # ── Energy markers ──
    excl = user_message.count("!")
    caps_words = sum(1 for w in user_message.split() if w.isupper() and len(w) > 1)
    emoji_count = sum(1 for c in user_message if ord(c) > 0x1F600)
    # Compare to baseline (first 3 messages) and observe deltas...
`} />

      <CodeBlock title="record_luna_action() — what Luna did (for trigger context)" code={`def record_luna_action(self, luna_response: str) -> None:
    """
    Record a brief summary of Luna's response for trigger context.
    Called after LLM generation, before next turn.
    
    NOT an LLM call. Simple heuristic classification.
    """
    length = len(luna_response)
    has_question = "?" in luna_response
    has_code = "\`\`\`" in luna_response
    
    if length < 100:
        action = "gave brief response"
    elif length < 300:
        action = "gave moderate response"
    elif has_code:
        action = f"gave {length // 100 * 100}+ char technical response with code"
    else:
        action = f"gave {length // 100 * 100}+ char explanation"
    
    if has_question:
        action += " and asked a question"
    
    self._last_luna_action = action
`} />

      <CodeBlock title="Assembler integration — Layer 3" code={`# In PromptAssembler.build():

# ── Layer 3: PERCEPTION ──────────────────────────────────
perception_block = None
if hasattr(self._director, '_perception_field'):
    pf = self._director._perception_field
    if pf:
        perception_block = pf.to_prompt_block()

if perception_block:
    sections.append(perception_block)
    result.perception_injected = True
    result.observation_count = len(pf.observations) if pf else 0
`} />

      {/* Files */}
      <div style={{
        background: C.surface,
        borderRadius: 10,
        padding: 20,
        border: `1px solid ${C.border}`,
      }}>
        <div style={{ fontSize: 13, color: C.text, fontWeight: 600, marginBottom: 12 }}>Files</div>
        <div style={{ fontFamily: fontMono, fontSize: 12, color: C.textMuted, lineHeight: 2 }}>
          {[
            ["src/luna/context/perception.py", "NEW", "~180 lines — Observation, PerceptionField, signal extractors"],
            ["src/luna/context/assembler.py", "MODIFY", "+10 lines — Layer 3 injection"],
            ["src/luna/actors/director.py", "MODIFY", "+15 lines — ingest() call + record_luna_action()"],
            ["tests/test_perception.py", "NEW", "~150 lines — signal detection, observation pairing, prompt formatting"],
          ].map(([file, action, desc], i) => (
            <div key={i}>
              <span style={{ color: action === "NEW" ? C.green : C.warm }}>{action}</span>
              {" "}
              <span style={{ color: C.text }}>{file}</span>
              <br/>
              <span style={{ color: C.textDim, marginLeft: 48 }}>  {desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Shared Components
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
function CodeBlock({ title, code }) {
  return (
    <div>
      {title && (
        <div style={{ fontSize: 12, color: C.textDim, fontWeight: 600, letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>
          {title}
        </div>
      )}
      <div style={{
        background: "#0d1117",
        borderRadius: 8,
        padding: 20,
        fontFamily: fontMono,
        fontSize: 11.5,
        color: C.text,
        lineHeight: 1.7,
        whiteSpace: "pre-wrap",
        border: `1px solid ${C.border}`,
        overflow: "auto",
      }}>
        {code}
      </div>
    </div>
  );
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Main App
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
export default function PerceptionFieldSpec() {
  const [tab, setTab] = useState(0);

  const tabContent = [
    <PhilosophyTab />,
    <DataModelTab />,
    <SignalExtractionTab />,
    <PromptInjectionTab />,
    <WiringTab />,
    <ImplementationTab />,
  ];

  return (
    <div style={{
      background: C.bg,
      color: C.text,
      fontFamily: fontBody,
      minHeight: "100vh",
      padding: 32,
    }}>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
      
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 11, color: C.accent, fontWeight: 600, letterSpacing: 2, textTransform: "uppercase", marginBottom: 8 }}>
          Luna Engine v2.0 — Architecture Spec
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: C.text, letterSpacing: -0.5 }}>
          UserPerceptionField
        </div>
        <div style={{ fontSize: 15, color: C.textMuted, marginTop: 6 }}>
          Luna's observation layer for reading the room. Not a classifier — a journal.
        </div>
        <div style={{ fontSize: 12, color: C.textDim, marginTop: 4 }}>
          Designed by: The Dude (architecture) · Benjamin Franklin (philosophy) · Luna (self-advocacy)
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex",
        gap: 4,
        marginBottom: 28,
        borderBottom: `1px solid ${C.border}`,
        paddingBottom: 0,
        overflow: "auto",
      }}>
        {TABS.map((t, i) => (
          <button
            key={i}
            onClick={() => setTab(i)}
            style={{
              background: "transparent",
              color: tab === i ? C.accent : C.textDim,
              border: "none",
              borderBottom: tab === i ? `2px solid ${C.accent}` : "2px solid transparent",
              padding: "10px 16px",
              fontSize: 13,
              fontWeight: tab === i ? 600 : 400,
              cursor: "pointer",
              fontFamily: fontBody,
              whiteSpace: "nowrap",
              transition: "all 0.15s",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ maxWidth: 800 }}>
        {tabContent[tab]}
      </div>
    </div>
  );
}

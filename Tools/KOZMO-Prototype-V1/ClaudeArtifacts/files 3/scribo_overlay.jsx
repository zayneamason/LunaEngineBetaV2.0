import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ============================================================================
// KOZMO SCRIBO — Annotation Overlay System
// Smart grid with anchor points for notes, comments, agent tasks, actions
// Bridges SCRIBO → LAB for media production planning
// ============================================================================

// --- Scene Content (Part One: The Departure) ---
const PARAGRAPHS = [
  {
    id: "p1",
    type: "title",
    text: "THE DINOSAUR, THE WIZARD, AND THE MOTHER",
  },
  {
    id: "p2",
    type: "section",
    text: "PART ONE: THE DEPARTURE",
  },
  {
    id: "p3",
    type: "prose",
    text: `Cornelius was not, by nature, a creature of haste. He had spent forty-three years cultivating deliberation—the careful placement of each claw, the measured cadence of his speech, the studied pause before commitment. It was a dignity he had earned through sheer force of will, the way a man might insist on wearing a waistcoat in the jungle. And it had served him well, or so he'd believed, until the morning Mordecai didn't return.`,
    entities: [
      { name: "Cornelius", color: "#4ade80", start: 0, end: 9 },
      { name: "Mordecai", color: "#a78bfa", start: 389, end: 397 },
    ],
  },
  {
    id: "p4",
    type: "prose",
    text: `They had lived together for seven years in the cottage at Blackstone Hollow—a modest arrangement for creatures of their respective strangeness. Mordecai, a wizard of middling talent and extraordinary appetites, had found in Cornelius a listener of uncommon patience. And Cornelius, who had spent the first thirty-six years of his life in servitude to a woman incapable of gratitude, had found in Mordecai something he'd never possessed: a friend.`,
    entities: [
      { name: "Blackstone Hollow", color: "#38bdf8", start: 58, end: 74 },
      { name: "Mordecai", color: "#a78bfa", start: 147, end: 155 },
      { name: "Cornelius", color: "#4ade80", start: 252, end: 261 },
      { name: "Cornelius", color: "#4ade80", start: 267, end: 276 },
      { name: "Mordecai", color: "#a78bfa", start: 410, end: 418 },
    ],
  },
  {
    id: "p5",
    type: "prose",
    text: `The cottage suited them both. Mordecai kept his study cluttered with grimoires and bottles—the bottles increasingly outnumbering the books in recent months. Cornelius maintained the garden, read voraciously, and composed letters he never sent to his mother. It was a life of quiet companionship, the sort that asks nothing of the world except to be left alone.`,
    entities: [
      { name: "Mordecai", color: "#a78bfa", start: 30, end: 38 },
      { name: "Cornelius", color: "#4ade80", start: 161, end: 170 },
    ],
  },
  {
    id: "p6",
    type: "prose",
    text: `But Mordecai had not come home. Not that night, nor the next morning, nor the morning after that. Cornelius had waited with the patience of stone, which is to say: the kind that cracks when you aren't looking. On the third day, he rose from his chair by the window, folded the letter he would never send, and stepped outside.`,
    entities: [
      { name: "Mordecai", color: "#a78bfa", start: 4, end: 12 },
      { name: "Cornelius", color: "#4ade80", start: 99, end: 108 },
    ],
  },
  {
    id: "p7",
    type: "prose",
    text: `The road north was not kind to creatures of his size. Every low branch a negotiation, every narrow bridge an argument he won only through stubbornness. He carried nothing except a leather satchel—Mordecai's, left behind—and the quiet certainty that something had gone terribly wrong.`,
    entities: [
      { name: "Mordecai", color: "#a78bfa", start: 175, end: 183 },
    ],
  },
  {
    id: "p8",
    type: "prose",
    text: `He did not know where Mordecai had gone. He knew only that the bottles had been empty for a week before the disappearance, and that Mordecai's hands had been shaking, and that the last thing Mordecai had said to him was: "Don't follow me, old man." Which, naturally, meant that Cornelius would.`,
    entities: [
      { name: "Mordecai", color: "#a78bfa", start: 22, end: 30 },
      { name: "Mordecai", color: "#a78bfa", start: 131, end: 139 },
      { name: "Mordecai", color: "#a78bfa", start: 172, end: 180 },
      { name: "Cornelius", color: "#4ade80", start: 283, end: 292 },
    ],
  },
];

// --- Annotation Types ---
const ANNOTATION_TYPES = {
  note: { icon: "✎", label: "Note", color: "#fbbf24", bg: "rgba(251, 191, 36, 0.08)", border: "rgba(251, 191, 36, 0.25)" },
  comment: { icon: "💬", label: "Comment", color: "#818cf8", bg: "rgba(129, 140, 248, 0.08)", border: "rgba(129, 140, 248, 0.25)" },
  continuity: { icon: "⚠", label: "Continuity", color: "#f87171", bg: "rgba(248, 113, 113, 0.08)", border: "rgba(248, 113, 113, 0.25)" },
  agent: { icon: "◈", label: "Agent Task", color: "#34d399", bg: "rgba(52, 211, 153, 0.08)", border: "rgba(52, 211, 153, 0.25)" },
  action: { icon: "▶", label: "LAB Action", color: "#c084fc", bg: "rgba(192, 132, 252, 0.08)", border: "rgba(192, 132, 252, 0.25)" },
  luna: { icon: "☾", label: "Luna", color: "#c084fc", bg: "rgba(192, 132, 252, 0.06)", border: "rgba(192, 132, 252, 0.2)" },
};

// --- Existing Annotations ---
const INITIAL_ANNOTATIONS = [
  {
    id: "a1", paragraphId: "p3", type: "luna",
    author: "Luna", time: "2:14 PM",
    text: "Opening paragraph establishes Cornelius's core trait (deliberation) and immediately breaks it. The waistcoat metaphor is doing double duty — dignity AND absurdity. Strong.",
    highlight: { start: 168, end: 280 },
    resolved: false,
  },
  {
    id: "a2", paragraphId: "p3", type: "continuity",
    author: "Luna", time: "2:15 PM",
    text: "\"Forty-three years\" — confirm this against Cornelius's CODEX entry. His age is listed as 'Ancient' which is vague. Pin this number down or make it consistent.",
    highlight: { start: 38, end: 56 },
    resolved: false,
  },
  {
    id: "a3", paragraphId: "p4", type: "action",
    author: "Ahab", time: "2:20 PM",
    text: "Need establishing shot of Blackstone Hollow. Cottage surrounded by overgrown garden, stone walls, morning mist. Cornelius-scale doorframe.",
    highlight: { start: 58, end: 74 },
    resolved: false,
    labAction: {
      type: "generate_image",
      status: "queued",
      prompt: "Establishing wide shot, stone cottage at Blackstone Hollow, overgrown garden, morning mist, oversized doorframe for a dinosaur, fantasy realism",
      entity: "blackstone_hollow",
      assignee: "Maya",
    },
  },
  {
    id: "a4", paragraphId: "p5", type: "note",
    author: "Ahab", time: "2:22 PM",
    text: "The bottles outnumbering books — this is the addiction creeping in visually. Camera should linger on this detail in the LAB shot. Close-up, shallow DOF, Cooke S7/i warmth.",
    resolved: false,
  },
  {
    id: "a5", paragraphId: "p5", type: "agent",
    author: "Ahab", time: "2:24 PM",
    text: "Maya: reference art for Cornelius in the garden. Gentle, morning light. He's at peace here — this is the 'before' image.",
    resolved: false,
    agentTask: {
      agent: "Maya",
      status: "pending",
      action: "generate_reference",
      entity: "cornelius",
    },
  },
  {
    id: "a6", paragraphId: "p6", type: "comment",
    author: "Ahab", time: "2:28 PM",
    text: "\"Patience of stone, which is to say: the kind that cracks when you aren't looking\" — this is maybe my favorite line. Cornelius's whole character in one metaphor.",
    resolved: false,
  },
  {
    id: "a7", paragraphId: "p7", type: "action",
    author: "Ahab", time: "2:31 PM",
    text: "The road north sequence needs 3-4 shots. Low branches, narrow bridges, Cornelius navigating a world not built for him. Montage energy.",
    resolved: false,
    labAction: {
      type: "shot_sequence",
      status: "planning",
      shots: [
        "Cornelius ducking under low branch, forest path, dappled light",
        "Narrow stone bridge, Cornelius testing it with one foot, river below",
        "Wide shot, vast landscape, tiny Cornelius on the road — scale",
        "Close-up: Mordecai's leather satchel bouncing on Cornelius's hip",
      ],
      assignee: "Chiba",
    },
  },
  {
    id: "a8", paragraphId: "p8", type: "luna",
    author: "Luna", time: "2:33 PM",
    text: "\"Don't follow me, old man.\" — This is the inciting line. It should echo in Act III when Mordecai says the opposite. Track this for the callback. Filed under ECHO patterns.",
    resolved: false,
  },
];

// --- Overlay Visibility Modes ---
const OVERLAY_MODES = [
  { id: "off", label: "OFF", icon: "○" },
  { id: "pins", label: "PINS", icon: "◉" },
  { id: "full", label: "FULL", icon: "◈" },
];

// --- Action Status ---
const ACTION_STATUS = {
  queued: { color: "#fbbf24", label: "Queued" },
  pending: { color: "#818cf8", label: "Pending" },
  planning: { color: "#c084fc", label: "Planning" },
  generating: { color: "#34d399", label: "Generating" },
  review: { color: "#38bdf8", label: "Review" },
  complete: { color: "#4ade80", label: "Complete" },
};

// ============================================================================
// Components
// ============================================================================

// --- Gutter Pin ---
function GutterPin({ count, types, onClick, isActive }) {
  const primaryType = types[0];
  const config = ANNOTATION_TYPES[primaryType] || ANNOTATION_TYPES.note;
  const hasAction = types.includes("action");
  const hasContinuity = types.includes("continuity");

  return (
    <div
      onClick={onClick}
      style={{
        position: "relative",
        width: 20, height: 20,
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer", borderRadius: 4,
        background: isActive ? config.bg : "transparent",
        border: `1px solid ${isActive ? config.border : "transparent"}`,
        transition: "all 0.15s ease",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.background = config.bg;
        e.currentTarget.style.borderColor = config.border;
      }}
      onMouseLeave={e => {
        if (!isActive) {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.borderColor = "transparent";
        }
      }}
    >
      <span style={{ fontSize: 10, color: config.color }}>{config.icon}</span>
      {count > 1 && (
        <span style={{
          position: "absolute", top: -4, right: -4,
          width: 12, height: 12, borderRadius: "50%",
          background: hasContinuity ? "#f87171" : hasAction ? "#c084fc" : config.color,
          color: "#0a0a0f", fontSize: 7, fontWeight: 700,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          {count}
        </span>
      )}
    </div>
  );
}

// --- Annotation Card ---
function AnnotationCard({ annotation, onResolve, onDelete, compact = false }) {
  const config = ANNOTATION_TYPES[annotation.type] || ANNOTATION_TYPES.note;
  const [expanded, setExpanded] = useState(!compact);

  return (
    <div style={{
      borderLeft: `2px solid ${config.color}`,
      borderRadius: "0 6px 6px 0",
      background: config.bg,
      marginBottom: 6,
      overflow: "hidden",
      opacity: annotation.resolved ? 0.5 : 1,
      transition: "all 0.2s ease",
    }}>
      {/* Header */}
      <div
        onClick={() => compact && setExpanded(!expanded)}
        style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "6px 10px",
          cursor: compact ? "pointer" : "default",
        }}
      >
        <span style={{ color: config.color, fontSize: 11 }}>{config.icon}</span>
        <span style={{
          color: config.color, fontSize: 9,
          fontFamily: "'JetBrains Mono', monospace",
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>
          {config.label}
        </span>
        <span style={{ color: "#2a2a3a", fontSize: 9 }}>·</span>
        <span style={{
          color: "#4a4a5a", fontSize: 10,
          fontFamily: "'Space Grotesk', sans-serif",
        }}>
          {annotation.author}
        </span>
        <span style={{ color: "#2a2a3a", fontSize: 9, marginLeft: "auto" }}>
          {annotation.time}
        </span>
        {compact && (
          <span style={{ color: "#2a2a3a", fontSize: 10 }}>
            {expanded ? "▾" : "▸"}
          </span>
        )}
      </div>

      {/* Body */}
      {(!compact || expanded) && (
        <div style={{ padding: "0 10px 8px" }}>
          <div style={{
            color: "#cbd5e1", fontSize: 12, lineHeight: 1.6,
            fontFamily: "'Space Grotesk', sans-serif",
          }}>
            {annotation.text}
          </div>

          {/* LAB Action */}
          {annotation.labAction && (
            <div style={{
              marginTop: 8, padding: "8px 10px",
              background: "rgba(192, 132, 252, 0.06)",
              borderRadius: 4, border: "1px solid rgba(192, 132, 252, 0.15)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                <span style={{
                  color: "#c084fc", fontSize: 9,
                  fontFamily: "'JetBrains Mono', monospace",
                  textTransform: "uppercase",
                }}>
                  ▶ LAB ACTION
                </span>
                <span style={{
                  color: ACTION_STATUS[annotation.labAction.status]?.color || "#64748b",
                  fontSize: 9, padding: "1px 6px", borderRadius: 3,
                  background: `${ACTION_STATUS[annotation.labAction.status]?.color || "#64748b"}15`,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {annotation.labAction.status}
                </span>
                {annotation.labAction.assignee && (
                  <span style={{ color: "#34d399", fontSize: 9, marginLeft: "auto" }}>
                    → {annotation.labAction.assignee}
                  </span>
                )}
              </div>
              {annotation.labAction.prompt && (
                <div style={{
                  color: "#94a3b8", fontSize: 11, fontStyle: "italic",
                  padding: "4px 8px", background: "rgba(0,0,0,0.2)", borderRadius: 3,
                }}>
                  {annotation.labAction.prompt}
                </div>
              )}
              {annotation.labAction.shots && (
                <div style={{ marginTop: 4 }}>
                  {annotation.labAction.shots.map((shot, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "flex-start", gap: 6,
                      padding: "3px 0", color: "#94a3b8", fontSize: 11,
                    }}>
                      <span style={{
                        color: "#c084fc", fontSize: 9, marginTop: 2,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span>{shot}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Agent Task */}
          {annotation.agentTask && (
            <div style={{
              marginTop: 8, padding: "6px 10px",
              background: "rgba(52, 211, 153, 0.06)",
              borderRadius: 4, border: "1px solid rgba(52, 211, 153, 0.15)",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span style={{ color: "#34d399", fontSize: 10 }}>◈</span>
              <span style={{
                color: "#34d399", fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {annotation.agentTask.agent}
              </span>
              <span style={{ color: "#4a4a5a", fontSize: 10 }}>
                {annotation.agentTask.action}
              </span>
              <span style={{
                marginLeft: "auto",
                color: ACTION_STATUS[annotation.agentTask.status]?.color || "#64748b",
                fontSize: 9, padding: "1px 6px", borderRadius: 3,
                background: `${ACTION_STATUS[annotation.agentTask.status]?.color || "#64748b"}15`,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {annotation.agentTask.status}
              </span>
            </div>
          )}

          {/* Actions row */}
          <div style={{
            display: "flex", gap: 8, marginTop: 8, alignItems: "center",
          }}>
            <button
              onClick={() => onResolve?.(annotation.id)}
              style={{
                padding: "2px 8px", borderRadius: 3, border: "1px solid #1e1e2e",
                background: "transparent", color: "#4a4a5a", fontSize: 9,
                cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "#4ade80"; e.currentTarget.style.color = "#4ade80"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "#1e1e2e"; e.currentTarget.style.color = "#4a4a5a"; }}
            >
              {annotation.resolved ? "↩ reopen" : "✓ resolve"}
            </button>
            {annotation.labAction && (
              <button style={{
                padding: "2px 8px", borderRadius: 3,
                border: "1px solid rgba(192, 132, 252, 0.3)",
                background: "rgba(192, 132, 252, 0.08)",
                color: "#c084fc", fontSize: 9, cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                → send to LAB
              </button>
            )}
            {annotation.agentTask && (
              <button style={{
                padding: "2px 8px", borderRadius: 3,
                border: "1px solid rgba(52, 211, 153, 0.3)",
                background: "rgba(52, 211, 153, 0.08)",
                color: "#34d399", fontSize: 9, cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                ◈ dispatch
              </button>
            )}
            <button
              onClick={() => onDelete?.(annotation.id)}
              style={{
                padding: "2px 6px", borderRadius: 3, border: "none",
                background: "transparent", color: "#2a2a3a", fontSize: 9,
                cursor: "pointer", marginLeft: "auto",
              }}
              onMouseEnter={e => e.currentTarget.style.color = "#f87171"}
              onMouseLeave={e => e.currentTarget.style.color = "#2a2a3a"}
            >
              ×
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// --- New Annotation Creator ---
function AnnotationCreator({ paragraphId, onAdd, onCancel }) {
  const [type, setType] = useState("note");
  const [text, setText] = useState("");
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const handleSubmit = () => {
    if (!text.trim()) return;
    onAdd({
      id: "a" + Date.now(),
      paragraphId,
      type,
      author: type === "luna" ? "Luna" : "Ahab",
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      text: text.trim(),
      resolved: false,
      ...(type === "action" ? {
        labAction: { type: "generate_image", status: "planning", prompt: text.trim(), assignee: "Maya" }
      } : {}),
      ...(type === "agent" ? {
        agentTask: { agent: "Maya", status: "pending", action: "generate_reference" }
      } : {}),
    });
    setText("");
    onCancel();
  };

  return (
    <div style={{
      background: "rgba(18, 18, 26, 0.95)", borderRadius: 6,
      border: "1px solid #1e1e2e", padding: 10, marginBottom: 6,
      backdropFilter: "blur(12px)",
    }}>
      {/* Type selector */}
      <div style={{ display: "flex", gap: 3, marginBottom: 8, flexWrap: "wrap" }}>
        {Object.entries(ANNOTATION_TYPES).map(([key, cfg]) => (
          <button
            key={key}
            onClick={() => setType(key)}
            style={{
              padding: "3px 8px", borderRadius: 3,
              border: `1px solid ${type === key ? cfg.color + "60" : "#1e1e2e"}`,
              background: type === key ? cfg.bg : "transparent",
              color: type === key ? cfg.color : "#4a4a5a",
              fontSize: 9, cursor: "pointer",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {cfg.icon} {cfg.label}
          </button>
        ))}
      </div>

      {/* Text input */}
      <textarea
        ref={inputRef}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === "Enter" && e.metaKey) handleSubmit(); if (e.key === "Escape") onCancel(); }}
        placeholder={
          type === "action" ? "Describe the LAB action (image, shot sequence, etc.)..."
          : type === "agent" ? "Describe the agent task..."
          : type === "continuity" ? "Describe the continuity issue..."
          : "Write your note..."
        }
        style={{
          width: "100%", minHeight: 60, padding: 8, borderRadius: 4,
          background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
          color: "#e2e8f0", fontSize: 12, resize: "vertical",
          fontFamily: "'Space Grotesk', sans-serif",
          outline: "none", lineHeight: 1.5,
        }}
        onFocus={e => e.currentTarget.style.borderColor = ANNOTATION_TYPES[type].color + "40"}
        onBlur={e => e.currentTarget.style.borderColor = "#1e1e2e"}
      />

      {/* Buttons */}
      <div style={{ display: "flex", gap: 6, marginTop: 6, justifyContent: "flex-end" }}>
        <button onClick={onCancel} style={{
          padding: "4px 10px", borderRadius: 4, border: "1px solid #1e1e2e",
          background: "transparent", color: "#4a4a5a", fontSize: 11, cursor: "pointer",
        }}>
          Cancel
        </button>
        <button onClick={handleSubmit} style={{
          padding: "4px 12px", borderRadius: 4, border: "none",
          background: text.trim() ? ANNOTATION_TYPES[type].color + "20" : "#1e1e2e",
          color: text.trim() ? ANNOTATION_TYPES[type].color : "#2a2a3a",
          fontSize: 11, cursor: text.trim() ? "pointer" : "default",
          fontFamily: "'Space Grotesk', sans-serif",
        }}>
          Add {ANNOTATION_TYPES[type].label} ⌘↵
        </button>
      </div>
    </div>
  );
}

// --- Action Plan Sidebar ---
function ActionPlan({ annotations, onJump }) {
  const actions = annotations.filter(a => a.labAction || a.agentTask);
  const notes = annotations.filter(a => a.type === "note" || a.type === "comment");
  const issues = annotations.filter(a => a.type === "continuity");
  const lunaInsights = annotations.filter(a => a.type === "luna");
  const unresolved = annotations.filter(a => !a.resolved);

  const [tab, setTab] = useState("actions");

  const tabItems = [
    { id: "actions", label: "Actions", count: actions.length, color: "#c084fc" },
    { id: "issues", label: "Issues", count: issues.length, color: "#f87171" },
    { id: "notes", label: "Notes", count: notes.length, color: "#fbbf24" },
    { id: "luna", label: "Luna", count: lunaInsights.length, color: "#c084fc" },
  ];

  const currentList = tab === "actions" ? actions
    : tab === "issues" ? issues
    : tab === "notes" ? notes
    : lunaInsights;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Summary */}
      <div style={{
        padding: "10px 12px", borderBottom: "1px solid #1e1e2e",
      }}>
        <div style={{
          fontSize: 10, color: "#4a4a5a",
          fontFamily: "'JetBrains Mono', monospace",
          textTransform: "uppercase", letterSpacing: "0.08em",
          marginBottom: 8,
        }}>
          Overlay Summary
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
          <div style={{ padding: "4px 8px", borderRadius: 3, background: "rgba(18, 18, 26, 0.5)" }}>
            <div style={{ color: "#2a2a3a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>Total</div>
            <div style={{ color: "#e2e8f0", fontSize: 16, fontWeight: 500 }}>{annotations.length}</div>
          </div>
          <div style={{ padding: "4px 8px", borderRadius: 3, background: "rgba(18, 18, 26, 0.5)" }}>
            <div style={{ color: "#2a2a3a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>Open</div>
            <div style={{ color: "#fbbf24", fontSize: 16, fontWeight: 500 }}>{unresolved.length}</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", padding: "6px 8px", gap: 2,
        borderBottom: "1px solid #1e1e2e",
      }}>
        {tabItems.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1, padding: "4px 4px", borderRadius: 3, border: "none",
              background: tab === t.id ? t.color + "15" : "transparent",
              color: tab === t.id ? t.color : "#4a4a5a",
              fontSize: 9, cursor: "pointer",
              fontFamily: "'JetBrains Mono', monospace",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 3,
            }}
          >
            {t.label}
            <span style={{
              background: tab === t.id ? t.color + "25" : "#1e1e2e",
              color: tab === t.id ? t.color : "#2a2a3a",
              padding: "0 4px", borderRadius: 2, fontSize: 8,
            }}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {/* List */}
      <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
        {currentList.length === 0 ? (
          <div style={{ color: "#2a2a3a", fontSize: 11, textAlign: "center", paddingTop: 24 }}>
            No {tab} yet
          </div>
        ) : currentList.map(ann => (
          <div
            key={ann.id}
            onClick={() => onJump?.(ann.paragraphId)}
            style={{ cursor: "pointer" }}
          >
            <AnnotationCard annotation={ann} compact={true} />
          </div>
        ))}
      </div>

      {/* Batch actions */}
      {tab === "actions" && actions.length > 0 && (
        <div style={{
          padding: "8px 12px", borderTop: "1px solid #1e1e2e",
          display: "flex", gap: 6,
        }}>
          <button style={{
            flex: 1, padding: "6px 10px", borderRadius: 4, border: "none",
            background: "rgba(192, 132, 252, 0.12)",
            color: "#c084fc", fontSize: 11, cursor: "pointer",
            fontFamily: "'Space Grotesk', sans-serif",
          }}>
            → Send All to LAB
          </button>
          <button style={{
            padding: "6px 10px", borderRadius: 4, border: "none",
            background: "rgba(52, 211, 153, 0.12)",
            color: "#34d399", fontSize: 11, cursor: "pointer",
            fontFamily: "'Space Grotesk', sans-serif",
          }}>
            ◈ Dispatch
          </button>
        </div>
      )}
    </div>
  );
}


// --- Paragraph with overlay ---
function AnnotatedParagraph({
  paragraph, annotations, overlayMode, activeParagraph,
  onPinClick, onAddAnnotation, isCreating, onCancelCreate,
  onResolve, onDelete,
}) {
  const paraAnnotations = annotations.filter(a => a.paragraphId === paragraph.id);
  const isActive = activeParagraph === paragraph.id;

  // Render text with entity highlights
  const renderText = (text, entities) => {
    if (!entities || entities.length === 0) return text;

    const sorted = [...entities].sort((a, b) => a.start - b.start);
    const parts = [];
    let lastEnd = 0;

    sorted.forEach((ent, i) => {
      if (ent.start > lastEnd) {
        parts.push(<span key={`t${i}`}>{text.slice(lastEnd, ent.start)}</span>);
      }
      parts.push(
        <span key={`e${i}`} style={{
          color: ent.color,
          textDecoration: "underline",
          textDecorationColor: ent.color + "40",
          textUnderlineOffset: "3px",
          cursor: "pointer",
        }}>
          {text.slice(ent.start, ent.end)}
        </span>
      );
      lastEnd = ent.end;
    });
    if (lastEnd < text.length) {
      parts.push(<span key="last">{text.slice(lastEnd)}</span>);
    }
    return parts;
  };

  const textStyle = paragraph.type === "title" ? {
    fontSize: 18, fontWeight: 600, color: "#e2e8f0",
    fontFamily: "'Space Grotesk', sans-serif",
    letterSpacing: "0.02em", padding: "8px 0",
  } : paragraph.type === "section" ? {
    fontSize: 13, fontWeight: 500, color: "#94a3b8",
    fontFamily: "'JetBrains Mono', monospace",
    letterSpacing: "0.06em", padding: "16px 0 4px",
    textTransform: "uppercase",
  } : {
    fontSize: 15, color: "#cbd5e1", lineHeight: 1.85,
    fontFamily: "'Crimson Pro', 'Georgia', serif",
    textIndent: "1.5em",
  };

  return (
    <div style={{
      position: "relative",
      display: "flex",
      gap: 0,
      marginBottom: paragraph.type === "prose" ? 20 : 8,
    }}>
      {/* Gutter */}
      <div style={{
        width: 28, flexShrink: 0,
        display: "flex", flexDirection: "column",
        alignItems: "center", paddingTop: paragraph.type === "prose" ? 4 : 0,
        gap: 4,
      }}>
        {overlayMode !== "off" && paraAnnotations.length > 0 && (
          <GutterPin
            count={paraAnnotations.length}
            types={paraAnnotations.map(a => a.type)}
            onClick={() => onPinClick(paragraph.id)}
            isActive={isActive}
          />
        )}
        {overlayMode !== "off" && paraAnnotations.length === 0 && paragraph.type === "prose" && (
          <div
            onClick={() => onAddAnnotation(paragraph.id)}
            style={{
              width: 18, height: 18, borderRadius: 3,
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", color: "#1e1e2e", fontSize: 12,
              transition: "all 0.15s",
            }}
            onMouseEnter={e => { e.currentTarget.style.color = "#4a4a5a"; e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
            onMouseLeave={e => { e.currentTarget.style.color = "#1e1e2e"; e.currentTarget.style.background = "transparent"; }}
          >
            +
          </div>
        )}
      </div>

      {/* Text + Annotations */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={textStyle}>
          {renderText(paragraph.text, paragraph.entities)}
        </div>

        {/* Inline annotations (full mode) */}
        {overlayMode === "full" && isActive && paraAnnotations.length > 0 && (
          <div style={{
            marginTop: 8, marginBottom: 4,
            paddingLeft: 8,
            borderLeft: "1px solid #1e1e2e",
          }}>
            {paraAnnotations.map(ann => (
              <AnnotationCard
                key={ann.id}
                annotation={ann}
                onResolve={onResolve}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}

        {/* Annotation creator */}
        {isCreating && activeParagraph === paragraph.id && (
          <div style={{ marginTop: 8 }}>
            <AnnotationCreator
              paragraphId={paragraph.id}
              onAdd={(ann) => onAddAnnotation(paragraph.id, ann)}
              onCancel={onCancelCreate}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main App
// ============================================================================

export default function ScriboOverlay() {
  const [annotations, setAnnotations] = useState(INITIAL_ANNOTATIONS);
  const [overlayMode, setOverlayMode] = useState("pins");
  const [activeParagraph, setActiveParagraph] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showActionPlan, setShowActionPlan] = useState(true);
  const [filterType, setFilterType] = useState("all");

  const handlePinClick = useCallback((paragraphId) => {
    if (activeParagraph === paragraphId) {
      setActiveParagraph(null);
    } else {
      setActiveParagraph(paragraphId);
      if (overlayMode === "pins") setOverlayMode("full");
    }
  }, [activeParagraph, overlayMode]);

  const handleAddAnnotation = useCallback((paragraphId, annotation) => {
    if (annotation) {
      setAnnotations(prev => [...prev, annotation]);
      setIsCreating(false);
    } else {
      setActiveParagraph(paragraphId);
      setIsCreating(true);
    }
  }, []);

  const handleResolve = useCallback((id) => {
    setAnnotations(prev => prev.map(a =>
      a.id === id ? { ...a, resolved: !a.resolved } : a
    ));
  }, []);

  const handleDelete = useCallback((id) => {
    setAnnotations(prev => prev.filter(a => a.id !== id));
  }, []);

  const handleJump = useCallback((paragraphId) => {
    setActiveParagraph(paragraphId);
    setOverlayMode("full");
    const el = document.getElementById(`para-${paragraphId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const filteredAnnotations = filterType === "all"
    ? annotations
    : annotations.filter(a => a.type === filterType);

  return (
    <div style={{
      width: "100%", height: "100vh", display: "flex", flexDirection: "column",
      background: "#0a0a0f", color: "#e2e8f0",
      fontFamily: "'Space Grotesk', -apple-system, sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&family=Crimson+Pro:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e1e2e; border-radius: 2px; }
        ::selection { background: rgba(192, 132, 252, 0.25); }
      `}</style>

      {/* Top bar */}
      <div style={{
        display: "flex", alignItems: "center", height: 40,
        borderBottom: "1px solid #1e1e2e", padding: "0 16px",
        background: "rgba(10, 10, 15, 0.9)", backdropFilter: "blur(12px)",
        gap: 12, flexShrink: 0,
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "3px 10px", borderRadius: 4,
          background: "rgba(192, 132, 252, 0.1)",
          border: "1px solid rgba(192, 132, 252, 0.2)",
        }}>
          <span style={{ color: "#c084fc", fontSize: 11, fontWeight: 600, letterSpacing: "0.08em" }}>
            SCRIBO
          </span>
        </div>

        <span style={{ color: "#4a4a5a", fontSize: 11 }}>›</span>
        <span style={{ color: "#94a3b8", fontSize: 12 }}>Part One: The Departure</span>

        <div style={{ flex: 1 }} />

        {/* Overlay mode toggle */}
        <div style={{
          display: "flex", alignItems: "center", gap: 2,
          padding: 2, borderRadius: 4,
          background: "rgba(18, 18, 26, 0.8)",
          border: "1px solid #1e1e2e",
        }}>
          <span style={{
            color: "#4a4a5a", fontSize: 9, padding: "0 6px",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            OVERLAY
          </span>
          {OVERLAY_MODES.map(mode => (
            <button
              key={mode.id}
              onClick={() => {
                setOverlayMode(mode.id);
                if (mode.id === "off") setActiveParagraph(null);
              }}
              style={{
                padding: "3px 8px", borderRadius: 3, border: "none",
                background: overlayMode === mode.id ? "rgba(192, 132, 252, 0.15)" : "transparent",
                color: overlayMode === mode.id ? "#c084fc" : "#4a4a5a",
                fontSize: 9, cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {mode.icon} {mode.label}
            </button>
          ))}
        </div>

        {/* Filter */}
        {overlayMode !== "off" && (
          <div style={{ display: "flex", gap: 2, alignItems: "center" }}>
            <span style={{
              color: "#2a2a3a", fontSize: 9,
              fontFamily: "'JetBrains Mono', monospace",
              padding: "0 4px",
            }}>
              FILTER
            </span>
            {[
              { id: "all", label: "All" },
              ...Object.entries(ANNOTATION_TYPES).map(([id, cfg]) => ({
                id, label: cfg.icon,
              }))
            ].map(f => (
              <button
                key={f.id}
                onClick={() => setFilterType(f.id)}
                style={{
                  padding: "2px 6px", borderRadius: 3, border: "none",
                  background: filterType === f.id ? "rgba(255,255,255,0.06)" : "transparent",
                  color: filterType === f.id ? "#e2e8f0" : "#2a2a3a",
                  fontSize: 10, cursor: "pointer",
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        )}

        {/* Action plan toggle */}
        <button
          onClick={() => setShowActionPlan(!showActionPlan)}
          style={{
            padding: "3px 10px", borderRadius: 4,
            border: `1px solid ${showActionPlan ? "rgba(192, 132, 252, 0.3)" : "#1e1e2e"}`,
            background: showActionPlan ? "rgba(192, 132, 252, 0.08)" : "transparent",
            color: showActionPlan ? "#c084fc" : "#4a4a5a",
            fontSize: 10, cursor: "pointer",
            fontFamily: "'JetBrains Mono', monospace",
          }}
        >
          ☰ Plan
        </button>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Writing surface with overlay */}
        <div style={{ flex: 1, overflow: "auto", padding: "32px 24px 80px" }}>
          <div style={{ maxWidth: 700, margin: "0 auto" }}>
            {/* Character tags bar */}
            <div style={{
              display: "flex", gap: 8, marginBottom: 24, flexWrap: "wrap",
            }}>
              {[
                { name: "Cornelius", color: "#4ade80" },
                { name: "Mordecai", color: "#a78bfa" },
              ].map(c => (
                <span key={c.name} style={{
                  display: "flex", alignItems: "center", gap: 4,
                  padding: "3px 10px", borderRadius: 4,
                  background: c.color + "12", border: `1px solid ${c.color}25`,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.color }} />
                  <span style={{ color: c.color, fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
                    {c.name}
                  </span>
                </span>
              ))}
              <span style={{ color: "#4a4a5a", fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}>
                ◎ Blackstone Hollow · ◑ Morning
              </span>
              <span style={{
                marginLeft: "auto", color: "#fbbf24", fontSize: 10,
                padding: "2px 8px", borderRadius: 3,
                background: "rgba(251, 191, 36, 0.1)",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                DRAFT
              </span>
            </div>

            {/* Paragraphs */}
            {PARAGRAPHS.map(para => (
              <div key={para.id} id={`para-${para.id}`}>
                <AnnotatedParagraph
                  paragraph={para}
                  annotations={filteredAnnotations}
                  overlayMode={overlayMode}
                  activeParagraph={activeParagraph}
                  onPinClick={handlePinClick}
                  onAddAnnotation={handleAddAnnotation}
                  isCreating={isCreating}
                  onCancelCreate={() => setIsCreating(false)}
                  onResolve={handleResolve}
                  onDelete={handleDelete}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Action Plan sidebar */}
        {showActionPlan && (
          <div style={{
            width: 300, borderLeft: "1px solid #1e1e2e",
            background: "rgba(10, 10, 15, 0.4)", flexShrink: 0,
          }}>
            <ActionPlan
              annotations={annotations}
              onJump={handleJump}
            />
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 12, padding: "6px 16px",
        borderTop: "1px solid #1e1e2e", background: "rgba(10, 10, 15, 0.5)",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "#4a4a5a",
      }}>
        <span>Scene: 875 words</span>
        <span style={{ color: "#2a2a3a" }}>|</span>
        <span>Project: 3,715 words</span>
        <span style={{ color: "#2a2a3a" }}>|</span>
        <span>
          Annotations: {annotations.length} ({annotations.filter(a => !a.resolved).length} open)
        </span>
        <span style={{ marginLeft: "auto", color: "#2a2a3a" }}>
          ⌘K commands · ⌥A new annotation · ⌘⇧O overlay toggle
        </span>
      </div>
    </div>
  );
}

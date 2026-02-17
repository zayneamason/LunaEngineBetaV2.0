import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ============================================================================
// KOZMO CODEX — Production Board
// Master planning view: all briefs across all scenes
// Plan → Organize → Discuss with AI → Push to LAB
// ============================================================================

// --- Status & Priority ---
const STATUS_CONFIG = {
  idea: { color: "#64748b", label: "Idea", icon: "○", order: 0 },
  planning: { color: "#818cf8", label: "Planning", icon: "◔", order: 1 },
  rigging: { color: "#fbbf24", label: "Rigging", icon: "◑", order: 2 },
  queued: { color: "#c084fc", label: "Queued", icon: "◕", order: 3 },
  generating: { color: "#34d399", label: "Generating", icon: "◉", order: 4 },
  review: { color: "#38bdf8", label: "Review", icon: "◈", order: 5 },
  approved: { color: "#4ade80", label: "Approved", icon: "✓", order: 6 },
  locked: { color: "#4ade80", label: "Locked", icon: "◆", order: 7 },
};

const PRIORITY_CONFIG = {
  critical: { color: "#f87171", label: "CRIT", weight: 4 },
  high: { color: "#fb923c", label: "HIGH", weight: 3 },
  medium: { color: "#fbbf24", label: "MED", weight: 2 },
  low: { color: "#64748b", label: "LOW", weight: 1 },
};

const AGENTS = [
  { id: "luna", name: "Luna", color: "#c084fc", icon: "☾", role: "Story & continuity" },
  { id: "maya", name: "Maya", color: "#34d399", icon: "◐", role: "Visual design & reference" },
  { id: "chiba", name: "Chiba", color: "#38bdf8", icon: "◎", role: "Camera & cinematography" },
  { id: "ben", name: "Ben", color: "#fbbf24", icon: "✎", role: "Script & structure" },
];

const ENTITY_COLORS = {
  cornelius: "#4ade80",
  mordecai: "#a78bfa",
  constance: "#f472b6",
  blackstone_hollow: "#38bdf8",
  the_tower: "#fbbf24",
  crooked_nail: "#fb923c",
};

// --- All Production Briefs (across all scenes) ---
const ALL_BRIEFS = [
  // Act I — The Departure
  {
    id: "pb_001", scene: "Part One: The Departure", act: "Act I — The Departure",
    type: "single", status: "rigging", priority: "high",
    title: "Blackstone Hollow — Establishing Shot",
    prompt: "Establishing wide shot, stone cottage at Blackstone Hollow, overgrown garden, morning mist, oversized doorframe for a dinosaur, fantasy realism",
    characters: ["cornelius", "mordecai"], location: "blackstone_hollow",
    assignee: "maya", tags: ["establishing", "location", "key_frame"],
    dependencies: [], notes: "",
    aiThread: [
      { role: "user", text: "Maya, I want this to feel like the first frame of the film. Quiet, lived-in, a little melancholy.", time: "2:20 PM" },
      { role: "maya", text: "Got it. I'd lean into morning mist to sell the stillness, and put the oversized doorframe off-center — rule of thirds, garden dominating the left. The scale tells the story before anyone speaks.", time: "2:21 PM" },
      { role: "user", text: "Yes. And the garden should look maintained but aging. Like someone cares but it's a losing battle.", time: "2:22 PM" },
    ],
  },
  {
    id: "pb_002", scene: "Part One: The Departure", act: "Act I — The Departure",
    type: "sequence", status: "planning", priority: "high",
    title: "The Road North — Travel Montage",
    prompt: "Cornelius traveling alone through landscape not built for his size",
    characters: ["cornelius"], location: "the_road_north",
    assignee: "chiba", tags: ["montage", "travel", "key_sequence"],
    dependencies: ["pb_003"],
    shotCount: 4,
    notes: "This is the first time we see Cornelius alone in the world. Scale is everything.",
    aiThread: [
      { role: "user", text: "Chiba, this montage needs to feel like the world is actively hostile to his size. Not malicious, just indifferent.", time: "2:31 PM" },
      { role: "chiba", text: "I'd alternate between tight claustrophobic shots (low branches, narrow bridge) and vast wides where he's tiny. The contrast sells the loneliness. Anamorphic would help — Panavision C-Series for the wides, Cooke S7/i for the close detail on the satchel.", time: "2:32 PM" },
    ],
  },
  {
    id: "pb_003", scene: "Part One: The Departure", act: "Act I — The Departure",
    type: "reference", status: "planning", priority: "medium",
    title: "Cornelius in the Garden — Reference Art",
    prompt: "Gentle dinosaur tending a vegetable garden in morning light, peaceful domestic scene, overgrown cottage in background, warm golden hour",
    characters: ["cornelius"], location: "blackstone_hollow",
    assignee: "maya", tags: ["reference", "character", "peaceful"],
    dependencies: [],
    notes: "This is the 'before' image — Cornelius at peace. Everything after this is departure from comfort.",
    aiThread: [],
  },
  {
    id: "pb_004", scene: "Part One: The Departure", act: "Act I — The Departure",
    type: "single", status: "generating", priority: "medium",
    title: "Bottles and Books — Close-up",
    prompt: "Close-up of cluttered wizard's desk, grimoires and empty bottles, bottles outnumbering books, warm candlelight, dust motes, shallow DOF",
    characters: ["mordecai"], location: "blackstone_hollow",
    assignee: "maya", tags: ["detail", "character", "symbolism"],
    dependencies: [],
    notes: "Visual metaphor for Mordecai's addiction. The ratio of bottles to books tells the whole story.",
    progress: 62,
    aiThread: [
      { role: "luna", text: "This shot should echo in Act III when Cornelius finds the tower study — same composition but the bottles are shattered, books are open. Track this as an ECHO pattern.", time: "2:35 PM" },
    ],
  },

  // Act II — The Tower
  {
    id: "pb_005", scene: "Part Two: The Tower", act: "Act II — The Tower",
    type: "single", status: "idea", priority: "high",
    title: "The Tower — First Reveal",
    prompt: "Massive dark tower emerging from fog, seen from below through dead trees, ominous but beautiful, fantasy realism",
    characters: [], location: "the_tower",
    assignee: "chiba", tags: ["establishing", "location", "key_frame", "act_break"],
    dependencies: ["pb_002"],
    notes: "This is the act break image. Everything changes here.",
    aiThread: [],
  },
  {
    id: "pb_006", scene: "Part Two: The Tower", act: "Act II — The Tower",
    type: "single", status: "idea", priority: "medium",
    title: "Cornelius at the Gate",
    prompt: "Dinosaur standing before massive iron gate, dwarfed by the tower, determination in posture despite fear, backlit by storm clouds",
    characters: ["cornelius"], location: "the_tower",
    assignee: "maya", tags: ["character", "key_frame", "threshold"],
    dependencies: ["pb_005"],
    notes: "Threshold crossing moment. He chooses to go in.",
    aiThread: [],
  },
  {
    id: "pb_007", scene: "Part Three: The Descent", act: "Act II — The Tower",
    type: "sequence", status: "idea", priority: "medium",
    title: "The Descent — Stairwell Sequence",
    prompt: "Cornelius descending a spiral staircase that's too narrow, scraping walls, lantern light",
    characters: ["cornelius"], location: "the_tower",
    assignee: "chiba", tags: ["sequence", "claustrophobia", "tension"],
    dependencies: ["pb_006"],
    shotCount: 3,
    notes: "Mirror the road north montage but vertical and interior. Same hostile architecture, different axis.",
    aiThread: [],
  },

  // Act III — The Reckoning
  {
    id: "pb_008", scene: "Part Four: The Reckoning", act: "Act III — The Reckoning",
    type: "single", status: "idea", priority: "critical",
    title: "Mordecai Found — The Reveal",
    prompt: "Mordecai slumped in a dark chamber, surrounded by glowing sigils, emaciated, transformed, barely recognizable",
    characters: ["mordecai"], location: "the_tower",
    assignee: "maya", tags: ["key_frame", "climax", "character"],
    dependencies: ["pb_007"],
    notes: "The emotional climax. Everything has been building to this image.",
    aiThread: [
      { role: "luna", text: "This needs to rhyme with the bottles-and-books shot (pb_004) — same character, same addiction, but the endgame. The sigils replace the bottles as the vice. Consider matching the Cooke S7/i lens to create visual continuity.", time: "2:40 PM" },
    ],
  },
  {
    id: "pb_009", scene: "Part Five: The Garden", act: "Act III — The Reckoning",
    type: "single", status: "idea", priority: "high",
    title: "The Garden Restored — Final Frame",
    prompt: "The cottage garden in full bloom, two chairs, morning light, a sense of return and healing",
    characters: ["cornelius", "mordecai"], location: "blackstone_hollow",
    assignee: "maya", tags: ["key_frame", "resolution", "bookend"],
    dependencies: ["pb_008"],
    notes: "Bookend with pb_001. Same location, different energy. The garden that was losing the battle has won.",
    aiThread: [],
  },
];

// --- Group By Options ---
const GROUP_OPTIONS = [
  { id: "act", label: "Act" },
  { id: "status", label: "Status" },
  { id: "character", label: "Character" },
  { id: "assignee", label: "Agent" },
  { id: "priority", label: "Priority" },
];

// ============================================================================
// Components
// ============================================================================

// --- Brief Row (compact list item) ---
function BriefRow({ brief, isSelected, onClick, onStatusChange }) {
  const status = STATUS_CONFIG[brief.status];
  const priority = PRIORITY_CONFIG[brief.priority];
  const hasDeps = brief.dependencies?.length > 0;
  const hasThread = brief.aiThread?.length > 0;

  return (
    <div
      onClick={() => onClick(brief.id)}
      style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 12px", cursor: "pointer",
        background: isSelected ? "rgba(129, 140, 248, 0.06)" : "transparent",
        borderLeft: `2px solid ${isSelected ? "#818cf8" : "transparent"}`,
        transition: "all 0.1s",
      }}
      onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.015)"; }}
      onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
    >
      {/* Status dot */}
      <span
        onClick={e => { e.stopPropagation(); onStatusChange?.(brief.id); }}
        style={{ color: status.color, fontSize: 12, cursor: "pointer", flexShrink: 0 }}
        title={status.label}
      >
        {status.icon}
      </span>

      {/* Priority */}
      <span style={{
        color: priority.color, fontSize: 7, padding: "1px 3px",
        border: `1px solid ${priority.color}30`, borderRadius: 2,
        fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
        minWidth: 24, textAlign: "center",
      }}>
        {priority.label}
      </span>

      {/* Title */}
      <span style={{
        color: "#e2e8f0", fontSize: 12, flex: 1, minWidth: 0,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        fontFamily: "'Space Grotesk', sans-serif",
      }}>
        {brief.title}
      </span>

      {/* Type badge */}
      {brief.type === "sequence" && (
        <span style={{
          color: "#c084fc", fontSize: 7, padding: "1px 4px",
          background: "rgba(192, 132, 252, 0.1)", borderRadius: 2,
          fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
        }}>
          {brief.shotCount || "?"} SHOTS
        </span>
      )}
      {brief.type === "reference" && (
        <span style={{
          color: "#34d399", fontSize: 7, padding: "1px 4px",
          background: "rgba(52, 211, 153, 0.1)", borderRadius: 2,
          fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
        }}>
          REF
        </span>
      )}

      {/* Indicators */}
      {hasDeps && <span style={{ color: "#fbbf24", fontSize: 9, flexShrink: 0 }} title="Has dependencies">⧫</span>}
      {hasThread && <span style={{ color: "#c084fc", fontSize: 9, flexShrink: 0 }} title="AI discussion">💬</span>}

      {/* Progress */}
      {brief.status === "generating" && (
        <span style={{ color: "#34d399", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", flexShrink: 0 }}>
          {brief.progress}%
        </span>
      )}

      {/* Assignee */}
      <span style={{
        color: AGENTS.find(a => a.id === brief.assignee)?.color || "#4a4a5a",
        fontSize: 9, fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
      }}>
        {AGENTS.find(a => a.id === brief.assignee)?.name || brief.assignee}
      </span>
    </div>
  );
}

// --- Group Header ---
function GroupHeader({ label, count, color, isOpen, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 12px", cursor: "pointer",
        borderBottom: "1px solid #1e1e2e",
        background: "rgba(18, 18, 26, 0.4)",
      }}
    >
      <span style={{ color: "#2a2a3a", fontSize: 10, transition: "transform 0.15s", transform: isOpen ? "rotate(90deg)" : "rotate(0)" }}>
        ▸
      </span>
      <span style={{
        color: color || "#94a3b8", fontSize: 11, fontWeight: 500,
        fontFamily: "'Space Grotesk', sans-serif",
      }}>
        {label}
      </span>
      <span style={{
        color: color || "#4a4a5a", fontSize: 9, padding: "1px 6px",
        background: (color || "#64748b") + "12", borderRadius: 3,
        fontFamily: "'JetBrains Mono', monospace",
      }}>
        {count}
      </span>
    </div>
  );
}

// --- Detail Panel (right side) ---
function DetailPanel({ brief, onClose, onUpdate }) {
  const [activeTab, setActiveTab] = useState("details");
  const [chatInput, setChatInput] = useState("");
  const [chatAgent, setChatAgent] = useState("luna");
  const chatEndRef = useRef(null);

  const status = STATUS_CONFIG[brief.status];
  const priority = PRIORITY_CONFIG[brief.priority];
  const statusEntries = Object.entries(STATUS_CONFIG);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [brief.aiThread?.length]);

  const handleSend = () => {
    if (!chatInput.trim()) return;
    const agent = AGENTS.find(a => a.id === chatAgent);
    const newThread = [
      ...(brief.aiThread || []),
      { role: "user", text: chatInput.trim(), time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) },
    ];
    // Simulate agent response
    setTimeout(() => {
      const responses = {
        luna: "I'll cross-reference this with the scene context and existing ECHO patterns. Give me a moment to trace the dependencies.",
        maya: "I can start with a mood board based on this prompt. Want me to pull reference from the existing entity profiles first?",
        chiba: "The camera language here should mirror what we established earlier. I'll draft a rig proposal based on the scene's emotional arc.",
        ben: "Let me check this against the narrative structure. The timing and placement within the act matters for pacing.",
      };
      onUpdate({
        ...brief,
        aiThread: [
          ...newThread,
          { role: chatAgent, text: responses[chatAgent] || "Processing...", time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) },
        ],
      });
    }, 800);
    onUpdate({ ...brief, aiThread: newThread });
    setChatInput("");
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{
        padding: "12px 16px", borderBottom: "1px solid #1e1e2e",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span style={{ color: status.color, fontSize: 13 }}>{status.icon}</span>
          <span style={{ color: "#e2e8f0", fontSize: 15, fontWeight: 500, flex: 1 }}>
            {brief.title}
          </span>
          <span onClick={onClose} style={{ color: "#2a2a3a", cursor: "pointer", fontSize: 16 }}>×</span>
        </div>

        {/* Status bar — click to change */}
        <div style={{ display: "flex", gap: 2, marginBottom: 8 }}>
          {statusEntries.map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => onUpdate({ ...brief, status: key })}
              style={{
                flex: 1, padding: "3px 0", borderRadius: 3, border: "none",
                background: brief.status === key ? cfg.color + "20" : "rgba(18, 18, 26, 0.4)",
                color: brief.status === key ? cfg.color : "#1e1e2e",
                fontSize: 7, cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
                transition: "all 0.1s",
              }}
              onMouseEnter={e => { if (brief.status !== key) e.currentTarget.style.color = cfg.color + "60"; }}
              onMouseLeave={e => { if (brief.status !== key) e.currentTarget.style.color = "#1e1e2e"; }}
            >
              {cfg.icon} {cfg.label}
            </button>
          ))}
        </div>

        {/* Meta row */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {/* Priority selector */}
          {Object.entries(PRIORITY_CONFIG).map(([key, cfg]) => (
            <button
              key={key}
              onClick={() => onUpdate({ ...brief, priority: key })}
              style={{
                padding: "2px 5px", borderRadius: 2,
                border: `1px solid ${brief.priority === key ? cfg.color + "40" : "#1e1e2e"}`,
                background: brief.priority === key ? cfg.color + "12" : "transparent",
                color: brief.priority === key ? cfg.color : "#2a2a3a",
                fontSize: 8, cursor: "pointer",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {cfg.label}
            </button>
          ))}

          <span style={{ color: "#1e1e2e" }}>·</span>

          {/* Characters */}
          {brief.characters.map(c => (
            <span key={c} style={{
              padding: "1px 6px", borderRadius: 2, fontSize: 9,
              color: ENTITY_COLORS[c] || "#94a3b8",
              background: (ENTITY_COLORS[c] || "#94a3b8") + "12",
              fontFamily: "'JetBrains Mono', monospace",
              textTransform: "capitalize",
            }}>
              {c}
            </span>
          ))}

          {brief.location && (
            <span style={{
              padding: "1px 6px", borderRadius: 2, fontSize: 9,
              color: ENTITY_COLORS[brief.location] || "#38bdf8",
              background: (ENTITY_COLORS[brief.location] || "#38bdf8") + "12",
              fontFamily: "'JetBrains Mono', monospace",
              textTransform: "capitalize",
            }}>
              ◎ {brief.location.replace(/_/g, " ")}
            </span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: "flex", gap: 0, borderBottom: "1px solid #1e1e2e",
      }}>
        {[
          { id: "details", label: "Details" },
          { id: "ai", label: `AI Chat ${brief.aiThread?.length ? `(${brief.aiThread.length})` : ""}` },
          { id: "deps", label: `Deps ${brief.dependencies?.length ? `(${brief.dependencies.length})` : ""}` },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "8px 14px", border: "none",
              background: activeTab === tab.id ? "rgba(129, 140, 248, 0.06)" : "transparent",
              color: activeTab === tab.id ? "#818cf8" : "#4a4a5a",
              fontSize: 11, cursor: "pointer",
              borderBottom: `2px solid ${activeTab === tab.id ? "#818cf8" : "transparent"}`,
              fontFamily: "'Space Grotesk', sans-serif",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: "auto" }}>

        {/* Details tab */}
        {activeTab === "details" && (
          <div style={{ padding: 16 }}>
            {/* Scene source */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                Source
              </div>
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "6px 10px", borderRadius: 4,
                background: "rgba(192, 132, 252, 0.04)",
                border: "1px solid rgba(192, 132, 252, 0.1)",
              }}>
                <span style={{ color: "#c084fc", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>SCRIBO</span>
                <span style={{ color: "#2a2a3a" }}>›</span>
                <span style={{ color: "#94a3b8", fontSize: 11 }}>{brief.act}</span>
                <span style={{ color: "#2a2a3a" }}>›</span>
                <span style={{ color: "#cbd5e1", fontSize: 11 }}>{brief.scene}</span>
              </div>
            </div>

            {/* Prompt */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                Prompt
              </div>
              <textarea
                defaultValue={brief.prompt}
                style={{
                  width: "100%", minHeight: 70, padding: 10, borderRadius: 4,
                  background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
                  color: "#e2e8f0", fontSize: 12, resize: "vertical",
                  fontFamily: "'Space Grotesk', sans-serif", outline: "none", lineHeight: 1.5,
                }}
                onFocus={e => e.currentTarget.style.borderColor = "#818cf830"}
                onBlur={e => e.currentTarget.style.borderColor = "#1e1e2e"}
              />
            </div>

            {/* Notes */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                Production Notes
              </div>
              <textarea
                defaultValue={brief.notes}
                placeholder="Add production notes..."
                style={{
                  width: "100%", minHeight: 50, padding: 10, borderRadius: 4,
                  background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
                  color: "#cbd5e1", fontSize: 12, resize: "vertical",
                  fontFamily: "'Space Grotesk', sans-serif", outline: "none", lineHeight: 1.5,
                }}
              />
            </div>

            {/* Tags */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                Tags
              </div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {brief.tags?.map(tag => (
                  <span key={tag} style={{
                    padding: "2px 8px", borderRadius: 3,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid #1e1e2e",
                    color: "#94a3b8", fontSize: 10,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>
                    {tag}
                  </span>
                ))}
                <span style={{
                  padding: "2px 8px", borderRadius: 3, cursor: "pointer",
                  border: "1px dashed #1e1e2e", color: "#2a2a3a", fontSize: 10,
                }}>
                  + tag
                </span>
              </div>
            </div>

            {/* Assignee */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
                Assigned To
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                {AGENTS.map(agent => (
                  <button
                    key={agent.id}
                    onClick={() => onUpdate({ ...brief, assignee: agent.id })}
                    style={{
                      padding: "4px 10px", borderRadius: 4,
                      border: `1px solid ${brief.assignee === agent.id ? agent.color + "40" : "#1e1e2e"}`,
                      background: brief.assignee === agent.id ? agent.color + "10" : "transparent",
                      color: brief.assignee === agent.id ? agent.color : "#4a4a5a",
                      fontSize: 11, cursor: "pointer",
                      fontFamily: "'Space Grotesk', sans-serif",
                    }}
                  >
                    {agent.icon} {agent.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Action buttons */}
            <div style={{ display: "flex", gap: 6, paddingTop: 8, borderTop: "1px solid #1e1e2e" }}>
              <button style={{
                flex: 1, padding: "8px 12px", borderRadius: 4, border: "none",
                background: "rgba(129, 140, 248, 0.12)", color: "#818cf8",
                fontSize: 12, cursor: "pointer", fontWeight: 500,
              }}>
                → Push to LAB
              </button>
              <button style={{
                padding: "8px 12px", borderRadius: 4,
                border: "1px solid rgba(192, 132, 252, 0.2)", background: "transparent",
                color: "#c084fc", fontSize: 12, cursor: "pointer",
              }}>
                ↗ Open in SCRIBO
              </button>
            </div>
          </div>
        )}

        {/* AI Chat tab */}
        {activeTab === "ai" && (
          <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
            {/* Agent selector */}
            <div style={{ display: "flex", gap: 3, padding: "8px 12px", borderBottom: "1px solid #1e1e2e" }}>
              {AGENTS.map(agent => (
                <button
                  key={agent.id}
                  onClick={() => setChatAgent(agent.id)}
                  style={{
                    padding: "3px 8px", borderRadius: 3,
                    border: `1px solid ${chatAgent === agent.id ? agent.color + "40" : "#1e1e2e"}`,
                    background: chatAgent === agent.id ? agent.color + "10" : "transparent",
                    color: chatAgent === agent.id ? agent.color : "#4a4a5a",
                    fontSize: 10, cursor: "pointer",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {agent.icon} {agent.name}
                </button>
              ))}
            </div>

            {/* Thread */}
            <div style={{ flex: 1, overflow: "auto", padding: "8px 12px" }}>
              {(!brief.aiThread || brief.aiThread.length === 0) ? (
                <div style={{ color: "#2a2a3a", fontSize: 12, textAlign: "center", paddingTop: 32 }}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>💬</div>
                  Start a conversation about this brief
                </div>
              ) : (
                brief.aiThread.map((msg, i) => {
                  const isUser = msg.role === "user";
                  const agent = !isUser ? AGENTS.find(a => a.id === msg.role) : null;
                  return (
                    <div key={i} style={{
                      marginBottom: 10,
                      paddingLeft: isUser ? 0 : 0,
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                        <span style={{
                          color: isUser ? "#e2e8f0" : agent?.color || "#94a3b8",
                          fontSize: 10, fontWeight: 500,
                        }}>
                          {isUser ? "Ahab" : agent?.icon + " " + (agent?.name || msg.role)}
                        </span>
                        <span style={{ color: "#2a2a3a", fontSize: 9 }}>{msg.time}</span>
                      </div>
                      <div style={{
                        color: isUser ? "#cbd5e1" : "#94a3b8",
                        fontSize: 12, lineHeight: 1.6,
                        padding: "6px 10px", borderRadius: 4,
                        background: isUser ? "rgba(255,255,255,0.02)" : (agent?.color || "#64748b") + "06",
                        borderLeft: `2px solid ${isUser ? "#2a2a3a" : (agent?.color || "#64748b") + "30"}`,
                      }}>
                        {msg.text}
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div style={{
              padding: "8px 12px", borderTop: "1px solid #1e1e2e",
              display: "flex", gap: 6,
            }}>
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
                placeholder={`Talk to ${AGENTS.find(a => a.id === chatAgent)?.name || "agent"} about this brief...`}
                style={{
                  flex: 1, padding: "8px 10px", borderRadius: 4,
                  background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
                  color: "#e2e8f0", fontSize: 12, outline: "none",
                  fontFamily: "'Space Grotesk', sans-serif",
                }}
                onFocus={e => e.currentTarget.style.borderColor = (AGENTS.find(a => a.id === chatAgent)?.color || "#818cf8") + "30"}
                onBlur={e => e.currentTarget.style.borderColor = "#1e1e2e"}
              />
              <button
                onClick={handleSend}
                style={{
                  padding: "6px 14px", borderRadius: 4, border: "none",
                  background: chatInput.trim() ? (AGENTS.find(a => a.id === chatAgent)?.color || "#818cf8") + "20" : "#1e1e2e",
                  color: chatInput.trim() ? (AGENTS.find(a => a.id === chatAgent)?.color || "#818cf8") : "#2a2a3a",
                  fontSize: 12, cursor: chatInput.trim() ? "pointer" : "default",
                }}
              >
                Send
              </button>
            </div>
          </div>
        )}

        {/* Dependencies tab */}
        {activeTab === "deps" && (
          <div style={{ padding: 16 }}>
            <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>
              Dependencies — must complete before this brief
            </div>

            {(!brief.dependencies || brief.dependencies.length === 0) ? (
              <div style={{ color: "#2a2a3a", fontSize: 12, textAlign: "center", paddingTop: 24 }}>
                No dependencies
              </div>
            ) : (
              brief.dependencies.map(depId => {
                const dep = ALL_BRIEFS.find(b => b.id === depId);
                if (!dep) return null;
                const depStatus = STATUS_CONFIG[dep.status];
                const isComplete = ["approved", "locked"].includes(dep.status);
                return (
                  <div key={depId} style={{
                    padding: "10px 12px", borderRadius: 4,
                    background: isComplete ? "rgba(74, 222, 128, 0.04)" : "rgba(251, 191, 36, 0.04)",
                    border: `1px solid ${isComplete ? "rgba(74, 222, 128, 0.15)" : "rgba(251, 191, 36, 0.15)"}`,
                    marginBottom: 6,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ color: depStatus.color, fontSize: 11 }}>{depStatus.icon}</span>
                      <span style={{ color: "#e2e8f0", fontSize: 12, flex: 1 }}>{dep.title}</span>
                      <span style={{
                        color: depStatus.color, fontSize: 9,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}>
                        {depStatus.label}
                      </span>
                    </div>
                    {!isComplete && (
                      <div style={{ color: "#fbbf24", fontSize: 10, marginTop: 4 }}>
                        ⧫ Blocking — this brief can't go to LAB until {dep.title} is complete
                      </div>
                    )}
                  </div>
                );
              })
            )}

            {/* Add dependency */}
            <button style={{
              width: "100%", padding: "8px 0", marginTop: 8,
              borderRadius: 4, border: "1px dashed #1e1e2e",
              background: "transparent", color: "#2a2a3a",
              fontSize: 11, cursor: "pointer",
            }}>
              + Add dependency
            </button>

            {/* Dependents */}
            <div style={{ marginTop: 20 }}>
              <div style={{ color: "#4a4a5a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 8 }}>
                Blocked by this — waiting for completion
              </div>
              {ALL_BRIEFS.filter(b => b.dependencies?.includes(brief.id)).map(dep => {
                const depStatus = STATUS_CONFIG[dep.status];
                return (
                  <div key={dep.id} style={{
                    padding: "8px 12px", borderRadius: 4,
                    background: "rgba(18, 18, 26, 0.4)", border: "1px solid #1e1e2e",
                    marginBottom: 4, display: "flex", alignItems: "center", gap: 6,
                  }}>
                    <span style={{ color: depStatus.color, fontSize: 10 }}>{depStatus.icon}</span>
                    <span style={{ color: "#94a3b8", fontSize: 11, flex: 1 }}>{dep.title}</span>
                    <span style={{ color: "#f87171", fontSize: 9 }}>blocked</span>
                  </div>
                );
              })}
              {ALL_BRIEFS.filter(b => b.dependencies?.includes(brief.id)).length === 0 && (
                <div style={{ color: "#2a2a3a", fontSize: 11, textAlign: "center" }}>
                  Nothing blocked by this brief
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// ============================================================================
// Main App
// ============================================================================

export default function CodexProductionBoard() {
  const [briefs, setBriefs] = useState(ALL_BRIEFS);
  const [selectedBrief, setSelectedBrief] = useState(null);
  const [groupBy, setGroupBy] = useState("act");
  const [statusFilter, setStatusFilter] = useState("all");
  const [openGroups, setOpenGroups] = useState({});
  const [selectedBriefs, setSelectedBriefs] = useState(new Set());

  const currentBrief = briefs.find(b => b.id === selectedBrief);

  // Toggle group open/close
  const toggleGroup = useCallback((key) => {
    setOpenGroups(prev => ({ ...prev, [key]: prev[key] === false ? true : prev[key] === undefined ? false : !prev[key] }));
  }, []);

  // Group briefs
  const grouped = useMemo(() => {
    const filtered = statusFilter === "all" ? briefs : briefs.filter(b => b.status === statusFilter);
    const groups = {};

    filtered.forEach(brief => {
      let key;
      switch (groupBy) {
        case "act": key = brief.act; break;
        case "status": key = STATUS_CONFIG[brief.status]?.label || brief.status; break;
        case "character":
          brief.characters.forEach(c => {
            const k = c.replace(/_/g, " ");
            if (!groups[k]) groups[k] = { key: k, color: ENTITY_COLORS[c], briefs: [] };
            groups[k].briefs.push(brief);
          });
          return;
        case "assignee":
          key = AGENTS.find(a => a.id === brief.assignee)?.name || brief.assignee;
          break;
        case "priority": key = PRIORITY_CONFIG[brief.priority]?.label || brief.priority; break;
        default: key = "All";
      }
      if (!groups[key]) {
        groups[key] = {
          key,
          color: groupBy === "status" ? STATUS_CONFIG[brief.status]?.color
            : groupBy === "assignee" ? AGENTS.find(a => a.id === brief.assignee)?.color
            : groupBy === "priority" ? PRIORITY_CONFIG[brief.priority]?.color
            : "#94a3b8",
          briefs: [],
        };
      }
      groups[key].briefs.push(brief);
    });

    return Object.values(groups);
  }, [briefs, groupBy, statusFilter]);

  // Stats
  const stats = useMemo(() => ({
    total: briefs.length,
    totalShots: briefs.reduce((s, b) => s + (b.shotCount || 1), 0),
    byStatus: Object.entries(STATUS_CONFIG).map(([key, cfg]) => ({
      key, ...cfg, count: briefs.filter(b => b.status === key).length,
    })).filter(s => s.count > 0),
  }), [briefs]);

  const handleUpdateBrief = useCallback((updated) => {
    setBriefs(prev => prev.map(b => b.id === updated.id ? updated : b));
  }, []);

  const cycleStatus = useCallback((id) => {
    setBriefs(prev => prev.map(b => {
      if (b.id !== id) return b;
      const keys = Object.keys(STATUS_CONFIG);
      const idx = keys.indexOf(b.status);
      return { ...b, status: keys[(idx + 1) % keys.length] };
    }));
  }, []);

  return (
    <div style={{
      width: "100%", height: "100vh", display: "flex", flexDirection: "column",
      background: "#0a0a0f", color: "#e2e8f0",
      fontFamily: "'Space Grotesk', -apple-system, sans-serif",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&family=Crimson+Pro:ital,wght@0,300;0,400;1,300;1,400&display=swap');
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
          padding: "3px 10px", borderRadius: 4,
          background: "rgba(251, 191, 36, 0.1)",
          border: "1px solid rgba(251, 191, 36, 0.2)",
        }}>
          <span style={{ color: "#fbbf24", fontSize: 11, fontWeight: 600, letterSpacing: "0.08em" }}>CODEX</span>
        </div>

        <span style={{ color: "#4a4a5a", fontSize: 11 }}>›</span>
        <span style={{ color: "#94a3b8", fontSize: 12 }}>Production Board</span>

        <div style={{ flex: 1 }} />

        {/* Status pipeline */}
        <div style={{ display: "flex", gap: 2, alignItems: "center" }}>
          {stats.byStatus.map((s, i) => (
            <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 2 }}>
              {i > 0 && <span style={{ color: "#1e1e2e", fontSize: 8 }}>→</span>}
              <button
                onClick={() => setStatusFilter(statusFilter === s.key ? "all" : s.key)}
                style={{
                  display: "flex", alignItems: "center", gap: 3,
                  padding: "2px 6px", borderRadius: 3, border: "none",
                  background: statusFilter === s.key ? s.color + "20" : "transparent",
                  color: statusFilter === s.key ? s.color : "#2a2a3a",
                  fontSize: 9, cursor: "pointer",
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                <span style={{ color: s.color, fontSize: 8 }}>{s.icon}</span>
                <span>{s.count}</span>
              </button>
            </div>
          ))}
        </div>

        <div style={{ width: 1, height: 16, background: "#1e1e2e" }} />

        {/* Mode tabs */}
        {["SCRIBO", "CODEX", "LAB"].map(mode => (
          <span key={mode} style={{
            color: mode === "CODEX" ? "#fbbf24" : "#2a2a3a",
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            cursor: "pointer", letterSpacing: "0.08em",
            padding: "3px 6px", borderRadius: 3,
            background: mode === "CODEX" ? "rgba(251, 191, 36, 0.08)" : "transparent",
          }}>
            {mode}
          </span>
        ))}
      </div>

      {/* Secondary bar — group by + bulk actions */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8, padding: "6px 16px",
        borderBottom: "1px solid #1e1e2e", background: "rgba(10, 10, 15, 0.4)",
      }}>
        <span style={{ color: "#2a2a3a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>GROUP</span>
        {GROUP_OPTIONS.map(g => (
          <button
            key={g.id}
            onClick={() => setGroupBy(g.id)}
            style={{
              padding: "2px 8px", borderRadius: 3, border: "none",
              background: groupBy === g.id ? "rgba(255,255,255,0.06)" : "transparent",
              color: groupBy === g.id ? "#e2e8f0" : "#4a4a5a",
              fontSize: 10, cursor: "pointer",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {g.label}
          </button>
        ))}

        <div style={{ flex: 1 }} />

        <span style={{ color: "#4a4a5a", fontSize: 10 }}>
          {stats.total} briefs · {stats.totalShots} shots
        </span>

        <button style={{
          padding: "3px 10px", borderRadius: 3, border: "none",
          background: "rgba(129, 140, 248, 0.08)", color: "#818cf8",
          fontSize: 10, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
        }}>
          → Push All Ready to LAB
        </button>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Brief list (left/center) */}
        <div style={{ flex: 1, overflow: "auto" }}>
          {grouped.map(group => {
            const isOpen = openGroups[group.key] !== false;
            return (
              <div key={group.key}>
                <GroupHeader
                  label={group.key}
                  count={group.briefs.length}
                  color={group.color}
                  isOpen={isOpen}
                  onToggle={() => toggleGroup(group.key)}
                />
                {isOpen && group.briefs.map(brief => (
                  <BriefRow
                    key={brief.id}
                    brief={brief}
                    isSelected={selectedBrief === brief.id}
                    onClick={setSelectedBrief}
                    onStatusChange={cycleStatus}
                  />
                ))}
              </div>
            );
          })}
        </div>

        {/* Detail panel (right) */}
        {currentBrief && (
          <div style={{
            width: 420, borderLeft: "1px solid #1e1e2e",
            background: "rgba(10, 10, 15, 0.4)", flexShrink: 0,
          }}>
            <DetailPanel
              brief={currentBrief}
              onClose={() => setSelectedBrief(null)}
              onUpdate={handleUpdateBrief}
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
        <span>The Dinosaur, The Wizard, and The Mother</span>
        <span style={{ color: "#2a2a3a" }}>|</span>
        <span>{stats.total} production briefs</span>
        <span style={{ color: "#2a2a3a" }}>|</span>
        <span style={{ color: "#fbbf24" }}>CODEX</span>
        <span style={{ marginLeft: "auto", color: "#2a2a3a" }}>
          ⌘G group · ⌘F filter · ⌘⇧L push to LAB
        </span>
      </div>
    </div>
  );
}

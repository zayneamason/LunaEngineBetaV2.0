import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ============================================================================
// KOZMO SCRIBO — The Writer's Room
// Hierarchical story navigation, mixed-format editor, agent collaboration
// ============================================================================

// --- Story Structure (DWM Project) ---
const STORY_TREE = {
  id: "dwm_root",
  title: "The Dinosaur, The Wizard, and The Mother",
  type: "series",
  icon: "◈",
  status: "in-progress",
  wordCount: 28400,
  children: [
    {
      id: "act_1", title: "Act I — The Departure", type: "act", icon: "◆",
      status: "draft", wordCount: 12200,
      children: [
        {
          id: "ch_01", title: "Chapter 1: Smoke and Silence", type: "chapter", icon: "§",
          status: "revised", wordCount: 4100,
          children: [
            { id: "sc_01", title: "Scene 1: The Crooked Nail", type: "scene", icon: "¶", status: "polished", wordCount: 1800 },
            { id: "sc_02", title: "Scene 2: What He Left Behind", type: "scene", icon: "¶", status: "revised", wordCount: 1200 },
            { id: "sc_03", title: "Scene 3: The Staff Remembers", type: "scene", icon: "¶", status: "draft", wordCount: 1100 },
          ]
        },
        {
          id: "ch_02", title: "Chapter 2: The Road North", type: "chapter", icon: "§",
          status: "draft", wordCount: 3800,
          children: [
            { id: "sc_04", title: "Scene 4: Mordecai's First Fix", type: "scene", icon: "¶", status: "draft", wordCount: 2100 },
            { id: "sc_05", title: "Scene 5: Cornelius Follows", type: "scene", icon: "¶", status: "idea", wordCount: 1700 },
          ]
        },
        {
          id: "ch_03", title: "Chapter 3: The Garden Gate", type: "chapter", icon: "§",
          status: "idea", wordCount: 4300,
          children: [
            { id: "sc_06", title: "Scene 6: Constance Alone", type: "scene", icon: "¶", status: "polished", wordCount: 2200 },
            { id: "sc_07", title: "Scene 7: The Princess Arrives", type: "scene", icon: "¶", status: "idea", wordCount: 2100 },
          ]
        },
      ]
    },
    {
      id: "act_2", title: "Act II — The Descent", type: "act", icon: "◆",
      status: "idea", wordCount: 9800,
      children: [
        {
          id: "ch_04", title: "Chapter 4: Underground", type: "chapter", icon: "§",
          status: "idea", wordCount: 5200,
          children: [
            { id: "sc_08", title: "Scene 8: The Market Below", type: "scene", icon: "¶", status: "idea", wordCount: 2600 },
            { id: "sc_09", title: "Scene 9: What She Offers", type: "scene", icon: "¶", status: "idea", wordCount: 2600 },
          ]
        },
        {
          id: "ch_05", title: "Chapter 5: Breaking Point", type: "chapter", icon: "§",
          status: "idea", wordCount: 4600,
          children: [
            { id: "sc_10", title: "Scene 10: The Unraveling", type: "scene", icon: "¶", status: "idea", wordCount: 4600 },
          ]
        },
      ]
    },
    {
      id: "act_3", title: "Act III — The Return", type: "act", icon: "◆",
      status: "idea", wordCount: 6400,
      children: [
        {
          id: "ch_06", title: "Chapter 6: Soil and Silence", type: "chapter", icon: "§",
          status: "idea", wordCount: 6400,
          children: [
            { id: "sc_11", title: "Scene 11: The Garden", type: "scene", icon: "¶", status: "idea", wordCount: 3200 },
            { id: "sc_12", title: "Scene 12: What Grows", type: "scene", icon: "¶", status: "idea", wordCount: 3200 },
          ]
        },
      ]
    },
  ]
};

// --- Scene Content (mixed Fountain + prose) ---
const SCENE_CONTENT = {
  sc_01: {
    frontmatter: {
      type: "scene",
      container: "ch_01",
      characters_present: ["mordecai", "cornelius"],
      location: "crooked_nail",
      time: "evening",
      status: "polished",
    },
    body: `The tavern smelled of woodsmoke and regret. Mordecai pushed through the door, staff clicking against the warped floorboards. The Crooked Nail had been dying for years — everyone in it had, too, they just hadn't noticed.

Three patrons. A dog. The barkeep, who'd stopped pretending to clean glasses sometime around the last war.

Cornelius sat in the far corner, where the ceiling was high enough for him. Even hunched, he filled the space like weather. His tail curled around the base of the chair — a habit from when Mordecai was small enough to trip over it.

MORDECAI
(dropping into the opposite chair)
You look terrible.

CORNELIUS
(long pause)
Boy.

MORDECAI
That's not a rebuttal.

CORNELIUS
Wasn't meant to be.

Mordecai ordered something brown. Cornelius already had water — he always had water, because taverns don't stock anything large enough for a dinosaur who's trying to be polite about it.

The silence between them had weight. Not the comfortable kind. The kind that accumulates when someone keeps almost saying something and then doesn't.

MORDECAI
I'm leaving tomorrow.

CORNELIUS
(not moving)
I know.

MORDECAI
You don't know where.

CORNELIUS
Don't need to.

Another silence. Mordecai's drink arrived. He didn't touch it.

MORDECAI
You could ask.

CORNELIUS
Would you answer?

The dog wandered over and rested its head on Cornelius's massive foot. He didn't look down, but his tail uncurled slightly. Some kindnesses are automatic.

MORDECAI
(quiet)
The north road. There's someone who can help with... this.

He gestured vaguely at himself. At everything.

CORNELIUS
(finally looking at him)
There's no one on the north road, Mordecai.
There's only the north road.`,
    lunaNotes: [
      { type: "continuity", text: "Staff is present — first appearance. Track this." },
      { type: "tone", text: "Silence as dialogue. Cornelius communicates more in pauses than words." },
      { type: "thematic", text: "'The tavern had been dying for years' — mirrors Mordecai's self-destruction." },
    ]
  },
  sc_06: {
    frontmatter: {
      type: "scene",
      container: "ch_03",
      characters_present: ["constance"],
      location: "constance_garden",
      time: "dawn",
      status: "polished",
    },
    body: `Dawn in Constance's garden arrived the way it always did — without asking permission.

She was already on her knees in the soil when the light found her. Had been for an hour, maybe more. Time moved differently when your hands were in the earth. It moved at the speed of roots.

The tomatoes were coming in wrong. Too much rain last week, not enough sun this week, and something — rabbits, probably, or that neighbor's goat — had been at the basil again. She'd replanted it three times. She'd replant it a fourth.

That was the thing about gardens. They didn't care about your plans. They grew or they didn't, and your job was to keep showing up with soil under your nails and no expectations.

CONSTANCE
(to no one, or to the tomatoes)
Listen. We talked about this.

She staked the sagging vine with practiced hands. Firm but not tight. Support, not a cage.

The house behind her was quiet. It had been quiet since Mordecai left. Before that, it had been loud in the wrong ways — doors slamming, arguments that started about dishes and ended about destiny, that horrible month when he'd stopped coming out of his room entirely.

Quiet was better. She told herself quiet was better.

Her hands found a weed and pulled it without looking. Twenty-seven years of gardening had given her fingers their own intelligence. They knew what didn't belong.

She sat back on her heels and looked at what she'd built. Not the garden — though the garden was part of it. The house. The fence she'd mended herself when Cornelius offered and she'd said no. The path worn smooth by her own feet going back and forth between the kitchen and this patch of earth.

CONSTANCE
(wiping her hands on her apron)
Good enough.

It wasn't. But it was hers.`,
    lunaNotes: [
      { type: "thematic", text: "'Support, not a cage.' — direct thematic mirror to Cornelius's arc. Both learning the same lesson from opposite directions." },
      { type: "production", text: "Zero reference images for Constance. Priority for art generation." },
      { type: "character", text: "The garden as coping mechanism. She tends what she can control because she can't tend Mordecai." },
    ]
  }
};

// --- Entity data for CODEX sidebar ---
const ENTITIES_BRIEF = [
  { id: "mordecai", name: "Mordecai", role: "The Wizard", color: "#a78bfa", type: "character", scenes: 7, status: "active" },
  { id: "cornelius", name: "Cornelius", role: "The Dinosaur", color: "#4ade80", type: "character", scenes: 6, status: "active" },
  { id: "constance", name: "Constance", role: "The Mother", color: "#f472b6", type: "character", scenes: 5, status: "active" },
  { id: "princess", name: "The Princess", role: "The Catalyst", color: "#fbbf24", type: "character", scenes: 3, status: "active" },
  { id: "crooked_nail", name: "The Crooked Nail", role: "Tavern", color: "#64748b", type: "location", scenes: 2, status: "active" },
  { id: "constance_garden", name: "Constance's Garden", role: "Home", color: "#64748b", type: "location", scenes: 3, status: "active" },
  { id: "mordecai_staff", name: "Mordecai's Staff", role: "Weapon/Focus", color: "#94a3b8", type: "prop", scenes: 5, status: "active" },
];

// --- Agent definitions ---
const AGENTS = [
  { id: "luna", name: "Luna", role: "Memory & Context", color: "#c084fc", status: "active", avatar: "☾" },
  { id: "maya", name: "Maya", role: "Visual Design", color: "#34d399", status: "idle", avatar: "◐" },
  { id: "chiba", name: "Chiba", role: "Orchestrator", color: "#818cf8", status: "idle", avatar: "◈" },
  { id: "ben", name: "Ben", role: "The Scribe", color: "#fbbf24", status: "idle", avatar: "✎" },
];

// --- Chat messages ---
const INITIAL_CHAT = [
  { id: 1, agent: "luna", text: "Scene 1 is really strong. The silence between Mordecai and Cornelius does more work than the dialogue — that's intentional, right?", time: "2:34 PM" },
  { id: 2, agent: "user", text: "yeah the whole point is cornelius communicates through absence. when he finally speaks in act 3 it should hit like a truck", time: "2:35 PM" },
  { id: 3, agent: "luna", text: "Got it. I'll flag any scene where Cornelius has more than three consecutive lines — that should feel wrong until Scene 11. Also noting: the staff appears in Scene 1 but your CODEX entry says first_appearance is Scene 3. Which is canon?", time: "2:35 PM" },
  { id: 4, agent: "user", text: "shit, scene 3. scene 1 he should just have his hands in his cloak pockets. fix the scene", time: "2:36 PM" },
  { id: 5, agent: "luna", text: "Updated. Removed the staff click from Scene 1's opening line. He pushes through the door with his hands in his cloak pockets now. Continuity flag cleared. ✓", time: "2:36 PM" },
];

// --- Status colors ---
const STATUS = {
  polished: { color: "#4ade80", label: "Polished", bg: "rgba(74, 222, 128, 0.1)" },
  revised: { color: "#818cf8", label: "Revised", bg: "rgba(129, 140, 248, 0.1)" },
  draft: { color: "#fbbf24", label: "Draft", bg: "rgba(251, 191, 36, 0.1)" },
  idea: { color: "#64748b", label: "Idea", bg: "rgba(100, 116, 139, 0.1)" },
  "in-progress": { color: "#c084fc", label: "In Progress", bg: "rgba(192, 132, 252, 0.1)" },
};

// ============================================================================
// Components
// ============================================================================

// --- Story Tree Navigation ---
function StoryTree({ tree, selected, onSelect, depth = 0, expanded, onToggle }) {
  const isExpanded = expanded.has(tree.id);
  const isSelected = selected === tree.id;
  const hasChildren = tree.children && tree.children.length > 0;
  const status = STATUS[tree.status] || STATUS.idea;

  return (
    <div>
      <div
        onClick={() => {
          onSelect(tree.id, tree);
          if (hasChildren) onToggle(tree.id);
        }}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 8px 6px " + (12 + depth * 16) + "px",
          cursor: "pointer", borderRadius: 4,
          background: isSelected ? "rgba(192, 132, 252, 0.12)" : "transparent",
          borderLeft: isSelected ? "2px solid #c084fc" : "2px solid transparent",
          transition: "all 0.15s ease",
        }}
        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
        onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
      >
        {hasChildren && (
          <span style={{ color: "#4a4a5a", fontSize: 10, width: 12, textAlign: "center", flexShrink: 0 }}>
            {isExpanded ? "▾" : "▸"}
          </span>
        )}
        {!hasChildren && <span style={{ width: 12, flexShrink: 0 }} />}
        <span style={{ color: status.color, fontSize: 11, flexShrink: 0 }}>{tree.icon}</span>
        <span style={{
          color: isSelected ? "#e2e8f0" : "#94a3b8",
          fontSize: 13, fontFamily: "'Space Grotesk', sans-serif",
          flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          fontWeight: isSelected ? 500 : 400,
        }}>
          {tree.title}
        </span>
        <span style={{
          color: status.color, fontSize: 9, padding: "1px 6px",
          background: status.bg, borderRadius: 3,
          fontFamily: "'JetBrains Mono', monospace", flexShrink: 0,
        }}>
          {tree.wordCount ? (tree.wordCount / 1000).toFixed(1) + "k" : ""}
        </span>
      </div>
      {hasChildren && isExpanded && tree.children.map(child => (
        <StoryTree
          key={child.id} tree={child} selected={selected} onSelect={onSelect}
          depth={depth + 1} expanded={expanded} onToggle={onToggle}
        />
      ))}
    </div>
  );
}

// --- Breadcrumb Navigation ---
function Breadcrumb({ path, onNavigate }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 4, padding: "0 4px" }}>
      {path.map((item, i) => (
        <span key={item.id} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {i > 0 && <span style={{ color: "#2a2a3a", fontSize: 11 }}>›</span>}
          <span
            onClick={() => onNavigate(item.id, item)}
            style={{
              color: i === path.length - 1 ? "#e2e8f0" : "#4a4a5a",
              fontSize: 12, cursor: "pointer",
              fontFamily: "'JetBrains Mono', monospace",
              transition: "color 0.15s",
            }}
            onMouseEnter={e => e.currentTarget.style.color = "#c084fc"}
            onMouseLeave={e => e.currentTarget.style.color = i === path.length - 1 ? "#e2e8f0" : "#4a4a5a"}
          >
            {item.icon} {item.title.length > 25 ? item.title.slice(0, 25) + "…" : item.title}
          </span>
        </span>
      ))}
    </div>
  );
}

// --- Inline Luna Note ---
function LunaNote({ note }) {
  const typeColors = {
    continuity: { border: "#f87171", icon: "⚠", label: "CONTINUITY" },
    tone: { border: "#818cf8", icon: "♪", label: "TONE" },
    thematic: { border: "#c084fc", icon: "◇", label: "THEME" },
    production: { border: "#fbbf24", icon: "▲", label: "PRODUCTION" },
    character: { border: "#4ade80", icon: "◉", label: "CHARACTER" },
  };
  const t = typeColors[note.type] || typeColors.thematic;

  return (
    <div style={{
      display: "flex", gap: 10, padding: "8px 12px", marginBottom: 6,
      borderLeft: `2px solid ${t.border}`, borderRadius: "0 4px 4px 0",
      background: "rgba(18, 18, 26, 0.6)",
    }}>
      <span style={{ color: t.border, fontSize: 11, flexShrink: 0, fontFamily: "'JetBrains Mono', monospace" }}>
        {t.icon} {t.label}
      </span>
      <span style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.5, fontStyle: "italic" }}>
        {note.text}
      </span>
    </div>
  );
}

// --- Entity Mention (inline highlight) ---
function EntityMention({ name, color }) {
  return (
    <span style={{
      color, borderBottom: `1px dotted ${color}40`,
      cursor: "pointer", transition: "border-color 0.15s",
    }}
    onMouseEnter={e => e.currentTarget.style.borderBottomColor = color}
    onMouseLeave={e => e.currentTarget.style.borderBottomColor = color + "40"}
    >
      {name}
    </span>
  );
}

// --- Scene Editor (the main writing surface) ---
function SceneEditor({ scene, content }) {
  if (!content) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#4a4a5a" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>¶</div>
          <div style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: 16 }}>Select a scene to begin writing</div>
          <div style={{ fontSize: 13, marginTop: 8, color: "#2a2a3a" }}>or create a new scene with ⌘N</div>
        </div>
      </div>
    );
  }

  const fm = content.frontmatter;
  const lines = content.body.split("\n");

  const renderLine = (line, idx) => {
    const trimmed = line.trim();

    // Character name (ALL CAPS, standalone)
    if (/^[A-Z][A-Z\s]{2,}$/.test(trimmed)) {
      const entity = ENTITIES_BRIEF.find(e => e.name.toUpperCase() === trimmed);
      return (
        <div key={idx} style={{
          color: entity ? entity.color : "#e2e8f0",
          fontFamily: "'Space Grotesk', sans-serif",
          fontWeight: 600, fontSize: 14,
          paddingTop: 16, paddingBottom: 2,
          textAlign: "center", letterSpacing: "0.05em",
        }}>
          {trimmed}
        </div>
      );
    }

    // Parenthetical
    if (/^\(.*\)$/.test(trimmed)) {
      return (
        <div key={idx} style={{
          color: "#4a4a5a", fontStyle: "italic", fontSize: 13,
          textAlign: "center", padding: "1px 0",
        }}>
          {trimmed}
        </div>
      );
    }

    // Dialogue (line after a character name or parenthetical — heuristic: check previous non-empty)
    const prevNonEmpty = lines.slice(0, idx).filter(l => l.trim()).pop()?.trim() || "";
    const isAfterCharacter = /^[A-Z][A-Z\s]{2,}$/.test(prevNonEmpty) || /^\(.*\)$/.test(prevNonEmpty);
    if (isAfterCharacter && trimmed && !/^[A-Z][A-Z\s]{2,}$/.test(trimmed)) {
      return (
        <div key={idx} style={{
          color: "#e2e8f0", fontSize: 14, lineHeight: 1.7,
          textAlign: "center", maxWidth: "70%", margin: "0 auto",
          padding: "2px 0",
        }}>
          {trimmed}
        </div>
      );
    }

    // Empty line
    if (!trimmed) {
      return <div key={idx} style={{ height: 14 }} />;
    }

    // Action / Prose (default)
    return (
      <div key={idx} style={{
        color: "#cbd5e1", fontSize: 14, lineHeight: 1.8,
        padding: "2px 0",
        fontFamily: "'Crimson Pro', 'Georgia', serif",
      }}>
        {trimmed}
      </div>
    );
  };

  return (
    <div style={{ height: "100%", overflow: "auto" }}>
      {/* Frontmatter bar */}
      <div style={{
        display: "flex", gap: 12, padding: "10px 16px",
        borderBottom: "1px solid #1e1e2e", flexWrap: "wrap", alignItems: "center",
      }}>
        {fm.characters_present?.map(cid => {
          const ent = ENTITIES_BRIEF.find(e => e.id === cid);
          return ent ? (
            <span key={cid} style={{
              display: "flex", alignItems: "center", gap: 4, padding: "2px 8px",
              background: ent.color + "15", borderRadius: 3, border: `1px solid ${ent.color}30`,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: ent.color }} />
              <span style={{ color: ent.color, fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                {ent.name}
              </span>
            </span>
          ) : null;
        })}
        <span style={{ color: "#4a4a5a", fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
          ◎ {ENTITIES_BRIEF.find(e => e.id === fm.location)?.name || fm.location}
        </span>
        <span style={{ color: "#4a4a5a", fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
          ◑ {fm.time}
        </span>
        <span style={{
          marginLeft: "auto", color: STATUS[fm.status]?.color || "#64748b",
          fontSize: 10, padding: "2px 8px", borderRadius: 3,
          background: STATUS[fm.status]?.bg || "transparent",
          fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase",
        }}>
          {fm.status}
        </span>
      </div>

      {/* Writing surface */}
      <div style={{ padding: "32px 48px 80px", maxWidth: 720, margin: "0 auto" }}>
        {lines.map(renderLine)}
      </div>

      {/* Luna notes */}
      {content.lunaNotes && content.lunaNotes.length > 0 && (
        <div style={{ padding: "0 48px 48px", maxWidth: 720, margin: "0 auto" }}>
          <div style={{
            fontSize: 10, color: "#4a4a5a", fontFamily: "'JetBrains Mono', monospace",
            textTransform: "uppercase", letterSpacing: "0.1em",
            padding: "12px 0 8px", borderTop: "1px solid #1e1e2e",
            marginBottom: 8,
          }}>
            ☾ Luna's Notes
          </div>
          {content.lunaNotes.map((note, i) => <LunaNote key={i} note={note} />)}
        </div>
      )}
    </div>
  );
}

// --- CODEX Sidebar (entity quick-reference) ---
function CodexSidebar({ entities, sceneCharacters }) {
  const [filter, setFilter] = useState("scene");

  const filtered = filter === "scene"
    ? entities.filter(e => sceneCharacters?.includes(e.id))
    : filter === "characters"
      ? entities.filter(e => e.type === "character")
      : entities;

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{
        padding: "12px 12px 8px", borderBottom: "1px solid #1e1e2e",
        display: "flex", gap: 4,
      }}>
        {["scene", "characters", "all"].map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "3px 8px", borderRadius: 3, border: "none",
            background: filter === f ? "rgba(192, 132, 252, 0.15)" : "transparent",
            color: filter === f ? "#c084fc" : "#4a4a5a",
            fontSize: 10, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
            textTransform: "uppercase", letterSpacing: "0.05em",
          }}>
            {f}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 8 }}>
        {filtered.length === 0 ? (
          <div style={{ color: "#2a2a3a", fontSize: 12, textAlign: "center", paddingTop: 24 }}>
            No entities in current scope
          </div>
        ) : filtered.map(entity => (
          <div key={entity.id} style={{
            padding: "10px 12px", marginBottom: 4, borderRadius: 6,
            background: "rgba(18, 18, 26, 0.5)", cursor: "pointer",
            border: "1px solid transparent", transition: "border-color 0.15s",
          }}
          onMouseEnter={e => e.currentTarget.style.borderColor = entity.color + "40"}
          onMouseLeave={e => e.currentTarget.style.borderColor = "transparent"}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{
                width: 8, height: 8, borderRadius: "50%", background: entity.color, flexShrink: 0,
              }} />
              <span style={{
                color: "#e2e8f0", fontSize: 13, fontFamily: "'Space Grotesk', sans-serif", fontWeight: 500,
              }}>
                {entity.name}
              </span>
              <span style={{
                color: "#4a4a5a", fontSize: 10, fontFamily: "'JetBrains Mono', monospace", marginLeft: "auto",
              }}>
                {entity.type}
              </span>
            </div>
            <div style={{ color: "#64748b", fontSize: 11, paddingLeft: 16 }}>
              {entity.role} · {entity.scenes} scenes
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Agent Chat Panel ---
function AgentChat({ messages, agents }) {
  const [input, setInput] = useState("");
  const [localMessages, setLocalMessages] = useState(messages);
  const chatEnd = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [localMessages]);

  const handleSend = () => {
    if (!input.trim()) return;
    setLocalMessages(prev => [...prev, {
      id: Date.now(), agent: "user", text: input.trim(),
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    }]);
    setInput("");
  };

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Agent roster */}
      <div style={{
        padding: "10px 12px", borderBottom: "1px solid #1e1e2e",
        display: "flex", gap: 6, flexWrap: "wrap",
      }}>
        {agents.map(a => (
          <div key={a.id} style={{
            display: "flex", alignItems: "center", gap: 4, padding: "3px 8px",
            borderRadius: 3, background: a.status === "active" ? a.color + "15" : "transparent",
            border: `1px solid ${a.status === "active" ? a.color + "40" : "#1e1e2e"}`,
            cursor: "pointer",
          }}>
            <span style={{ fontSize: 11 }}>{a.avatar}</span>
            <span style={{
              color: a.status === "active" ? a.color : "#4a4a5a",
              fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            }}>
              {a.name}
            </span>
            <span style={{
              width: 5, height: 5, borderRadius: "50%",
              background: a.status === "active" ? a.color : "#2a2a3a",
            }} />
          </div>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflow: "auto", padding: "12px" }}>
        {localMessages.map(msg => {
          const agent = agents.find(a => a.id === msg.agent);
          const isUser = msg.agent === "user";

          return (
            <div key={msg.id} style={{
              marginBottom: 12,
              display: "flex", flexDirection: "column",
              alignItems: isUser ? "flex-end" : "flex-start",
            }}>
              {!isUser && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 4, marginBottom: 3,
                }}>
                  <span style={{ fontSize: 10 }}>{agent?.avatar}</span>
                  <span style={{
                    color: agent?.color || "#64748b", fontSize: 10,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}>
                    {agent?.name}
                  </span>
                  <span style={{ color: "#2a2a3a", fontSize: 9 }}>{msg.time}</span>
                </div>
              )}
              <div style={{
                padding: "8px 12px", borderRadius: isUser ? "10px 10px 2px 10px" : "10px 10px 10px 2px",
                background: isUser ? "rgba(192, 132, 252, 0.12)" : "rgba(18, 18, 26, 0.8)",
                border: `1px solid ${isUser ? "#c084fc20" : "#1e1e2e"}`,
                maxWidth: "85%",
              }}>
                <span style={{
                  color: isUser ? "#e2e8f0" : "#cbd5e1",
                  fontSize: 13, lineHeight: 1.5,
                }}>
                  {msg.text}
                </span>
              </div>
              {isUser && (
                <span style={{ color: "#2a2a3a", fontSize: 9, marginTop: 2 }}>{msg.time}</span>
              )}
            </div>
          );
        })}
        <div ref={chatEnd} />
      </div>

      {/* Input */}
      <div style={{
        padding: "10px 12px", borderTop: "1px solid #1e1e2e",
        display: "flex", gap: 8,
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleSend()}
          placeholder="Talk to your agents..."
          style={{
            flex: 1, padding: "8px 12px", borderRadius: 6,
            background: "rgba(10, 10, 15, 0.8)", border: "1px solid #1e1e2e",
            color: "#e2e8f0", fontSize: 13, outline: "none",
            fontFamily: "'Space Grotesk', sans-serif",
          }}
          onFocus={e => e.currentTarget.style.borderColor = "#c084fc40"}
          onBlur={e => e.currentTarget.style.borderColor = "#1e1e2e"}
        />
        <button
          onClick={handleSend}
          style={{
            padding: "8px 14px", borderRadius: 6, border: "none",
            background: input.trim() ? "rgba(192, 132, 252, 0.2)" : "transparent",
            color: input.trim() ? "#c084fc" : "#2a2a3a",
            cursor: input.trim() ? "pointer" : "default",
            fontSize: 13, fontFamily: "'Space Grotesk', sans-serif",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

// --- Word count bar ---
function WordCountBar({ scene, total }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, padding: "6px 16px",
      borderTop: "1px solid #1e1e2e", background: "rgba(10, 10, 15, 0.5)",
      fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "#4a4a5a",
    }}>
      <span>Scene: {scene?.toLocaleString() || "—"} words</span>
      <span style={{ color: "#2a2a3a" }}>|</span>
      <span>Project: {total?.toLocaleString() || "—"} words</span>
      <span style={{ marginLeft: "auto", color: "#2a2a3a" }}>⌘K commands · ⌘/ agents · ⌘B codex</span>
    </div>
  );
}


// ============================================================================
// Main App
// ============================================================================

export default function KozmoScribo() {
  const [selected, setSelected] = useState("sc_01");
  const [selectedNode, setSelectedNode] = useState(null);
  const [expanded, setExpanded] = useState(new Set(["dwm_root", "act_1", "ch_01", "ch_02", "ch_03"]));
  const [rightPanel, setRightPanel] = useState("chat"); // chat | codex
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);

  // Find node in tree
  const findNode = useCallback((tree, id) => {
    if (tree.id === id) return tree;
    if (tree.children) {
      for (const child of tree.children) {
        const found = findNode(child, id);
        if (found) return found;
      }
    }
    return null;
  }, []);

  // Build breadcrumb path
  const buildPath = useCallback((tree, id, trail = []) => {
    if (tree.id === id) return [...trail, tree];
    if (tree.children) {
      for (const child of tree.children) {
        const found = buildPath(child, id, [...trail, tree]);
        if (found) return found;
      }
    }
    return null;
  }, []);

  const currentNode = findNode(STORY_TREE, selected);
  const breadcrumb = buildPath(STORY_TREE, selected) || [];
  const content = SCENE_CONTENT[selected] || null;

  const handleSelect = (id, node) => {
    setSelected(id);
    setSelectedNode(node);
  };

  const handleToggle = (id) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const sceneCharacters = content?.frontmatter?.characters_present || [];

  return (
    <div style={{
      width: "100%", height: "100vh", display: "flex", flexDirection: "column",
      background: "#0a0a0f", color: "#e2e8f0",
      fontFamily: "'Space Grotesk', -apple-system, sans-serif",
    }}>
      {/* Google Fonts */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400;500&family=Crimson+Pro:ital,wght@0,300;0,400;0,500;1,300;1,400&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1e1e2e; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #2a2a3a; }
        ::selection { background: rgba(192, 132, 252, 0.25); }
      `}</style>

      {/* Top bar */}
      <div style={{
        display: "flex", alignItems: "center", height: 40,
        borderBottom: "1px solid #1e1e2e", padding: "0 12px",
        background: "rgba(10, 10, 15, 0.8)", backdropFilter: "blur(12px)",
        gap: 12, flexShrink: 0,
      }}>
        {/* Mode badge */}
        <div style={{
          display: "flex", alignItems: "center", gap: 6,
          padding: "3px 10px", borderRadius: 4,
          background: "rgba(192, 132, 252, 0.1)",
          border: "1px solid rgba(192, 132, 252, 0.2)",
        }}>
          <span style={{ color: "#c084fc", fontSize: 12, fontWeight: 600, letterSpacing: "0.08em" }}>
            SCRIBO
          </span>
        </div>

        {/* Breadcrumb */}
        <Breadcrumb path={breadcrumb} onNavigate={handleSelect} />

        <div style={{ flex: 1 }} />

        {/* Mode switcher */}
        {["SCRIBO", "CODEX", "LAB"].map(mode => (
          <span key={mode} style={{
            color: mode === "SCRIBO" ? "#c084fc" : "#2a2a3a",
            fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
            cursor: "pointer", letterSpacing: "0.08em",
            padding: "3px 6px", borderRadius: 3,
            background: mode === "SCRIBO" ? "rgba(192, 132, 252, 0.08)" : "transparent",
          }}>
            {mode}
          </span>
        ))}
      </div>

      {/* Main content */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left: Story tree */}
        {!leftCollapsed && (
          <div style={{
            width: 260, borderRight: "1px solid #1e1e2e", display: "flex", flexDirection: "column",
            background: "rgba(10, 10, 15, 0.4)", flexShrink: 0,
          }}>
            <div style={{
              padding: "10px 12px", borderBottom: "1px solid #1e1e2e",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}>
              <span style={{
                fontSize: 10, color: "#4a4a5a", fontFamily: "'JetBrains Mono', monospace",
                textTransform: "uppercase", letterSpacing: "0.1em",
              }}>
                Story
              </span>
              <span
                onClick={() => setLeftCollapsed(true)}
                style={{ color: "#2a2a3a", fontSize: 12, cursor: "pointer" }}
              >
                ◂
              </span>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "4px 0" }}>
              <StoryTree
                tree={STORY_TREE} selected={selected} onSelect={handleSelect}
                expanded={expanded} onToggle={handleToggle}
              />
            </div>

            {/* Quick stats */}
            <div style={{
              padding: "10px 12px", borderTop: "1px solid #1e1e2e",
              display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4,
            }}>
              {[
                { label: "Scenes", value: "12" },
                { label: "Words", value: "28.4k" },
                { label: "Polished", value: "3" },
                { label: "Draft", value: "4" },
              ].map(s => (
                <div key={s.label} style={{
                  padding: "4px 8px", borderRadius: 3,
                  background: "rgba(18, 18, 26, 0.5)",
                }}>
                  <div style={{ color: "#2a2a3a", fontSize: 9, fontFamily: "'JetBrains Mono', monospace" }}>
                    {s.label}
                  </div>
                  <div style={{ color: "#64748b", fontSize: 14, fontWeight: 500 }}>{s.value}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Collapse toggle (left) */}
        {leftCollapsed && (
          <div
            onClick={() => setLeftCollapsed(false)}
            style={{
              width: 24, borderRight: "1px solid #1e1e2e",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", color: "#2a2a3a", fontSize: 12,
              background: "rgba(10, 10, 15, 0.4)",
            }}
          >
            ▸
          </div>
        )}

        {/* Center: Editor */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <SceneEditor scene={currentNode} content={content} />
          <WordCountBar scene={currentNode?.wordCount} total={STORY_TREE.wordCount} />
        </div>

        {/* Collapse toggle (right) */}
        {rightCollapsed && (
          <div
            onClick={() => setRightCollapsed(false)}
            style={{
              width: 24, borderLeft: "1px solid #1e1e2e",
              display: "flex", alignItems: "center", justifyContent: "center",
              cursor: "pointer", color: "#2a2a3a", fontSize: 12,
              background: "rgba(10, 10, 15, 0.4)",
            }}
          >
            ◂
          </div>
        )}

        {/* Right: Chat or Codex */}
        {!rightCollapsed && (
          <div style={{
            width: 300, borderLeft: "1px solid #1e1e2e", display: "flex", flexDirection: "column",
            background: "rgba(10, 10, 15, 0.4)", flexShrink: 0,
          }}>
            <div style={{
              padding: "10px 12px", borderBottom: "1px solid #1e1e2e",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              {[
                { id: "chat", label: "AGENTS", icon: "◈" },
                { id: "codex", label: "CODEX", icon: "◆" },
              ].map(tab => (
                <button key={tab.id} onClick={() => setRightPanel(tab.id)} style={{
                  flex: 1, padding: "4px 8px", borderRadius: 3, border: "none",
                  background: rightPanel === tab.id ? "rgba(192, 132, 252, 0.12)" : "transparent",
                  color: rightPanel === tab.id ? "#c084fc" : "#4a4a5a",
                  fontSize: 10, cursor: "pointer", fontFamily: "'JetBrains Mono', monospace",
                  letterSpacing: "0.05em", display: "flex", alignItems: "center",
                  justifyContent: "center", gap: 4,
                }}>
                  <span>{tab.icon}</span> {tab.label}
                </button>
              ))}
              <span
                onClick={() => setRightCollapsed(true)}
                style={{ color: "#2a2a3a", fontSize: 12, cursor: "pointer", marginLeft: 4 }}
              >
                ▸
              </span>
            </div>
            <div style={{ flex: 1, overflow: "hidden" }}>
              {rightPanel === "chat" ? (
                <AgentChat messages={INITIAL_CHAT} agents={AGENTS} />
              ) : (
                <CodexSidebar entities={ENTITIES_BRIEF} sceneCharacters={sceneCharacters} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

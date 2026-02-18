import { useState, useEffect, useRef } from "react";

const COLORS = {
  bg: "#0a0a0f",
  bgCard: "#12121a",
  bgCardHover: "#1a1a28",
  accent: "#c8ff00",
  accentDim: "#4a5f00",
  eden: "#00d4aa",
  edenDim: "#004d3d",
  luna: "#a78bfa",
  lunaDim: "#3d2d6b",
  text: "#e8e8f0",
  textMuted: "#6b6b80",
  textDim: "#3a3a50",
  border: "#1e1e2e",
  danger: "#ff4757",
};

const fonts = {
  display: "'Instrument Serif', Georgia, serif",
  body: "'DM Sans', 'Helvetica Neue', sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', monospace",
};

const sections = [
  "overview",
  "problem",
  "kozmo",
  "architecture",
  "storyLab",
  "agents",
  "partnership",
  "roadmap",
];

const sectionLabels = {
  overview: "Overview",
  problem: "The Problem",
  kozmo: "KOZMO",
  architecture: "Architecture",
  storyLab: "The Story Lab",
  agents: "Agent Fleet",
  partnership: "Partnership",
  roadmap: "Roadmap",
};

// ─── NAV ───
function Nav({ active, onNav }) {
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 100,
        background: `${COLORS.bg}ee`,
        backdropFilter: "blur(20px)",
        borderBottom: `1px solid ${COLORS.border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 32px",
        height: 56,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontFamily: fonts.mono,
            fontSize: 11,
            color: COLORS.accent,
            letterSpacing: 4,
            fontWeight: 700,
          }}
        >
          KOZMO
        </span>
        <span
          style={{
            fontFamily: fonts.mono,
            fontSize: 10,
            color: COLORS.textDim,
            letterSpacing: 2,
          }}
        >
          × EDEN
        </span>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {sections.map((s) => (
          <button
            key={s}
            onClick={() => onNav(s)}
            style={{
              background:
                active === s ? `${COLORS.accent}15` : "transparent",
              border:
                active === s
                  ? `1px solid ${COLORS.accent}40`
                  : "1px solid transparent",
              color: active === s ? COLORS.accent : COLORS.textMuted,
              fontFamily: fonts.mono,
              fontSize: 10,
              padding: "6px 12px",
              borderRadius: 6,
              cursor: "pointer",
              letterSpacing: 0.5,
              transition: "all 0.2s",
            }}
          >
            {sectionLabels[s]}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── HERO / OVERVIEW ───
function Overview() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    setTimeout(() => setShow(true), 100);
  }, []);
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background grid */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(${COLORS.border}40 1px, transparent 1px),
            linear-gradient(90deg, ${COLORS.border}40 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          opacity: 0.4,
        }}
      />
      {/* Radial glow */}
      <div
        style={{
          position: "absolute",
          width: 800,
          height: 800,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accent}08 0%, transparent 70%)`,
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
      />

      <div
        style={{
          position: "relative",
          textAlign: "center",
          opacity: show ? 1 : 0,
          transform: show ? "translateY(0)" : "translateY(30px)",
          transition: "all 1.2s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 12,
            color: COLORS.textMuted,
            letterSpacing: 6,
            marginBottom: 24,
          }}
        >
          INTRODUCING
        </div>
        <h1
          style={{
            fontFamily: fonts.display,
            fontSize: 120,
            fontWeight: 400,
            color: COLORS.text,
            margin: 0,
            lineHeight: 0.9,
            letterSpacing: -3,
          }}
        >
          KOZMO
        </h1>
        <div
          style={{
            fontFamily: fonts.display,
            fontSize: 28,
            color: COLORS.textMuted,
            fontStyle: "italic",
            marginTop: 16,
            letterSpacing: 1,
          }}
        >
          The AI Creative Studio That Remembers
        </div>

        <div
          style={{
            display: "flex",
            gap: 48,
            justifyContent: "center",
            marginTop: 64,
            opacity: show ? 1 : 0,
            transition: "opacity 1s 0.6s",
          }}
        >
          {[
            { label: "LUNA", sub: "Creative Intelligence", color: COLORS.luna },
            { label: "ECLISSI", sub: "Platform & Memory", color: COLORS.text },
            { label: "EDEN", sub: "Rendering Muscle", color: COLORS.eden },
          ].map((item) => (
            <div key={item.label} style={{ textAlign: "center" }}>
              <div
                style={{
                  fontFamily: fonts.mono,
                  fontSize: 14,
                  color: item.color,
                  letterSpacing: 3,
                  fontWeight: 600,
                }}
              >
                {item.label}
              </div>
              <div
                style={{
                  fontFamily: fonts.body,
                  fontSize: 13,
                  color: COLORS.textMuted,
                  marginTop: 4,
                }}
              >
                {item.sub}
              </div>
            </div>
          ))}
        </div>

        <div
          style={{
            marginTop: 80,
            fontFamily: fonts.body,
            fontSize: 15,
            color: COLORS.textDim,
            maxWidth: 500,
            lineHeight: 1.7,
            margin: "80px auto 0",
          }}
        >
          A partnership proposal from Ahab (Luna/Eclissi) to Eden
        </div>
      </div>
    </div>
  );
}

// ─── THE PROBLEM ───
function Problem() {
  const gaps = [
    {
      tool: "Dashtoon / LlamaGen / Fotor",
      does: "Generate panels from prompts",
      missing: "No memory. No story structure. No creative partnership. Start from zero every project.",
    },
    {
      tool: "Adobe Firefly",
      does: "Reference-based generation + layout",
      missing: "Walled garden. No narrative intelligence. Can't trace creative decisions across sessions.",
    },
    {
      tool: "Shai Creative / Boords",
      does: "Script → storyboard with collaboration",
      missing: "Pre-production only. No generative pipeline. Can't execute the vision, only plan it.",
    },
    {
      tool: "Clip Studio Paint",
      does: "Professional comic production (industry standard)",
      missing: "Zero AI. Pure manual craft. Amazing for finishing, impossible for ideation at speed.",
    },
  ];

  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="THE PROBLEM" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 24px",
          maxWidth: 700,
          lineHeight: 1.15,
        }}
      >
        Every AI creative tool has amnesia
      </h2>
      <p
        style={{
          fontFamily: fonts.body,
          fontSize: 17,
          color: COLORS.textMuted,
          maxWidth: 600,
          lineHeight: 1.7,
          marginBottom: 56,
        }}
      >
        Existing tools generate images. None of them understand story. They
        can't hold a creative vision across sessions, trace consequences of
        narrative changes, or accumulate understanding of your aesthetic over
        time.
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {gaps.map((g) => (
          <div
            key={g.tool}
            style={{
              display: "grid",
              gridTemplateColumns: "220px 260px 1fr",
              gap: 24,
              padding: "20px 24px",
              background: COLORS.bgCard,
              borderRadius: 10,
              border: `1px solid ${COLORS.border}`,
            }}
          >
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 12,
                color: COLORS.textMuted,
              }}
            >
              {g.tool}
            </div>
            <div
              style={{
                fontFamily: fonts.body,
                fontSize: 13,
                color: COLORS.text,
                lineHeight: 1.5,
              }}
            >
              {g.does}
            </div>
            <div
              style={{
                fontFamily: fonts.body,
                fontSize: 13,
                color: COLORS.danger,
                lineHeight: 1.5,
                opacity: 0.8,
              }}
            >
              {g.missing}
            </div>
          </div>
        ))}
      </div>

      <div
        style={{
          marginTop: 56,
          padding: "32px 36px",
          background: `linear-gradient(135deg, ${COLORS.accent}08, ${COLORS.eden}08)`,
          borderRadius: 12,
          border: `1px solid ${COLORS.accent}20`,
          maxWidth: 700,
        }}
      >
        <div
          style={{
            fontFamily: fonts.display,
            fontSize: 24,
            color: COLORS.text,
            fontStyle: "italic",
            lineHeight: 1.5,
          }}
        >
          "Remember that noir style from the Kira project? Apply that to this
          new thing."
        </div>
        <div
          style={{
            fontFamily: fonts.body,
            fontSize: 14,
            color: COLORS.textMuted,
            marginTop: 12,
          }}
        >
          No existing tool can do this. KOZMO can.
        </div>
      </div>
    </div>
  );
}

// ─── WHAT IS KOZMO ───
function WhatIsKozmo() {
  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="THE PRODUCT" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 48px",
          lineHeight: 1.15,
        }}
      >
        KOZMO is a creative studio, not a generator
      </h2>

      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}
      >
        <Card
          accent={COLORS.accent}
          title="Chaos → Canon → Execution"
          body="The creative process isn't linear. You brainstorm, worldbuild, tear things down, rebuild. KOZMO holds the entire creative state — the story as source of truth — and renders any output format from it. Comic books. Storyboards. Concept art. Video. The story is the product. Everything else is a rendering."
        />
        <Card
          accent={COLORS.luna}
          title="Luna: The Orchestrator"
          body="An AI companion with persistent memory that acts as creative partner and agent foreman. She doesn't generate art or write story — she translates your creative intent into agent work orders, manages the execution fleet, and holds the narrative intelligence that accumulates over months of collaboration."
        />
        <Card
          accent={COLORS.eden}
          title="Eden: The Render Farm"
          body="Specialized agents powered by Eden's API — Flux Kontext for images, Kling for video, ElevenLabs for voice, training pipelines for character LoRAs. Agents are stateless chess pieces that Luna dispatches with rich context. They produce artifacts. They don't think about story."
        />
        <Card
          accent={COLORS.text}
          title="Eclissi: The Substrate"
          body="Memory Matrix (graph + FTS5 + vectors), tool routing (T0-T4 tiers), process management, credential vault. The infrastructure that makes persistent creative intelligence possible. Every creative decision, every killed darling, every style evolution — stored, traversable, recoverable."
        />
      </div>

      {/* The Sentence */}
      <div
        style={{
          marginTop: 56,
          padding: "28px 36px",
          background: COLORS.bgCard,
          borderRadius: 12,
          border: `1px solid ${COLORS.border}`,
        }}
      >
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 10,
            color: COLORS.textDim,
            letterSpacing: 3,
            marginBottom: 12,
          }}
        >
          ONE SENTENCE
        </div>
        <div
          style={{
            fontFamily: fonts.display,
            fontSize: 22,
            color: COLORS.text,
            lineHeight: 1.6,
            fontStyle: "italic",
          }}
        >
          "Hey Luna, make me another image like that cyberpunk thing from last
          week but with a samurai vibe."
        </div>
        <div
          style={{
            display: "flex",
            gap: 24,
            marginTop: 16,
            fontFamily: fonts.mono,
            fontSize: 11,
          }}
        >
          <span style={{ color: COLORS.luna }}>
            Luna → voice + orchestration
          </span>
          <span style={{ color: COLORS.text }}>
            Eclissi → memory recall + routing
          </span>
          <span style={{ color: COLORS.eden }}>
            Eden → generation with style reference
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── ARCHITECTURE ───
function Architecture() {
  const [hover, setHover] = useState(null);

  const nodes = [
    {
      id: "you",
      x: 400,
      y: 60,
      label: "YOU",
      sub: "Creative Director",
      color: COLORS.accent,
      r: 36,
    },
    {
      id: "luna",
      x: 400,
      y: 190,
      label: "LUNA",
      sub: "Orchestrator",
      color: COLORS.luna,
      r: 40,
    },
    {
      id: "kozmo",
      x: 180,
      y: 330,
      label: "KOZMO",
      sub: "Story Lab UI",
      color: COLORS.accent,
      r: 36,
    },
    {
      id: "eclissi",
      x: 400,
      y: 330,
      label: "ECLISSI",
      sub: "Memory + Routing",
      color: COLORS.text,
      r: 36,
    },
    {
      id: "eden",
      x: 620,
      y: 330,
      label: "EDEN",
      sub: "Agent Fleet",
      color: COLORS.eden,
      r: 36,
    },
    {
      id: "memory",
      x: 300,
      y: 455,
      label: "MEMORY",
      sub: "Matrix Graph",
      color: COLORS.textMuted,
      r: 30,
    },
    {
      id: "agents",
      x: 700,
      y: 455,
      label: "AGENTS",
      sub: "Render Workers",
      color: COLORS.edenDim,
      r: 30,
    },
    {
      id: "chiba",
      x: 620,
      y: 190,
      label: "CHIBA",
      sub: "Eden Orchestrator",
      color: COLORS.eden,
      r: 36,
    },
  ];

  const edges = [
    { from: "you", to: "luna", label: "creative intent" },
    { from: "luna", to: "kozmo", label: "UI state" },
    { from: "luna", to: "eclissi", label: "MCP" },
    { from: "luna", to: "chiba", label: "partners" },
    { from: "chiba", to: "eden", label: "orchestrates" },
    { from: "eclissi", to: "memory", label: "graph ops" },
    { from: "eden", to: "agents", label: "dispatch" },
    { from: "kozmo", to: "eclissi", label: "hosted in" },
  ];

  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="ARCHITECTURE" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 48px",
          lineHeight: 1.15,
        }}
      >
        Two hemispheres, one brain
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 48,
          alignItems: "start",
        }}
      >
        <svg viewBox="0 0 860 520" style={{ width: "100%" }}>
          <defs>
            <marker
              id="arrow"
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill={COLORS.textDim} />
            </marker>
          </defs>

          {/* Zones */}
          <rect
            x={80}
            y={270}
            width={390}
            height={220}
            rx={16}
            fill={COLORS.luna + "08"}
            stroke={COLORS.luna + "20"}
            strokeDasharray="4 4"
          />
          <text
            x={100}
            y={295}
            fill={COLORS.luna + "40"}
            fontSize={10}
            fontFamily={fonts.mono}
          >
            LUNA / ECLISSI
          </text>

          <rect
            x={530}
            y={270}
            width={195}
            height={220}
            rx={16}
            fill={COLORS.eden + "08"}
            stroke={COLORS.eden + "20"}
            strokeDasharray="4 4"
          />
          <text
            x={550}
            y={295}
            fill={COLORS.eden + "40"}
            fontSize={10}
            fontFamily={fonts.mono}
          >
            EDEN / CHIBA
          </text>

          {edges.map((e, i) => {
            const from = nodes.find((n) => n.id === e.from);
            const to = nodes.find((n) => n.id === e.to);
            const mx = (from.x + to.x) / 2;
            const my = (from.y + to.y) / 2;
            return (
              <g key={i}>
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  stroke={COLORS.textDim}
                  strokeWidth={1}
                  markerEnd="url(#arrow)"
                  opacity={0.5}
                />
                <text
                  x={mx}
                  y={my - 6}
                  fill={COLORS.textDim}
                  fontSize={9}
                  fontFamily={fonts.mono}
                  textAnchor="middle"
                >
                  {e.label}
                </text>
              </g>
            );
          })}

          {nodes.map((n) => (
            <g
              key={n.id}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
              style={{ cursor: "pointer" }}
            >
              <circle
                cx={n.x}
                cy={n.y}
                r={hover === n.id ? n.r + 4 : n.r}
                fill={n.color + "15"}
                stroke={n.color + "60"}
                strokeWidth={hover === n.id ? 2 : 1}
                style={{ transition: "all 0.2s" }}
              />
              <text
                x={n.x}
                y={n.y - 4}
                fill={n.color}
                fontSize={11}
                fontFamily={fonts.mono}
                textAnchor="middle"
                fontWeight={600}
              >
                {n.label}
              </text>
              <text
                x={n.x}
                y={n.y + 10}
                fill={COLORS.textMuted}
                fontSize={9}
                fontFamily={fonts.body}
                textAnchor="middle"
              >
                {n.sub}
              </text>
            </g>
          ))}
        </svg>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <ArchRow
            label="Protocol"
            items={[
              "Luna ↔ Eclissi: MCP (20+ tools, already built)",
              "Luna ↔ Eden: REST (Eden's native API)",
              "KOZMO ↔ Eclissi: hosted inside, direct access",
            ]}
          />
          <ArchRow
            label="Memory"
            items={[
              "L1 Hot: Luna's context window (4K tokens)",
              "L2 Warm: Memory Matrix graph + FTS5 (24h)",
              "L3 Cold: Archived summaries (30d+)",
              "L4 External: Eden creation refs (new node type)",
            ]}
          />
          <ArchRow
            label="Roles"
            items={[
              "Luna + Eclissi: creative intelligence + platform",
              "Eden + Chiba: generation muscle + agent orchestration",
              "KOZMO: co-developed product, jointly shaped",
              "Clean integration boundary — both sides evolve independently",
            ]}
          />
        </div>
      </div>
    </div>
  );
}

// ─── STORY LAB ───
function StoryLab() {
  const [activeView, setActiveView] = useState("story");

  const views = [
    {
      id: "story",
      label: "Story View",
      icon: "📖",
      desc: "Screenplay / script layer. Scenes, dialogue, beats, pacing. The narrative as experienced.",
    },
    {
      id: "world",
      label: "World Builder",
      icon: "🌍",
      desc: "Settings, rules, lore, factions, locations. The universe the story lives in.",
    },
    {
      id: "character",
      label: "Character Lab",
      icon: "👤",
      desc: "Bios, arcs, relationships, visual refs, voice profiles. Deep entity per character.",
    },
    {
      id: "output",
      label: "Output Preview",
      icon: "🎨",
      desc: "Rendered artifacts — comic pages, concept art, storyboards, video. The gallery.",
    },
  ];

  const tools = [
    {
      id: "timeline",
      label: "Timeline",
      desc: "Temporal view. Drag scenes, see parallel plots, identify pacing issues.",
    },
    {
      id: "pathway",
      label: "Pathway Nodes",
      desc: "Graph view. Story elements as nodes, relationships as edges. Cause-and-effect exploration.",
    },
    {
      id: "arc",
      label: "Story Arc",
      desc: "Narrative shape overlay. Tension curves, act breaks, beat mapping.",
    },
    {
      id: "relations",
      label: "Relationship Web",
      desc: "Character connections. Dynamic per beat — who knows what, who wants what.",
    },
    {
      id: "mood",
      label: "Mood Board",
      desc: "Curated references. Images, video, audio, text. Tagged and linkable to Canon.",
    },
    {
      id: "graveyard",
      label: "Graveyard",
      desc: "Cut content archive. Fully navigable, fully restorable. Every killed darling preserved.",
    },
  ];

  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="THE STORY LAB" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 16px",
          lineHeight: 1.15,
        }}
      >
        Where creative work actually happens
      </h2>
      <p
        style={{
          fontFamily: fonts.body,
          fontSize: 15,
          color: COLORS.textMuted,
          maxWidth: 600,
          lineHeight: 1.7,
          marginBottom: 48,
        }}
      >
        KOZMO's Story Lab is a standalone application inside Eclissi. Multiple
        views into the same project graph. Different lenses, same truth.
      </p>

      {/* Views */}
      <div
        style={{
          fontFamily: fonts.mono,
          fontSize: 10,
          color: COLORS.textDim,
          letterSpacing: 3,
          marginBottom: 16,
        }}
      >
        VIEWS
      </div>
      <div
        style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 40 }}
      >
        {views.map((v) => (
          <button
            key={v.id}
            onClick={() => setActiveView(v.id)}
            style={{
              background:
                activeView === v.id ? `${COLORS.accent}12` : COLORS.bgCard,
              border:
                activeView === v.id
                  ? `1px solid ${COLORS.accent}40`
                  : `1px solid ${COLORS.border}`,
              borderRadius: 10,
              padding: "20px 18px",
              cursor: "pointer",
              textAlign: "left",
              transition: "all 0.2s",
            }}
          >
            <div style={{ fontSize: 22, marginBottom: 8 }}>{v.icon}</div>
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 12,
                color:
                  activeView === v.id ? COLORS.accent : COLORS.text,
                marginBottom: 6,
              }}
            >
              {v.label}
            </div>
            <div
              style={{
                fontFamily: fonts.body,
                fontSize: 12,
                color: COLORS.textMuted,
                lineHeight: 1.5,
              }}
            >
              {v.desc}
            </div>
          </button>
        ))}
      </div>

      {/* Tools */}
      <div
        style={{
          fontFamily: fonts.mono,
          fontSize: 10,
          color: COLORS.textDim,
          letterSpacing: 3,
          marginBottom: 16,
        }}
      >
        TOOLS
      </div>
      <div
        style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}
      >
        {tools.map((t) => (
          <div
            key={t.id}
            style={{
              background: COLORS.bgCard,
              border: `1px solid ${COLORS.border}`,
              borderRadius: 10,
              padding: "16px 18px",
            }}
          >
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 12,
                color: COLORS.text,
                marginBottom: 6,
              }}
            >
              {t.label}
            </div>
            <div
              style={{
                fontFamily: fonts.body,
                fontSize: 12,
                color: COLORS.textMuted,
                lineHeight: 1.5,
              }}
            >
              {t.desc}
            </div>
          </div>
        ))}
      </div>

      {/* Data Model */}
      <div
        style={{
          marginTop: 40,
          padding: "24px 28px",
          background: COLORS.bgCard,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 12,
        }}
      >
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 10,
            color: COLORS.textDim,
            letterSpacing: 3,
            marginBottom: 16,
          }}
        >
          PROJECT DATA MODEL
        </div>
        <pre
          style={{
            fontFamily: fonts.mono,
            fontSize: 12,
            color: COLORS.textMuted,
            lineHeight: 1.8,
            margin: 0,
            whiteSpace: "pre-wrap",
          }}
        >
{`PROJECT
├── SOURCES  (raw inputs — screenplays, sketches, video, voice memos, mood refs)
├── CANON    (the current truth)
│   ├── World       (settings, rules, locations, era)
│   ├── Characters  (bios, arcs, relationships, visual refs)
│   ├── Narrative   (theme, structure, scenes — draft/locked/cut)
│   └── Style       (visual direction, tone, locked references)
├── GRAVEYARD  (killed darlings — preserved with full context, restorable)
└── OUTPUTS    (rendered artifacts — comic pages, concept art, storyboards, video)`}
        </pre>
      </div>
    </div>
  );
}

// ─── AGENT FLEET ───
function AgentFleet() {
  const [selectedAgent, setSelectedAgent] = useState(0);

  const agents = [
    {
      name: "Concept Artist",
      color: COLORS.eden,
      eden_tool: "flux_kontext",
      input: "Scene description + style ref + mood anchors",
      output: "Environment / concept art images",
      example: "\"Rain district at night, heavy ink noir, neon reflections on wet pavement\"",
    },
    {
      name: "Character Designer",
      color: COLORS.eden,
      eden_tool: "flux_kontext + training",
      input: "Character description + existing refs",
      output: "Reference sheets (front/side/expressions), optional LoRA",
      example: "\"Kira: mid-20s, short white hair, cybernetic left arm, leather jacket — generate ref sheet\"",
    },
    {
      name: "Panel Renderer",
      color: COLORS.eden,
      eden_tool: "flux_kontext",
      input: "Panel spec + character refs + style lock + camera grammar",
      output: "Individual comic panel (clean art, no text)",
      example: "\"Medium shot, Kira and Informant face-off, rain, tense — use panel_renderer agent\"",
    },
    {
      name: "Video Producer",
      color: COLORS.eden,
      eden_tool: "kling",
      input: "Scene description or storyboard frames as keyframes",
      output: "Short video clip / animatic",
      example: "\"30 second chase sequence through rain district — rough motion, storyboard frames as keys\"",
    },
    {
      name: "Page Compositor",
      color: COLORS.accent,
      eden_tool: "local (Python + Pillow)",
      input: "Panel images + layout template + dialogue data",
      output: "Assembled comic page with gutters, bubbles, text",
      example: "\"Assemble page 3: 6 panels, noir gutters, speech bubbles from scene 14 dialogue\"",
    },
    {
      name: "Custom Agent ✦",
      color: COLORS.textMuted,
      eden_tool: "user-defined",
      input: "Whatever you specify",
      output: "Whatever you need",
      example: "\"You describe it. Luna helps you build the instruction set. Eden provides the runtime.\"",
    },
  ];

  const a = agents[selectedAgent];

  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="AGENT FLEET" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 16px",
          lineHeight: 1.15,
        }}
      >
        Luna's chess pieces
      </h2>
      <p
        style={{
          fontFamily: fonts.body,
          fontSize: 15,
          color: COLORS.textMuted,
          maxWidth: 650,
          lineHeight: 1.7,
          marginBottom: 48,
        }}
      >
        Eden's global orchestration agent <strong style={{ color: COLORS.eden }}>Chiba</strong> is 
        the agent fleet commander — like Claude Code but specialized for creative 
        production. Chiba's library of functions manipulates agents, tunes parameters, 
        chains pipelines, and handles complex multi-agent coordination. Luna partners 
        with Chiba to translate creative intent into executed work. Luna knows the 
        story. Chiba knows the tools.
      </p>

      <div style={{ display: "flex", gap: 24 }}>
        {/* Agent selector */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
            minWidth: 200,
          }}
        >
          {agents.map((ag, i) => (
            <button
              key={i}
              onClick={() => setSelectedAgent(i)}
              style={{
                background:
                  selectedAgent === i
                    ? `${ag.color}12`
                    : "transparent",
                border:
                  selectedAgent === i
                    ? `1px solid ${ag.color}40`
                    : `1px solid transparent`,
                borderRadius: 8,
                padding: "10px 14px",
                textAlign: "left",
                cursor: "pointer",
                fontFamily: fonts.mono,
                fontSize: 12,
                color:
                  selectedAgent === i ? ag.color : COLORS.textMuted,
                transition: "all 0.15s",
              }}
            >
              {ag.name}
            </button>
          ))}
        </div>

        {/* Agent detail */}
        <div
          style={{
            flex: 1,
            background: COLORS.bgCard,
            border: `1px solid ${a.color}30`,
            borderRadius: 12,
            padding: "28px 32px",
          }}
        >
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: 18,
              color: a.color,
              marginBottom: 24,
              letterSpacing: 1,
            }}
          >
            {a.name}
          </div>

          {[
            { label: "EDEN TOOL", value: a.eden_tool },
            { label: "INPUT", value: a.input },
            { label: "OUTPUT", value: a.output },
          ].map((row) => (
            <div key={row.label} style={{ marginBottom: 16 }}>
              <div
                style={{
                  fontFamily: fonts.mono,
                  fontSize: 9,
                  color: COLORS.textDim,
                  letterSpacing: 2,
                  marginBottom: 4,
                }}
              >
                {row.label}
              </div>
              <div
                style={{
                  fontFamily: fonts.body,
                  fontSize: 14,
                  color: COLORS.text,
                  lineHeight: 1.5,
                }}
              >
                {row.value}
              </div>
            </div>
          ))}

          <div
            style={{
              marginTop: 20,
              padding: "14px 18px",
              background: `${a.color}08`,
              borderRadius: 8,
              border: `1px solid ${a.color}15`,
            }}
          >
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 9,
                color: COLORS.textDim,
                letterSpacing: 2,
                marginBottom: 6,
              }}
            >
              EXAMPLE DISPATCH
            </div>
            <div
              style={{
                fontFamily: fonts.display,
                fontSize: 15,
                color: COLORS.textMuted,
                fontStyle: "italic",
                lineHeight: 1.5,
              }}
            >
              {a.example}
            </div>
          </div>
        </div>
      </div>

      {/* Luna + Chiba Partnership */}
      <div
        style={{
          marginTop: 40,
          padding: "24px 28px",
          background: `linear-gradient(135deg, ${COLORS.luna}06, ${COLORS.eden}06)`,
          border: `1px solid ${COLORS.luna}15`,
          borderRadius: 12,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 10,
            color: COLORS.textDim,
            letterSpacing: 3,
            marginBottom: 16,
          }}
        >
          LUNA + CHIBA — THE PARTNERSHIP IN ACTION
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 20, alignItems: "start" }}>
          <div>
            <div style={{ fontFamily: fonts.mono, fontSize: 12, color: COLORS.luna, marginBottom: 8 }}>
              LUNA knows...
            </div>
            {["The story and narrative context", "Character relationships & arcs", "Creative history & style evolution", "Your aesthetic preferences", "What's in the Graveyard"].map((item, i) => (
              <div key={i} style={{ fontFamily: fonts.body, fontSize: 12, color: COLORS.textMuted, lineHeight: 1.8, paddingLeft: 10, borderLeft: `2px solid ${COLORS.luna}25` }}>
                {item}
              </div>
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, paddingTop: 28 }}>
            <div style={{ fontFamily: fonts.mono, fontSize: 18, color: COLORS.accent }}>⇄</div>
            <div style={{ fontFamily: fonts.mono, fontSize: 9, color: COLORS.textDim, letterSpacing: 1 }}>PARTNER</div>
          </div>
          <div>
            <div style={{ fontFamily: fonts.mono, fontSize: 12, color: COLORS.eden, marginBottom: 8 }}>
              CHIBA knows...
            </div>
            {["Agent capabilities & parameters", "Pipeline optimization & chaining", "Eden tool functions & limits", "How to tune generation settings", "Complex multi-agent coordination"].map((item, i) => (
              <div key={i} style={{ fontFamily: fonts.body, fontSize: 12, color: COLORS.textMuted, lineHeight: 1.8, paddingLeft: 10, borderLeft: `2px solid ${COLORS.eden}25` }}>
                {item}
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 20, padding: "14px 18px", background: `${COLORS.accent}06`, borderRadius: 8, border: `1px solid ${COLORS.accent}10` }}>
          <div style={{ fontFamily: fonts.display, fontSize: 14, color: COLORS.textMuted, fontStyle: "italic", lineHeight: 1.6 }}>
            "Hey Luna, render the confrontation scene — make it intense."<br/>
            <span style={{ color: COLORS.luna }}>Luna</span> assembles narrative context, character refs, mood anchors, style lock → hands to <span style={{ color: COLORS.eden }}>Chiba</span> → Chiba selects agents, tunes parameters, chains the pipeline, manages parallel renders, handles retries → results flow back through Luna to you.
          </div>
        </div>
      </div>

      {/* Pipeline example */}
      <div
        style={{
          marginTop: 40,
          padding: "24px 28px",
          background: COLORS.bgCard,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 12,
        }}
      >
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 10,
            color: COLORS.textDim,
            letterSpacing: 3,
            marginBottom: 16,
          }}
        >
          EXAMPLE PIPELINE — "RENDER PAGE 3"
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {[
            { label: "Story View", color: COLORS.accent, type: "source" },
            { label: "→" },
            { label: "Luna", color: COLORS.luna, type: "agent" },
            { label: "(context)", color: COLORS.textDim, type: "note" },
            { label: "→" },
            { label: "Chiba", color: COLORS.eden, type: "agent" },
            { label: "(orchestrate)", color: COLORS.textDim, type: "note" },
            { label: "→" },
            { label: "Panel Renderer ×6", color: COLORS.eden, type: "agent" },
            { label: "(parallel)", color: COLORS.textDim, type: "note" },
            { label: "→" },
            { label: "Compositor", color: COLORS.accent, type: "agent" },
            { label: "→" },
            { label: "Output Preview", color: COLORS.accent, type: "dest" },
          ].map((step, i) =>
            step.type ? (
              <span
                key={i}
                style={{
                  fontFamily: step.type === "note" ? fonts.body : fonts.mono,
                  fontSize: step.type === "note" ? 11 : 12,
                  color: step.color,
                  padding: step.type !== "note" ? "6px 12px" : "0",
                  background:
                    step.type !== "note" ? `${step.color}10` : "transparent",
                  borderRadius: 6,
                  border:
                    step.type !== "note"
                      ? `1px solid ${step.color}25`
                      : "none",
                  fontStyle: step.type === "note" ? "italic" : "normal",
                }}
              >
                {step.label}
              </span>
            ) : (
              <span
                key={i}
                style={{
                  color: COLORS.textDim,
                  fontFamily: fonts.mono,
                  fontSize: 14,
                }}
              >
                {step.label}
              </span>
            )
          )}
        </div>
      </div>
    </div>
  );
}

// ─── PARTNERSHIP ───
function Partnership() {
  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="THE PARTNERSHIP" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 48px",
          lineHeight: 1.15,
          maxWidth: 700,
        }}
      >
        What each side brings
      </h2>

      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}
      >
        {/* Ahab side */}
        <div
          style={{
            background: `linear-gradient(160deg, ${COLORS.luna}08, ${COLORS.accent}05)`,
            border: `1px solid ${COLORS.luna}20`,
            borderRadius: 14,
            padding: "32px 28px",
          }}
        >
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: 12,
              color: COLORS.luna,
              letterSpacing: 3,
              marginBottom: 24,
            }}
          >
            LUNA / ECLISSI SIDE
          </div>
          {[
            {
              title: "Luna — Persistent AI Orchestration",
              desc: "A creative AI companion with cross-session memory, narrative intelligence, and relationship continuity. The brain that makes KOZMO more than a UI.",
            },
            {
              title: "Eclissi — Infrastructure Substrate",
              desc: "Memory Matrix (graph + FTS5 + vectors), T0-T4 routing, Hub Daemon, credential management. The platform KOZMO runs on.",
            },
            {
              title: "Story Lab — Creative Application",
              desc: "The studio UI: views, tools, project model, data architecture. The creative workspace where story comes to life.",
            },
            {
              title: "The \"Droid Model\" Philosophy",
              desc: "AI companions that develop through accumulated experience. A creative partner that gets better the more you work together.",
            },
          ].map((item) => (
            <div key={item.title} style={{ marginBottom: 20 }}>
              <div
                style={{
                  fontFamily: fonts.body,
                  fontSize: 14,
                  color: COLORS.text,
                  fontWeight: 600,
                  marginBottom: 4,
                }}
              >
                {item.title}
              </div>
              <div
                style={{
                  fontFamily: fonts.body,
                  fontSize: 13,
                  color: COLORS.textMuted,
                  lineHeight: 1.6,
                }}
              >
                {item.desc}
              </div>
            </div>
          ))}
        </div>

        {/* Eden side */}
        <div
          style={{
            background: `linear-gradient(160deg, ${COLORS.eden}08, ${COLORS.eden}03)`,
            border: `1px solid ${COLORS.eden}20`,
            borderRadius: 14,
            padding: "32px 28px",
          }}
        >
          <div
            style={{
              fontFamily: fonts.mono,
              fontSize: 12,
              color: COLORS.eden,
              letterSpacing: 3,
              marginBottom: 24,
            }}
          >
            EDEN / CHIBA SIDE
          </div>
          {[
            {
              title: "Generation API — Best-in-Class",
              desc: "Flux Kontext (image), Kling (video), ElevenLabs (voice), training pipelines (LoRA). The rendering muscle KOZMO needs.",
            },
            {
              title: "Chiba — Agent Orchestration Engine",
              desc: "Eden's global orchestration agent. A specialized command layer for manipulating agents, tuning parameters, chaining pipelines, and coordinating complex multi-agent tasks. Luna's partner on the execution side.",
            },
            {
              title: "Agent Infrastructure",
              desc: "Session-based agent system, budget metering (manna/tokens/turns), deployment and trigger management. The runtime for KOZMO's agent fleet.",
            },
            {
              title: "Flagship Integration Story",
              desc: "KOZMO exercises Eden's most advanced capabilities: character consistency, multi-agent workflows, style locking, training pipelines. A showcase of what the platform can do.",
            },
          ].map((item) => (
            <div key={item.title} style={{ marginBottom: 20 }}>
              <div
                style={{
                  fontFamily: fonts.body,
                  fontSize: 14,
                  color: COLORS.text,
                  fontWeight: 600,
                  marginBottom: 4,
                }}
              >
                {item.title}
              </div>
              <div
                style={{
                  fontFamily: fonts.body,
                  fontSize: 13,
                  color: COLORS.textMuted,
                  lineHeight: 1.6,
                }}
              >
                {item.desc}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Together */}
      <div
        style={{
          marginTop: 32,
          padding: "28px 32px",
          background: `linear-gradient(135deg, ${COLORS.luna}06, ${COLORS.eden}06)`,
          border: `1px solid ${COLORS.accent}15`,
          borderRadius: 14,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontFamily: fonts.mono,
            fontSize: 10,
            color: COLORS.textDim,
            letterSpacing: 3,
            marginBottom: 12,
          }}
        >
          TOGETHER
        </div>
        <div
          style={{
            fontFamily: fonts.display,
            fontSize: 26,
            color: COLORS.text,
            fontStyle: "italic",
            lineHeight: 1.5,
            maxWidth: 700,
            margin: "0 auto",
          }}
        >
          Luna brings the creative memory. Chiba brings the execution muscle.
          Together they power the first AI creative studio that thinks about
          story and renders at any scale.
        </div>
      </div>
    </div>
  );
}

// ─── ROADMAP ───
function Roadmap() {
  const phases = [
    {
      phase: "1",
      title: "Foundation",
      time: "Weeks 1–4",
      color: COLORS.accent,
      items: [
        "Eden tool integration in Luna's ToolRegistry",
        "CREATION node type in Memory Matrix",
        "Basic agent dispatch: concept art + character sheets",
        "Credential vault (macOS Keychain)",
        "Proof of concept: voice → memory → generation → recall",
      ],
    },
    {
      phase: "2",
      title: "Story Lab MVP",
      time: "Weeks 5–10",
      color: COLORS.luna,
      items: [
        "KOZMO application shell (Tauri + React)",
        "Story View + Character Lab (first two views)",
        "Project data model in Memory Matrix",
        "Panel Renderer + Compositor agents",
        "First full comic page generation pipeline",
      ],
    },
    {
      phase: "3",
      title: "Agent Fleet",
      time: "Weeks 11–16",
      color: COLORS.eden,
      items: [
        "Multi-agent orchestration (parallel dispatch, chaining)",
        "Custom agent creation workflow",
        "LoRA training integration for character consistency",
        "World Builder + Timeline tools",
        "Graveyard system with full versioning",
      ],
    },
    {
      phase: "4",
      title: "Full Studio",
      time: "Weeks 17+",
      color: COLORS.text,
      items: [
        "All views and tools operational",
        "Video production pipeline (Kling integration)",
        "Export to professional tools (PSD/CSP layered files)",
        "Cross-project creative memory",
        "Multi-user collaboration",
      ],
    },
  ];

  return (
    <div style={{ minHeight: "100vh", padding: "120px 60px 80px" }}>
      <SectionTag label="ROADMAP" />
      <h2
        style={{
          fontFamily: fonts.display,
          fontSize: 52,
          color: COLORS.text,
          fontWeight: 400,
          margin: "16px 0 48px",
          lineHeight: 1.15,
        }}
      >
        How we get there
      </h2>

      <div
        style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}
      >
        {phases.map((p) => (
          <div
            key={p.phase}
            style={{
              background: COLORS.bgCard,
              border: `1px solid ${p.color}25`,
              borderRadius: 12,
              padding: "24px 20px",
              borderTop: `3px solid ${p.color}60`,
            }}
          >
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 10,
                color: p.color,
                letterSpacing: 2,
                marginBottom: 4,
              }}
            >
              PHASE {p.phase}
            </div>
            <div
              style={{
                fontFamily: fonts.body,
                fontSize: 18,
                color: COLORS.text,
                fontWeight: 600,
                marginBottom: 4,
              }}
            >
              {p.title}
            </div>
            <div
              style={{
                fontFamily: fonts.mono,
                fontSize: 11,
                color: COLORS.textMuted,
                marginBottom: 16,
              }}
            >
              {p.time}
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              {p.items.map((item, i) => (
                <div
                  key={i}
                  style={{
                    fontFamily: fonts.body,
                    fontSize: 12,
                    color: COLORS.textMuted,
                    lineHeight: 1.5,
                    paddingLeft: 12,
                    borderLeft: `2px solid ${p.color}20`,
                  }}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* CTA */}
      <div
        style={{
          marginTop: 80,
          textAlign: "center",
          padding: "48px 32px",
        }}
      >
        <div
          style={{
            fontFamily: fonts.display,
            fontSize: 36,
            color: COLORS.text,
            fontWeight: 400,
            marginBottom: 16,
          }}
        >
          Let's build something that remembers.
        </div>
        <div
          style={{
            fontFamily: fonts.body,
            fontSize: 15,
            color: COLORS.textMuted,
            maxWidth: 500,
            margin: "0 auto",
            lineHeight: 1.7,
          }}
        >
          Luna + Chiba. Creative memory + execution muscle.
          Neither side can build KOZMO alone. Together it's a new
          category of creative tool.
        </div>
      </div>
    </div>
  );
}

// ─── HELPERS ───
function SectionTag({ label }) {
  return (
    <div
      style={{
        fontFamily: fonts.mono,
        fontSize: 10,
        color: COLORS.accent,
        letterSpacing: 4,
        fontWeight: 600,
      }}
    >
      {label}
    </div>
  );
}

function Card({ accent, title, body }) {
  return (
    <div
      style={{
        background: COLORS.bgCard,
        border: `1px solid ${accent}20`,
        borderRadius: 12,
        padding: "24px 24px",
        borderLeft: `3px solid ${accent}50`,
      }}
    >
      <div
        style={{
          fontFamily: fonts.body,
          fontSize: 16,
          color: COLORS.text,
          fontWeight: 600,
          marginBottom: 10,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontFamily: fonts.body,
          fontSize: 13,
          color: COLORS.textMuted,
          lineHeight: 1.7,
        }}
      >
        {body}
      </div>
    </div>
  );
}

function ArchRow({ label, items }) {
  return (
    <div
      style={{
        background: COLORS.bgCard,
        border: `1px solid ${COLORS.border}`,
        borderRadius: 10,
        padding: "16px 20px",
      }}
    >
      <div
        style={{
          fontFamily: fonts.mono,
          fontSize: 10,
          color: COLORS.textDim,
          letterSpacing: 2,
          marginBottom: 10,
        }}
      >
        {label}
      </div>
      {items.map((item, i) => (
        <div
          key={i}
          style={{
            fontFamily: fonts.body,
            fontSize: 12,
            color: COLORS.textMuted,
            lineHeight: 1.6,
            paddingLeft: 10,
            borderLeft: `2px solid ${COLORS.border}`,
            marginBottom: i < items.length - 1 ? 6 : 0,
          }}
        >
          {item}
        </div>
      ))}
    </div>
  );
}

// ─── MAIN ───
export default function KozmoPitch() {
  const [activeSection, setActiveSection] = useState("overview");
  const scrollRef = useRef(null);

  useEffect(() => {
    const el = document.getElementById(`section-${activeSection}`);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }, [activeSection]);

  // Track scroll position to update nav
  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY + 200;
      for (let i = sections.length - 1; i >= 0; i--) {
        const el = document.getElementById(`section-${sections[i]}`);
        if (el && el.offsetTop <= scrollY) {
          setActiveSection(sections[i]);
          break;
        }
      }
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div
      style={{
        background: COLORS.bg,
        color: COLORS.text,
        minHeight: "100vh",
        fontFamily: fonts.body,
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Instrument+Serif:ital@0;1&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: ${COLORS.bg}; }
        ::-webkit-scrollbar-thumb { background: ${COLORS.border}; border-radius: 3px; }
        ::selection { background: ${COLORS.accent}30; color: ${COLORS.accent}; }
      `}</style>

      <Nav active={activeSection} onNav={setActiveSection} />

      <div id="section-overview"><Overview /></div>
      <div id="section-problem"><Problem /></div>
      <div id="section-kozmo"><WhatIsKozmo /></div>
      <div id="section-architecture"><Architecture /></div>
      <div id="section-storyLab"><StoryLab /></div>
      <div id="section-agents"><AgentFleet /></div>
      <div id="section-partnership"><Partnership /></div>
      <div id="section-roadmap"><Roadmap /></div>
    </div>
  );
}

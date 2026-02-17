import { useState, useCallback, useRef, useEffect, useMemo } from "react";

// ============================================================================
// KOZMO CODEX — World Bible + Agent Command Center
// Entity browsing, relationship navigation, agent dispatch
// ============================================================================

// --- Project Data (Dinosaur/Wizard/Mother) ---
const PROJECT = {
  name: "The Dinosaur, The Wizard, and The Mother",
  slug: "dinosaur_wizard_mother",
  stats: { entities: 14, scenes: 9, shots: 6, relationships: 23 },
};

const ENTITIES = {
  characters: [
    {
      id: "cornelius", type: "character", name: "Cornelius", role: "The Dinosaur",
      status: "active", color: "#4ade80",
      physical: { age: "Ancient", build: "Massive, gentle", hair: "n/a — scaled hide, moss-green fading to grey", distinguishing: "One horn cracked from a fight he won't talk about" },
      wardrobe: { default: "Worn leather harness with too many pockets", tavern: "Same. He doesn't change." },
      traits: ["protective", "stubborn", "aging", "loyal"],
      arc: { summary: "Caretaker → Rescuer → Enabler → Acceptance", turning_point: "scene_08" },
      voice: { speech_pattern: "Simple sentences. Long pauses. Says the most with silence.", verbal_tics: ["Calls Mordecai 'boy' even though he's 28"] },
      relationships: [
        { entity: "mordecai", type: "father-figure", detail: "Raised him. Can't let go." },
        { entity: "constance", type: "partner", detail: "The only one who tells him the truth." },
      ],
      references: { images: ["cornelius_concept_v2.png", "cornelius_turnaround.png"], lora: "lora_cornelius_v1" },
      props: [{ entity: "cornelius_harness", note: "Always present. The pockets contain things he's saving 'just in case.'" }],
      scenes: ["scene_01", "scene_02", "scene_05", "scene_07", "scene_08", "scene_09"],
      tags: ["main_cast", "act_1", "act_2", "act_3"],
      luna_notes: "Ahab described Cornelius as 'what happens when love becomes a cage.' His arc isn't about learning to fight — it's about learning to stop.",
    },
    {
      id: "mordecai", type: "character", name: "Mordecai", role: "The Wizard",
      status: "active", color: "#a78bfa",
      physical: { age: "28", build: "Lean, angular", hair: "Dark, unkempt — hasn't been cut since he left home", distinguishing: "Burn scars on palms from early magic. He hides them." },
      wardrobe: { default: "Threadbare traveling cloak, leather satchel", tavern: "Cloak removed, shirtsleeves rolled, scars visible", underground: "Disheveled. Cloak missing. Doesn't notice." },
      traits: ["brilliant", "self-destructive", "charming", "addicted"],
      arc: { summary: "Prodigy → Lost → Broken → ???", turning_point: "scene_04" },
      voice: { speech_pattern: "Eloquent when sober, fragmented when using", verbal_tics: ["Addresses Cornelius as 'old man'", "Quotes things nobody's heard of"] },
      relationships: [
        { entity: "cornelius", type: "family", detail: "Son. Resents his protection. Needs it." },
        { entity: "princess", type: "complicated", detail: "She offers what he wants. That's the problem." },
        { entity: "constance", type: "family", detail: "Mother. Can't face her. Won't call her." },
      ],
      references: { images: ["mordecai_concept_v1.png"], lora: null },
      props: [{ entity: "mordecai_staff", note: "Appears Scene 3 onward. NOT in Scene 1." }],
      scenes: ["scene_01", "scene_02", "scene_03", "scene_04", "scene_05", "scene_07", "scene_09"],
      tags: ["main_cast", "magic_sector", "act_1", "act_2", "act_3"],
      luna_notes: "Mordecai's addiction is to numbness, not to magic itself. Key distinction Ahab emphasized. The magic is just the delivery mechanism.",
    },
    {
      id: "constance", type: "character", name: "Constance", role: "The Mother",
      status: "active", color: "#f472b6",
      physical: { age: "52", build: "Strong hands, tired eyes", hair: "Silver-streaked, always tied back — practical", distinguishing: "Garden soil permanently under her fingernails" },
      wardrobe: { default: "Linen apron over simple dress. Working clothes." },
      traits: ["fierce", "exhausted", "watchful", "grieving"],
      arc: { summary: "Guardian → Martyr → Rage → Release", turning_point: "scene_06" },
      voice: { speech_pattern: "Clipped. Efficient. Wastes nothing, including words.", verbal_tics: ["Starts sentences with 'Listen.'"] },
      relationships: [
        { entity: "cornelius", type: "partner", detail: "The only one who tells him the truth." },
        { entity: "mordecai", type: "mother", detail: "Loves him. Has stopped trying to save him." },
      ],
      references: { images: [], lora: null },
      props: [],
      scenes: ["scene_01", "scene_06", "scene_07", "scene_08", "scene_09"],
      tags: ["main_cast", "act_1", "act_3"],
      luna_notes: "Constance's garden is the physical metaphor for what she builds when she stops trying to fix people. The soil under her nails = she's already started.",
    },
    {
      id: "princess", type: "character", name: "The Princess", role: "The Catalyst",
      status: "active", color: "#fbbf24",
      physical: { age: "Ageless", build: "Impossible to describe consistently — shifts", hair: "Changes. Always beautiful. That's the point.", distinguishing: "Her shadow arrives before she does" },
      wardrobe: { default: "Whatever you want to see. Literally." },
      traits: ["seductive", "dangerous", "honest", "necessary"],
      arc: { summary: "Temptation → Mirror → Truth", turning_point: "scene_07" },
      voice: { speech_pattern: "Questions that sound like answers. Never raises her voice.", verbal_tics: ["Repeats your last word back to you as a question"] },
      relationships: [
        { entity: "mordecai", type: "catalyst", detail: "She's not the villain. She's the thing that makes the cracks visible." },
      ],
      references: { images: [], lora: null },
      props: [],
      scenes: ["scene_04", "scene_05", "scene_07"],
      tags: ["main_cast", "act_2", "act_3"],
      luna_notes: "Without the Princess, they'd have stayed comfortable and dying slowly. She's necessary pain.",
    },
  ],
  locations: [
    { id: "crooked_nail", type: "location", name: "The Crooked Nail", mood: "Dark → Tempting", time: "evening", desc: "A ramshackle pub at the edge of nowhere. Warm light through dirty windows. The kind of place that looks inviting from outside and honest from inside.", lighting: "Practical warm — oil lamps, firelight. Deep shadows in corners.", camera_suggestion: "Cooke S7/i for warmth. Shallow DoF to isolate characters from the murk.", color: "#f59e0b", scenes: ["scene_01", "scene_03"], references: { images: ["crooked_nail_exterior.png"] }, relationships: [{ entity: "cornelius", type: "frequents", detail: "His usual table, back to the wall." }], luna_notes: "The Crooked Nail is a character itself. It should feel like it's been here longer than anyone in it." },
    { id: "crystal_tower", type: "location", name: "The Crystal Tower", mood: "Beautiful → Sinister", time: "perpetual twilight", desc: "Where the Princess holds court. Everything gleams. Nothing is clean.", lighting: "Cold practical — bioluminescent surfaces. No warm light anywhere.", camera_suggestion: "Zeiss Supreme for clinical precision. Anamorphic only for Princess POV shots.", color: "#818cf8", scenes: ["scene_04"], references: { images: [] }, relationships: [{ entity: "princess", type: "domain", detail: "Her space. Her rules." }], luna_notes: "The tower should never look the same twice. Subtle shifts between shots — geometry that doesn't quite add up." },
    { id: "the_road", type: "location", name: "The Long Road", mood: "Open → Oppressive", time: "midday, harsh", desc: "Stretches between what was and what might be. No shade.", lighting: "Overexposed daylight. Nowhere to hide.", camera_suggestion: "Wide glass, 24mm. Let the emptiness do the work.", color: "#6b7280", scenes: ["scene_02"], references: { images: [] }, relationships: [], luna_notes: null },
    { id: "underground", type: "location", name: "The Underground", mood: "Hidden → Suffocating", time: "timeless", desc: "Where addicts go. Dark, warm, honest in the worst way.", lighting: "Practicals only — candles, embers. CineStill 800T territory.", camera_suggestion: "Canon K35 for vintage softness. Handheld. Tight framing — no escape.", color: "#ef4444", scenes: ["scene_05"], references: { images: [] }, relationships: [{ entity: "mordecai", type: "drawn_to", detail: "He knows the way by heart." }], luna_notes: "Mirror of the Crooked Nail. Both hiding places. One for the soul, one for the body." },
  ],
  props: [
    { id: "mordecai_staff", type: "prop", name: "Mordecai's Staff", desc: "Ancient wood, cracked, faint glow lines that pulse when magic is near. It chose him. He didn't choose it.", significance: "physical manifestation of his gift/curse", color: "#a78bfa", first_appearance: "scene_03", references: { images: [] }, relationships: [{ entity: "mordecai", type: "belongs_to" }, { entity: "magic_system", type: "governed_by" }], luna_notes: "⚠️ CONTINUITY: Staff appears Scene 3. Do NOT include in Scene 1 or 2 shots." },
    { id: "constance_letter", type: "prop", name: "The Letter", desc: "Folded, refolded, tear-stained. Contains everything Constance feared, confirmed.", significance: "The physical object that triggers Constance's turning point", color: "#f472b6", first_appearance: "scene_06", references: { images: [] }, relationships: [{ entity: "constance", type: "belongs_to" }, { entity: "mordecai", type: "about" }], luna_notes: "We never see what's in the letter. We only see Constance's face reading it." },
  ],
  lore: [
    { id: "magic_system", type: "lore", name: "The Gift / The Burn", desc: "Magic in this world costs. Every use leaves a physical mark — the burn scars. Overuse leads to numbness, which leads to chasing more magic to feel anything. It's addiction as built-in mechanic.", color: "#c8ff00", relationships: [{ entity: "mordecai", type: "affects" }, { entity: "mordecai_staff", type: "channels_through" }], luna_notes: "Ahab is revamping this system. Core metaphor: magic as substance abuse is intentional and should be respected, not glamorized.", references: { images: [] } },
  ],
};

// --- Agent State ---
const AGENTS = [
  { id: "chiba", name: "Chiba", role: "Orchestrator", status: "ready", color: "#c8ff00", desc: "Routes tasks to optimal Eden pipelines" },
  { id: "maya", name: "Maya", role: "Vision + Consistency", status: "idle", color: "#4ade80", desc: "Generates art, locks reference anchors" },
  { id: "di_agent", name: "DI Agent", role: "Color + Post", status: "idle", color: "#f59e0b", desc: "Film stock emulation, color grading" },
  { id: "luna", name: "Luna", role: "Memory + Context", status: "active", color: "#818cf8", desc: "World bible intelligence, continuity tracking" },
  { id: "foley", name: "Foley", role: "Audio + SFX", status: "standby", color: "#6b6b80", desc: "Sound design, voice, music" },
];

const GENERATION_QUEUE = [
  { id: "g1", entity: "cornelius", agent: "Maya", task: "Character turnaround sheet v3", status: "complete", time: "2:41" },
  { id: "g2", entity: "crooked_nail", agent: "Maya", task: "Exterior establishing — evening", status: "running", progress: 72, time: "2:43" },
  { id: "g3", entity: "mordecai", agent: "Maya", task: "Staff detail reference", status: "queued", time: "2:44" },
];

// ============================================================================
// COMPONENTS
// ============================================================================

function FileTree({ entities, selected, onSelect }) {
  const groups = [
    { key: "characters", label: "CHARACTERS", icon: "◉", items: entities.characters },
    { key: "locations", label: "LOCATIONS", icon: "◈", items: entities.locations },
    { key: "props", label: "PROPS", icon: "◇", items: entities.props },
    { key: "lore", label: "LORE", icon: "◆", items: entities.lore },
  ];
  const [expanded, setExpanded] = useState({ characters: true, locations: true, props: true, lore: true });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {groups.map(g => (
        <div key={g.key}>
          <button onClick={() => setExpanded(e => ({ ...e, [g.key]: !e[g.key] }))}
            style={{
              width: "100%", display: "flex", alignItems: "center", gap: 6,
              padding: "6px 10px", background: "transparent", border: "none",
              color: "#4a4a60", cursor: "pointer", fontFamily: "inherit",
              fontSize: 8, letterSpacing: 2, textAlign: "left",
            }}>
            <span style={{ fontSize: 6, transform: expanded[g.key] ? "rotate(90deg)" : "rotate(0deg)", transition: "0.15s" }}>▶</span>
            <span>{g.icon}</span>
            <span>{g.label}</span>
            <span style={{ color: "#2a2a3a", marginLeft: "auto" }}>{g.items.length}</span>
          </button>
          {expanded[g.key] && g.items.map(item => (
            <button key={item.id} onClick={() => onSelect(item.id)}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: 8,
                padding: "5px 10px 5px 28px", background: selected === item.id ? "#12122a" : "transparent",
                border: "none", borderLeft: selected === item.id ? `2px solid ${item.color}` : "2px solid transparent",
                color: selected === item.id ? "#e8e8f0" : "#6b6b80",
                cursor: "pointer", fontFamily: "inherit", fontSize: 10,
                textAlign: "left", transition: "all 0.1s",
              }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: item.color, flexShrink: 0, opacity: 0.7 }} />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.name}</span>
              {item.lora || item.references?.lora ? (
                <span style={{ fontSize: 6, color: "#4ade80", marginLeft: "auto", letterSpacing: 1 }}>LoRA</span>
              ) : null}
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

function RelationshipBadge({ rel, allEntities, onNavigate }) {
  const target = allEntities.find(e => e.id === rel.entity);
  return (
    <div onClick={() => target && onNavigate(rel.entity)}
      style={{
        display: "flex", alignItems: "flex-start", gap: 8, padding: "6px 8px",
        borderRadius: 4, cursor: target ? "pointer" : "default",
        background: "#0a0a14", border: "1px solid #141420",
        transition: "border-color 0.15s",
      }}
      onMouseEnter={e => target && (e.currentTarget.style.borderColor = target.color + "40")}
      onMouseLeave={e => e.currentTarget.style.borderColor = "#141420"}>
      <span style={{ width: 5, height: 5, borderRadius: "50%", background: target?.color || "#3a3a50", flexShrink: 0, marginTop: 4 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ fontSize: 10, color: "#e8e8f0" }}>{target?.name || rel.entity}</span>
          <span style={{ fontSize: 7, color: "#3a3a50", padding: "1px 4px", background: "#141420", borderRadius: 2, letterSpacing: 0.5 }}>{rel.type}</span>
        </div>
        {rel.detail && <div style={{ fontSize: 9, color: "#4a4a60", lineHeight: 1.4 }}>{rel.detail}</div>}
      </div>
    </div>
  );
}

function EntityCard({ entity, allEntities, onNavigate }) {
  const [section, setSection] = useState("overview"); // overview | details | scenes | refs

  const sectionTabs = entity.type === "character"
    ? ["overview", "details", "scenes", "refs"]
    : ["overview", "scenes", "refs"];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Entity Header */}
      <div style={{
        padding: "16px 20px", borderBottom: "1px solid #141420",
        background: `linear-gradient(135deg, ${entity.color}06 0%, transparent 60%)`,
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: entity.color }} />
              <span style={{ fontSize: 18, color: "#e8e8f0", fontWeight: 700, letterSpacing: -0.5 }}>{entity.name}</span>
            </div>
            {entity.role && <div style={{ fontSize: 11, color: entity.color, marginBottom: 6, marginLeft: 16, opacity: 0.8 }}>{entity.role}</div>}
            {entity.desc && <div style={{ fontSize: 10, color: "#6b6b80", lineHeight: 1.5, marginLeft: 16, maxWidth: 500 }}>{entity.desc}</div>}
            {entity.mood && <div style={{ fontSize: 10, color: "#6b6b80", marginLeft: 16 }}>Mood: <span style={{ color: "#9ca3af" }}>{entity.mood}</span></div>}
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
            <span style={{
              fontSize: 7, padding: "2px 8px", borderRadius: 3, letterSpacing: 1.5,
              background: "#141420", color: "#4a4a60", fontWeight: 600,
            }}>{entity.type.toUpperCase()}</span>
            {entity.status && (
              <span style={{
                fontSize: 7, padding: "2px 8px", borderRadius: 3, letterSpacing: 1,
                background: entity.status === "active" ? "#0a2010" : "#1a1a24",
                color: entity.status === "active" ? "#4ade80" : "#3a3a50",
              }}>{entity.status.toUpperCase()}</span>
            )}
          </div>
        </div>

        {/* Section Tabs */}
        <div style={{ display: "flex", gap: 2, marginTop: 14, marginLeft: 16 }}>
          {sectionTabs.map(t => (
            <button key={t} onClick={() => setSection(t)} style={{
              padding: "4px 10px", fontSize: 8, letterSpacing: 1.5,
              borderRadius: 3, border: "none", textTransform: "uppercase",
              background: section === t ? "#1a1a2e" : "transparent",
              color: section === t ? "#c8ff00" : "#3a3a50",
              cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s",
            }}>{t}</button>
          ))}
        </div>
      </div>

      {/* Section Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>

        {section === "overview" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Traits */}
            {entity.traits && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>TRAITS</div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {entity.traits.map(t => (
                    <span key={t} style={{
                      fontSize: 9, padding: "3px 8px", borderRadius: 3,
                      background: "#0d0d18", border: "1px solid #1a1a24", color: "#9ca3af",
                    }}>{t}</span>
                  ))}
                </div>
              </div>
            )}

            {/* Arc */}
            {entity.arc && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>ARC</div>
                <div style={{ fontSize: 11, color: "#c8cad0", lineHeight: 1.5, padding: "8px 12px", background: "#0a0a14", borderRadius: 6, borderLeft: `2px solid ${entity.color}30` }}>{entity.arc.summary}</div>
                {entity.arc.turning_point && (
                  <div style={{ fontSize: 8, color: "#4a4a60", marginTop: 4, marginLeft: 14 }}>
                    Turning point: <span style={{ color: "#6b6b80" }}>{entity.arc.turning_point.replace("_", " ")}</span>
                  </div>
                )}
              </div>
            )}

            {/* Voice */}
            {entity.voice && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>VOICE</div>
                <div style={{ fontSize: 10, color: "#6b6b80", lineHeight: 1.5, padding: "8px 12px", background: "#0a0a14", borderRadius: 6 }}>
                  {entity.voice.speech_pattern}
                  {entity.voice.verbal_tics?.length > 0 && (
                    <div style={{ marginTop: 6, fontSize: 9, color: "#4a4a60" }}>
                      {entity.voice.verbal_tics.map((t, i) => <div key={i}>• {t}</div>)}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Camera Suggestion (locations) */}
            {entity.camera_suggestion && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>CAMERA NOTES</div>
                <div style={{ fontSize: 10, color: "#9ca3af", lineHeight: 1.5, padding: "8px 12px", background: "#0a0a14", borderRadius: 6, borderLeft: "2px solid #f59e0b30" }}>{entity.camera_suggestion}</div>
              </div>
            )}

            {/* Lighting (locations) */}
            {entity.lighting && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>LIGHTING</div>
                <div style={{ fontSize: 10, color: "#6b6b80", lineHeight: 1.5 }}>{entity.lighting}</div>
              </div>
            )}

            {/* Significance (props) */}
            {entity.significance && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>SIGNIFICANCE</div>
                <div style={{ fontSize: 10, color: "#6b6b80", lineHeight: 1.5 }}>{entity.significance}</div>
              </div>
            )}

            {/* Relationships */}
            {entity.relationships?.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>RELATIONSHIPS</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {entity.relationships.map((r, i) => (
                    <RelationshipBadge key={i} rel={r} allEntities={allEntities} onNavigate={onNavigate} />
                  ))}
                </div>
              </div>
            )}

            {/* Luna Notes */}
            {entity.luna_notes && (
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 8, color: "#818cf8", letterSpacing: 2 }}>LUNA</span>
                </div>
                <div style={{
                  fontSize: 10, color: "#9ca3af", lineHeight: 1.6, padding: "10px 12px",
                  background: "#0d0a1a", borderRadius: 6, border: "1px solid #818cf820",
                  fontStyle: "italic",
                }}>{entity.luna_notes}</div>
              </div>
            )}
          </div>
        )}

        {section === "details" && entity.type === "character" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {entity.physical && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>PHYSICAL</div>
                {Object.entries(entity.physical).map(([k, v]) => (
                  <div key={k} style={{ display: "flex", gap: 12, padding: "4px 0", borderBottom: "1px solid #0d0d18" }}>
                    <span style={{ fontSize: 9, color: "#3a3a50", minWidth: 80, textTransform: "capitalize" }}>{k.replace("_", " ")}</span>
                    <span style={{ fontSize: 10, color: "#9ca3af", lineHeight: 1.4 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
            {entity.wardrobe && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>WARDROBE</div>
                {Object.entries(entity.wardrobe).map(([k, v]) => (
                  <div key={k} style={{ display: "flex", gap: 12, padding: "4px 0", borderBottom: "1px solid #0d0d18" }}>
                    <span style={{ fontSize: 9, color: "#3a3a50", minWidth: 80, textTransform: "capitalize" }}>{k}</span>
                    <span style={{ fontSize: 10, color: "#9ca3af", lineHeight: 1.4 }}>{v}</span>
                  </div>
                ))}
              </div>
            )}
            {entity.props?.length > 0 && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>PROPS</div>
                {entity.props.map((p, i) => (
                  <div key={i} onClick={() => onNavigate(p.entity)}
                    style={{ display: "flex", gap: 8, padding: "6px 8px", borderRadius: 4, cursor: "pointer", background: "#0a0a14", border: "1px solid #141420", marginBottom: 4 }}>
                    <span style={{ fontSize: 10, color: "#a78bfa" }}>{p.entity.replace(/_/g, " ")}</span>
                    {p.note && <span style={{ fontSize: 9, color: "#4a4a60" }}>— {p.note}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {section === "scenes" && (
          <div>
            <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>APPEARS IN</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {(entity.scenes || []).map(s => (
                <div key={s} style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "6px 10px",
                  background: "#0a0a14", borderRadius: 4, border: "1px solid #141420",
                }}>
                  <span style={{ fontSize: 10, color: "#c8ff00", fontWeight: 600, minWidth: 60 }}>{s.replace("_", " ").toUpperCase()}</span>
                  <span style={{ fontSize: 9, color: "#4a4a60" }}>
                    {s === "scene_01" && "The Departure"}
                    {s === "scene_02" && "The Road"}
                    {s === "scene_03" && "The Tavern"}
                    {s === "scene_04" && "The Wizard's Offer"}
                    {s === "scene_05" && "The Descent"}
                    {s === "scene_06" && "The Letter"}
                    {s === "scene_07" && "The Confrontation"}
                    {s === "scene_08" && "The Return"}
                    {s === "scene_09" && "The Quiet"}
                  </span>
                </div>
              ))}
            </div>
            {entity.first_appearance && (
              <div style={{ marginTop: 8, fontSize: 9, color: "#f59e0b", padding: "6px 10px", background: "#2a221008", borderRadius: 4, border: "1px solid #f59e0b20" }}>
                ⚠ First appearance: {entity.first_appearance.replace("_", " ")}
              </div>
            )}
          </div>
        )}

        {section === "refs" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 8 }}>REFERENCE IMAGES</div>
              {entity.references?.images?.length > 0 ? (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {entity.references.images.map((img, i) => (
                    <div key={i} style={{
                      aspectRatio: "4/3", background: "linear-gradient(135deg, #141420, #0a0a14)",
                      borderRadius: 6, border: "1px solid #1a1a24",
                      display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
                    }}>
                      <span style={{ fontSize: 8, color: "#2a2a3a", textAlign: "center", padding: 8 }}>{img}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: 20, background: "#0a0a14", borderRadius: 6, border: "1px dashed #1a1a24", textAlign: "center" }}>
                  <div style={{ fontSize: 9, color: "#2a2a3a", marginBottom: 4 }}>No references yet</div>
                  <div style={{ fontSize: 8, color: "#1a1a24" }}>Use agent panel to generate →</div>
                </div>
              )}
            </div>
            <div>
              <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>LoRA MODEL</div>
              {entity.references?.lora ? (
                <div style={{ padding: "8px 12px", background: "#0a200e", borderRadius: 6, border: "1px solid #4ade8020", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80" }} />
                  <span style={{ fontSize: 10, color: "#4ade80" }}>{entity.references.lora}</span>
                  <span style={{ fontSize: 7, color: "#2a5a30", marginLeft: "auto" }}>TRAINED</span>
                </div>
              ) : (
                <div style={{ padding: "8px 12px", background: "#0a0a14", borderRadius: 6, border: "1px dashed #1a1a24", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#2a2a3a" }} />
                  <span style={{ fontSize: 10, color: "#3a3a50" }}>Not trained</span>
                  <span style={{ fontSize: 8, color: "#1a1a24", marginLeft: "auto" }}>Needs 3-10 ref images</span>
                </div>
              )}
            </div>
            {entity.tags && (
              <div>
                <div style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>TAGS</div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {entity.tags.map(t => (
                    <span key={t} style={{ fontSize: 8, padding: "2px 6px", borderRadius: 2, background: "#0d0d18", color: "#4a4a60" }}>{t}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// MAIN
// ============================================================================
export default function KozmoCodex() {
  const [selectedEntity, setSelectedEntity] = useState("mordecai");
  const [agentChatInput, setAgentChatInput] = useState("");
  const [agentChat, setAgentChat] = useState([
    { role: "luna", text: "Mordecai loaded. I see a continuity flag — his staff appears in Scene 3 but isn't established in Scenes 1-2. Want me to check if any shots reference it before Scene 3?" },
  ]);
  const [queue, setQueue] = useState(GENERATION_QUEUE);
  const [searchQuery, setSearchQuery] = useState("");
  const chatEndRef = useRef(null);

  const allEntities = useMemo(() => [
    ...ENTITIES.characters,
    ...ENTITIES.locations,
    ...ENTITIES.props,
    ...ENTITIES.lore,
  ], []);

  const entity = allEntities.find(e => e.id === selectedEntity) || allEntities[0];

  const handleNavigate = useCallback((id) => {
    const target = allEntities.find(e => e.id === id);
    if (target) {
      setSelectedEntity(id);
      // Luna contextual response on navigation
      const lunaResponses = {
        cornelius: "Cornelius has 2 reference images and a trained LoRA. His harness prop is in every scene — consistent.",
        mordecai: "⚠ Continuity: Staff doesn't appear until Scene 3. No LoRA trained yet — needs reference art first.",
        constance: "Constance has zero reference images. No LoRA. She's in 5 scenes. This is a production gap.",
        princess: "The Princess has no fixed appearance by design. But we still need a visual anchor. Consider training a LoRA on mood/aesthetic rather than likeness.",
        crooked_nail: "Exterior reference exists. Interior hasn't been generated. Camera note: Cooke S7/i for warmth.",
        crystal_tower: "No references. This location needs concept art before any shots can be set up.",
        mordecai_staff: "⚠ First appearance: Scene 3. Currently referenced in 0 shots. Needs detail reference for consistency.",
        constance_letter: "Appears only in Scene 6. Constance solo scene. Consider generating a close-up hero frame of the letter itself.",
        magic_system: "Ahab is revamping this system. Don't generate any magic VFX until the rules are finalized.",
      };
      setAgentChat(prev => [...prev, {
        role: "luna",
        text: lunaResponses[id] || `Navigated to ${target.name}. ${target.references?.images?.length || 0} reference images on file.`,
      }]);
    }
  }, [allEntities]);

  const handleAgentChat = useCallback(() => {
    if (!agentChatInput.trim()) return;
    const msg = agentChatInput.trim();
    setAgentChat(prev => [...prev, { role: "user", text: msg }]);
    setAgentChatInput("");

    setTimeout(() => {
      const lower = msg.toLowerCase();
      let response = "";
      let agentAction = null;

      if (lower.includes("generate") || lower.includes("create") || lower.includes("draw") || lower.includes("art")) {
        response = `Dispatching to Chiba → Maya pipeline. Generating reference art for ${entity.name}. Style: project defaults. Adding to queue.`;
        agentAction = { entity: entity.id, agent: "Maya", task: `Reference art — ${entity.name}`, status: "queued", time: "now" };
      } else if (lower.includes("lora") || lower.includes("train")) {
        const imgCount = entity.references?.images?.length || 0;
        if (imgCount < 3) {
          response = `Can't train LoRA yet — ${entity.name} has ${imgCount} reference images. Need at least 3. Generate more references first?`;
        } else {
          response = `Queuing LoRA training for ${entity.name} using ${imgCount} reference images. Eden will process via custom model pipeline. ETA: ~10 minutes.`;
          agentAction = { entity: entity.id, agent: "Chiba", task: `LoRA training — ${entity.name}`, status: "queued", time: "now" };
        }
      } else if (lower.includes("continuity") || lower.includes("check") || lower.includes("consistent")) {
        response = `Running continuity scan on ${entity.name}...\n\nScenes: ${entity.scenes?.length || 0} appearances. ${entity.props?.length ? `Props: ${entity.props.map(p => p.entity.replace(/_/g, " ")).join(", ")}. ` : ""}${entity.luna_notes ? `\n\nNote: ${entity.luna_notes}` : ""}`;
      } else if (lower.includes("shot") || lower.includes("studio")) {
        response = `${entity.name} appears in ${entity.scenes?.length || 0} scenes. Opening in Studio would let you set up shots with ${entity.type === "location" ? `the camera notes: "${entity.camera_suggestion}"` : `their current reference anchors`}.`;
      } else if (lower.includes("describe") || lower.includes("prompt")) {
        if (entity.type === "character") {
          response = `Eden-ready prompt for ${entity.name}:\n\n"${entity.physical?.build || ""}, ${entity.physical?.hair || ""}, ${entity.physical?.distinguishing || ""}. Wearing ${entity.wardrobe?.default || "unspecified"}. ${entity.traits?.slice(0, 2).join(", ")} demeanor."`;
        } else if (entity.type === "location") {
          response = `Eden-ready prompt for ${entity.name}:\n\n"${entity.desc} ${entity.lighting || ""} ${entity.time ? `Time: ${entity.time}.` : ""}"`;
        } else {
          response = `Eden-ready prompt for ${entity.name}:\n\n"${entity.desc}"`;
        }
      } else {
        response = `I can help with: generate reference art, train LoRA, run continuity check, create Eden prompt, or check shot readiness. What do you need for ${entity.name}?`;
      }

      setAgentChat(prev => [...prev, { role: "luna", text: response }]);
      if (agentAction) {
        setQueue(prev => [agentAction, ...prev]);
      }
    }, 600);
  }, [agentChatInput, entity]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [agentChat]);

  // Search filter
  const filteredEntities = useMemo(() => {
    if (!searchQuery) return ENTITIES;
    const q = searchQuery.toLowerCase();
    const filter = (items) => items.filter(e =>
      e.name.toLowerCase().includes(q) ||
      e.id.includes(q) ||
      e.tags?.some(t => t.includes(q)) ||
      e.luna_notes?.toLowerCase().includes(q)
    );
    return {
      characters: filter(ENTITIES.characters),
      locations: filter(ENTITIES.locations),
      props: filter(ENTITIES.props),
      lore: filter(ENTITIES.lore),
    };
  }, [searchQuery]);

  // Relationship mini-map data
  const relationshipNodes = useMemo(() => {
    if (!entity.relationships) return [];
    return entity.relationships.map(r => {
      const target = allEntities.find(e => e.id === r.entity);
      return target ? { ...target, relType: r.type } : null;
    }).filter(Boolean);
  }, [entity, allEntities]);

  return (
    <div style={{
      display: "flex", flexDirection: "column", height: "100vh",
      background: "#08080e", color: "#c8cad0",
      fontFamily: "'DM Mono', 'SF Mono', 'Cascadia Code', monospace",
      fontSize: 12, overflow: "hidden",
    }}>

      {/* ═══ TITLE BAR ═══ */}
      <div style={{
        height: 38, background: "#06060a", borderBottom: "1px solid #141420",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 16px", flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 10, letterSpacing: 4, color: "#c8ff00", fontWeight: 800 }}>KOZMO</span>
          <span style={{ fontSize: 10, letterSpacing: 2, color: "#2a2a3a" }}>CODEX</span>
          <div style={{ width: 1, height: 14, background: "#1a1a24", margin: "0 4px" }} />
          <span style={{ fontSize: 9, color: "#3a3a50" }}>{PROJECT.name}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 8, color: "#3a3a50" }}>
          <span>{PROJECT.stats.entities} entities</span>
          <span>{PROJECT.stats.relationships} relationships</span>
          <span>{PROJECT.stats.scenes} scenes</span>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#4ade80", boxShadow: "0 0 8px #4ade8060" }} />
          <span style={{ color: "#4ade80" }}>EDEN</span>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#818cf8", boxShadow: "0 0 8px #818cf860" }} />
          <span style={{ color: "#818cf8" }}>LUNA</span>
        </div>
      </div>

      {/* ═══ MAIN BODY ═══ */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* ─── LEFT: File Tree ─── */}
        <div style={{
          width: 220, borderRight: "1px solid #141420", background: "#0a0a10",
          display: "flex", flexDirection: "column", flexShrink: 0,
        }}>
          {/* Search */}
          <div style={{ padding: "8px 10px", borderBottom: "1px solid #141420" }}>
            <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search entities..."
              style={{
                width: "100%", padding: "5px 8px", background: "#0d0d18",
                border: "1px solid #1a1a24", borderRadius: 4, color: "#c8cad0",
                fontFamily: "inherit", fontSize: 9, outline: "none",
              }}
              onFocus={e => e.target.style.borderColor = "#c8ff0030"}
              onBlur={e => e.target.style.borderColor = "#1a1a24"}
            />
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: "4px 0" }}>
            <FileTree entities={filteredEntities} selected={selectedEntity} onSelect={handleNavigate} />
          </div>
          {/* Project path */}
          <div style={{ padding: "8px 10px", borderTop: "1px solid #141420", fontSize: 7, color: "#1a1a24" }}>
            projects/{PROJECT.slug}/
          </div>
        </div>

        {/* ─── CENTER: Entity View ─── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "#08080e" }}>
          <EntityCard entity={entity} allEntities={allEntities} onNavigate={handleNavigate} />
        </div>

        {/* ─── RIGHT: Agent Panel ─── */}
        <div style={{
          width: 320, borderLeft: "1px solid #141420", background: "#0a0a10",
          display: "flex", flexDirection: "column", flexShrink: 0,
        }}>
          {/* Agent Roster - compact */}
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #141420" }}>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {AGENTS.map(a => (
                <div key={a.id} style={{
                  display: "flex", alignItems: "center", gap: 4, padding: "3px 8px",
                  borderRadius: 4, background: a.status === "active" || a.status === "ready" ? `${a.color}08` : "#0d0d18",
                  border: `1px solid ${a.status === "active" || a.status === "ready" ? a.color + "20" : "#141420"}`,
                }} title={a.desc}>
                  <div style={{
                    width: 5, height: 5, borderRadius: "50%",
                    background: a.status === "standby" ? "#2a2a3a" : a.color,
                    boxShadow: a.status !== "standby" ? `0 0 4px ${a.color}40` : "none",
                  }} />
                  <span style={{ fontSize: 8, color: a.status === "standby" ? "#3a3a50" : "#9ca3af" }}>{a.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{ padding: "10px 12px", borderBottom: "1px solid #141420" }}>
            <div style={{ fontSize: 7, color: "#3a3a50", letterSpacing: 2, marginBottom: 6 }}>ACTIONS · {entity.name.toUpperCase()}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {[
                { label: "Generate Reference Art", icon: "◎", agent: "Maya", color: "#4ade80" },
                { label: "Create Eden Prompt", icon: "✦", agent: "Chiba", color: "#c8ff00" },
                { label: "Run Continuity Check", icon: "⚡", agent: "Luna", color: "#818cf8" },
                { label: "Train LoRA Model", icon: "◈", agent: "Chiba → Eden", color: "#f59e0b",
                  disabled: (entity.references?.images?.length || 0) < 3 },
                { label: "Open in Studio", icon: "▶", agent: "→ Studio", color: "#6b6b80" },
              ].map((action, i) => (
                <button key={i} onClick={() => {
                  setAgentChatInput(action.label.toLowerCase());
                  setTimeout(() => {
                    const input = action.label.toLowerCase();
                    setAgentChat(prev => [...prev, { role: "user", text: input }]);
                    setAgentChatInput("");
                    // Trigger response
                    setTimeout(() => {
                      if (input.includes("generate")) {
                        setAgentChat(prev => [...prev, { role: "luna", text: `Dispatching to Chiba → Maya. Generating reference art for ${entity.name}. Added to queue.` }]);
                        setQueue(prev => [{ entity: entity.id, agent: "Maya", task: `Reference art — ${entity.name}`, status: "queued", time: "now" }, ...prev]);
                      } else if (input.includes("prompt")) {
                        const desc = entity.desc || entity.physical?.build || entity.name;
                        setAgentChat(prev => [...prev, { role: "luna", text: `Eden prompt: "${desc}"` }]);
                      } else if (input.includes("continuity")) {
                        setAgentChat(prev => [...prev, { role: "luna", text: `Continuity scan: ${entity.name} appears in ${entity.scenes?.length || 0} scenes. ${entity.luna_notes || "No flags."}` }]);
                      } else if (input.includes("lora")) {
                        const n = entity.references?.images?.length || 0;
                        setAgentChat(prev => [...prev, { role: "luna", text: n < 3 ? `Need ${3 - n} more reference images to train LoRA.` : `Queuing LoRA training with ${n} images.` }]);
                      }
                    }, 500);
                  }, 50);
                }}
                  disabled={action.disabled}
                  style={{
                    display: "flex", alignItems: "center", gap: 8, width: "100%",
                    padding: "6px 10px", borderRadius: 4, border: "none",
                    background: "transparent", cursor: action.disabled ? "not-allowed" : "pointer",
                    fontFamily: "inherit", textAlign: "left", transition: "background 0.1s",
                    opacity: action.disabled ? 0.3 : 1,
                  }}
                  onMouseEnter={e => !action.disabled && (e.currentTarget.style.background = "#12121e")}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <span style={{ fontSize: 12, color: action.color, width: 16 }}>{action.icon}</span>
                  <span style={{ fontSize: 9, color: "#9ca3af", flex: 1 }}>{action.label}</span>
                  <span style={{ fontSize: 7, color: "#2a2a3a" }}>{action.agent}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Agent Chat */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "8px 12px", borderBottom: "1px solid #141420" }}>
              <div style={{ fontSize: 7, color: "#818cf8", letterSpacing: 2 }}>LUNA + EDEN AGENTS</div>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "8px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
              {agentChat.map((msg, i) => (
                <div key={i} style={{
                  padding: "8px 10px", borderRadius: 6,
                  background: msg.role === "user" ? "#141428" : "#0d0a1a",
                  border: `1px solid ${msg.role === "user" ? "#1a1a30" : "#818cf815"}`,
                  alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                  maxWidth: "92%",
                }}>
                  {msg.role === "luna" && (
                    <div style={{ fontSize: 7, color: "#818cf8", marginBottom: 4, letterSpacing: 1 }}>LUNA</div>
                  )}
                  <div style={{
                    fontSize: 10, color: msg.role === "user" ? "#c8cad0" : "#9ca3af",
                    lineHeight: 1.5, whiteSpace: "pre-wrap",
                  }}>{msg.text}</div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input */}
            <div style={{ padding: "8px 12px", borderTop: "1px solid #141420" }}>
              <div style={{ display: "flex", gap: 6 }}>
                <input value={agentChatInput} onChange={e => setAgentChatInput(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleAgentChat()}
                  placeholder={`Ask about ${entity.name}...`}
                  style={{
                    flex: 1, padding: "6px 10px", background: "#0d0d18",
                    border: "1px solid #1a1a24", borderRadius: 4, color: "#c8cad0",
                    fontFamily: "inherit", fontSize: 10, outline: "none",
                  }}
                  onFocus={e => e.target.style.borderColor = "#818cf830"}
                  onBlur={e => e.target.style.borderColor = "#1a1a24"}
                />
                <button onClick={handleAgentChat} style={{
                  padding: "6px 10px", borderRadius: 4, border: "none",
                  background: "#818cf8", color: "#08080e", fontWeight: 700,
                  fontSize: 9, cursor: "pointer", fontFamily: "inherit",
                }}>↵</button>
              </div>
            </div>
          </div>

          {/* Generation Queue */}
          <div style={{ borderTop: "1px solid #141420", maxHeight: 140, overflow: "auto" }}>
            <div style={{ padding: "6px 12px", fontSize: 7, color: "#3a3a50", letterSpacing: 2, borderBottom: "1px solid #0d0d18" }}>
              QUEUE · {queue.length}
            </div>
            {queue.map((item, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 8, padding: "5px 12px",
                borderBottom: "1px solid #0d0d1a",
              }}>
                <div style={{
                  width: 5, height: 5, borderRadius: "50%",
                  background: item.status === "complete" ? "#4ade80" : item.status === "running" ? "#f59e0b" : "#3a3a50",
                  boxShadow: item.status === "running" ? "0 0 6px #f59e0b40" : "none",
                }} />
                <span style={{ fontSize: 8, color: "#6b6b80", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.task}</span>
                <span style={{ fontSize: 7, color: "#2a2a3a" }}>{item.agent}</span>
                {item.status === "running" && (
                  <span style={{ fontSize: 7, color: "#f59e0b" }}>{item.progress}%</span>
                )}
                {item.status === "complete" && (
                  <span style={{ fontSize: 7, color: "#4ade80" }}>✓</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ═══ BOTTOM: Relationship Map ═══ */}
      <div style={{
        height: 56, borderTop: "1px solid #141420", background: "#06060a",
        display: "flex", alignItems: "center", padding: "0 16px",
        flexShrink: 0, gap: 12,
      }}>
        <span style={{ fontSize: 8, color: "#3a3a50", letterSpacing: 2, minWidth: 50 }}>GRAPH</span>

        {/* Mini relationship visualization */}
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {/* Center node */}
          <div style={{
            width: 24, height: 24, borderRadius: "50%",
            background: `${entity.color}15`, border: `2px solid ${entity.color}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 7, color: entity.color, fontWeight: 700,
          }}>{entity.name.charAt(0)}</div>

          {/* Connections */}
          {relationshipNodes.map((node, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 2 }}
              onClick={() => handleNavigate(node.id)}>
              <div style={{ width: 20 + (i * 4), height: 1, background: `${node.color}30` }} />
              <div style={{
                padding: "3px 8px", borderRadius: 10,
                background: `${node.color}10`, border: `1px solid ${node.color}25`,
                fontSize: 8, color: node.color, cursor: "pointer",
                whiteSpace: "nowrap", transition: "all 0.15s",
              }}
                onMouseEnter={e => { e.currentTarget.style.background = `${node.color}20`; e.currentTarget.style.borderColor = `${node.color}50`; }}
                onMouseLeave={e => { e.currentTarget.style.background = `${node.color}10`; e.currentTarget.style.borderColor = `${node.color}25`; }}>
                <span style={{ fontSize: 6, opacity: 0.6, marginRight: 3 }}>{node.relType}</span>
                {node.name}
              </div>
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        <div style={{ fontSize: 7, color: "#1a1a24", display: "flex", gap: 12 }}>
          <span>◉ character</span>
          <span>◈ location</span>
          <span>◇ prop</span>
          <span>◆ lore</span>
        </div>
      </div>

      <style>{`
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #1a1a24; border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: #2a2a3a; }
        * { box-sizing: border-box; }
      `}</style>
    </div>
  );
}

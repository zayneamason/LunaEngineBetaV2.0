import { useState } from "react";

const data = {
  categories: [
    {
      name: "Core Philosophy",
      eden: {
        label: "Open Creative Toolkit",
        detail: "Open-source platform for artists. Agent-based creation with custom model training. Community-driven ecosystem where creators contribute ComfyUI workflows and earn revenue. Think: creative co-op meets API.",
        score: null,
      },
      higgsfield: {
        label: "Virtual Film Studio",
        detail: "Deterministic cinema production. Simulates real optical physics — camera bodies, lens profiles, focal lengths, aperture. Hero Frame workflow locks visual identity before animation. Think: virtual camera department.",
        score: null,
      },
      kozmo: "Eden's agent architecture maps to KOZMO's multi-agent fleet. Higgsfield's deterministic controls map to KOZMO's style-lock system. Both patterns are needed.",
    },
    {
      name: "Image Generation",
      eden: {
        label: "Multi-Model Pipeline",
        detail: "Flux, Stable Diffusion, custom LoRAs via ComfyUI. txt2img, img2img, controlnet, inpainting. Custom model trainer for consistent characters/styles. Open-ended — you bring the aesthetic.",
        score: 4,
      },
      higgsfield: {
        label: "Cinema-Grade Stills",
        detail: "Text-to-image with camera simulation baked in. ARRI Alexa 35, Panavision C-series lens profiles. Native 21:9 CinemaScope. Hero Frame First philosophy — generate, approve, then animate.",
        score: 4,
      },
      kozmo: "Eden for concept art and style exploration. Higgsfield for production frames that need to match specific camera rigs. KOZMO's Chiba orchestrator should route based on intent.",
    },
    {
      name: "Video Generation",
      eden: {
        label: "Workflow-Based",
        detail: "RunWay integration, TextureFlow morphing animations, img2vid pipelines via ComfyUI. Reel creation for commercials/trailers. Flexible but requires more prompt craft. No native camera simulation.",
        score: 3,
      },
      higgsfield: {
        label: "Director-Grade Control",
        detail: "50+ camera presets (dolly, crane, FPV, orbit). Up to 3 combined movements per shot. Start/End frame keyframe interpolation. Reference Anchor locks face/wardrobe across shots. Slow-mo toggle. 5-20sec @ 720p.",
        score: 5,
      },
      kozmo: "Higgsfield is the clear winner for cinematic video. The filmmaker in that video basically described what Cinema Studio does — specify camera, lens, movement. Eden's video is more experimental/artistic.",
    },
    {
      name: "Character Consistency",
      eden: {
        label: "LoRA Training",
        detail: "Train custom models on 3-10 images of a subject. Reuse across all generation tools. Agent-assisted workflow guides users through upload → train → generate. Persistent model IDs.",
        score: 4,
      },
      higgsfield: {
        label: "Reference Anchor",
        detail: "Hero Frame locks facial geometry and wardrobe. Video engine inherits exact appearance from approved still. 'Higgsfield Soul' avatar system for identity persistence. No training required — session-based.",
        score: 4,
      },
      kozmo: "Eden's approach = deeper consistency over time (trained model). Higgsfield = faster per-session consistency (reference anchor). KOZMO needs both — trained models for series work, anchors for one-off shots.",
    },
    {
      name: "Camera / Cinematography",
      eden: {
        label: "Prompt-Described",
        detail: "Camera movement described in text prompts. No native lens simulation or camera body selection. Relies on user's cinematography knowledge to describe the look they want. Generic 'cinematic style' modifiers.",
        score: 1,
      },
      higgsfield: {
        label: "Physics-Simulated",
        detail: "Camera body selection (ARRI, RED, VHS/Film profiles). Lens type (anamorphic, spherical, Cooke). Focal length, aperture/DoF control. Deterministic optical physics engine. Save custom camera presets.",
        score: 5,
      },
      kozmo: "This is the gap. Eden has zero cinematography awareness. For KOZMO's film workflow, Higgsfield's camera system is essential. Could Eden add this via custom ComfyUI workflows? Maybe — but Higgsfield has it native.",
    },
    {
      name: "Agent / AI System",
      eden: {
        label: "Full Agent Framework",
        detail: "Custom personality, tools, instructions, visual model per agent. Agent memory system. Deploy to social media. Session-based API with streaming. Agents can use all Eden creation tools autonomously.",
        score: 5,
      },
      higgsfield: {
        label: "No Agent System",
        detail: "Pure generation platform. No conversational agents, no memory, no autonomous creation. Manual UI-driven workflow. API exists but is task-based, not agent-based.",
        score: 0,
      },
      kozmo: "Eden's agent framework IS the foundation for KOZMO's agent fleet (Chiba, Maya, Foley, etc.). Higgsfield can't provide this — it's a tool, not a collaborator. KOZMO = Eden agents wielding Higgsfield-like controls.",
    },
    {
      name: "API / Dev Experience",
      eden: {
        label: "SDK + Sessions",
        detail: "JavaScript SDK (@edenlabs/eden-sdk). Task-based creation API with polling. Session-based agent conversations with streaming. REST API for all operations. Open-source, self-hostable ComfyUI workflows. API keys in beta.",
        score: 4,
      },
      higgsfield: {
        label: "Web-First, API Secondary",
        detail: "Primarily a web UI product. Credit-based system. Project sync/sharing for teams. Export-focused workflow. No public SDK or documented API for programmatic access. Closed ecosystem.",
        score: 2,
      },
      kozmo: "Eden is API-native — built for exactly what KOZMO needs. Higgsfield is built for humans clicking buttons. Integrating Higgsfield's camera logic would require either their API (if it exists) or reimplementing it.",
    },
    {
      name: "Custom Training",
      eden: {
        label: "Full Pipeline",
        detail: "Train LoRAs on your own images. Style transfer, character models, aesthetic models. Agent-guided training workflow. Models are reusable across all tools. Community model sharing.",
        score: 5,
      },
      higgsfield: {
        label: "Limited",
        detail: "No user-trainable models. Style Snap for outfit swaps. Recast for character replacement. Camera presets are saveable. But no custom model training — you work within their system.",
        score: 1,
      },
      kozmo: "For KOZMO's vision of a personal creative studio with your style baked in, Eden's training pipeline is non-negotiable. Higgsfield's preset system is too constrained.",
    },
    {
      name: "Audio / Music",
      eden: {
        label: "ElevenLabs Integration",
        detail: "Integrated audio generation through ElevenLabs and other providers. Text-to-speech, potentially music generation through custom workflows. Agents can create multimodal content including audio.",
        score: 3,
      },
      higgsfield: {
        label: "WAN 2.5 Lipsync",
        detail: "Lip-sync engine for speaking subjects in video. No standalone audio generation. Video-first — audio is an enhancement layer, not a standalone capability.",
        score: 2,
      },
      kozmo: "Neither is a complete audio solution. KOZMO's Foley agent needs dedicated audio generation. Eden's plugin architecture could integrate Udio/Suno. Higgsfield's lipsync is useful but narrow.",
    },
    {
      name: "Pricing Model",
      eden: {
        label: "Manna Credits",
        detail: "Internal credit system ('Manna'). Pay-per-generation. Open-source tools can run locally for free. API access requires credits. Community contributions can earn credits.",
        score: 4,
      },
      higgsfield: {
        label: "Sub + Credits",
        detail: "Subscription tiers + optional credit packs (expire after 90 days). Iterating burns credits fast. $1.3B valuation. Mixed reviews on cost-efficiency (3.7 Trustpilot). Commercial rights on paid plans.",
        score: 2,
      },
      kozmo: "Eden's model is more KOZMO-friendly — pay for what you use, run local when possible. Higgsfield's subscription + expiring credits is friction for an orchestration layer that needs to manage budgets.",
    },
  ],
};

const ScoreBar = ({ score, max = 5 }) => {
  if (score === null) return null;
  return (
    <div className="flex items-center gap-1.5 mt-2">
      {Array.from({ length: max }, (_, i) => (
        <div
          key={i}
          className="h-1.5 flex-1 rounded-full transition-all"
          style={{
            backgroundColor: i < score ? "currentColor" : "rgba(128,128,128,0.15)",
            opacity: i < score ? 0.8 : 1,
          }}
        />
      ))}
      <span className="text-xs opacity-50 ml-1" style={{ fontFamily: "monospace" }}>{score}/{max}</span>
    </div>
  );
};

export default function EdenVsHiggsfield() {
  const [expandedRow, setExpandedRow] = useState(null);
  const [view, setView] = useState("comparison");

  return (
    <div
      className="min-h-screen p-4 md:p-8"
      style={{
        fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace",
        backgroundColor: "#0a0a0c",
        color: "#d4d4d8",
      }}
    >
      <div className="max-w-5xl mx-auto mb-8">
        <div className="flex items-baseline gap-3 mb-2">
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "#f0f0f0" }}>
            KOZMO INTEL
          </h1>
          <span className="text-xs opacity-40">PLATFORM COMPARISON v1.0</span>
        </div>
        <div className="h-px w-full mb-4" style={{ background: "linear-gradient(to right, #3b82f6, #10b981, transparent)" }} />
        <p className="text-sm opacity-60 leading-relaxed max-w-3xl">
          Eden.art vs Higgsfield Cinema Studio — evaluated through the lens of KOZMO's
          AI filmmaking architecture. Which capabilities map to which agents? Where are the gaps?
        </p>

        <div className="flex gap-2 mt-4">
          {["comparison", "verdict"].map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-3 py-1 text-xs rounded transition-all"
              style={{
                backgroundColor: view === v ? "#1e293b" : "transparent",
                color: view === v ? "#e2e8f0" : "#64748b",
                border: `1px solid ${view === v ? "#334155" : "#1e293b"}`,
              }}
            >
              {v.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {view === "comparison" && (
        <div className="max-w-5xl mx-auto space-y-3">
          <div className="grid grid-cols-12 gap-3 px-4 mb-2">
            <div className="col-span-2" />
            <div className="col-span-4 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: "#3b82f6" }} />
              <span className="text-xs font-bold tracking-wider opacity-70">EDEN.ART</span>
            </div>
            <div className="col-span-4 flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: "#10b981" }} />
              <span className="text-xs font-bold tracking-wider opacity-70">HIGGSFIELD</span>
            </div>
            <div className="col-span-2 text-xs font-bold tracking-wider opacity-70 text-center">KOZMO</div>
          </div>

          {data.categories.map((cat, i) => {
            const isExpanded = expandedRow === i;
            return (
              <div
                key={i}
                className="rounded-lg transition-all cursor-pointer"
                style={{
                  backgroundColor: isExpanded ? "#111115" : "#0d0d10",
                  border: `1px solid ${isExpanded ? "#1e293b" : "#151518"}`,
                }}
                onClick={() => setExpandedRow(isExpanded ? null : i)}
              >
                <div className="grid grid-cols-12 gap-3 p-4 items-start">
                  <div className="col-span-2">
                    <span className="text-xs font-bold tracking-wide" style={{ color: "#94a3b8" }}>
                      {cat.name.toUpperCase()}
                    </span>
                  </div>
                  <div className="col-span-4">
                    <div className="text-sm font-medium" style={{ color: "#60a5fa" }}>{cat.eden.label}</div>
                    {!isExpanded && (
                      <div className="text-xs opacity-40 mt-1 line-clamp-2">{cat.eden.detail.slice(0, 80)}...</div>
                    )}
                    <div style={{ color: "#3b82f6" }}><ScoreBar score={cat.eden.score} /></div>
                  </div>
                  <div className="col-span-4">
                    <div className="text-sm font-medium" style={{ color: "#34d399" }}>{cat.higgsfield.label}</div>
                    {!isExpanded && (
                      <div className="text-xs opacity-40 mt-1 line-clamp-2">{cat.higgsfield.detail.slice(0, 80)}...</div>
                    )}
                    <div style={{ color: "#10b981" }}><ScoreBar score={cat.higgsfield.score} /></div>
                  </div>
                  <div className="col-span-2 flex justify-center">
                    <span className="text-lg opacity-30">{isExpanded ? "−" : "+"}</span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-4 pb-4">
                    <div className="grid grid-cols-12 gap-3">
                      <div className="col-span-2" />
                      <div className="col-span-4 text-xs leading-relaxed p-3 rounded" style={{ backgroundColor: "rgba(59,130,246,0.05)", border: "1px solid rgba(59,130,246,0.1)" }}>
                        {cat.eden.detail}
                      </div>
                      <div className="col-span-4 text-xs leading-relaxed p-3 rounded" style={{ backgroundColor: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.1)" }}>
                        {cat.higgsfield.detail}
                      </div>
                      <div className="col-span-2" />
                    </div>
                    <div className="mt-3 mx-auto p-3 rounded text-xs leading-relaxed" style={{ backgroundColor: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.15)", maxWidth: "calc(100% - 2rem)" }}>
                      <span className="font-bold" style={{ color: "#f59e0b" }}>KOZMO → </span>
                      <span style={{ color: "#d4d4d8" }}>{cat.kozmo}</span>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {view === "verdict" && (
        <div className="max-w-3xl mx-auto space-y-6">
          <div className="rounded-lg p-6" style={{ backgroundColor: "#111115", border: "1px solid #1e293b" }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: "#f59e0b" }}>THE VERDICT</h2>
            <p className="text-sm leading-relaxed opacity-80 mb-4">
              They're not competitors — they're complementary layers. Eden is the <em>platform</em>{" "}
              KOZMO needs. Higgsfield is the <em>capability</em> KOZMO needs. The filmmaker in that
              video essentially described KOZMO's workflow: shoot real footage → identify gaps →
              use AI to fill them with cinema-grade output → color grade to match.
            </p>
            <p className="text-sm leading-relaxed opacity-80">
              The missing piece? Nobody has both an agent framework AND deterministic
              cinema controls. That's KOZMO's wedge.
            </p>
          </div>

          <div className="rounded-lg p-6" style={{ backgroundColor: "#111115", border: "1px solid #1e293b" }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: "#3b82f6" }}>RECOMMENDED ARCHITECTURE</h2>
            <div className="space-y-3 text-sm">
              {[
                ["LAYER 1", "#60a5fa", "Eden Agent Framework", "KOZMO agents (Chiba, Maya, Foley) built on Eden's agent system. Custom personalities, tool access, memory. This is the brain."],
                ["LAYER 2", "#34d399", "Higgsfield-Style Camera System", "Either integrate their API (if available), build equivalent controls as Eden ComfyUI workflows, or create KOZMO's own 'virtual camera' abstraction that routes to the best provider."],
                ["LAYER 3", "#a78bfa", "Luna Memory + Style Lock", "Luna maintains project context, shot lists, color palettes, camera profiles. The 'creative director' who ensures every AI-generated shot matches the project's visual DNA."],
              ].map(([layer, color, title, desc], i) => (
                <div key={i} className="flex gap-3">
                  <span className="font-bold opacity-50 w-16 shrink-0">{layer}</span>
                  <div>
                    <span className="font-bold" style={{ color }}>{title}</span> — {desc}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg p-6" style={{ backgroundColor: "#111115", border: "1px solid #1e293b" }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: "#ef4444" }}>GAPS TO CLOSE</h2>
            <div className="space-y-2 text-sm">
              {[
                ["Camera Abstraction", "Nobody offers agent-driven camera control. Higgsfield has the controls but no agents. Eden has agents but no camera awareness. KOZMO bridges this."],
                ["Post-Processing", "The filmmaker's 'secret sauce' was Dehancer + color grading. Neither platform automates this. KOZMO needs a 'DI Agent' for automated color matching."],
                ["Shot Continuity", "Higgsfield's Reference Anchor helps within a session. Eden's LoRAs help across sessions. Neither tracks continuity across an entire edit timeline."],
                ["Audio/Music", "Both are weak here. KOZMO's Foley agent needs ElevenLabs, Udio/Suno, and lip-sync — none solved by either platform alone."],
              ].map(([title, desc], i) => (
                <div key={i} className="flex gap-3 py-2" style={{ borderTop: i > 0 ? "1px solid #1a1a1e" : "none" }}>
                  <span className="font-bold text-xs w-40 shrink-0" style={{ color: "#f87171" }}>{title}</span>
                  <span className="text-xs opacity-70 leading-relaxed">{desc}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg p-6" style={{ backgroundColor: "#111115", border: "1px solid #1e293b" }}>
            <h2 className="text-lg font-bold mb-4" style={{ color: "#10b981" }}>FILMMAKER'S WORKFLOW → KOZMO</h2>
            <div className="space-y-2 text-xs">
              {[
                ["Screenshot real footage", "Maya (vision) ingests reference frame"],
                ["Upload to AI platform", "Chiba routes to optimal generator"],
                ["Specify camera/lens", "Style Lock applies project camera profile"],
                ["Generate stills → approve", "Hero Frame review in KOZMO timeline"],
                ["Animate to video", "Eden/Higgsfield img2vid with camera motion"],
                ["Color grade + Dehancer", "DI Agent matches LUT + film stock emulation"],
                ["A/B with real footage", "KOZMO timeline shows side-by-side cuts"],
                ["Export 1-2sec clip", "Render agent delivers timeline-ready clips"],
              ].map(([manual, kozmo], i) => (
                <div key={i} className="grid grid-cols-2 gap-4 py-2" style={{ borderTop: i > 0 ? "1px solid #1a1a1e" : "none" }}>
                  <span className="opacity-50">{manual}</span>
                  <span style={{ color: "#34d399" }}>→ {kozmo}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto mt-8 pt-4" style={{ borderTop: "1px solid #151518" }}>
        <p className="text-xs opacity-30 text-center">
          KOZMO Platform Intelligence · Eden.art + Higgsfield Cinema Studio Analysis
        </p>
      </div>
    </div>
  );
}

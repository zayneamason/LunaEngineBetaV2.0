import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchDraft, updateDraft, startDraftBuild,
  runPreflight, fetchDirectives, fetchSystemKnowledge, fetchConfigFile,
} from "../api";

// ── Shared UI primitives ──

function Section({ title, children }) {
  return (
    <div className="mb-5">
      <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider mb-2">
        {title}
      </h3>
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-9 h-5 rounded-full transition-colors ${
          checked ? "bg-cyan-600" : "bg-gray-700"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : ""
          }`}
        />
      </button>
      <span className={`text-sm ${checked ? "text-gray-200" : "text-gray-500"}`}>
        {label}
      </span>
    </label>
  );
}

function Tag({ label, onRemove }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-xs text-gray-300">
      {label}
      {onRemove && (
        <button onClick={onRemove} className="text-gray-500 hover:text-red-400 ml-0.5">
          {"\u00d7"}
        </button>
      )}
    </span>
  );
}

// ── Constants ──

const ALL_PATCHES = [
  "bootstrap_001_sovereignty",
  "bootstrap_002_relationship",
  "bootstrap_003_honesty",
  "bootstrap_004_consciousness",
];
const ALL_PROVIDERS = ["claude", "groq", "local"];
const BUILD_SKILL_DEFAULTS = ["math", "logic", "diagnostic", "reading", "analytics"];
const PLATFORM_OPTIONS = [
  { value: "auto", label: "Auto-detect (current machine)" },
  { value: "macos-arm64", label: "macOS (Apple Silicon)" },
  { value: "macos-x64", label: "macOS (Intel)" },
  { value: "linux-x64", label: "Linux (x86_64)" },
  { value: "linux-arm64", label: "Linux (ARM64)" },
  { value: "windows-x64", label: "Windows (x86_64)" },
];

const PLATFORM_INFO = {
  macos: { tts: "Apple TTS", stt: "MLX-Whisper", inference: "MLX (Apple Silicon)" },
  linux: { tts: "Piper TTS", stt: "Whisper ONNX", inference: "ONNX Runtime" },
  windows: { tts: "Piper TTS", stt: "Whisper ONNX", inference: "ONNX Runtime" },
};

function platformFamily(p) {
  if (!p || p === "auto") return null;
  if (p.startsWith("macos")) return "macos";
  if (p.startsWith("linux")) return "linux";
  if (p.startsWith("windows")) return "windows";
  return null;
}

function detectPlatform() {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("mac")) return "macos";
  if (ua.includes("linux")) return "linux";
  if (ua.includes("win")) return "windows";
  return "unknown";
}

// ── Main component ──

export default function BuildEditor({ draftId, onBuild, onBack }) {
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [saveStatus, setSaveStatus] = useState("saved"); // saved | saving | error

  // Build name
  const [buildName, setBuildName] = useState("");

  // Platform
  const [platform, setPlatform] = useState("auto");

  // Config sections
  const [dbMode, setDbMode] = useState("seed");
  const [pages, setPages] = useState({});
  const [widgets, setWidgets] = useState({});
  const [remap, setRemap] = useState({});
  const [collections, setCollections] = useState({});
  const [collectionModes, setCollectionModes] = useState({});
  const [patches, setPatches] = useState([]);
  const [chain, setChain] = useState([]);
  const [excludedPkgs, setExcludedPkgs] = useState([]);
  const [newPkg, setNewPkg] = useState("");
  const [skills, setSkills] = useState({});
  const [buildSkillModes, setBuildSkillModes] = useState({});
  const [tokenPreset, setTokenPreset] = useState("balanced");
  const [gestureFreq, setGestureFreq] = useState("moderate");
  const [bootOnFirst, setBootOnFirst] = useState(true);
  const [disabledDirIds, setDisabledDirIds] = useState(new Set());

  // Wizard config
  const [wizardEnabled, setWizardEnabled] = useState(true);
  const [wizardProviders, setWizardProviders] = useState(["groq", "claude", "gemini"]);
  const [wizardDefaultProvider, setWizardDefaultProvider] = useState("groq");
  const [wizardShowVoice, setWizardShowVoice] = useState(true);
  const [wizardShowPersonality, setWizardShowPersonality] = useState(true);
  const [wizardCustomWelcome, setWizardCustomWelcome] = useState("");

  // Lazy-loaded data
  const [directivesData, setDirectivesData] = useState(null);
  const [sysKnowledge, setSysKnowledge] = useState(null);
  const [configCache, setConfigCache] = useState({});
  const [expandedDetails, setExpandedDetails] = useState({});
  const [expandedDoc, setExpandedDoc] = useState(null);

  // Preflight
  const [preflight, setPreflight] = useState(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState(null);

  // Auto-save debounce
  const saveTimer = useRef(null);
  const configVersion = useRef(0);

  // ── Load draft ──
  useEffect(() => {
    fetchDraft(draftId)
      .then((d) => {
        setDraft(d);
        setBuildName(d.name || "");
        setPlatform(d.platform || "auto");
        const cfg = d.config || {};
        setDbMode(cfg.database?.mode || "seed");
        setPages(cfg.frontend?.pages || {});
        setWidgets(cfg.frontend?.widgets || {});
        setRemap(cfg.frontend?.remap || {});

        const colls = cfg.collections || {};
        const collEnabled = {};
        const collModes = {};
        for (const [name, info] of Object.entries(colls)) {
          collEnabled[name] = typeof info === "object" ? (info.enabled ?? true) : !!info;
          collModes[name] = typeof info === "object" ? (info.mode || "compiled") : "compiled";
        }
        setCollections(collEnabled);
        setCollectionModes(collModes);

        const cfgSection = cfg.config || {};
        setPatches(cfgSection.personality_patches || cfgSection.personality?.bootstrap_patches || []);
        setChain(cfgSection.fallback_chain?.chain || cfgSection.fallback_chain || []);

        const nuitka = cfg.nuitka || {};
        setExcludedPkgs(nuitka.exclude_packages || nuitka.excluded_packages || []);

        const sk = cfgSection.skills || {};
        const skState = {};
        for (const [name, info] of Object.entries(sk)) {
          if (typeof info === "object" && "enabled" in info) skState[name] = info.enabled;
          else if (typeof info === "boolean") skState[name] = info;
        }
        setSkills(skState);

        const bsk = cfg.skills || {};
        const bskModes = {};
        for (const key of [...new Set([...Object.keys(bsk), ...BUILD_SKILL_DEFAULTS])]) {
          bskModes[key] = bsk[key]?.mode || "compiled";
        }
        setBuildSkillModes(bskModes);

        const pers = cfgSection.personality || {};
        setTokenPreset(pers.token_budget?.default_preset || "balanced");
        setGestureFreq(pers.expression?.gesture_frequency || "moderate");
        setBootOnFirst(pers.bootstrap?.run_on_first_launch ?? true);

        const wiz = cfg.wizard || {};
        setWizardEnabled(wiz.enabled !== false);
        setWizardProviders(wiz.providers || ["groq", "claude", "gemini"]);
        setWizardDefaultProvider(wiz.default_provider || "groq");
        setWizardShowVoice(wiz.show_voice_step !== false);
        setWizardShowPersonality(wiz.show_personality_step !== false);
        setWizardCustomWelcome(wiz.custom_welcome || "");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

    fetchDirectives().then(setDirectivesData).catch(() => {});
    fetchSystemKnowledge().then(setSysKnowledge).catch(() => {});
  }, [draftId]);

  // ── Build full config from state ──
  function getFullConfig() {
    const collObj = {};
    for (const [name, enabled] of Object.entries(collections)) {
      collObj[name] = { enabled, mode: collectionModes[name] || "compiled" };
    }

    const skillsObj = {};
    for (const [name, mode] of Object.entries(buildSkillModes)) {
      skillsObj[name] = { mode };
    }

    return {
      database: { mode: dbMode },
      collections: collObj,
      skills: skillsObj,
      config: {
        personality_patches: patches,
        fallback_chain: chain,
        skills,
        personality: {
          token_budget: { default_preset: tokenPreset },
          expression: { gesture_frequency: gestureFreq },
          bootstrap: { run_on_first_launch: bootOnFirst },
        },
        directives: disabledDirIds.size > 0 ? { disabled_ids: [...disabledDirIds] } : undefined,
      },
      frontend: { build: true, pages, widgets, remap },
      nuitka: { exclude_packages: excludedPkgs },
      wizard: {
        enabled: wizardEnabled,
        providers: wizardProviders,
        default_provider: wizardDefaultProvider,
        show_voice_step: wizardShowVoice,
        show_personality_step: wizardShowPersonality,
        custom_welcome: wizardCustomWelcome,
      },
    };
  }

  // ── Auto-save ──
  useEffect(() => {
    if (loading || !draft) return;
    configVersion.current += 1;
    const version = configVersion.current;

    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaveStatus("saving");

    saveTimer.current = setTimeout(async () => {
      try {
        await updateDraft(draftId, getFullConfig(), buildName, platform);
        if (configVersion.current === version) setSaveStatus("saved");
      } catch {
        setSaveStatus("error");
      }
    }, 1500);

    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [
    pages, widgets, remap, collections, collectionModes, patches, chain,
    excludedPkgs, skills, buildSkillModes, tokenPreset, gestureFreq,
    bootOnFirst, disabledDirIds, buildName, platform, dbMode,
    wizardEnabled, wizardProviders, wizardDefaultProvider, wizardShowVoice,
    wizardShowPersonality, wizardCustomWelcome,
  ]);

  // ── Toggle helpers ──
  function togglePage(key) { setPages((p) => ({ ...p, [key]: !p[key] })); }
  function toggleWidget(key) { setWidgets((p) => ({ ...p, [key]: !p[key] })); }
  function toggleCollection(name) { setCollections((p) => ({ ...p, [name]: !p[name] })); }
  function setCollectionMode(name, mode) { setCollectionModes((p) => ({ ...p, [name]: mode })); }
  function togglePatch(patch) {
    setPatches((p) => p.includes(patch) ? p.filter((x) => x !== patch) : [...p, patch]);
  }
  function toggleSkill(name) { setSkills((p) => ({ ...p, [name]: !p[name] })); }
  function toggleDirective(id) {
    setDisabledDirIds((p) => { const n = new Set(p); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  }

  function setRemapTarget(target) {
    if (target === "none") { const n = { ...remap }; delete n.nexus; setRemap(n); }
    else setRemap({ ...remap, nexus: { from: "studio", to: target, position: remap.nexus?.position || "header" } });
  }
  function setRemapPosition(position) {
    if (!remap.nexus) return;
    setRemap({ ...remap, nexus: { ...remap.nexus, position } });
  }

  function moveChainItem(index, direction) {
    const next = [...chain];
    const swap = index + direction;
    if (swap < 0 || swap >= next.length) return;
    [next[index], next[swap]] = [next[swap], next[index]];
    setChain(next);
  }
  function addChainProvider(p) { if (!chain.includes(p)) setChain([...chain, p]); }
  function removeChainProvider(p) { setChain(chain.filter((x) => x !== p)); }

  function addExcludedPkg() {
    const pkg = newPkg.trim();
    if (pkg && !excludedPkgs.includes(pkg)) { setExcludedPkgs([...excludedPkgs, pkg]); setNewPkg(""); }
  }
  function removeExcludedPkg(pkg) { setExcludedPkgs(excludedPkgs.filter((p) => p !== pkg)); }

  const toggleDetail = useCallback((key, fileKey) => {
    setExpandedDetails((p) => ({ ...p, [key]: !p[key] }));
    if (!configCache[fileKey]) {
      fetchConfigFile(fileKey)
        .then((data) => { if (data) setConfigCache((p) => ({ ...p, [fileKey]: data })); })
        .catch(() => {});
    }
  }, [configCache]);

  // ── Preflight ──
  async function handlePreflight() {
    setPreflightLoading(true);
    setPreflightError(null);
    setPreflight(null);
    try {
      const result = await runPreflight(draft?.template || "luna-only", platform, getFullConfig());
      setPreflight(result);
    } catch (e) {
      setPreflightError(e.message);
    }
    setPreflightLoading(false);
  }

  // ── Start build ──
  async function handleBuild() {
    setStarting(true);
    setError(null);
    try {
      // Save latest config before building
      await updateDraft(draftId, getFullConfig(), buildName, platform);
      const { build_id } = await startDraftBuild(draftId);
      onBuild(build_id);
    } catch (e) {
      setError(e.message);
      setStarting(false);
    }
  }

  if (loading) return <div className="text-center py-16 text-gray-500">Loading build...</div>;
  if (error && !draft) return <div className="text-center py-16 text-red-400">{error}</div>;

  const preflightPassed = preflight?.passed === true;
  const preflightFailed = preflight && !preflight.passed;
  const hostFamily = detectPlatform();
  const selectedFamily = platformFamily(platform);
  const isCrossCompile = selectedFamily && selectedFamily !== hostFamily;
  const platformInfo = PLATFORM_INFO[selectedFamily || hostFamily];
  const BUILD_SKILL_KEYS = Object.keys(buildSkillModes);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <button onClick={onBack} className="text-sm text-gray-500 hover:text-white shrink-0">
            {"\u2190"} Builds
          </button>
          <input
            type="text"
            value={buildName}
            onChange={(e) => setBuildName(e.target.value)}
            className="bg-transparent border-b border-gray-700 focus:border-cyan-500 outline-none text-lg font-semibold text-gray-200 flex-1 min-w-0 px-1 py-0.5"
          />
        </div>
        <span className={`text-[10px] px-2 py-1 rounded ml-3 shrink-0 ${
          saveStatus === "saved" ? "text-gray-600" :
          saveStatus === "saving" ? "text-amber-400" :
          "text-red-400"
        }`}>
          {saveStatus === "saved" ? "Saved" : saveStatus === "saving" ? "Saving..." : "Save failed"}
        </span>
      </div>

      <div className="bg-gray-900 rounded-lg border border-gray-800 p-5 space-y-1">
        {draft?.template && (
          <div className="text-xs text-gray-600 mb-4">Template: {draft.template}</div>
        )}

        {/* Target Platform */}
        <Section title="Target Platform">
          <div className="flex items-center gap-4">
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200"
            >
              {PLATFORM_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            {platformInfo && (
              <div className="flex gap-3 text-[10px] text-gray-600">
                <span>TTS: {platformInfo.tts}</span>
                <span>STT: {platformInfo.stt}</span>
                <span>Inference: {platformInfo.inference}</span>
              </div>
            )}
          </div>
          {isCrossCompile && (
            <div className="mt-2 text-xs text-amber-400 bg-amber-900/20 border border-amber-800/30 rounded px-3 py-2">
              Cross-compilation is not supported. You must build on the target platform.
              This configuration will be saved for when you build on a {selectedFamily} machine.
            </div>
          )}
        </Section>

        {/* Database */}
        <Section title="Database">
          <select
            value={dbMode}
            onChange={(e) => setDbMode(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
          >
            <option value="seed">seed (blank)</option>
            <option value="filtered">filtered (sanitized)</option>
          </select>
        </Section>

        {/* Collections */}
        <Section title="Collections">
          <div className="space-y-2">
            {Object.entries(collections).map(([name, enabled]) => (
              <div key={name} className="flex items-center gap-3">
                <Toggle label={name} checked={enabled} onChange={() => toggleCollection(name)} />
                <select
                  value={collectionModes[name] || "compiled"}
                  onChange={(e) => setCollectionMode(name, e.target.value)}
                  disabled={!enabled}
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5 text-xs text-gray-300 disabled:opacity-40"
                >
                  <option value="compiled">compiled</option>
                  <option value="plugin">plugin</option>
                </select>
              </div>
            ))}
            {Object.keys(collections).length === 0 && (
              <span className="text-xs text-gray-600">No collections configured</span>
            )}
          </div>
        </Section>

        {/* Bootstrap Patches */}
        <Section title="Bootstrap Patches">
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {ALL_PATCHES.map((patch) => (
              <Toggle
                key={patch}
                label={patch.replace("bootstrap_", "").replace(/_/g, " ")}
                checked={patches.includes(patch)}
                onChange={() => togglePatch(patch)}
              />
            ))}
          </div>
        </Section>

        {/* Fallback Chain */}
        <Section title="LLM Fallback Chain">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              {chain.map((provider, i) => (
                <div key={provider} className="flex items-center gap-1">
                  {i > 0 && <span className="text-gray-600 text-xs">{"\u2192"}</span>}
                  <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm text-gray-200">
                    {provider}
                    <button onClick={() => moveChainItem(i, -1)} disabled={i === 0} className="text-gray-500 hover:text-white disabled:opacity-30 text-xs">{"\u2190"}</button>
                    <button onClick={() => moveChainItem(i, 1)} disabled={i === chain.length - 1} className="text-gray-500 hover:text-white disabled:opacity-30 text-xs">{"\u2192"}</button>
                    <button onClick={() => removeChainProvider(provider)} className="text-gray-500 hover:text-red-400 text-xs ml-0.5">{"\u00d7"}</button>
                  </span>
                </div>
              ))}
            </div>
            {ALL_PROVIDERS.filter((p) => !chain.includes(p)).length > 0 && (
              <div className="flex gap-2">
                {ALL_PROVIDERS.filter((p) => !chain.includes(p)).map((p) => (
                  <button key={p} onClick={() => addChainProvider(p)} className="text-xs px-2 py-0.5 rounded border border-dashed border-gray-700 text-gray-500 hover:text-cyan-400 hover:border-cyan-700">
                    + {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        </Section>

        {/* Frontend — Pages */}
        <Section title={"Frontend \u2014 Pages"}>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {Object.keys(pages).map((key) => (
              <Toggle key={key} label={key} checked={pages[key]} onChange={() => togglePage(key)} />
            ))}
          </div>
        </Section>

        {/* Frontend — Widgets */}
        <Section title={"Frontend \u2014 Widgets"}>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2">
            {Object.keys(widgets).map((key) => (
              <Toggle key={key} label={key} checked={widgets[key]} onChange={() => toggleWidget(key)} />
            ))}
          </div>
        </Section>

        {/* Frontend — Remap */}
        <Section title={"Frontend \u2014 Remap"}>
          <div className="flex items-center gap-4 text-sm">
            <label className="text-gray-400">
              Nexus target:
              <select value={remap.nexus?.to || "none"} onChange={(e) => setRemapTarget(e.target.value)} className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200">
                <option value="none">none</option>
                <option value="eclissi">eclissi</option>
                <option value="studio">studio</option>
              </select>
            </label>
            {remap.nexus && (
              <label className="text-gray-400">
                Position:
                <select value={remap.nexus?.position || "header"} onChange={(e) => setRemapPosition(e.target.value)} className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200">
                  <option value="header">header</option>
                  <option value="sidebar">sidebar</option>
                </select>
              </label>
            )}
          </div>
        </Section>

        {/* Nuitka Exclusions */}
        <Section title="Nuitka Exclusions">
          <div className="flex flex-wrap gap-1.5 mb-2">
            {excludedPkgs.map((pkg) => (
              <Tag key={pkg} label={pkg} onRemove={() => removeExcludedPkg(pkg)} />
            ))}
            {excludedPkgs.length === 0 && <span className="text-xs text-gray-600">No exclusions</span>}
          </div>
          <div className="flex gap-2">
            <input
              type="text" value={newPkg}
              onChange={(e) => setNewPkg(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addExcludedPkg()}
              placeholder="Add package..."
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 w-48"
            />
            <button onClick={addExcludedPkg} className="text-xs px-2 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700">Add</button>
          </div>
        </Section>

        {/* Skills */}
        <Section title="Skills">
          <div className="space-y-2">
            {BUILD_SKILL_KEYS.map((name) => (
              <div key={name} className="flex items-center gap-4">
                <span className="text-sm text-gray-300 min-w-[100px]">{name}</span>
                <select
                  value={buildSkillModes[name] || "compiled"}
                  onChange={(e) => setBuildSkillModes((p) => ({ ...p, [name]: e.target.value }))}
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5 text-xs text-gray-300"
                >
                  <option value="compiled">compiled</option>
                  <option value="plugin">plugin</option>
                  <option value="exclude">exclude</option>
                </select>
                {name in skills && (
                  <Toggle label="runtime" checked={skills[name]} onChange={() => toggleSkill(name)} />
                )}
              </div>
            ))}
          </div>
        </Section>

        {/* Personality */}
        <Section title="Personality">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
            <label className="text-gray-400">
              Token budget:
              <select value={tokenPreset} onChange={(e) => setTokenPreset(e.target.value)} className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200">
                <option value="minimal">minimal (1500)</option>
                <option value="balanced">balanced (3000)</option>
                <option value="rich">rich (5500)</option>
              </select>
            </label>
            <label className="text-gray-400">
              Gesture frequency:
              <select value={gestureFreq} onChange={(e) => setGestureFreq(e.target.value)} className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200">
                <option value="low">low</option>
                <option value="moderate">moderate</option>
                <option value="high">high</option>
              </select>
            </label>
            <Toggle label="Bootstrap on first launch" checked={bootOnFirst} onChange={setBootOnFirst} />
          </div>
        </Section>

        {/* Setup Wizard */}
        <Section title="Setup Wizard">
          <div className="space-y-3">
            <Toggle label="Show setup wizard on first run" checked={wizardEnabled} onChange={setWizardEnabled} />
            {wizardEnabled && (
              <>
                <div>
                  <div className="text-xs text-gray-500 mb-1.5">LLM Providers to offer:</div>
                  <div className="flex flex-wrap gap-x-5 gap-y-2">
                    {["groq", "claude", "gemini"].map((p) => (
                      <Toggle
                        key={p}
                        label={p}
                        checked={wizardProviders.includes(p)}
                        onChange={(checked) => {
                          setWizardProviders((prev) =>
                            checked ? [...prev, p] : prev.filter((x) => x !== p)
                          );
                        }}
                      />
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <label className="text-gray-400">
                    Default provider:
                    <select
                      value={wizardDefaultProvider}
                      onChange={(e) => setWizardDefaultProvider(e.target.value)}
                      className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
                    >
                      {wizardProviders.map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <Toggle label="Show voice configuration step" checked={wizardShowVoice} onChange={setWizardShowVoice} />
                <Toggle label="Show personality preset step" checked={wizardShowPersonality} onChange={setWizardShowPersonality} />
                <div>
                  <div className="text-xs text-gray-500 mb-1">Custom welcome subtitle (optional):</div>
                  <input
                    type="text"
                    value={wizardCustomWelcome}
                    onChange={(e) => setWizardCustomWelcome(e.target.value)}
                    placeholder="Let's get you set up."
                    className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 w-full"
                  />
                </div>
              </>
            )}
          </div>
        </Section>

        {/* Directives */}
        {directivesData && directivesData.seed_directives?.length > 0 && (
          <Section title="Directives">
            <div className="space-y-2">
              {directivesData.seed_directives.map((dir) => (
                <div key={dir.id} className="flex items-center justify-between p-2 rounded bg-gray-800/50 border border-gray-800">
                  <div className="flex items-center gap-3">
                    <Toggle label="" checked={!disabledDirIds.has(dir.id)} onChange={() => toggleDirective(dir.id)} />
                    <div>
                      <span className="text-sm text-gray-200">{dir.title}</span>
                      <div className="flex gap-2 mt-0.5">
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">{dir.trigger_type}</span>
                        <span className="text-xs text-gray-500">{dir.action}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* System Knowledge */}
        {sysKnowledge && sysKnowledge.length > 0 && (
          <Section title="System Knowledge">
            <div className="space-y-1.5">
              {sysKnowledge.map((doc) => (
                <div key={doc.filename} className="rounded bg-gray-800/30 border border-gray-800/50">
                  <button
                    onClick={() => setExpandedDoc(expandedDoc === doc.filename ? null : doc.filename)}
                    className="w-full text-left px-3 py-2 flex items-center justify-between text-sm"
                  >
                    <span className="text-gray-300">{doc.title}</span>
                    <span className="text-gray-600 text-xs">{expandedDoc === doc.filename ? "\u25B2" : "\u25BC"}</span>
                  </button>
                  {expandedDoc === doc.filename && (
                    <div className="px-3 pb-3 text-xs text-gray-500 whitespace-pre-wrap border-t border-gray-800/50 pt-2 max-h-48 overflow-y-auto">
                      {doc.content}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>

      {/* Preflight */}
      <div className="mt-6 p-4 rounded-lg border border-gray-800 bg-gray-900/50">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">Preflight Checks</h3>
          <button
            onClick={handlePreflight}
            disabled={preflightLoading || isCrossCompile}
            className="text-xs px-3 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700 disabled:opacity-50 transition-colors"
          >
            {preflightLoading ? "Checking..." : "Run Preflight"}
          </button>
        </div>
        {isCrossCompile && (
          <p className="text-xs text-gray-600 mb-2">Preflight unavailable for cross-platform targets</p>
        )}
        {preflightError && <p className="text-xs text-red-400 mb-2">{preflightError}</p>}
        {preflight && (
          <div className="space-y-1">
            {preflight.checks.map((check, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={check.status === "pass" ? "text-green-400" : check.status === "warn" ? "text-amber-400" : "text-red-400"}>
                  {check.status === "pass" ? "\u2713" : check.status === "warn" ? "\u26A0" : "\u2717"}
                </span>
                <span className="text-gray-400 min-w-[160px]">{check.name}</span>
                <span className="text-gray-600">{check.detail}</span>
              </div>
            ))}
            <div className={`text-xs font-medium mt-2 ${preflightPassed ? "text-green-400" : "text-red-400"}`}>
              {preflightPassed ? "All checks passed" : `${preflight.checks.filter((c) => c.status === "fail").length} check(s) failed`}
            </div>
          </div>
        )}
        {!preflight && !preflightError && !isCrossCompile && (
          <p className="text-xs text-gray-600">Click "Run Preflight" to validate before building</p>
        )}
      </div>

      {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

      {/* Actions */}
      <div className="mt-4 flex gap-3">
        <button
          onClick={handleBuild}
          disabled={starting || preflightFailed || isCrossCompile}
          className="px-5 py-2 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-50 font-medium text-sm"
        >
          {starting ? "Starting..." : "Start Build"}
        </button>
        <button onClick={onBack} className="px-5 py-2 rounded border border-gray-700 text-gray-400 hover:text-white text-sm">
          Back to Builds
        </button>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import { startBuild, runPreflight, fetchDirectives, fetchSystemKnowledge, fetchConfigFile } from "../api";
import { useWarnings } from "../hooks/useWarnings";
import WarningPanel from "./WarningPanel";
import DetailPanel from "./DetailPanel";
import BuildEstimator from "./BuildEstimator";
import SettingsPreConfig from "./SettingsPreConfig";

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

const ALL_PATCHES = [
  "bootstrap_001_sovereignty",
  "bootstrap_002_relationship",
  "bootstrap_003_honesty",
  "bootstrap_004_consciousness",
];

const ALL_PROVIDERS = ["claude", "groq", "local"];

export default function ConfigPreview({ profileName, manifest, onBuild, onBack }) {
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  // Editable state — initialized from manifest
  const fe = manifest?.frontend || {};
  const [pages, setPages] = useState(() => ({ ...fe.pages }));
  const [widgets, setWidgets] = useState(() => ({ ...fe.widgets }));
  const [remap, setRemap] = useState(() => ({ ...fe.remap }));

  // Collections — enabled state + build mode
  const manifestCollections = manifest?.collections || {};
  const [collections, setCollections] = useState(() => {
    const init = {};
    for (const [name, info] of Object.entries(manifestCollections)) {
      init[name] = info.enabled;
    }
    return init;
  });
  const [collectionModes, setCollectionModes] = useState(() => {
    const init = {};
    for (const [name, info] of Object.entries(manifestCollections)) {
      init[name] = info.mode || "compiled";
    }
    return init;
  });

  // Config — patches and chain
  const manifestConfig = manifest?.config || {};
  const [patches, setPatches] = useState(() => [...(manifestConfig.personality_patches || [])]);
  const [chain, setChain] = useState(() => [...(manifestConfig.fallback_chain || [])]);

  // Nuitka exclusions
  const manifestNuitka = manifest?.nuitka || {};
  const [excludedPkgs, setExcludedPkgs] = useState(() => [
    ...(manifestNuitka.exclude_packages || manifestNuitka.excluded_packages || []),
  ]);
  const [newPkg, setNewPkg] = useState("");

  // Skills — runtime enable/disable from config.skills
  const manifestSkills = manifest?.config?.skills || {};
  const SKILL_KEYS = ["math", "logic", "formatting", "reading", "diagnostic", "eden", "analytics", "options"];
  const [skills, setSkills] = useState(() => {
    const init = {};
    for (const [name, info] of Object.entries(manifestSkills)) {
      if (typeof info === "object" && "enabled" in info) init[name] = info.enabled;
    }
    return init;
  });

  // Skills — build mode (compiled/plugin/exclude) from top-level skills section
  const manifestBuildSkills = manifest?.skills || {};
  const BUILD_SKILL_KEYS = [...new Set([
    ...Object.keys(manifestBuildSkills),
    "math", "logic", "diagnostic", "reading", "analytics",
  ])];
  const [buildSkillModes, setBuildSkillModes] = useState(() => {
    const init = {};
    for (const key of BUILD_SKILL_KEYS) {
      init[key] = manifestBuildSkills[key]?.mode || "compiled";
    }
    return init;
  });

  // Personality
  const manifestPersonality = manifest?.config?.personality || {};
  const [tokenPreset, setTokenPreset] = useState(
    manifestPersonality.token_budget?.default_preset || "balanced"
  );
  const [gestureFreq, setGestureFreq] = useState(
    manifestPersonality.expression?.gesture_frequency || "moderate"
  );
  const [bootOnFirst, setBootOnFirst] = useState(
    manifestPersonality.bootstrap?.run_on_first_launch ?? true
  );

  // Directives (fetched separately)
  const [directivesData, setDirectivesData] = useState(null);
  const [disabledDirIds, setDisabledDirIds] = useState(new Set());

  // System Knowledge (fetched separately, read-only)
  const [sysKnowledge, setSysKnowledge] = useState(null);
  const [expandedDoc, setExpandedDoc] = useState(null);

  // Detail panels — lazy-loaded config files
  const [expandedDetails, setExpandedDetails] = useState({});
  const [configCache, setConfigCache] = useState({});

  // Settings pre-configuration overrides
  const [settingsOverrides, setSettingsOverrides] = useState(null);

  // Preflight checks
  const [preflight, setPreflight] = useState(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState(null);

  // Warnings
  const warnings = useWarnings({
    pages, widgets, collections, patches, chain, remap,
    secretsMode: manifest?.secrets_mode,
  });
  const hasErrors = warnings.some((w) => w.severity === "error");

  function handleWarningFix(fixKey) {
    if (fixKey.type === "collection") setCollections((p) => ({ ...p, [fixKey.name]: fixKey.value }));
    if (fixKey.type === "widget") setWidgets((p) => ({ ...p, [fixKey.name]: fixKey.value }));
    if (fixKey.type === "page") setPages((p) => ({ ...p, [fixKey.name]: fixKey.value }));
  }

  // Toggle detail panel and lazy-fetch config file
  const toggleDetail = useCallback((key, fileKey) => {
    setExpandedDetails((prev) => ({ ...prev, [key]: !prev[key] }));
    if (!configCache[fileKey]) {
      fetchConfigFile(fileKey)
        .then((data) => {
          if (data) setConfigCache((prev) => ({ ...prev, [fileKey]: data }));
        })
        .catch((e) => console.warn("Config file load failed:", fileKey, e));
    }
  }, [configCache]);

  useEffect(() => {
    fetchDirectives().then(setDirectivesData).catch((e) => console.warn("Directives load failed:", e));
    fetchSystemKnowledge().then(setSysKnowledge).catch((e) => console.warn("System knowledge load failed:", e));
  }, []);

  if (!manifest) return null;

  const db = manifest.database || {};

  // -- Toggle helpers --
  function togglePage(key) {
    setPages((prev) => ({ ...prev, [key]: !prev[key] }));
  }
  function toggleWidget(key) {
    setWidgets((prev) => ({ ...prev, [key]: !prev[key] }));
  }
  function toggleCollection(name) {
    setCollections((prev) => ({ ...prev, [name]: !prev[name] }));
  }
  function setCollectionMode(name, mode) {
    setCollectionModes((prev) => ({ ...prev, [name]: mode }));
  }
  function togglePatch(patch) {
    setPatches((prev) =>
      prev.includes(patch) ? prev.filter((p) => p !== patch) : [...prev, patch]
    );
  }

  function toggleSkill(name) {
    setSkills((prev) => ({ ...prev, [name]: !prev[name] }));
  }
  function toggleDirective(id) {
    setDisabledDirIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // -- Remap --
  function setRemapTarget(target) {
    if (target === "none") {
      const next = { ...remap };
      delete next.nexus;
      setRemap(next);
    } else {
      setRemap({
        ...remap,
        nexus: { from: "studio", to: target, position: remap.nexus?.position || "header" },
      });
    }
  }
  function setRemapPosition(position) {
    if (!remap.nexus) return;
    setRemap({ ...remap, nexus: { ...remap.nexus, position } });
  }

  // -- Chain reorder --
  function moveChainItem(index, direction) {
    const next = [...chain];
    const swapIdx = index + direction;
    if (swapIdx < 0 || swapIdx >= next.length) return;
    [next[index], next[swapIdx]] = [next[swapIdx], next[index]];
    setChain(next);
  }
  function addChainProvider(provider) {
    if (!chain.includes(provider)) setChain([...chain, provider]);
  }
  function removeChainProvider(provider) {
    setChain(chain.filter((p) => p !== provider));
  }

  // -- Nuitka exclusions --
  function addExcludedPkg() {
    const pkg = newPkg.trim();
    if (pkg && !excludedPkgs.includes(pkg)) {
      setExcludedPkgs([...excludedPkgs, pkg]);
      setNewPkg("");
    }
  }
  function removeExcludedPkg(pkg) {
    setExcludedPkgs(excludedPkgs.filter((p) => p !== pkg));
  }

  // -- Build overrides --
  function getOverrides() {
    const ov = {};
    // Frontend
    const feOv = {};
    if (JSON.stringify(pages) !== JSON.stringify(fe.pages)) feOv.pages = pages;
    if (JSON.stringify(widgets) !== JSON.stringify(fe.widgets)) feOv.widgets = widgets;
    if (JSON.stringify(remap) !== JSON.stringify(fe.remap)) feOv.remap = remap;
    if (Object.keys(feOv).length) ov.frontend = feOv;

    // Collections — enabled + mode
    const collOv = {};
    for (const [name, enabled] of Object.entries(collections)) {
      const origEnabled = manifestCollections[name]?.enabled;
      const origMode = manifestCollections[name]?.mode || "compiled";
      const newMode = collectionModes[name] || "compiled";
      if (enabled !== origEnabled || newMode !== origMode) {
        collOv[name] = { enabled, mode: newMode };
      }
    }
    if (Object.keys(collOv).length) ov.collections = collOv;

    // Config
    const cfgOv = {};
    if (JSON.stringify(patches) !== JSON.stringify(manifestConfig.personality_patches))
      cfgOv.personality_patches = patches;
    if (JSON.stringify(chain) !== JSON.stringify(manifestConfig.fallback_chain))
      cfgOv.fallback_chain = chain;
    if (Object.keys(cfgOv).length) ov.config = cfgOv;

    // Nuitka
    const origPkgs = manifestNuitka.exclude_packages || manifestNuitka.excluded_packages || [];
    if (JSON.stringify(excludedPkgs) !== JSON.stringify(origPkgs))
      ov.nuitka = { exclude_packages: excludedPkgs };

    // Skills — runtime enables
    const skillsOv = {};
    for (const [name, enabled] of Object.entries(skills)) {
      if (enabled !== manifestSkills[name]?.enabled) skillsOv[name] = enabled;
    }
    if (Object.keys(skillsOv).length) {
      ov.config = ov.config || {};
      ov.config.skills = skillsOv;
    }

    // Skills — build modes (compiled/plugin/exclude)
    const buildSkillsOv = {};
    for (const [name, mode] of Object.entries(buildSkillModes)) {
      const origMode = manifestBuildSkills[name]?.mode || "compiled";
      if (mode !== origMode) buildSkillsOv[name] = { mode };
    }
    if (Object.keys(buildSkillsOv).length) ov.skills = buildSkillsOv;

    // Personality
    const persOv = {};
    if (tokenPreset !== (manifestPersonality.token_budget?.default_preset || "balanced"))
      persOv.token_budget_preset = tokenPreset;
    if (gestureFreq !== (manifestPersonality.expression?.gesture_frequency || "moderate"))
      persOv.gesture_frequency = gestureFreq;
    if (bootOnFirst !== (manifestPersonality.bootstrap?.run_on_first_launch ?? true))
      persOv.run_on_first_launch = bootOnFirst;
    if (Object.keys(persOv).length) {
      ov.config = ov.config || {};
      ov.config.personality = persOv;
    }

    // Directives
    if (disabledDirIds.size > 0) {
      ov.config = ov.config || {};
      ov.config.directives = { disabled_ids: [...disabledDirIds] };
    }

    // Settings pre-configuration
    if (settingsOverrides && Object.keys(settingsOverrides).length > 0) {
      ov.settings_overrides = settingsOverrides;
    }

    return Object.keys(ov).length ? ov : null;
  }

  async function handlePreflight() {
    setPreflightLoading(true);
    setPreflightError(null);
    setPreflight(null);
    try {
      const overrides = getOverrides();
      const result = await runPreflight(profileName, "auto", overrides);
      setPreflight(result);
    } catch (e) {
      setPreflightError(e.message);
    }
    setPreflightLoading(false);
  }

  async function handleBuild() {
    setStarting(true);
    setError(null);
    try {
      const overrides = getOverrides();
      const { build_id } = await startBuild(profileName, "auto", overrides);
      onBuild(build_id);
    } catch (e) {
      setError(e.message);
      setStarting(false);
    }
  }

  const preflightPassed = preflight?.passed === true;
  const preflightFailed = preflight && !preflight.passed;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">
          Build Preview: <span className="text-cyan-400">{manifest.profile}</span>
        </h2>
        <button onClick={onBack} className="text-sm text-gray-400 hover:text-white">
          Back
        </button>
      </div>

      <div className="bg-gray-900 rounded-lg border border-gray-800 p-5 space-y-1">
        <div className="text-sm text-gray-400 mb-4">
          Version: {manifest.version} | Platform: {manifest.platform}
        </div>

        <WarningPanel warnings={warnings} onFix={handleWarningFix} />

        <Section title="Database">
          <div className="text-sm">Mode: {db.mode || "seed"}</div>
        </Section>

        {/* Collections — toggles + mode */}
        <Section title="Collections">
          <div className="space-y-2">
            {Object.entries(manifestCollections).map(([name, info]) => (
              <div key={name}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Toggle
                      label={name}
                      checked={collections[name]}
                      onChange={() => toggleCollection(name)}
                    />
                    <select
                      value={collectionModes[name] || "compiled"}
                      onChange={(e) => setCollectionMode(name, e.target.value)}
                      disabled={!collections[name]}
                      className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5 text-xs text-gray-300 disabled:opacity-40"
                    >
                      <option value="compiled">compiled</option>
                      <option value="plugin">plugin</option>
                    </select>
                  </div>
                  <span className="text-xs text-gray-600">
                    {info.exists
                      ? `${(info.size / (1024 * 1024)).toFixed(1)} MB`
                      : "NOT FOUND"}
                  </span>
                </div>
                {configCache.registry && (
                  <DetailPanel
                    title={`View ${name} details`}
                    isOpen={expandedDetails[`coll-${name}`]}
                    onToggle={() => toggleDetail(`coll-${name}`, "registry")}
                  >
                    {(() => {
                      const reg = configCache.registry;
                      const entry = reg?.collections?.[name] || reg?.[name];
                      if (!entry) return <span className="text-gray-600">No registry entry</span>;
                      return (
                        <div className="space-y-1">
                          {entry.db_path && <div><span className="text-gray-400">db_path:</span> {entry.db_path}</div>}
                          {entry.schema_type && <div><span className="text-gray-400">schema:</span> {entry.schema_type}</div>}
                          {entry.chunk_count != null && <div><span className="text-gray-400">chunks:</span> {entry.chunk_count}</div>}
                          {entry.doc_count != null && <div><span className="text-gray-400">docs:</span> {entry.doc_count}</div>}
                          {entry.tags && <div><span className="text-gray-400">tags:</span> {Array.isArray(entry.tags) ? entry.tags.join(", ") : String(entry.tags)}</div>}
                        </div>
                      );
                    })()}
                  </DetailPanel>
                )}
                {!configCache.registry && expandedDetails[`coll-${name}`] === undefined && (
                  <button
                    onClick={() => toggleDetail(`coll-${name}`, "registry")}
                    className="text-xs text-gray-600 hover:text-gray-400 mt-0.5 ml-11"
                  >
                    View details
                  </button>
                )}
              </div>
            ))}
          </div>
        </Section>

        {/* Bootstrap patches — checkboxes */}
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
          <DetailPanel
            title="View patch content"
            isOpen={expandedDetails["bootstrap"]}
            onToggle={() => toggleDetail("bootstrap", "bootstrap-patches")}
          >
            {configCache["bootstrap-patches"] ? (
              <div className="space-y-2">
                {(configCache["bootstrap-patches"]?.bootstrap?.seed_patches ||
                  configCache["bootstrap-patches"]?.seed_patches ||
                  []).map((p, i) => (
                  <div key={i} className="p-2 rounded bg-gray-800/50 border border-gray-800">
                    <div className="text-gray-300 text-xs font-medium mb-1">
                      {p.topic || p.id || `Patch ${i + 1}`}
                      {p.subtopic && <span className="text-gray-500 ml-1">/ {p.subtopic}</span>}
                    </div>
                    <div className="text-gray-500 text-xs whitespace-pre-wrap">{p.content || p.text || JSON.stringify(p, null, 2)}</div>
                    <div className="flex gap-3 mt-1 text-gray-600 text-xs">
                      {p.lock_in != null && <span>lock_in: {p.lock_in}</span>}
                      {p.metadata?.bootstrap && <span className="text-purple-400">core value</span>}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-gray-600">Loading...</span>
            )}
          </DetailPanel>
        </Section>

        {/* Fallback chain — reorderable */}
        <Section title="LLM Fallback Chain">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              {chain.map((provider, i) => (
                <div key={provider} className="flex items-center gap-1">
                  {i > 0 && <span className="text-gray-600 text-xs">{"\u2192"}</span>}
                  <span className="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-800 border border-gray-700 text-sm text-gray-200">
                    {provider}
                    <button
                      onClick={() => moveChainItem(i, -1)}
                      disabled={i === 0}
                      className="text-gray-500 hover:text-white disabled:opacity-30 text-xs"
                    >
                      {"\u2190"}
                    </button>
                    <button
                      onClick={() => moveChainItem(i, 1)}
                      disabled={i === chain.length - 1}
                      className="text-gray-500 hover:text-white disabled:opacity-30 text-xs"
                    >
                      {"\u2192"}
                    </button>
                    <button
                      onClick={() => removeChainProvider(provider)}
                      className="text-gray-500 hover:text-red-400 text-xs ml-0.5"
                    >
                      {"\u00d7"}
                    </button>
                  </span>
                </div>
              ))}
            </div>
            {ALL_PROVIDERS.filter((p) => !chain.includes(p)).length > 0 && (
              <div className="flex gap-2">
                {ALL_PROVIDERS.filter((p) => !chain.includes(p)).map((p) => (
                  <button
                    key={p}
                    onClick={() => addChainProvider(p)}
                    className="text-xs px-2 py-0.5 rounded border border-dashed border-gray-700 text-gray-500 hover:text-cyan-400 hover:border-cyan-700"
                  >
                    + {p}
                  </button>
                ))}
              </div>
            )}
          </div>
          <DetailPanel
            title="View provider config"
            isOpen={expandedDetails["fallback"]}
            onToggle={() => toggleDetail("fallback", "fallback-chain")}
          >
            {configCache["fallback-chain"] ? (
              <pre className="text-xs text-gray-500 whitespace-pre-wrap">
                {JSON.stringify(configCache["fallback-chain"], null, 2)}
              </pre>
            ) : (
              <span className="text-gray-600">Loading...</span>
            )}
          </DetailPanel>
        </Section>

        <Section title="Secrets">
          <div className="text-sm">{manifest.secrets_mode || "template"}</div>
        </Section>

        {/* Frontend — Pages */}
        <Section title="Frontend \u2014 Pages">
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {Object.keys(pages).map((key) => (
              <Toggle
                key={key}
                label={key}
                checked={pages[key]}
                onChange={() => togglePage(key)}
              />
            ))}
          </div>
        </Section>

        {/* Frontend — Widgets */}
        <Section title="Frontend \u2014 Widgets">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2">
            {Object.keys(widgets).map((key) => (
              <Toggle
                key={key}
                label={key}
                checked={widgets[key]}
                onChange={() => toggleWidget(key)}
              />
            ))}
          </div>
        </Section>

        {/* Frontend — Remap */}
        <Section title="Frontend \u2014 Remap">
          <div className="flex items-center gap-4 text-sm">
            <label className="text-gray-400">
              Nexus target:
              <select
                value={remap.nexus?.to || "none"}
                onChange={(e) => setRemapTarget(e.target.value)}
                className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
              >
                <option value="none">none</option>
                <option value="eclissi">eclissi</option>
                <option value="studio">studio</option>
              </select>
            </label>
            {remap.nexus && (
              <label className="text-gray-400">
                Position:
                <select
                  value={remap.nexus?.position || "header"}
                  onChange={(e) => setRemapPosition(e.target.value)}
                  className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
                >
                  <option value="header">header</option>
                  <option value="sidebar">sidebar</option>
                </select>
              </label>
            )}
          </div>
        </Section>

        {/* Nuitka exclusions — removable tags */}
        <Section title="Nuitka Exclusions">
          <div className="flex flex-wrap gap-1.5 mb-2">
            {excludedPkgs.map((pkg) => (
              <Tag key={pkg} label={pkg} onRemove={() => removeExcludedPkg(pkg)} />
            ))}
            {excludedPkgs.length === 0 && (
              <span className="text-xs text-gray-600">No exclusions</span>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newPkg}
              onChange={(e) => setNewPkg(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addExcludedPkg()}
              placeholder="Add package..."
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 w-48"
            />
            <button
              onClick={addExcludedPkg}
              className="text-xs px-2 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700"
            >
              Add
            </button>
          </div>
        </Section>

        {/* Skills — build mode + runtime toggles */}
        <Section title="Skills">
          <div className="space-y-2">
            {BUILD_SKILL_KEYS.map((name) => (
              <div key={name} className="flex items-center gap-4">
                <span className="text-sm text-gray-300 min-w-[100px]">{name}</span>
                <select
                  value={buildSkillModes[name] || "compiled"}
                  onChange={(e) => setBuildSkillModes((prev) => ({ ...prev, [name]: e.target.value }))}
                  className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5 text-xs text-gray-300"
                >
                  <option value="compiled">compiled</option>
                  <option value="plugin">plugin</option>
                  <option value="exclude">exclude</option>
                </select>
                {name in skills && (
                  <Toggle
                    label="runtime"
                    checked={skills[name]}
                    onChange={() => toggleSkill(name)}
                  />
                )}
              </div>
            ))}
          </div>
        </Section>

        {/* Personality tuning */}
        <Section title="Personality">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm">
            <label className="text-gray-400">
              Token budget:
              <select
                value={tokenPreset}
                onChange={(e) => setTokenPreset(e.target.value)}
                className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
              >
                <option value="minimal">minimal (1500)</option>
                <option value="balanced">balanced (3000)</option>
                <option value="rich">rich (5500)</option>
              </select>
            </label>
            <label className="text-gray-400">
              Gesture frequency:
              <select
                value={gestureFreq}
                onChange={(e) => setGestureFreq(e.target.value)}
                className="ml-2 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200"
              >
                <option value="low">low</option>
                <option value="moderate">moderate</option>
                <option value="high">high</option>
              </select>
            </label>
            <Toggle
              label="Bootstrap on first launch"
              checked={bootOnFirst}
              onChange={setBootOnFirst}
            />
          </div>
        </Section>

        {/* Settings Pre-Configuration */}
        <Section title="Pre-Configure Settings">
          <SettingsPreConfig manifest={manifest} onChange={setSettingsOverrides} />
        </Section>

        {/* Directives */}
        {directivesData && directivesData.seed_directives?.length > 0 && (
          <Section title="Directives">
            <div className="space-y-2">
              {directivesData.seed_directives.map((dir) => (
                <div
                  key={dir.id}
                  className="flex items-center justify-between p-2 rounded bg-gray-800/50 border border-gray-800"
                >
                  <div className="flex items-center gap-3">
                    <Toggle
                      label=""
                      checked={!disabledDirIds.has(dir.id)}
                      onChange={() => toggleDirective(dir.id)}
                    />
                    <div>
                      <span className="text-sm text-gray-200">{dir.title}</span>
                      <div className="flex gap-2 mt-0.5">
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                          {dir.trigger_type}
                        </span>
                        <span className="text-xs text-gray-500">{dir.action}</span>
                        <span className={`text-xs ${dir.priority === "high" ? "text-amber-400" : "text-gray-500"}`}>
                          {dir.priority}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {directivesData.seed_skills?.length > 0 && (
              <div className="mt-3">
                <h4 className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">Seed Skills</h4>
                {directivesData.seed_skills.map((sk) => (
                  <div key={sk.id} className="p-2 rounded bg-gray-800/30 border border-gray-800/50 mb-1.5">
                    <span className="text-sm text-gray-300">{sk.title}</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {sk.steps?.map((step, i) => (
                        <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-gray-700/50 text-gray-500">
                          {step}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Section>
        )}

        {/* System Knowledge — read-only */}
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
                    <span className="text-gray-600 text-xs">
                      {expandedDoc === doc.filename ? "\u25B2" : "\u25BC"}
                    </span>
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

        <BuildEstimator
          pages={pages}
          widgets={widgets}
          collections={collections}
          manifestCollections={manifestCollections}
          chain={chain}
          patches={patches}
        />
      </div>

      {/* Preflight Checks */}
      <div className="mt-6 p-4 rounded-lg border border-gray-800 bg-gray-900/50">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">
            Preflight Checks
          </h3>
          <button
            onClick={handlePreflight}
            disabled={preflightLoading}
            className="text-xs px-3 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700 disabled:opacity-50 transition-colors"
          >
            {preflightLoading ? "Checking..." : "Run Preflight"}
          </button>
        </div>
        {preflightError && (
          <p className="text-xs text-red-400 mb-2">{preflightError}</p>
        )}
        {preflight && (
          <div className="space-y-1">
            {preflight.checks.map((check, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className={
                  check.status === "pass" ? "text-green-400" :
                  check.status === "warn" ? "text-amber-400" :
                  "text-red-400"
                }>
                  {check.status === "pass" ? "\u2713" : check.status === "warn" ? "\u26A0" : "\u2717"}
                </span>
                <span className="text-gray-400 min-w-[160px]">{check.name}</span>
                <span className="text-gray-600">{check.detail}</span>
              </div>
            ))}
            <div className={`text-xs font-medium mt-2 ${preflightPassed ? "text-green-400" : "text-red-400"}`}>
              {preflightPassed ? "All checks passed" : `${preflight.checks.filter(c => c.status === "fail").length} check(s) failed`}
            </div>
          </div>
        )}
        {!preflight && !preflightError && (
          <p className="text-xs text-gray-600">Click "Run Preflight" to validate before building</p>
        )}
      </div>

      {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

      <div className="mt-4 flex gap-3">
        <button
          onClick={handleBuild}
          disabled={starting || hasErrors || preflightFailed}
          title={
            hasErrors ? "Fix errors above before building" :
            preflightFailed ? "Fix preflight failures before building" :
            !preflight ? "Run preflight checks first" : undefined
          }
          className="px-5 py-2 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-50 font-medium text-sm"
        >
          {starting ? "Starting..." : "Start Build"}
        </button>
        <button
          onClick={onBack}
          className="px-5 py-2 rounded border border-gray-700 text-gray-400 hover:text-white text-sm"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

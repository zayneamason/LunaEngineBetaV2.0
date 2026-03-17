import { useState } from "react";

function Card({ title, defaultOpen, children }) {
  const [open, setOpen] = useState(defaultOpen || false);
  return (
    <div className="rounded bg-gray-800/40 border border-gray-800/60 mb-2">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-3 py-2 flex items-center justify-between text-sm text-gray-300 hover:text-white"
      >
        <span>{title}</span>
        <span className="text-gray-600 text-xs">{open ? "\u25B2" : "\u25BC"}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-gray-800/50 pt-2 space-y-3">
          {children}
        </div>
      )}
    </div>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-400">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="ml-auto bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200 text-xs"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}

function ToggleField({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none text-sm text-gray-400">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative w-8 h-4 rounded-full transition-colors ${checked ? "bg-cyan-600" : "bg-gray-700"}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${checked ? "translate-x-4" : ""}`} />
      </button>
      <span className={checked ? "text-gray-200" : "text-gray-500"}>{label}</span>
    </label>
  );
}

export default function SettingsPreConfig({ manifest, onChange }) {
  const cfg = manifest?.config || {};
  const pers = cfg.personality || {};

  const [overrides, setOverrides] = useState({});

  function update(section, key, value) {
    setOverrides((prev) => {
      const next = { ...prev, [section]: { ...prev[section], [key]: value } };
      onChange(next);
      return next;
    });
  }

  const get = (section, key, fallback) =>
    overrides[section]?.[key] ?? fallback;

  return (
    <div>
      {/* LLM */}
      <Card title="LLM Providers">
        <SelectField
          label="Default provider"
          value={get("llm", "default_provider", cfg.fallback_chain?.[0] || "groq")}
          onChange={(v) => update("llm", "default_provider", v)}
          options={[
            { value: "groq", label: "Groq" },
            { value: "claude", label: "Claude" },
            { value: "gemini", label: "Gemini" },
            { value: "local", label: "Local" },
          ]}
        />
        <p className="text-xs text-gray-600">API keys are configured at runtime via Settings.</p>
      </Card>

      {/* Personality */}
      <Card title="Personality">
        <SelectField
          label="Token budget"
          value={get("personality", "token_budget_preset", pers.token_budget?.default_preset || "balanced")}
          onChange={(v) => update("personality", "token_budget_preset", v)}
          options={[
            { value: "minimal", label: "Minimal (1500)" },
            { value: "balanced", label: "Balanced (3000)" },
            { value: "rich", label: "Rich (5500)" },
          ]}
        />
        <SelectField
          label="Gesture frequency"
          value={get("personality", "gesture_frequency", pers.expression?.gesture_frequency || "moderate")}
          onChange={(v) => update("personality", "gesture_frequency", v)}
          options={[
            { value: "minimal", label: "Minimal" },
            { value: "moderate", label: "Moderate" },
            { value: "expressive", label: "Expressive" },
          ]}
        />
        <SelectField
          label="Display mode"
          value={get("personality", "display_mode", "visible")}
          onChange={(v) => update("personality", "display_mode", v)}
          options={[
            { value: "visible", label: "Visible" },
            { value: "stripped", label: "Stripped" },
          ]}
        />
        <ToggleField
          label="Bootstrap on first launch"
          checked={get("personality", "run_on_first_launch", pers.bootstrap?.run_on_first_launch ?? true)}
          onChange={(v) => update("personality", "run_on_first_launch", v)}
        />
      </Card>

      {/* Voice */}
      <Card title="Voice">
        <SelectField
          label="TTS provider"
          value={get("voice", "tts_provider", "piper")}
          onChange={(v) => update("voice", "tts_provider", v)}
          options={[
            { value: "piper", label: "Piper" },
            { value: "apple", label: "Apple TTS" },
            { value: "edge", label: "Edge TTS" },
          ]}
        />
        <SelectField
          label="TTS voice"
          value={get("voice", "tts_voice", "en_US-amy-medium")}
          onChange={(v) => update("voice", "tts_voice", v)}
          options={[
            { value: "en_US-amy-medium", label: "Amy (US, medium)" },
            { value: "en_US-lessac-medium", label: "Lessac (US, medium)" },
            { value: "en_GB-alba-medium", label: "Alba (GB, medium)" },
          ]}
        />
        <SelectField
          label="STT provider"
          value={get("voice", "stt_provider", "mlx_whisper")}
          onChange={(v) => update("voice", "stt_provider", v)}
          options={[
            { value: "mlx_whisper", label: "MLX Whisper" },
            { value: "apple", label: "Apple Speech" },
            { value: "google", label: "Google STT" },
          ]}
        />
        <SelectField
          label="Mode"
          value={get("voice", "mode", "push_to_talk")}
          onChange={(v) => update("voice", "mode", v)}
          options={[
            { value: "push_to_talk", label: "Push to Talk" },
            { value: "hands_free", label: "Hands Free" },
          ]}
        />
      </Card>

      {/* Memory */}
      <Card title="Memory">
        <SelectField
          label="Max active patches"
          value={get("memory", "max_active_patches", String(pers.personality_patch_storage?.max_active_patches || 25))}
          onChange={(v) => update("memory", "max_active_patches", parseInt(v, 10))}
          options={[
            { value: "10", label: "10" },
            { value: "25", label: "25 (default)" },
            { value: "50", label: "50" },
            { value: "100", label: "100" },
          ]}
        />
        <SelectField
          label="Decay threshold"
          value={get("memory", "decay_threshold", String(pers.personality_patch_storage?.decay_threshold || 0.3))}
          onChange={(v) => update("memory", "decay_threshold", parseFloat(v))}
          options={[
            { value: "0.1", label: "0.1 (aggressive)" },
            { value: "0.3", label: "0.3 (default)" },
            { value: "0.5", label: "0.5 (conservative)" },
          ]}
        />
        <SelectField
          label="Consolidation threshold"
          value={get("memory", "consolidation_threshold", String(pers.personality_patch_storage?.consolidation_threshold || 0.85))}
          onChange={(v) => update("memory", "consolidation_threshold", parseFloat(v))}
          options={[
            { value: "0.7", label: "0.7 (loose)" },
            { value: "0.85", label: "0.85 (default)" },
            { value: "0.95", label: "0.95 (strict)" },
          ]}
        />
      </Card>

      {/* Skills */}
      <Card title="Skills">
        <ToggleField
          label="Eden (creative generation)"
          checked={get("skills", "eden", true)}
          onChange={(v) => update("skills", "eden", v)}
        />
        <ToggleField
          label="Analytics"
          checked={get("skills", "analytics", true)}
          onChange={(v) => update("skills", "analytics", v)}
        />
        <ToggleField
          label="Reading (document analysis)"
          checked={get("skills", "reading", true)}
          onChange={(v) => update("skills", "reading", v)}
        />
      </Card>
    </div>
  );
}

import { useState } from "react";

const SEVERITY_CONFIG = {
  error: { bg: "bg-red-900/30", border: "border-red-800/50", icon: "\u26D4", label: "Errors", text: "text-red-300" },
  warn:  { bg: "bg-amber-900/30", border: "border-amber-800/50", icon: "\u26A0\uFE0F", label: "Warnings", text: "text-amber-300" },
  info:  { bg: "bg-blue-900/30", border: "border-blue-800/50", icon: "\u2139\uFE0F", label: "Info", text: "text-blue-300" },
};

export default function WarningPanel({ warnings, onFix }) {
  const [showInfo, setShowInfo] = useState(false);

  if (!warnings || warnings.length === 0) return null;

  const groups = { error: [], warn: [], info: [] };
  for (const w of warnings) {
    groups[w.severity]?.push(w);
  }

  return (
    <div className="mb-4 space-y-2">
      {["error", "warn", "info"].map((severity) => {
        const items = groups[severity];
        if (items.length === 0) return null;
        const cfg = SEVERITY_CONFIG[severity];

        if (severity === "info" && !showInfo) {
          return (
            <button
              key={severity}
              onClick={() => setShowInfo(true)}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              {items.length} info note{items.length > 1 ? "s" : ""} (click to show)
            </button>
          );
        }

        return (
          <div key={severity} className={`rounded-lg ${cfg.bg} border ${cfg.border} p-3`}>
            <h4 className={`text-xs font-semibold uppercase tracking-wider mb-2 ${cfg.text}`}>
              {cfg.label} ({items.length})
            </h4>
            <div className="space-y-1.5">
              {items.map((w) => (
                <div key={w.id} className="flex items-start gap-2 text-sm">
                  <span className="flex-shrink-0 text-xs mt-0.5">{cfg.icon}</span>
                  <span className={cfg.text}>{w.message}</span>
                  {w.fixKey && onFix && (
                    <button
                      onClick={() => onFix(w.fixKey)}
                      className="ml-auto flex-shrink-0 text-xs px-2 py-0.5 rounded border border-gray-600 text-gray-400 hover:text-white hover:border-gray-400"
                    >
                      Fix
                    </button>
                  )}
                </div>
              ))}
            </div>
            {severity === "info" && (
              <button
                onClick={() => setShowInfo(false)}
                className="text-xs text-blue-500 hover:text-blue-400 mt-1"
              >
                hide
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

import { DEPENDENCIES } from "../lib/dependencies";

const BASE_ENGINE_SIZE_MB = 120;

export default function BuildEstimator({ pages, widgets, collections, manifestCollections, chain, patches }) {
  // Estimated size: base engine + enabled collections
  let sizeMB = BASE_ENGINE_SIZE_MB;
  for (const [name, enabled] of Object.entries(collections)) {
    if (enabled && manifestCollections[name]?.exists) {
      sizeMB += (manifestCollections[name].size || 0) / (1024 * 1024);
    }
  }

  // Count enabled pages
  const pageCount = Object.values(pages).filter(Boolean).length;

  // Count enabled widgets whose parent page is also enabled
  let widgetCount = 0;
  for (const [name, enabled] of Object.entries(widgets)) {
    if (!enabled) continue;
    const dep = DEPENDENCIES.widgets[name];
    if (!dep || pages[dep.needs_page] !== false) {
      widgetCount++;
    }
  }

  // Feature summary
  const collCount = Object.values(collections).filter(Boolean).length;
  const chainStr = chain.length > 0 ? chain.join(" \u2192 ") : "none";
  const patchCount = patches.length;

  const summary = [
    `${collCount} collection${collCount !== 1 ? "s" : ""}`,
    `LLM: ${chainStr}`,
    `${patchCount} bootstrap patch${patchCount !== 1 ? "es" : ""}`,
  ].join(", ");

  return (
    <div className="sticky bottom-0 mt-4 -mx-5 -mb-5 px-5 py-3 bg-gray-900/95 border-t border-gray-700 backdrop-blur-sm">
      <div className="flex items-center justify-between text-xs text-gray-400">
        <div className="flex items-center gap-4">
          <span>
            <span className="text-gray-200 font-medium">{sizeMB.toFixed(0)} MB</span> est.
          </span>
          <span>
            <span className="text-gray-200 font-medium">{pageCount}</span> page{pageCount !== 1 ? "s" : ""}
          </span>
          <span>
            <span className="text-gray-200 font-medium">{widgetCount}</span> widget{widgetCount !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="text-gray-500 truncate max-w-md">{summary}</div>
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { fetchDrafts, createDraft, deleteDraft } from "../api";

const STATUS_COLORS = {
  draft: "bg-gray-700 text-gray-300",
  configured: "bg-cyan-900/60 text-cyan-400",
  building: "bg-amber-900/60 text-amber-400",
  complete: "bg-green-900/60 text-green-400",
  failed: "bg-red-900/60 text-red-400",
};

function timeAgo(iso) {
  if (!iso) return "";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

export default function BuildManager({ profiles, onEditDraft, onBuildDraft }) {
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);

  useEffect(() => {
    refreshDrafts();
  }, []);

  function refreshDrafts() {
    setLoading(true);
    fetchDrafts()
      .then(setDrafts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  async function handleCreateDraft(templateName) {
    setShowTemplatePicker(false);
    setError(null);
    try {
      const draft = await createDraft(templateName || null);
      setDrafts((prev) => [draft, ...prev]);
      onEditDraft(draft.id);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleDeleteDraft(id, e) {
    e.stopPropagation();
    try {
      await deleteDraft(id);
      setDrafts((prev) => prev.filter((d) => d.id !== id));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">Builds</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Create, configure, and compile Luna builds
          </p>
        </div>
        <button
          onClick={() => setShowTemplatePicker(true)}
          className="px-4 py-2 rounded bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-colors"
        >
          + New Build
        </button>
      </div>

      {error && <p className="text-red-400 text-xs mb-4">{error}</p>}

      {/* Template Picker Modal */}
      {showTemplatePicker && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowTemplatePicker(false)}>
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-base font-semibold mb-4">Choose a Template</h3>
            <div className="space-y-2 mb-4 max-h-64 overflow-y-auto">
              <button
                onClick={() => handleCreateDraft(null)}
                className="w-full text-left px-4 py-3 rounded-lg border border-dashed border-gray-700 hover:border-purple-600 hover:bg-gray-800/50 transition-colors"
              >
                <div className="text-sm text-gray-300">Blank Build</div>
                <div className="text-[10px] text-gray-600">Start from default settings</div>
              </button>
              {profiles.map((p) => (
                <button
                  key={p.name}
                  onClick={() => handleCreateDraft(p.name)}
                  className="w-full text-left px-4 py-3 rounded-lg border border-gray-800 hover:border-purple-600 hover:bg-gray-800/50 transition-colors"
                >
                  <div className="text-sm text-gray-200">{p.display_name || p.name}</div>
                  <div className="text-[10px] text-gray-500 mt-0.5">
                    {p.description || `${p.database_mode || "seed"} mode`}
                    {p.collections_count ? ` · ${p.collections_count} collections` : ""}
                  </div>
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowTemplatePicker(false)}
              className="w-full text-center text-xs text-gray-500 hover:text-gray-300 py-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Drafts List */}
      {loading ? (
        <div className="text-center py-16 text-gray-500">Loading builds...</div>
      ) : drafts.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-gray-500 mb-2">No builds yet</div>
          <button
            onClick={() => setShowTemplatePicker(true)}
            className="text-sm text-purple-400 hover:text-purple-300"
          >
            Create your first build
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {drafts.map((draft) => (
            <div
              key={draft.id}
              onClick={() => draft.status !== "building" && onEditDraft(draft.id)}
              className="p-4 rounded-lg border border-gray-800 hover:border-gray-600 bg-gray-900/40 cursor-pointer transition-colors group"
            >
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-gray-200 truncate">
                      {draft.name}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded ${STATUS_COLORS[draft.status] || STATUS_COLORS.draft}`}>
                      {draft.status}
                    </span>
                  </div>
                  <div className="flex gap-3 text-[10px] text-gray-600">
                    {draft.template && <span>from {draft.template}</span>}
                    <span>{draft.platform || "auto"}</span>
                    <span>{timeAgo(draft.updated_at)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  {(draft.status === "configured" || draft.status === "draft") && (
                    <button
                      onClick={(e) => { e.stopPropagation(); onBuildDraft && onBuildDraft(draft.id); }}
                      className="text-xs px-3 py-1 rounded bg-green-700 hover:bg-green-600 text-white"
                    >
                      Build
                    </button>
                  )}
                  <button
                    onClick={(e) => handleDeleteDraft(draft.id, e)}
                    className="text-xs px-2 py-1 text-gray-600 hover:text-red-400"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

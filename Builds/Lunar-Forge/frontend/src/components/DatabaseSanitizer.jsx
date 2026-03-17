import { useState, useEffect } from "react";
import {
  fetchSanitizerStats,
  fetchSanitizerEntities,
  fetchSanitizerNodeTypes,
  runSanitizerPreview,
  runSanitizerExport,
  fetchSanitizerTemplates,
  loadSanitizerTemplate,
  saveSanitizerTemplate,
  deleteSanitizerTemplate,
} from "../api";

function Section({ title, action, children }) {
  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">
          {title}
        </h3>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function DatabaseSanitizer() {
  const [stats, setStats] = useState(null);
  const [entities, setEntities] = useState([]);
  const [nodeTypes, setNodeTypes] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter state
  const [selectedEntities, setSelectedEntities] = useState(new Set());
  const [selectedNodeTypes, setSelectedNodeTypes] = useState(new Set());
  const [minConfidence, setMinConfidence] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeConversations, setIncludeConversations] = useState(false);
  const [outputName, setOutputName] = useState("filtered");

  // Templates
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [templateName, setTemplateName] = useState("");
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);

  // Results
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [exportResult, setExportResult] = useState(null);
  const [exportLoading, setExportLoading] = useState(false);
  const [actionError, setActionError] = useState(null);

  useEffect(() => {
    Promise.all([
      fetchSanitizerStats(),
      fetchSanitizerEntities(),
      fetchSanitizerNodeTypes(),
      fetchSanitizerTemplates(),
    ])
      .then(([s, e, n, t]) => {
        setStats(s);
        setEntities(e);
        setNodeTypes(n);
        setTemplates(t);
        // Default: select system entities + all node types
        setSelectedEntities(new Set(e.filter((ent) => ent.origin === "system").map((ent) => ent.id)));
        setSelectedNodeTypes(new Set(Object.keys(n)));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function toggleEntity(id) {
    setSelectedEntities((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setPreview(null);
  }

  function selectAllEntities() {
    setSelectedEntities(new Set(entities.map((e) => e.id)));
    setPreview(null);
  }

  function selectNoEntities() {
    // Keep system entities
    setSelectedEntities(new Set(entities.filter((e) => e.origin === "system").map((e) => e.id)));
    setPreview(null);
  }

  function toggleNodeType(type) {
    setSelectedNodeTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
    setPreview(null);
  }

  function buildConfig() {
    const config = {
      include_entities: [...selectedEntities],
      include_node_types: [...selectedNodeTypes],
      min_confidence: minConfidence,
      include_conversations: includeConversations,
      output_name: outputName,
    };
    if (dateFrom) config.date_from = dateFrom;
    if (dateTo) config.date_to = dateTo;
    return config;
  }

  async function handlePreview() {
    setPreviewLoading(true);
    setActionError(null);
    setExportResult(null);
    try {
      const result = await runSanitizerPreview(buildConfig());
      setPreview(result);
    } catch (e) {
      setActionError(e.message);
    }
    setPreviewLoading(false);
  }

  async function handleLoadTemplate() {
    if (!selectedTemplate) return;
    setActionError(null);
    try {
      const tpl = await loadSanitizerTemplate(selectedTemplate);
      const cfg = tpl.config || {};
      if (cfg.include_entities) setSelectedEntities(new Set(cfg.include_entities));
      if (cfg.include_node_types) setSelectedNodeTypes(new Set(cfg.include_node_types));
      if (cfg.min_confidence !== undefined) setMinConfidence(cfg.min_confidence);
      setDateFrom(cfg.date_from || "");
      setDateTo(cfg.date_to || "");
      if (cfg.include_conversations !== undefined) setIncludeConversations(cfg.include_conversations);
      if (cfg.output_name) setOutputName(cfg.output_name);
      setPreview(null);
    } catch (e) {
      setActionError(e.message);
    }
  }

  async function handleSaveTemplate() {
    if (!templateName.trim()) return;
    setActionError(null);
    try {
      await saveSanitizerTemplate(templateName.trim(), buildConfig());
      setTemplates(await fetchSanitizerTemplates());
      setShowSaveTemplate(false);
      setTemplateName("");
    } catch (e) {
      setActionError(e.message);
    }
  }

  async function handleDeleteTemplate(name) {
    setActionError(null);
    try {
      await deleteSanitizerTemplate(name);
      setTemplates(await fetchSanitizerTemplates());
      if (selectedTemplate === name) setSelectedTemplate("");
    } catch (e) {
      setActionError(e.message);
    }
  }

  async function handleExport() {
    setExportLoading(true);
    setActionError(null);
    try {
      const result = await runSanitizerExport(buildConfig());
      setExportResult(result);
      setPreview(null);
    } catch (e) {
      setActionError(e.message);
    }
    setExportLoading(false);
  }

  if (loading) return <div className="text-center py-16 text-gray-500">Loading database info...</div>;
  if (error) return <div className="text-center py-16 text-red-400">{error}</div>;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-lg font-bold">Database Sanitizer</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Create a filtered copy of luna_engine.db for clean builds
        </p>
      </div>

      {/* Templates */}
      <div className="mb-5 p-3 rounded-lg border border-gray-800 bg-gray-900/30">
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={selectedTemplate}
            onChange={(e) => setSelectedTemplate(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 min-w-[160px]"
          >
            <option value="">-- Load Template --</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>{t.name}</option>
            ))}
          </select>
          <button
            onClick={handleLoadTemplate}
            disabled={!selectedTemplate}
            className="text-xs px-3 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700 disabled:opacity-40"
          >
            Load
          </button>
          {selectedTemplate && (
            <button
              onClick={() => handleDeleteTemplate(selectedTemplate)}
              className="text-xs px-2 py-1 text-gray-600 hover:text-red-400"
            >
              Delete
            </button>
          )}
          <div className="flex-1" />
          {showSaveTemplate ? (
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value.replace(/[^a-zA-Z0-9_-]/g, ""))}
                placeholder="template-name"
                className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 w-36"
                autoFocus
                onKeyDown={(e) => e.key === "Enter" && handleSaveTemplate()}
              />
              <button
                onClick={handleSaveTemplate}
                disabled={!templateName.trim()}
                className="text-xs px-3 py-1 rounded bg-purple-600 hover:bg-purple-500 text-white disabled:opacity-40"
              >
                Save
              </button>
              <button
                onClick={() => { setShowSaveTemplate(false); setTemplateName(""); }}
                className="text-xs px-2 py-1 text-gray-600 hover:text-gray-300"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowSaveTemplate(true)}
              className="text-xs px-3 py-1 rounded border border-gray-700 text-gray-400 hover:text-purple-400 hover:border-purple-700"
            >
              Save as Template
            </button>
          )}
        </div>
      </div>

      {/* Source stats */}
      <div className="mb-6 p-4 rounded-lg border border-gray-800 bg-gray-900/50">
        <div className="text-sm text-gray-400 mb-1">
          Source: <span className="text-gray-200">luna_engine.db</span>
          <span className="text-gray-600 ml-2">({stats?.size_mb} MB)</span>
        </div>
        <div className="flex gap-4 text-xs text-gray-500">
          <span>{stats?.memory_nodes?.toLocaleString()} nodes</span>
          <span>{stats?.entities} entities</span>
          <span>{stats?.conversation_turns?.toLocaleString()} turns</span>
          <span>{stats?.graph_edges?.toLocaleString()} edges</span>
        </div>
      </div>

      {/* Entities */}
      <Section
        title={`Entities (${selectedEntities.size} / ${entities.length})`}
        action={
          <div className="flex gap-2">
            <button onClick={selectAllEntities} className="text-xs text-gray-500 hover:text-cyan-400">All</button>
            <button onClick={selectNoEntities} className="text-xs text-gray-500 hover:text-cyan-400">System Only</button>
          </div>
        }
      >
        <div className="max-h-60 overflow-y-auto space-y-1 rounded border border-gray-800 p-2 bg-gray-900/30">
          {entities.map((ent) => (
            <label key={ent.id} className="flex items-center gap-2 cursor-pointer py-0.5 hover:bg-gray-800/50 px-1 rounded">
              <input
                type="checkbox"
                checked={selectedEntities.has(ent.id)}
                onChange={() => toggleEntity(ent.id)}
                disabled={ent.origin === "system"}
                className="accent-cyan-500"
              />
              <span className="text-sm text-gray-300 flex-1">{ent.name}</span>
              <span className="text-[10px] text-gray-600">{ent.entity_type}</span>
              <span className={`text-[10px] px-1 rounded ${ent.origin === "system" ? "bg-cyan-900/40 text-cyan-400" : "bg-gray-800 text-gray-500"}`}>
                {ent.origin}
              </span>
              <span className="text-[10px] text-gray-600 w-16 text-right">{ent.mention_count} refs</span>
            </label>
          ))}
        </div>
      </Section>

      {/* Node Types */}
      <Section title="Node Types">
        <div className="flex flex-wrap gap-2">
          {Object.entries(nodeTypes).map(([type, count]) => (
            <label key={type} className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedNodeTypes.has(type)}
                onChange={() => toggleNodeType(type)}
                className="accent-cyan-500"
              />
              <span className="text-sm text-gray-300">{type}</span>
              <span className="text-[10px] text-gray-600">({count.toLocaleString()})</span>
            </label>
          ))}
        </div>
      </Section>

      {/* Confidence */}
      <Section title={`Confidence Threshold: >= ${minConfidence}`}>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={minConfidence}
          onChange={(e) => { setMinConfidence(parseFloat(e.target.value)); setPreview(null); }}
          className="w-full accent-cyan-500"
        />
        <div className="flex justify-between text-[10px] text-gray-600">
          <span>0.0 (all)</span>
          <span>0.5</span>
          <span>1.0 (highest only)</span>
        </div>
      </Section>

      {/* Date Range */}
      <Section title="Date Range">
        <div className="flex gap-3 items-center">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPreview(null); }}
            className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
          />
          <span className="text-gray-600 text-sm">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPreview(null); }}
            className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200"
          />
          {(dateFrom || dateTo) && (
            <button
              onClick={() => { setDateFrom(""); setDateTo(""); setPreview(null); }}
              className="text-xs text-gray-500 hover:text-red-400"
            >
              Clear
            </button>
          )}
        </div>
      </Section>

      {/* Conversations */}
      <Section title="Conversations">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={includeConversations}
            onChange={(e) => { setIncludeConversations(e.target.checked); setPreview(null); }}
            className="accent-cyan-500"
          />
          <span className="text-sm text-gray-300">Include raw conversation history</span>
          <span className="text-[10px] text-gray-600">({stats?.conversation_turns?.toLocaleString()} turns)</span>
        </label>
      </Section>

      {/* Output name */}
      <Section title="Output">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={outputName}
            onChange={(e) => setOutputName(e.target.value.replace(/[^a-z0-9_-]/g, ""))}
            className="bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 w-48"
          />
          <span className="text-xs text-gray-600">.db</span>
        </div>
      </Section>

      {/* Preview result */}
      {preview && (
        <div className="mb-4 p-4 rounded-lg border border-cyan-800/50 bg-cyan-900/10">
          <h4 className="text-sm font-semibold text-cyan-400 mb-2">Preview</h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="text-gray-400">
              Nodes: <span className="text-gray-200">{preview.output_stats?.memory_nodes?.toLocaleString()}</span>
              <span className="text-gray-600"> / {preview.source_stats?.memory_nodes?.toLocaleString()}</span>
            </div>
            <div className="text-gray-400">
              Entities: <span className="text-gray-200">{preview.output_stats?.entities}</span>
              <span className="text-gray-600"> / {preview.source_stats?.entities}</span>
            </div>
            <div className="text-gray-400">
              Turns: <span className="text-gray-200">{preview.output_stats?.conversation_turns?.toLocaleString()}</span>
            </div>
            <div className="text-gray-400">
              Est. size: <span className="text-gray-200">{preview.output_stats?.est_size_mb} MB</span>
              <span className="text-gray-600"> (from {preview.source_stats?.size_mb} MB)</span>
            </div>
          </div>
          <div className="mt-2 text-[10px] text-gray-600">
            {preview.filters_applied?.join(" | ")}
          </div>
        </div>
      )}

      {/* Export result */}
      {exportResult && (
        <div className="mb-4 p-4 rounded-lg border border-green-800/50 bg-green-900/10">
          <h4 className="text-sm font-semibold text-green-400 mb-2">Export Complete</h4>
          <div className="text-xs text-gray-400 space-y-1">
            <div>Nodes: {exportResult.output_stats?.memory_nodes?.toLocaleString()}</div>
            <div>Entities: {exportResult.output_stats?.entities}</div>
            <div>Size: {exportResult.output_stats?.size_mb} MB</div>
            <div className="text-gray-600">Output: {exportResult.output_path}</div>
            <div className="mt-2 text-gray-500">
              Use <code className="text-gray-400">database.mode: "filtered"</code> with{" "}
              <code className="text-gray-400">source: "staging/{outputName}.db"</code> in your profile.
            </div>
          </div>
        </div>
      )}

      {actionError && <p className="text-red-400 text-xs mb-4">{actionError}</p>}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handlePreview}
          disabled={previewLoading || selectedEntities.size === 0}
          className="text-sm px-4 py-2 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700 disabled:opacity-50 transition-colors"
        >
          {previewLoading ? "Previewing..." : "Preview"}
        </button>
        <button
          onClick={handleExport}
          disabled={exportLoading || selectedEntities.size === 0 || !outputName}
          className="text-sm px-5 py-2 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-50 font-medium text-white transition-colors"
        >
          {exportLoading ? "Exporting..." : "Export Filtered DB"}
        </button>
      </div>
    </div>
  );
}

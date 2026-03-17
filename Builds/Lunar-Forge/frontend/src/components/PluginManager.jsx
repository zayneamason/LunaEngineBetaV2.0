import { useState, useEffect, useCallback } from "react";
import {
  fetchCollections,
  fetchPlugins,
  createCollection,
  ingestDocument,
  packageCollection,
} from "../api";

function Section({ title, action, children }) {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-purple-400 uppercase tracking-wider">
          {title}
        </h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function Badge({ label, color = "gray" }) {
  const colors = {
    gray: "bg-gray-800 text-gray-400",
    cyan: "bg-cyan-900/50 text-cyan-400",
    purple: "bg-purple-900/50 text-purple-400",
    green: "bg-green-900/50 text-green-400",
    amber: "bg-amber-900/50 text-amber-400",
    red: "bg-red-900/50 text-red-400",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium uppercase ${colors[color] || colors.gray}`}>
      {label}
    </span>
  );
}

function CollectionCard({ coll, onIngest, onPackage }) {
  const [ingestPath, setIngestPath] = useState("");
  const [ingestTitle, setIngestTitle] = useState("");
  const [showIngest, setShowIngest] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function handleIngest() {
    if (!ingestPath.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const r = await ingestDocument(coll.key, ingestPath.trim(), ingestTitle.trim());
      setResult({ ok: true, msg: `Ingested: ${r.chunks} chunks` });
      setIngestPath("");
      setIngestTitle("");
      onIngest?.();
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    }
    setBusy(false);
  }

  async function handlePackage() {
    setBusy(true);
    try {
      await packageCollection(coll.key);
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    }
    setBusy(false);
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-start justify-between mb-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-200">{coll.name || coll.key}</span>
            <Badge
              label={coll.source === "plugin" ? "plugin" : "registry"}
              color={coll.source === "plugin" ? "purple" : "cyan"}
            />
            {!coll.db_exists && <Badge label="missing" color="red" />}
            {coll.read_only && <Badge label="read-only" color="amber" />}
          </div>
          {coll.description && (
            <p className="text-xs text-gray-500 mt-0.5">{coll.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {coll.size_mb > 0 && <span>{coll.size_mb} MB</span>}
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-gray-400 mb-3">
        <span>{coll.documents} docs</span>
        <span className="text-gray-700">|</span>
        <span>{coll.chunks} chunks</span>
        {coll.tags?.length > 0 && (
          <>
            <span className="text-gray-700">|</span>
            <span className="text-gray-500">{coll.tags.join(", ")}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        {!coll.read_only && (
          <button
            onClick={() => setShowIngest(!showIngest)}
            className="text-xs px-2.5 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700 transition-colors"
          >
            {showIngest ? "Cancel" : "Ingest"}
          </button>
        )}
        {coll.source === "plugin" && (
          <button
            onClick={handlePackage}
            disabled={busy}
            className="text-xs px-2.5 py-1 rounded border border-gray-700 text-gray-400 hover:text-purple-400 hover:border-purple-700 transition-colors disabled:opacity-50"
          >
            Package .zip
          </button>
        )}
      </div>

      {showIngest && (
        <div className="mt-3 p-3 rounded bg-gray-800/50 border border-gray-800 space-y-2">
          <input
            type="text"
            value={ingestPath}
            onChange={(e) => setIngestPath(e.target.value)}
            placeholder="File path (e.g., /path/to/document.txt)"
            className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600"
          />
          <div className="flex gap-2">
            <input
              type="text"
              value={ingestTitle}
              onChange={(e) => setIngestTitle(e.target.value)}
              placeholder="Title (optional)"
              className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600"
            />
            <button
              onClick={handleIngest}
              disabled={busy || !ingestPath.trim()}
              className="text-xs px-3 py-1.5 rounded bg-cyan-700 text-white hover:bg-cyan-600 disabled:opacity-50 disabled:hover:bg-cyan-700 transition-colors"
            >
              {busy ? "..." : "Ingest"}
            </button>
          </div>
          {result && (
            <p className={`text-xs ${result.ok ? "text-green-400" : "text-red-400"}`}>
              {result.msg}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function SkillPluginCard({ skill }) {
  const isBuiltin = skill.source === "builtin";
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-200">{skill.name}</span>
          <Badge
            label={isBuiltin ? "builtin" : "plugin"}
            color={isBuiltin ? "cyan" : "purple"}
          />
          {!skill.has_init && <Badge label="no init" color="red" />}
          {skill.enabled === false && <Badge label="disabled" color="amber" />}
        </div>
      </div>
      {skill.requirements?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {skill.requirements.map((r) => (
            <span
              key={r}
              className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-500 border border-gray-700"
            >
              {r}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PluginManager({ plugins: pluginsProp, onRefresh }) {
  const [collections, setCollections] = useState([]);
  const [plugins, setPlugins] = useState(pluginsProp || { skills: [], collections: [] });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newTags, setNewTags] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [createResult, setCreateResult] = useState(null);

  // Update from prop when it changes
  useEffect(() => {
    if (pluginsProp) setPlugins(pluginsProp);
  }, [pluginsProp]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const colls = await fetchCollections();
      setCollections(colls);
      onRefresh?.();
    } catch (e) {
      setLoadError(e.message);
      console.error("Failed to load plugin data:", e);
    }
    setLoading(false);
  }, [onRefresh]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleCreate() {
    if (!newKey.trim() || !newName.trim()) return;
    setCreateBusy(true);
    setCreateResult(null);
    try {
      await createCollection(
        newKey.trim(),
        newName.trim(),
        newDesc.trim(),
        newTags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      );
      setCreateResult({ ok: true, msg: `Created "${newName.trim()}"` });
      setNewKey("");
      setNewName("");
      setNewDesc("");
      setNewTags("");
      setShowCreate(false);
      refresh();
    } catch (e) {
      setCreateResult({ ok: false, msg: e.message });
    }
    setCreateBusy(false);
  }

  if (loading) {
    return (
      <div className="text-center py-16 text-gray-500">Loading plugins...</div>
    );
  }

  if (loadError) {
    return (
      <div className="text-center py-16">
        <p className="text-red-400 mb-2">Failed to load plugin data</p>
        <p className="text-xs text-gray-500">{loadError}</p>
        <button onClick={refresh} className="mt-3 text-xs px-3 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400">
          Retry
        </button>
      </div>
    );
  }

  const registryCollections = collections.filter((c) => c.source === "registry");
  const pluginCollections = collections.filter((c) => c.source === "plugin");

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-bold">Plugin Manager</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Manage Nexus collections and skill plugins independently from build profiles
          </p>
        </div>
      </div>

      {/* Nexus Collections — Registry */}
      <Section title="Nexus Collections (Registry)">
        {registryCollections.length === 0 ? (
          <p className="text-xs text-gray-600">No registry collections found</p>
        ) : (
          <div className="space-y-3">
            {registryCollections.map((c) => (
              <CollectionCard key={c.key} coll={c} onIngest={refresh} />
            ))}
          </div>
        )}
      </Section>

      {/* Nexus Collections — Plugins */}
      <Section
        title="Nexus Collections (Plugins)"
        action={
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="text-xs px-3 py-1 rounded border border-gray-700 text-gray-400 hover:text-cyan-400 hover:border-cyan-700 transition-colors"
          >
            {showCreate ? "Cancel" : "+ New Collection"}
          </button>
        }
      >
        {showCreate && (
          <div className="mb-4 p-4 rounded-lg border border-gray-800 bg-gray-900/50 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <input
                type="text"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value.replace(/[^a-z0-9_-]/g, ""))}
                placeholder="key (e.g., my-research)"
                className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600"
              />
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Display Name"
                className="bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600"
              />
            </div>
            <input
              type="text"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description (optional)"
              className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600"
            />
            <div className="flex gap-2">
              <input
                type="text"
                value={newTags}
                onChange={(e) => setNewTags(e.target.value)}
                placeholder="Tags (comma-separated)"
                className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200 placeholder-gray-600"
              />
              <button
                onClick={handleCreate}
                disabled={createBusy || !newKey.trim() || !newName.trim()}
                className="text-xs px-4 py-1.5 rounded bg-cyan-700 text-white hover:bg-cyan-600 disabled:opacity-50 transition-colors"
              >
                {createBusy ? "Creating..." : "Create"}
              </button>
            </div>
            {createResult && (
              <p className={`text-xs ${createResult.ok ? "text-green-400" : "text-red-400"}`}>
                {createResult.msg}
              </p>
            )}
          </div>
        )}

        {pluginCollections.length === 0 && !showCreate ? (
          <p className="text-xs text-gray-600">
            No plugin collections installed. Click "+ New Collection" to create one,
            or drop a collection folder into <code className="text-gray-500">collections/</code>.
          </p>
        ) : (
          <div className="space-y-3">
            {pluginCollections.map((c) => (
              <CollectionCard key={c.key} coll={c} onIngest={refresh} />
            ))}
          </div>
        )}
      </Section>

      {/* Skills (Builtin + Plugins) */}
      <Section title="Skills">
        {plugins.skills.length === 0 ? (
          <p className="text-xs text-gray-600">
            No skills found. Drop a skill folder into{" "}
            <code className="text-gray-500">plugins/</code> with an{" "}
            <code className="text-gray-500">__init__.py</code> exporting{" "}
            <code className="text-gray-500">SkillClass</code>.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {plugins.skills.map((s) => (
              <SkillPluginCard key={s.name} skill={s} />
            ))}
          </div>
        )}
      </Section>

      {/* Summary footer */}
      <div className="mt-6 pt-4 border-t border-gray-800 text-xs text-gray-500 flex gap-4">
        <span>{collections.length} collections</span>
        <span>{plugins.skills.length} skills</span>
        <span>
          {collections.reduce((a, c) => a + c.chunks, 0).toLocaleString()} total chunks
        </span>
      </div>
    </div>
  );
}

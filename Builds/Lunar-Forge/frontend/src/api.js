import { useState, useEffect, useRef } from "react";

const BASE = import.meta.env.VITE_API_URL || "";

export async function fetchProfiles() {
  const res = await fetch(`${BASE}/api/profiles`);
  if (!res.ok) throw new Error("Failed to fetch profiles");
  return res.json();
}

export async function fetchPreview(name) {
  const res = await fetch(`${BASE}/api/profiles/${name}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Profile not found: ${name}`);
  }
  return res.json();
}

export async function startBuild(profile, platform = "auto", overrides = null) {
  const body = { profile, platform };
  if (overrides) body.overrides = overrides;
  const res = await fetch(`${BASE}/api/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    // Surface validation errors, preflight failures, and other details
    if (err.detail?.message) throw new Error(err.detail.message);
    if (typeof err.detail === "string") throw new Error(err.detail);
    if (res.status === 409) throw new Error("A build is already in progress");
    if (res.status === 422) throw new Error(err.detail?.errors?.join("; ") || "Profile validation failed");
    throw new Error("Failed to start build");
  }
  return res.json();
}

export async function runPreflight(profile, platform = "auto", overrides = null) {
  const body = { profile, platform };
  if (overrides) body.overrides = overrides;
  const res = await fetch(`${BASE}/api/build/preflight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.detail || "Preflight check failed");
  }
  return res.json();
}

export async function fetchReport(buildId) {
  const res = await fetch(`${BASE}/api/build/${buildId}/report`);
  if (!res.ok) return null;
  return res.json();
}

export async function fetchOutputs() {
  const res = await fetch(`${BASE}/api/outputs`);
  if (!res.ok) throw new Error("Failed to fetch outputs");
  return res.json();
}

export async function fetchActiveBuild() {
  const res = await fetch(`${BASE}/api/build/active`);
  if (!res.ok) return null;
  return res.json();
}

export async function deleteOutput(name) {
  const res = await fetch(`${BASE}/api/outputs/${name}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete: ${name}`);
  return res.json();
}

export async function fetchSystemKnowledge() {
  const res = await fetch(`${BASE}/api/system-knowledge`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchDirectives() {
  const res = await fetch(`${BASE}/api/directives`);
  if (!res.ok) return { seed_directives: [], seed_skills: [] };
  return res.json();
}

export async function fetchConfigFile(key) {
  const res = await fetch(`${BASE}/api/files/${encodeURIComponent(key)}`);
  if (!res.ok) return null;
  return res.json();
}

// ── Database Sanitizer ──

export async function fetchSanitizerStats() {
  const res = await fetch(`${BASE}/api/sanitizer/stats`);
  if (!res.ok) throw new Error("Failed to fetch DB stats");
  return res.json();
}

export async function fetchSanitizerEntities() {
  const res = await fetch(`${BASE}/api/sanitizer/entities`);
  if (!res.ok) throw new Error("Failed to fetch entities");
  return res.json();
}

export async function fetchSanitizerNodeTypes() {
  const res = await fetch(`${BASE}/api/sanitizer/node-types`);
  if (!res.ok) throw new Error("Failed to fetch node types");
  return res.json();
}

export async function runSanitizerPreview(config) {
  const res = await fetch(`${BASE}/api/sanitizer/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Preview failed");
  }
  return res.json();
}

export async function runSanitizerExport(config) {
  const res = await fetch(`${BASE}/api/sanitizer/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Export failed");
  }
  return res.json();
}

// ── Sanitizer Templates ──

export async function fetchSanitizerTemplates() {
  const res = await fetch(`${BASE}/api/sanitizer/templates`);
  if (!res.ok) return [];
  return res.json();
}

export async function saveSanitizerTemplate(name, config) {
  const res = await fetch(`${BASE}/api/sanitizer/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, config }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to save template");
  }
  return res.json();
}

export async function loadSanitizerTemplate(name) {
  const res = await fetch(`${BASE}/api/sanitizer/templates/${encodeURIComponent(name)}`);
  if (!res.ok) throw new Error("Template not found");
  return res.json();
}

export async function deleteSanitizerTemplate(name) {
  const res = await fetch(`${BASE}/api/sanitizer/templates/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to delete template");
  return res.json();
}

// ── Build Drafts ──

export async function fetchDrafts() {
  const res = await fetch(`${BASE}/api/builds/drafts`);
  if (!res.ok) throw new Error("Failed to fetch drafts");
  return res.json();
}

export async function createDraft(templateProfile = null, name = null) {
  const body = {};
  if (templateProfile) body.template_profile = templateProfile;
  if (name) body.name = name;
  const res = await fetch(`${BASE}/api/builds/drafts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create draft");
  }
  return res.json();
}

export async function fetchDraft(id) {
  const res = await fetch(`${BASE}/api/builds/drafts/${id}`);
  if (!res.ok) throw new Error(`Draft not found: ${id}`);
  return res.json();
}

export async function updateDraft(id, config, name = null, platform = null) {
  const body = {};
  if (config !== null) body.config = config;
  if (name !== null) body.name = name;
  if (platform !== null) body.platform = platform;
  const res = await fetch(`${BASE}/api/builds/drafts/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update draft");
  }
  return res.json();
}

export async function deleteDraft(id) {
  const res = await fetch(`${BASE}/api/builds/drafts/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete draft");
  return res.json();
}

export async function startDraftBuild(id) {
  const res = await fetch(`${BASE}/api/builds/drafts/${id}/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (err.detail?.message) throw new Error(err.detail.message);
    if (typeof err.detail === "string") throw new Error(err.detail);
    if (res.status === 409) throw new Error("A build is already in progress");
    throw new Error("Failed to start build");
  }
  return res.json();
}

// ── Plugin Management ──

export async function fetchCollections() {
  const res = await fetch(`${BASE}/api/collections`);
  if (!res.ok) return [];
  return res.json();
}

export async function fetchPlugins() {
  const res = await fetch(`${BASE}/api/plugins`);
  if (!res.ok) return { skills: [], collections: [] };
  return res.json();
}

export async function createCollection(key, name, description = "", tags = []) {
  const res = await fetch(`${BASE}/api/collections/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key, name, description, tags }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create collection");
  }
  return res.json();
}

export async function ingestDocument(collectionKey, filePath, title = "", metadata = {}) {
  const res = await fetch(`${BASE}/api/collections/${collectionKey}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath, title, metadata }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Ingestion failed");
  }
  return res.json();
}

export async function packageCollection(collectionKey) {
  const res = await fetch(`${BASE}/api/collections/${collectionKey}/package`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to package collection");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${collectionKey}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

/** SSE hook — streams build progress events. */
export function useSSE(buildId) {
  const [messages, setMessages] = useState([]);
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState(null);
  const [isDone, setIsDone] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const esRef = useRef(null);

  useEffect(() => {
    if (!buildId) return;

    const es = new EventSource(`${BASE}/api/build/${buildId}/progress`);
    esRef.current = es;

    es.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);

        if (data.event === "done") {
          setIsDone(true);
          setReport(data.report || null);
          setProgress(100);
          if (data.error) setError(data.error);
          es.close();
          return;
        }

        setMessages((prev) => [...prev, data.message]);
        if (data.pct >= 0) setProgress(data.pct);
        if (data.stage) setStage(data.stage);
      } catch (parseErr) {
        console.warn("SSE parse error:", evt.data, parseErr);
      }
    };

    es.onerror = () => {
      setError("Connection lost — check Forge terminal for details");
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [buildId]);

  return { messages, progress, stage, isDone, report, error };
}

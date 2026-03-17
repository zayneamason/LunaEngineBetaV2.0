import { useState, useEffect, useCallback } from "react";
import { fetchActiveBuild, fetchProfiles, fetchPlugins } from "./api";
import BuildManager from "./components/BuildManager";
import BuildEditor from "./components/BuildEditor";
import ProfileSelector from "./components/ProfileSelector";
import ConfigPreview from "./components/ConfigPreview";
import BuildProgress from "./components/BuildProgress";
import BuildReport from "./components/BuildReport";
import OutputManager from "./components/OutputManager";
import PluginManager from "./components/PluginManager";
import DatabaseSanitizer from "./components/DatabaseSanitizer";

export default function App() {
  const [view, setView] = useState("select");
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [manifest, setManifest] = useState(null);
  const [buildId, setBuildId] = useState(null);
  const [report, setReport] = useState(null);
  const [selectedDraftId, setSelectedDraftId] = useState(null);

  // App-level data — fetched once, passed as props
  const [profiles, setProfiles] = useState([]);
  const [plugins, setPlugins] = useState({ skills: [], collections: [] });

  const refreshProfiles = useCallback(() => {
    fetchProfiles().then(setProfiles).catch((e) => console.error("Profile fetch failed:", e));
  }, []);

  const refreshPlugins = useCallback(() => {
    fetchPlugins().then(setPlugins).catch((e) => console.error("Plugin fetch failed:", e));
  }, []);

  useEffect(() => {
    refreshProfiles();
    refreshPlugins();
    fetchActiveBuild().then((data) => {
      if (data && data.build_id) {
        setBuildId(data.build_id);
        setSelectedProfile(data.profile);
        setView("building");
      }
    });
  }, [refreshProfiles, refreshPlugins]);

  // Legacy profile-based flow (still accessible)
  function handleProfileSelected(profileName, manifestData) {
    setSelectedProfile(profileName);
    setManifest(manifestData);
    setView("preview");
  }

  function handleBuildStarted(id) {
    setBuildId(id);
    setView("building");
  }

  function handleBuildComplete(reportData) {
    setReport(reportData);
    setView("report");
  }

  // Draft-based flow
  function handleEditDraft(draftId) {
    setSelectedDraftId(draftId);
    setView("draft_edit");
  }

  function handleDraftBuild(id) {
    setBuildId(id);
    setView("building");
  }

  const isBuildsTab = view === "select" || view === "draft_edit";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-wide">
          <span className="text-purple-400">Lunar</span> Forge
        </h1>
        <div className="flex gap-3">
          <button
            onClick={() => setView("select")}
            className={`text-sm px-3 py-1 rounded ${isBuildsTab ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
          >
            Builds
          </button>
          <button
            onClick={() => setView("plugins")}
            className={`text-sm px-3 py-1 rounded ${view === "plugins" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
          >
            Plugins
          </button>
          <button
            onClick={() => setView("sanitizer")}
            className={`text-sm px-3 py-1 rounded ${view === "sanitizer" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
          >
            Sanitizer
          </button>
          <button
            onClick={() => setView("outputs")}
            className={`text-sm px-3 py-1 rounded ${view === "outputs" ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
          >
            Outputs
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        {/* Draft-based build flow (primary) */}
        {view === "select" && (
          <BuildManager
            profiles={profiles}
            onEditDraft={handleEditDraft}
            onBuildDraft={(id) => handleEditDraft(id)}
          />
        )}
        {view === "draft_edit" && selectedDraftId && (
          <BuildEditor
            draftId={selectedDraftId}
            onBuild={handleDraftBuild}
            onBack={() => setView("select")}
          />
        )}

        {/* Legacy profile-based flow (accessible via direct profile selection) */}
        {view === "preview" && (
          <ConfigPreview
            profileName={selectedProfile}
            manifest={manifest}
            onBuild={handleBuildStarted}
            onBack={() => setView("select")}
          />
        )}

        {/* Shared views */}
        {view === "building" && (
          <BuildProgress
            buildId={buildId}
            profileName={selectedProfile || "Draft Build"}
            onComplete={handleBuildComplete}
          />
        )}
        {view === "report" && (
          <BuildReport
            report={report}
            onNewBuild={() => setView("select")}
            onViewOutputs={() => setView("outputs")}
          />
        )}
        {view === "plugins" && <PluginManager plugins={plugins} onRefresh={refreshPlugins} />}
        {view === "sanitizer" && <DatabaseSanitizer />}
        {view === "outputs" && <OutputManager />}
      </main>
    </div>
  );
}

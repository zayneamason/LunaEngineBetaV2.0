import { useEffect, useRef, useState } from "react";
import { useSSE } from "../api";

const PIPELINE_STAGES = [
  { key: "staging", label: "Prepare Staging" },
  { key: "frontend", label: "Copy Frontend" },
  { key: "config", label: "Assemble Config" },
  { key: "data", label: "Assemble Data" },
  { key: "secrets", label: "Write Secrets" },
  { key: "frontend_cfg", label: "Frontend Config" },
  { key: "nuitka", label: "Nuitka Compile" },
  { key: "post_process", label: "Post-Process" },
  { key: "qa", label: "QA Validation" },
  { key: "output", label: "Final Output" },
];

function StageIcon({ status }) {
  if (status === "done")
    return <span className="text-green-400">{"\u2713"}</span>;
  if (status === "active")
    return <span className="text-cyan-400 animate-pulse">{"\u25C9"}</span>;
  if (status === "error")
    return <span className="text-red-400">{"\u2717"}</span>;
  return <span className="text-gray-600">{"\u25CB"}</span>;
}

export default function BuildProgress({ buildId, profileName, onComplete }) {
  const { messages, progress, stage, isDone, report, error } = useSSE(buildId);
  const [elapsed, setElapsed] = useState(0);
  const logRef = useRef(null);
  const startTime = useRef(Date.now());

  // Elapsed timer
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [messages]);

  // Notify parent on completion
  useEffect(() => {
    if (isDone && report) {
      const timer = setTimeout(() => onComplete(report), 1500);
      return () => clearTimeout(timer);
    }
  }, [isDone, report, onComplete]);

  // Compute stage statuses
  const stageStatuses = {};
  let reachedCurrent = false;
  for (let i = PIPELINE_STAGES.length - 1; i >= 0; i--) {
    const s = PIPELINE_STAGES[i];
    if (s.key === stage) {
      stageStatuses[s.key] = isDone ? "done" : "active";
      reachedCurrent = true;
    } else if (reachedCurrent) {
      stageStatuses[s.key] = "done";
    } else {
      stageStatuses[s.key] = "pending";
    }
  }
  if (isDone) {
    for (const s of PIPELINE_STAGES) stageStatuses[s.key] = "done";
  }

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold">
          Building: <span className="text-cyan-400">{profileName}</span>
        </h2>
        <span className="text-sm text-gray-500 font-mono">
          {mins}:{secs.toString().padStart(2, "0")}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Pipeline tracker */}
        <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
          <div className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-3">
            Pipeline
          </div>
          <div className="space-y-0">
            {PIPELINE_STAGES.map((s, i) => (
              <div key={s.key}>
                <div className="flex items-center gap-2 py-1">
                  <StageIcon status={stageStatuses[s.key] || "pending"} />
                  <span
                    className={`text-sm ${
                      stageStatuses[s.key] === "active"
                        ? "text-cyan-300 font-medium"
                        : stageStatuses[s.key] === "done"
                          ? "text-gray-400"
                          : "text-gray-600"
                    }`}
                  >
                    {s.label}
                  </span>
                </div>
                {i < PIPELINE_STAGES.length - 1 && (
                  <div
                    className={`ml-[7px] h-3 border-l ${
                      stageStatuses[s.key] === "done"
                        ? "border-green-700"
                        : stageStatuses[s.key] === "active"
                          ? "border-cyan-700"
                          : "border-gray-800"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Progress + Log */}
        <div className="md:col-span-2 space-y-4">
          {/* Progress bar */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <div className="flex justify-between text-sm mb-2">
              <span className="text-gray-400">Progress</span>
              <span className="text-white font-mono">{progress}%</span>
            </div>
            <div className="w-full bg-gray-800 rounded-full h-2">
              <div
                className="bg-purple-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>

          {/* Log */}
          <div className="bg-gray-900 rounded-lg border border-gray-800 p-4">
            <div className="text-xs font-semibold text-purple-400 uppercase tracking-wider mb-2">
              Build Log
            </div>
            <div
              ref={logRef}
              className="h-64 overflow-y-auto font-mono text-xs text-gray-400 space-y-0.5"
            >
              {messages.map((msg, i) => (
                <div key={i}>{msg}</div>
              ))}
              {error && <div className="text-red-400">{error}</div>}
              {isDone && (
                <div className="text-green-400 mt-2 font-medium">
                  Build complete.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

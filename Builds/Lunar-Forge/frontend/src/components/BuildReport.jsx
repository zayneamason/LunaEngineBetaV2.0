function Stat({ label, value }) {
  return (
    <div>
      <div className="text-xs text-gray-500 uppercase">{label}</div>
      <div className="text-sm text-white">{value}</div>
    </div>
  );
}

export default function BuildReport({ report, onNewBuild, onViewOutputs }) {
  if (!report) return null;

  const success = report.status === "SUCCESS";
  const sizeMB = report.binary_size
    ? (report.binary_size / (1024 * 1024)).toFixed(0)
    : "?";
  const totalMB = report.total_size
    ? (report.total_size / (1024 * 1024)).toFixed(0)
    : "?";
  const duration = report.duration_seconds
    ? `${(report.duration_seconds / 60).toFixed(1)} min`
    : "?";

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-lg font-semibold">Build Report</h2>
        <span
          className={`text-xs font-bold px-2 py-0.5 rounded ${
            success
              ? "bg-green-900/50 text-green-400 border border-green-700"
              : "bg-red-900/50 text-red-400 border border-red-700"
          }`}
        >
          {report.status}
        </span>
      </div>

      <div className="bg-gray-900 rounded-lg border border-gray-800 p-5">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
          <Stat label="Profile" value={report.profile_name || "?"} />
          <Stat label="Platform" value={report.platform || "?"} />
          <Stat label="Duration" value={duration} />
          <Stat label="Version" value={report.version || "?"} />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Stat label="Binary" value={`${sizeMB} MB`} />
          <Stat label="Total" value={`${totalMB} MB`} />
          <Stat label="Files" value={report.file_count ?? "?"} />
          <Stat label="Dirs" value={report.dir_count ?? "?"} />
        </div>

        {report.errors && report.errors.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-red-400 font-semibold uppercase mb-1">
              Errors
            </div>
            <ul className="text-sm text-red-300 space-y-1">
              {report.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          </div>
        )}

        {report.warnings && report.warnings.length > 0 && (
          <div className="mt-4">
            <div className="text-xs text-yellow-400 font-semibold uppercase mb-1">
              Warnings
            </div>
            <ul className="text-sm text-yellow-300 space-y-1">
              {report.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {report.qa_results && (
          <div className="mt-5 pt-4 border-t border-gray-800">
            <div className="flex items-center gap-2 mb-3">
              <div className="text-xs font-semibold text-purple-400 uppercase tracking-wider">
                Post-Build QA
              </div>
              <span
                className={`text-xs font-bold px-2 py-0.5 rounded ${
                  report.qa_results.passed
                    ? "bg-green-900/50 text-green-400 border border-green-700"
                    : "bg-red-900/50 text-red-400 border border-red-700"
                }`}
              >
                {report.qa_results.passed ? "PASSED" : "FAILED"}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-3">
              <Stat label="Assertions" value={report.qa_results.total ?? 0} />
              <Stat label="Passed" value={report.qa_results.passed_count ?? 0} />
              <Stat label="Failed" value={report.qa_results.failed_count ?? 0} />
              <Stat label="Latency" value={`${(report.qa_results.latency_ms || 0).toFixed(0)}ms`} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Stat label="Engine Boot" value={report.qa_results.engine_booted ? "OK" : "FAILED"} />
              <Stat label="Test Prompt" value={report.qa_results.test_prompt || "N/A"} />
            </div>
            {report.qa_results.failed_assertions?.length > 0 && (
              <div className="mt-3">
                <div className="text-xs text-red-400 font-semibold uppercase mb-1">
                  Failed Assertions
                </div>
                <ul className="text-sm text-red-300 space-y-1">
                  {report.qa_results.failed_assertions.map((a, i) => (
                    <li key={i}>
                      <span className="text-red-400 font-mono text-xs">[{a.severity}]</span>{" "}
                      {a.name}{a.details ? ` — ${a.details}` : ""}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {report.qa_results.diagnosis && (
              <div className="mt-3">
                <div className="text-xs text-gray-500 font-semibold uppercase mb-1">
                  Diagnosis
                </div>
                <p className="text-sm text-gray-400 whitespace-pre-wrap">
                  {report.qa_results.diagnosis}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={onNewBuild}
          className="px-5 py-2 rounded bg-purple-600 hover:bg-purple-500 font-medium text-sm"
        >
          New Build
        </button>
        <button
          onClick={onViewOutputs}
          className="px-5 py-2 rounded border border-gray-700 text-gray-400 hover:text-white text-sm"
        >
          View Outputs
        </button>
      </div>
    </div>
  );
}

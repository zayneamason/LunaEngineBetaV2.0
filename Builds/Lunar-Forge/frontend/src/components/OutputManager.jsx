import { useEffect, useState } from "react";
import { fetchOutputs, deleteOutput } from "../api";

export default function OutputManager() {
  const [outputs, setOutputs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  function load() {
    setLoading(true);
    fetchOutputs()
      .then(setOutputs)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleDelete(name) {
    if (!window.confirm(`Delete build "${name}"? This cannot be undone.`))
      return;
    try {
      await deleteOutput(name);
      load();
    } catch (e) {
      setError(e.message);
    }
  }

  if (loading) return <p className="text-gray-500">Loading outputs...</p>;
  if (error) return <p className="text-red-400">{error}</p>;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Build Outputs</h2>

      {outputs.length === 0 ? (
        <p className="text-gray-500">No builds found.</p>
      ) : (
        <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-800">
                <th className="px-4 py-2">Name</th>
                <th className="px-4 py-2">Size</th>
                <th className="px-4 py-2">Report</th>
                <th className="px-4 py-2">QA</th>
                <th className="px-4 py-2">Modified</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {outputs.map((o) => (
                <tr
                  key={o.name}
                  className="border-b border-gray-800/50 hover:bg-gray-800/30"
                >
                  <td className="px-4 py-2 text-white font-mono text-xs">
                    {o.name}
                  </td>
                  <td className="px-4 py-2 text-gray-400">{o.size_mb} MB</td>
                  <td className="px-4 py-2">
                    {o.has_report ? (
                      <span className="text-green-400 text-xs">{"\u2713"}</span>
                    ) : (
                      <span className="text-gray-600 text-xs">--</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {o.qa ? (
                      <span className={`text-xs font-mono ${o.qa.passed ? "text-green-400" : "text-red-400"}`}>
                        {o.qa.passed ? "\u2713" : "\u2717"} {o.qa.total - o.qa.failed_count}/{o.qa.total}
                      </span>
                    ) : (
                      <span className="text-gray-600 text-xs">--</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-gray-500 text-xs">
                    {new Date(o.modified).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => handleDelete(o.name)}
                      className="text-xs text-red-400 hover:text-red-300"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

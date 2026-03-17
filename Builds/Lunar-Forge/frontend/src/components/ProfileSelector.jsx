import { useState } from "react";
import { fetchPreview } from "../api";

export default function ProfileSelector({ profiles, onSelect }) {
  const [error, setError] = useState(null);

  async function handleClick(profile) {
    try {
      const manifest = await fetchPreview(profile.file.replace(".yaml", ""));
      onSelect(profile.file.replace(".yaml", ""), manifest);
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) return <p className="text-red-400">{error}</p>;

  return (
    <div>
      <h2 className="text-lg font-semibold mb-4">Select a Profile</h2>
      {profiles.length === 0 ? (
        <p className="text-gray-500">Loading profiles...</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {profiles.map((p) => (
            <button
              key={p.file}
              onClick={() => handleClick(p)}
              className="text-left p-4 rounded-lg border border-gray-700 bg-gray-900 hover:border-cyan-500 transition-colors"
            >
              <div className="font-medium text-white">{p.name}</div>
              <div className="text-sm text-gray-400 mt-1">{p.description}</div>
              <div className="text-xs text-gray-500 mt-2 flex gap-4">
                <span>db: {p.database_mode}</span>
                <span>collections: {p.collections_count}</span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

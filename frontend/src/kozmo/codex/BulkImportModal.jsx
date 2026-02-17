/**
 * Bulk Import Modal for KOZMO CODEX
 *
 * Allows importing multiple entities from JSON file or pasted text.
 * Features:
 * - File upload (.json) or paste JSON
 * - Preview parsed entities before import
 * - Duplicate strategy selection (skip/overwrite/fail)
 * - Import progress and results display
 * - Partial success handling
 */
import React, { useState } from 'react';
import { useKozmo } from '../KozmoProvider';

export default function BulkImportModal({ isOpen, onClose }) {
  const { bulkCreateEntities, loading } = useKozmo();
  const [inputMethod, setInputMethod] = useState('paste'); // 'paste' | 'upload'
  const [jsonText, setJsonText] = useState('');
  const [duplicateStrategy, setDuplicateStrategy] = useState('skip');
  const [results, setResults] = useState(null);
  const [preview, setPreview] = useState(null);

  const handleParse = () => {
    try {
      const parsed = JSON.parse(jsonText);
      if (!parsed.entities || !Array.isArray(parsed.entities)) {
        alert('JSON must have "entities" array at top level.\n\nExample:\n{\n  "entities": [\n    {"type": "characters", "name": "Sarah"}\n  ]\n}');
        return;
      }
      setPreview(parsed.entities);
      setResults(null); // Clear previous results
    } catch (e) {
      alert(`Invalid JSON: ${e.message}`);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      setJsonText(event.target.result);
      setInputMethod('paste'); // Switch to paste view after upload
    };
    reader.readAsText(file);
  };

  const handleImport = async () => {
    if (!preview || preview.length === 0) {
      alert('Parse JSON first to preview entities');
      return;
    }

    const result = await bulkCreateEntities(preview, duplicateStrategy);
    if (result) {
      setResults(result);
    }
  };

  const handleReset = () => {
    setJsonText('');
    setPreview(null);
    setResults(null);
    setDuplicateStrategy('skip');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#1a1a1f] border border-[#2a2a3a] rounded-lg p-6 w-[800px] max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold mb-4">Bulk Import Entities</h2>

        {/* Input Method Toggle */}
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setInputMethod('paste')}
            className={`px-4 py-2 rounded ${inputMethod === 'paste' ? 'bg-blue-600' : 'bg-[#2a2a3a]'} hover:opacity-80 transition`}
          >
            Paste JSON
          </button>
          <button
            onClick={() => setInputMethod('upload')}
            className={`px-4 py-2 rounded ${inputMethod === 'upload' ? 'bg-blue-600' : 'bg-[#2a2a3a]'} hover:opacity-80 transition`}
          >
            Upload File
          </button>
        </div>

        {/* Input Area */}
        {inputMethod === 'paste' ? (
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            placeholder='Paste JSON here:
{
  "entities": [
    {"type": "characters", "name": "Sarah Connor", "tags": ["protagonist"]},
    {"type": "locations", "name": "Tech Noir", "tags": ["nightclub"]}
  ]
}'
            className="w-full h-48 bg-[#0a0a0f] border border-[#2a2a3a] rounded p-3 font-mono text-sm text-gray-300 placeholder-gray-600"
          />
        ) : (
          <div>
            <input
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              className="w-full p-2 bg-[#0a0a0f] border border-[#2a2a3a] rounded text-gray-300"
            />
            <p className="text-xs text-gray-500 mt-1">
              Upload a .json file with an "entities" array
            </p>
          </div>
        )}

        {/* Parse Button */}
        <div className="flex gap-2 mt-2">
          <button
            onClick={handleParse}
            className="px-4 py-2 bg-green-600 rounded hover:bg-green-700 transition"
          >
            Parse & Preview
          </button>
          {jsonText && (
            <button
              onClick={handleReset}
              className="px-4 py-2 bg-[#2a2a3a] rounded hover:bg-[#3a3a4a] transition"
            >
              Clear
            </button>
          )}
        </div>

        {/* Preview */}
        {preview && (
          <div className="mt-4 p-3 bg-[#0a0a0f] border border-[#2a2a3a] rounded">
            <h3 className="font-bold mb-2">Preview ({preview.length} entities)</h3>
            <div className="max-h-40 overflow-y-auto space-y-1 text-sm">
              {preview.map((e, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-blue-400 font-semibold">{e.type}</span>
                  <span className="text-gray-200">{e.name}</span>
                  {e.tags && e.tags.length > 0 && (
                    <span className="text-gray-500 text-xs">[{e.tags.join(', ')}]</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Duplicate Strategy */}
        {preview && !results && (
          <div className="mt-4">
            <label className="block mb-2 font-semibold text-gray-200">
              If entity already exists:
            </label>
            <select
              value={duplicateStrategy}
              onChange={(e) => setDuplicateStrategy(e.target.value)}
              className="w-full p-2 bg-[#0a0a0f] border border-[#2a2a3a] rounded text-gray-200"
            >
              <option value="skip">Skip (recommended) - Keep existing entity</option>
              <option value="overwrite">Overwrite - Replace existing entity</option>
              <option value="fail">Fail - Mark as error if exists</option>
            </select>
          </div>
        )}

        {/* Import Button */}
        {preview && !results && (
          <button
            onClick={handleImport}
            disabled={loading}
            className="mt-4 px-6 py-2 bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? 'Importing...' : `Import ${preview.length} Entities`}
          </button>
        )}

        {/* Results */}
        {results && (
          <div className="mt-4 p-3 bg-[#0a0a0f] border border-green-600 rounded">
            <h3 className="font-bold mb-2 text-green-400">Import Results</h3>
            <div className="space-y-2 text-sm">
              <div className="text-green-400">✓ Created: {results.created.length}</div>
              {results.skipped && results.skipped.length > 0 && (
                <div className="text-yellow-400">⊘ Skipped: {results.skipped.length}</div>
              )}
              {results.failed && results.failed.length > 0 && (
                <div className="text-red-400">✗ Failed: {results.failed.length}</div>
              )}
            </div>

            {/* Created Entities List */}
            {results.created.length > 0 && (
              <details className="mt-2" open>
                <summary className="cursor-pointer text-green-400 font-semibold">
                  View Created ({results.created.length})
                </summary>
                <div className="mt-2 max-h-32 overflow-y-auto text-xs space-y-1">
                  {results.created.map((c, i) => (
                    <div key={i} className="flex gap-2 text-gray-300">
                      <span className="text-blue-400">{c.type}</span>
                      <span>{c.name}</span>
                      <span className="text-gray-500">({c.slug})</span>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Failed Entities List */}
            {results.failed && results.failed.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-red-400 font-semibold">
                  View Failures ({results.failed.length})
                </summary>
                <div className="mt-2 max-h-32 overflow-y-auto text-xs space-y-2">
                  {results.failed.map((f, i) => (
                    <div key={i} className="mb-1 text-gray-300">
                      <strong className="text-red-400">{f.entity.name}:</strong> {f.error}
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Skipped Entities List */}
            {results.skipped && results.skipped.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-yellow-400 font-semibold">
                  View Skipped ({results.skipped.length})
                </summary>
                <div className="mt-2 max-h-32 overflow-y-auto text-xs space-y-1">
                  {results.skipped.map((s, i) => (
                    <div key={i} className="flex gap-2 text-gray-300">
                      <span className="text-yellow-400">{s.entity.type}</span>
                      <span>{s.entity.name}</span>
                      <span className="text-gray-500">({s.reason})</span>
                    </div>
                  ))}
                </div>
              </details>
            )}

            {/* Import Another Button */}
            <button
              onClick={handleReset}
              className="mt-3 px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 transition"
            >
              Import Another
            </button>
          </div>
        )}

        {/* Close Button */}
        <button
          onClick={onClose}
          className="mt-4 px-4 py-2 bg-[#2a2a3a] rounded hover:bg-[#3a3a4a] transition"
        >
          Close
        </button>
      </div>
    </div>
  );
}

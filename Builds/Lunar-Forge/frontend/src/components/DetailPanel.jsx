export default function DetailPanel({ title, isOpen, onToggle, children }) {
  return (
    <div className="mt-1.5 rounded bg-gray-800/30 border border-gray-800/50">
      <button
        onClick={onToggle}
        className="w-full text-left px-3 py-2 flex items-center justify-between text-xs text-gray-400 hover:text-gray-200"
      >
        <span>{title}</span>
        <span className="text-gray-600">{isOpen ? "\u25B2" : "\u25BC"}</span>
      </button>
      {isOpen && (
        <div className="px-3 pb-3 border-t border-gray-800/50 pt-2 max-h-64 overflow-y-auto text-xs text-gray-500">
          {children}
        </div>
      )}
    </div>
  );
}

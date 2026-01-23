import React, { useState, useEffect, useRef } from 'react';
import GlassCard from './GlassCard';

const ThoughtStream = ({ apiUrl = 'http://localhost:8000' }) => {
  const [thoughts, setThoughts] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentGoal, setCurrentGoal] = useState(null);
  const streamRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    // Connect to thought stream SSE
    const connectToStream = () => {
      const eventSource = new EventSource(`${apiUrl}/thoughts`);
      streamRef.current = eventSource;

      eventSource.onopen = () => {
        setIsConnected(true);
        addThought({ type: 'system', message: 'Connected to Luna\'s mind...' });
      };

      eventSource.addEventListener('status', (event) => {
        const data = JSON.parse(event.data);
        setIsProcessing(data.is_processing);
        setCurrentGoal(data.goal);
      });

      eventSource.addEventListener('thought', (event) => {
        const data = JSON.parse(event.data);
        setIsProcessing(data.is_processing);
        setCurrentGoal(data.goal);
        addThought({ type: 'thought', message: data.message });
      });

      eventSource.addEventListener('ping', (event) => {
        const data = JSON.parse(event.data);
        setIsProcessing(data.is_processing);
      });

      eventSource.onerror = () => {
        setIsConnected(false);
        addThought({ type: 'error', message: 'Connection lost. Reconnecting...' });
        eventSource.close();
        // Reconnect after 2 seconds
        setTimeout(connectToStream, 2000);
      };
    };

    connectToStream();

    return () => {
      if (streamRef.current) {
        streamRef.current.close();
      }
    };
  }, [apiUrl]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [thoughts]);

  const addThought = (thought) => {
    const timestamp = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
    setThoughts(prev => [...prev.slice(-50), { ...thought, timestamp }]); // Keep last 50
  };

  const getPhaseColor = (message) => {
    if (message.includes('[OBSERVE]')) return 'text-cyan-400';
    if (message.includes('[THINK]')) return 'text-violet-400';
    if (message.includes('[ACT:')) return 'text-amber-400';
    if (message.includes('[OK]')) return 'text-emerald-400';
    if (message.includes('[FAIL]')) return 'text-red-400';
    if (message.includes('[COMPLETE]')) return 'text-emerald-400';
    if (message.includes('[ABORTED]')) return 'text-red-400';
    if (message.includes('Plan:')) return 'text-blue-400';
    return 'text-white/60';
  };

  const getPhaseIcon = (message) => {
    if (message.includes('[OBSERVE]')) return '👁';
    if (message.includes('[THINK]')) return '💭';
    if (message.includes('[ACT:')) return '⚡';
    if (message.includes('[OK]')) return '✓';
    if (message.includes('[FAIL]')) return '✗';
    if (message.includes('[COMPLETE]')) return '🎯';
    if (message.includes('[ABORTED]')) return '⏹';
    if (message.includes('Plan:')) return '📋';
    if (message.includes('Starting:')) return '🚀';
    return '•';
  };

  return (
    <GlassCard padding="p-0" hover={false}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-1 h-5 bg-gradient-to-b from-violet-400 to-cyan-400 rounded-full" />
          <h3 className="text-sm font-light tracking-wide text-white/80">Thought Stream</h3>
        </div>
        <div className="flex items-center gap-2">
          {isProcessing && (
            <span className="text-[10px] text-amber-400 animate-pulse">PROCESSING</span>
          )}
          <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} />
        </div>
      </div>

      {/* Current Goal */}
      {currentGoal && (
        <div className="px-4 py-2 bg-white/5 border-b border-white/5">
          <div className="text-[10px] text-white/30 uppercase tracking-wider mb-1">Current Goal</div>
          <div className="text-xs text-white/70 truncate">{currentGoal}</div>
        </div>
      )}

      {/* Thought Stream */}
      <div
        ref={containerRef}
        className="h-48 overflow-y-auto p-3 font-mono text-xs space-y-1 scrollbar-thin scrollbar-thumb-white/10"
      >
        {thoughts.length === 0 ? (
          <div className="text-white/30 text-center py-8">
            Waiting for Luna's thoughts...
          </div>
        ) : (
          thoughts.map((thought, idx) => (
            <div
              key={idx}
              className={`flex items-start gap-2 ${thought.type === 'error' ? 'text-red-400' : ''}`}
            >
              <span className="text-white/20 flex-shrink-0">{thought.timestamp}</span>
              <span className="flex-shrink-0">{getPhaseIcon(thought.message)}</span>
              <span className={getPhaseColor(thought.message)}>
                {thought.message}
              </span>
            </div>
          ))
        )}

        {/* Processing indicator */}
        {isProcessing && (
          <div className="flex items-center gap-2 text-amber-400/60">
            <span className="text-white/20">
              {new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
            <span className="animate-pulse">●</span>
            <span className="animate-pulse">Processing...</span>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-white/5 flex justify-between text-[10px] text-white/30">
        <span>{thoughts.length} thoughts</span>
        <span>{isConnected ? 'Live' : 'Disconnected'}</span>
      </div>
    </GlassCard>
  );
};

export default ThoughtStream;

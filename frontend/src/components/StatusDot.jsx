import React from 'react';

const StatusDot = ({ status, size = 'w-2 h-2' }) => {
  const colors = {
    connected: 'bg-emerald-400 shadow-emerald-400/50',
    active: 'bg-emerald-400 shadow-emerald-400/50',
    running: 'bg-emerald-400 shadow-emerald-400/50',
    loading: 'bg-blue-400 shadow-blue-400/50 animate-pulse',
    syncing: 'bg-blue-400 shadow-blue-400/50 animate-pulse',
    disconnected: 'bg-amber-400 shadow-amber-400/50',
    error: 'bg-red-400 shadow-red-400/50',
    neutral: 'bg-gray-400 shadow-gray-400/50',
    curious: 'bg-violet-400 shadow-violet-400/50',
    focused: 'bg-cyan-400 shadow-cyan-400/50',
    playful: 'bg-pink-400 shadow-pink-400/50',
    thoughtful: 'bg-indigo-400 shadow-indigo-400/50',
  };

  return (
    <div className={`${size} rounded-full shadow-lg ${colors[status] || colors.neutral}`} />
  );
};

export default StatusDot;

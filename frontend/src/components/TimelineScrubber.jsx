import React, { useState, useEffect } from 'react';

const STATE_COLORS = {
  personal: '#60a5fa',
  project: '#34d399',
  bridge: '#fbbf24',
  mixed: '#c084fc',
};

/**
 * TimelineScrubber — month-based timeline in the chat header.
 * Each month is a proportionally-sized segment. Click scrolls to that period.
 */
export default function TimelineScrubber({ onScrollToMonth }) {
  const [months, setMonths] = useState([]);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/history/timeline')
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!cancelled && data?.months?.length) setMonths(data.months);
      })
      .catch(() => {}); // Graceful fallback
    return () => { cancelled = true; };
  }, []);

  if (months.length === 0) return null;

  const maxCount = Math.max(...months.map((m) => m.count), 1);
  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-end',
      gap: 2,
      height: 20,
      padding: '0 4px',
    }}>
      {months.map((m) => {
        const ratio = m.count / maxCount;
        const isCurrent = m.month === currentMonth;
        const color = m.dominant_state
          ? (STATE_COLORS[m.dominant_state] || '#94a3b8')
          : '#94a3b8';

        return (
          <div
            key={m.month}
            onClick={() => onScrollToMonth?.(m.month)}
            title={`${m.month}: ${m.count} messages`}
            style={{
              flex: Math.max(ratio, 0.15),
              height: Math.max(ratio * 16, 3),
              background: `${color}${isCurrent ? '40' : '20'}`,
              borderRadius: 2,
              cursor: 'pointer',
              border: isCurrent ? `1px solid ${color}60` : 'none',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = `${color}50`; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = `${color}${isCurrent ? '40' : '20'}`; }}
          />
        );
      })}
    </div>
  );
}

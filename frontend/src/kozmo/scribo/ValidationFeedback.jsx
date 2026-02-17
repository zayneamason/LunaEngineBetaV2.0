/**
 * Validation Feedback
 *
 * Displays errors, warnings, and suggestions for frontmatter validation.
 * Provides actionable buttons to resolve issues.
 */
import React from 'react';

export function ValidationFeedback({ validationResults, onActionClick }) {
  const { errors, warnings, suggestions } = validationResults;

  if (errors.length === 0 && warnings.length === 0 && suggestions.length === 0) {
    return null;
  }

  const renderIssue = (issue) => {
    const styles = {
      error: {
        bg: 'rgba(239, 68, 68, 0.1)',
        border: '#ef4444',
        icon: '🚫'
      },
      warning: {
        bg: 'rgba(251, 191, 36, 0.1)',
        border: '#fbbf24',
        icon: '⚠️'
      },
      suggestion: {
        bg: 'rgba(96, 165, 250, 0.1)',
        border: '#60a5fa',
        icon: '💡'
      }
    };

    const style = styles[issue.severity];

    return (
      <div
        key={`${issue.field}-${issue.value}`}
        style={{
          padding: '10px 12px',
          marginBottom: 8,
          background: style.bg,
          border: `1px solid ${style.border}40`,
          borderLeft: `3px solid ${style.border}`,
          borderRadius: 4,
          fontSize: 12
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <span style={{ fontSize: 14, flexShrink: 0 }}>{style.icon}</span>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#e2e8f0', marginBottom: 4 }}>
              {issue.message}
            </div>
            {issue.values && (
              <div style={{
                color: '#94a3b8',
                fontSize: 11,
                fontFamily: "'JetBrains Mono', monospace"
              }}>
                {issue.values.join(', ')}
              </div>
            )}
          </div>
          {issue.action && (
            <button
              onClick={() => onActionClick(issue.action)}
              style={{
                padding: '4px 10px',
                background: style.border,
                border: 'none',
                borderRadius: 3,
                color: '#08080e',
                fontSize: 10,
                fontWeight: 600,
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              {getActionLabel(issue.action.type)}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{
      padding: '12px 16px',
      background: 'rgba(10, 10, 15, 0.4)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      borderTop: '1px solid #1e1e2e',
      maxHeight: '200px',
      overflowY: 'auto'
    }}>
      {errors.map(renderIssue)}
      {warnings.map(renderIssue)}
      {suggestions.map(renderIssue)}
    </div>
  );
}

function getActionLabel(actionType) {
  const labels = {
    create_entity: 'Create',
    view_entity: 'View',
    add_props: 'Add Props',
    set_time: 'Apply',
    fix_status: 'Fix',
    define_relationship: 'Define'
  };
  return labels[actionType] || 'Fix';
}

/**
 * MarkdownRenderer — renders markdown content with Eclissi design tokens.
 *
 * Wraps react-markdown with GFM support and syntax highlighting.
 * Integrates with AnnotatedText for entity highlighting within markdown.
 */

import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import AnnotatedText from './AnnotatedText';

/**
 * Custom text renderer that wraps plain text nodes in AnnotatedText
 * for entity highlighting, while preserving markdown formatting.
 */
function EntityText({ children, entities, onEntityClick }) {
  if (!entities || entities.length === 0) return <>{children}</>;

  // Only process string children
  const parts = React.Children.map(children, (child) => {
    if (typeof child === 'string') {
      return (
        <AnnotatedText
          text={child}
          entities={entities}
          onEntityClick={onEntityClick}
        />
      );
    }
    return child;
  });

  return <>{parts}</>;
}

/**
 * Build custom component overrides that inject entity highlighting
 * into markdown text nodes while preserving all formatting.
 */
function useMarkdownComponents(entities, onEntityClick) {
  return useMemo(() => ({
    // Block elements
    h1: ({ children }) => (
      <h1 className="luna-md-h1">
        <EntityText entities={entities} onEntityClick={onEntityClick}>{children}</EntityText>
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="luna-md-h2">
        <EntityText entities={entities} onEntityClick={onEntityClick}>{children}</EntityText>
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="luna-md-h3">
        <EntityText entities={entities} onEntityClick={onEntityClick}>{children}</EntityText>
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="luna-md-h4">
        <EntityText entities={entities} onEntityClick={onEntityClick}>{children}</EntityText>
      </h4>
    ),
    p: ({ children }) => (
      <p className="luna-md-p">
        <EntityText entities={entities} onEntityClick={onEntityClick}>{children}</EntityText>
      </p>
    ),
    li: ({ children }) => (
      <li className="luna-md-li">
        <EntityText entities={entities} onEntityClick={onEntityClick}>{children}</EntityText>
      </li>
    ),

    // Lists
    ul: ({ children }) => <ul className="luna-md-ul">{children}</ul>,
    ol: ({ children }) => <ol className="luna-md-ol">{children}</ol>,

    // Code
    code: ({ inline, className, children, ...props }) => {
      if (inline) {
        return <code className="luna-md-inline-code" {...props}>{children}</code>;
      }
      return (
        <pre className="luna-md-code-block">
          <code className={className} {...props}>{children}</code>
        </pre>
      );
    },

    // Blockquote
    blockquote: ({ children }) => (
      <blockquote className="luna-md-blockquote">{children}</blockquote>
    ),

    // Table
    table: ({ children }) => (
      <div className="luna-md-table-wrapper">
        <table className="luna-md-table">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="luna-md-thead">{children}</thead>,
    tbody: ({ children }) => <tbody>{children}</tbody>,
    tr: ({ children }) => <tr className="luna-md-tr">{children}</tr>,
    th: ({ children }) => <th className="luna-md-th">{children}</th>,
    td: ({ children }) => <td className="luna-md-td">{children}</td>,

    // Inline
    strong: ({ children }) => (
      <strong style={{ color: 'var(--ec-text)', fontWeight: 600 }}>{children}</strong>
    ),
    em: ({ children }) => (
      <em style={{ color: 'var(--ec-text-soft)' }}>{children}</em>
    ),
    a: ({ href, children }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          color: 'var(--ec-accent-luna)',
          textDecoration: 'none',
          borderBottom: '1px solid rgba(192,132,252,0.3)',
        }}
      >
        {children}
      </a>
    ),
    hr: () => (
      <hr style={{
        border: 'none',
        borderTop: '1px solid var(--ec-border)',
        margin: '1em 0',
      }} />
    ),
  }), [entities, onEntityClick]);
}

const PLUGINS_REMARK = [remarkGfm];
const PLUGINS_REHYPE = [rehypeHighlight];

export default function MarkdownRenderer({ children, entities, onEntityClick }) {
  const components = useMarkdownComponents(entities, onEntityClick);

  if (!children) return null;

  return (
    <div className="luna-md">
      <ReactMarkdown
        remarkPlugins={PLUGINS_REMARK}
        rehypePlugins={PLUGINS_REHYPE}
        components={components}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

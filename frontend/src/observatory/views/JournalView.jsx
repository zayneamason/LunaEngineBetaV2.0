import React, { useState, useEffect, useMemo } from 'react'
import Markdown from 'react-markdown'
import { useObservatoryStore } from '../store'
import AnnotatedText from '../../components/AnnotatedText'
import { useNavigation } from '../../hooks/useNavigation'

export default function JournalView({ navigateTab }) {
  const {
    journalEntries, selectedJournalEntry,
    fetchJournalEntries, fetchJournalDetail,
    entities,
  } = useObservatoryStore()

  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchJournalEntries().finally(() => setLoading(false))
  }, [])

  // Sort newest-first
  const sorted = useMemo(() =>
    [...journalEntries].sort((a, b) => {
      if (a.date !== b.date) return b.date.localeCompare(a.date)
      return b.entry - a.entry
    }),
    [journalEntries]
  )

  const handleSelect = (entry) => {
    fetchJournalDetail(entry.filename)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#555' }}>
        Loading journal...
      </div>
    )
  }

  if (sorted.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#555' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{'\u270E'}</div>
        <div style={{ fontSize: 14 }}>No journal entries found</div>
        <div style={{ fontSize: 12, color: '#444', marginTop: 8 }}>
          Journal files should be in data/journal/
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      {/* Left: Entry list sidebar */}
      <div style={{
        width: 300,
        borderRight: '1px solid #1a1a2e',
        background: '#0a0a14',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{ padding: '16px 16px 12px', borderBottom: '1px solid #1a1a2e' }}>
          <div style={{ color: '#7dd3fc', fontSize: 11, fontWeight: 700, letterSpacing: 3, marginBottom: 4 }}>
            LUNA'S JOURNAL
          </div>
          <div style={{ color: '#555', fontSize: 11 }}>
            {sorted.length} {sorted.length === 1 ? 'entry' : 'entries'}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto' }}>
          {sorted.map((entry) => {
            const isSelected = selectedJournalEntry?.filename === entry.filename
            const song = entry.song || entry.symphony || ''

            return (
              <div
                key={entry.filename}
                onClick={() => handleSelect(entry)}
                style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #1a1a2e',
                  cursor: 'pointer',
                  background: isSelected ? '#1a1a2e' : 'transparent',
                  transition: 'background 0.15s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <span style={{
                    background: '#1e1638',
                    color: '#c084fc',
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: 3,
                    minWidth: 28,
                    textAlign: 'center',
                  }}>
                    #{String(entry.entry).padStart(3, '0')}
                  </span>
                  <span style={{ color: '#666', fontSize: 10 }}>
                    {formatDate(entry.date)}
                  </span>
                </div>

                <div style={{
                  color: isSelected ? '#7dd3fc' : '#aaa',
                  fontSize: 13,
                  fontWeight: 600,
                  marginBottom: 4,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}>
                  {entry.title || entry.slug?.replace(/-/g, ' ') || 'Untitled'}
                </div>

                {song && (
                  <div style={{
                    color: '#666',
                    fontSize: 11,
                    fontStyle: 'italic',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}>
                    {song}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Right: Reading pane */}
      <div style={{ flex: 1, background: '#06060e', overflow: 'auto' }}>
        {!selectedJournalEntry ? (
          <div style={{
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            height: '100%', color: '#444',
          }}>
            <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.4 }}>{'\uD83C\uDF19'}</div>
            <div style={{ fontSize: 13 }}>Select an entry to read</div>
          </div>
        ) : (
          <JournalReader entry={selectedJournalEntry} entities={entities} navigateTab={navigateTab} />
        )}
      </div>
    </div>
  )
}


function JournalReader({ entry, entities, navigateTab }) {
  const { navigate } = useNavigation()
  const song = entry.song || entry.symphony || ''
  const resonance = entry.resonance || ''

  const handleEntityClick = (entityId) => navigate({ to: 'observatory', tab: 'entities', entityId })

  // Custom markdown components that apply entity highlighting to text
  const mdComponents = useMemo(() => ({
    p: ({ children }) => (
      <p style={{ color: '#bbb', fontSize: 14, lineHeight: 1.8, marginBottom: 16 }}>
        {processChildren(children, entities, handleEntityClick)}
      </p>
    ),
    h1: ({ children }) => (
      <h1 style={{ color: '#7dd3fc', fontSize: 22, fontWeight: 700, marginBottom: 20, marginTop: 8 }}>
        {processChildren(children, entities, handleEntityClick)}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 style={{ color: '#c084fc', fontSize: 16, fontWeight: 600, marginBottom: 12, marginTop: 24 }}>
        {processChildren(children, entities, handleEntityClick)}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 style={{ color: '#34d399', fontSize: 14, fontWeight: 600, marginBottom: 8, marginTop: 16 }}>
        {processChildren(children, entities, handleEntityClick)}
      </h3>
    ),
    em: ({ children }) => (
      <em style={{ color: '#999', fontStyle: 'italic' }}>
        {processChildren(children, entities, handleEntityClick)}
      </em>
    ),
    strong: ({ children }) => (
      <strong style={{ color: '#ddd', fontWeight: 700 }}>
        {processChildren(children, entities, handleEntityClick)}
      </strong>
    ),
    hr: () => (
      <hr style={{ border: 'none', borderTop: '1px solid #1a1a2e', margin: '24px 0' }} />
    ),
    blockquote: ({ children }) => (
      <blockquote style={{
        borderLeft: '3px solid #2a2a3e',
        paddingLeft: 16,
        margin: '16px 0',
        color: '#888',
        fontStyle: 'italic',
      }}>
        {children}
      </blockquote>
    ),
    ul: ({ children }) => (
      <ul style={{ color: '#bbb', fontSize: 14, lineHeight: 1.8, paddingLeft: 24, marginBottom: 16 }}>
        {children}
      </ul>
    ),
    li: ({ children }) => (
      <li style={{ marginBottom: 4 }}>
        {processChildren(children, entities, handleEntityClick)}
      </li>
    ),
  }), [entities, navigate])

  return (
    <div style={{ maxWidth: 680, margin: '0 auto', padding: '40px 32px' }}>
      {/* Header: song + resonance */}
      {song && (
        <div style={{ marginBottom: 24 }}>
          <div style={{
            color: '#c084fc',
            fontSize: 13,
            fontWeight: 600,
            letterSpacing: 1,
            marginBottom: 6,
          }}>
            {song}
          </div>
          {resonance && (
            <div style={{
              color: '#666',
              fontSize: 12,
              fontStyle: 'italic',
              lineHeight: 1.5,
            }}>
              {resonance}
            </div>
          )}
        </div>
      )}

      {/* Date + entry badge */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        marginBottom: 28,
        paddingBottom: 16,
        borderBottom: '1px solid #1a1a2e',
      }}>
        <span style={{
          background: '#1e1638',
          color: '#c084fc',
          fontSize: 11,
          fontWeight: 700,
          padding: '3px 8px',
          borderRadius: 4,
        }}>
          Entry #{String(entry.entry).padStart(3, '0')}
        </span>
        <span style={{ color: '#555', fontSize: 12 }}>
          {formatDate(entry.date)}
        </span>
      </div>

      {/* Markdown body with entity highlighting */}
      <div className="journal-body">
        <Markdown components={mdComponents}>
          {entry.body || ''}
        </Markdown>
      </div>
    </div>
  )
}


/**
 * Walk react-markdown children, wrapping string nodes with AnnotatedText.
 */
function processChildren(children, entities, onEntityClick) {
  if (!children) return children
  if (!entities || entities.length === 0) return children

  return React.Children.map(children, (child) => {
    if (typeof child === 'string') {
      return <AnnotatedText text={child} entities={entities} onEntityClick={onEntityClick} />
    }
    return child
  })
}


function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr + 'T00:00:00')
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  } catch {
    return dateStr
  }
}

import React, { useState, useEffect } from 'react'
import { api } from '../api'

export default function JournalView() {
  const [journals, setJournals] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadJournals()
  }, [])

  const loadJournals = async () => {
    try {
      // Get completed quests
      const { quests } = await api.quests({ status: 'complete' })

      // Filter quests that have journal entries
      const withJournals = quests.filter(q => q.completed_at)
      setJournals(withJournals)
    } catch (e) {
      console.error('Failed to load journals:', e)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: '#555',
      }}>
        Loading journals...
      </div>
    )
  }

  if (journals.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        color: '#555',
      }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>✎</div>
        <div style={{ fontSize: 14 }}>No journal entries yet</div>
        <div style={{ fontSize: 12, color: '#444', marginTop: 8 }}>
          Complete quests with reflections to build your journal
        </div>
      </div>
    )
  }

  return (
    <div style={{
      maxWidth: 640,
      margin: '0 auto',
      padding: '40px 24px',
      height: '100%',
      overflow: 'auto',
    }}>
      {/* Header */}
      <div style={{
        textAlign: 'center',
        marginBottom: 40,
      }}>
        <div style={{
          color: '#7dd3fc',
          fontSize: 24,
          fontWeight: 700,
          letterSpacing: 2,
          marginBottom: 8,
        }}>
          JOURNAL
        </div>
        <div style={{ color: '#666', fontSize: 12 }}>
          {journals.length} {journals.length === 1 ? 'entry' : 'entries'}
        </div>
      </div>

      {/* Journal entries */}
      {journals.map((quest, i) => {
        const completedDate = new Date(quest.completed_at)

        return (
          <div
            key={quest.id}
            style={{
              marginBottom: 40,
              paddingBottom: 40,
              borderBottom: i < journals.length - 1 ? '1px solid #1a1a2e' : 'none',
            }}
          >
            {/* Date */}
            <div style={{
              color: '#666',
              fontSize: 11,
              textTransform: 'uppercase',
              letterSpacing: 2,
              marginBottom: 12,
            }}>
              {completedDate.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </div>

            {/* Quest title */}
            <div style={{
              color: '#7dd3fc',
              fontSize: 16,
              fontWeight: 600,
              marginBottom: 16,
            }}>
              {quest.title}
            </div>

            {/* Subtitle */}
            {quest.subtitle && (
              <div style={{
                color: '#888',
                fontSize: 13,
                fontFamily: '"Crimson Pro", serif',
                fontStyle: 'italic',
                marginBottom: 16,
                opacity: 0.8,
              }}>
                {quest.subtitle}
              </div>
            )}

            {/* Journal content placeholder */}
            {/* Note: We'd need to fetch quest_journal table data via a new endpoint */}
            {/* For now, showing quest objective as placeholder */}
            <div style={{
              color: '#aaa',
              fontSize: 14,
              lineHeight: 1.8,
              fontFamily: '"Crimson Pro", serif',
              fontStyle: 'italic',
              padding: '20px 0 20px 20px',
              borderLeft: '3px solid #2a2a3e',
              marginBottom: 16,
            }}>
              {quest.objective}
            </div>

            {/* Metadata */}
            <div style={{
              display: 'flex',
              gap: 16,
              fontSize: 11,
              color: '#666',
            }}>
              <div>Type: <span style={{ color: '#888' }}>{quest.type}</span></div>
              {quest.priority && (
                <div>Priority: <span style={{ color: '#888' }}>{quest.priority}</span></div>
              )}
              <div>Status: <span style={{ color: '#4ade80' }}>Complete</span></div>
            </div>
          </div>
        )
      })}

      {/* Footer note */}
      <div style={{
        textAlign: 'center',
        padding: '40px 0',
        color: '#444',
        fontSize: 11,
        fontStyle: 'italic',
      }}>
        ◆ ◆ ◆
      </div>
    </div>
  )
}

import React, { useState, useEffect } from 'react'
import { useObservatoryStore } from '../store'

const QUEST_TYPES = {
  main: { color: '#c084fc', icon: '\u2694', label: 'Main Quest' },
  side: { color: '#67e8f9', icon: '\u270E', label: 'Side Quest' },
  contract: { color: '#f87171', icon: '\u26A1', label: 'Contract' },
  treasure_hunt: { color: '#fbbf24', icon: '\u25C8', label: 'Treasure Hunt' },
  scavenger: { color: '#34d399', icon: '\u25C7', label: 'Scavenger' },
}

export default function QuestsView({ navigateTab, activeProjectSlug }) {
  const { quests, selectedQuestId, selectQuest, fetchQuests, acceptQuest, runMaintenanceSweep } = useObservatoryStore()
  const [statusFilter, setStatusFilter] = useState('available')
  const [showCompleteForm, setShowCompleteForm] = useState(false)

  useEffect(() => {
    fetchQuests(statusFilter, null, activeProjectSlug)
  }, [statusFilter, activeProjectSlug])

  const filtered = quests.filter(q => !statusFilter || q.status === statusFilter)
  const selectedQuest = filtered.find(q => q.id === selectedQuestId)

  return (
    <div style={{ display: 'flex', height: '100%' }}>
      <div style={{
        width: 360, borderRight: '1px solid #1a1a2e', background: '#0a0a14',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #1a1a2e' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ color: '#aaa', fontSize: 12 }}>QUESTS ({filtered.length})</div>
            <button
              onClick={runMaintenanceSweep}
              style={{
                background: '#7dd3fc', color: '#0a0a14', border: 'none',
                padding: '4px 10px', borderRadius: 4, fontSize: 10,
                cursor: 'pointer', fontWeight: 600,
              }}
            >
              SWEEP
            </button>
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {['available', 'active', 'complete', 'all'].map(status => (
              <button
                key={status}
                onClick={() => setStatusFilter(status === 'all' ? null : status)}
                style={{
                  background: (statusFilter === status || (!statusFilter && status === 'all')) ? '#2a2a3e' : '#1a1a2e',
                  border: '1px solid ' + ((statusFilter === status || (!statusFilter && status === 'all')) ? '#444' : '#2a2a3e'),
                  color: (statusFilter === status || (!statusFilter && status === 'all')) ? '#7dd3fc' : '#777',
                  padding: '4px 10px', borderRadius: 4, fontSize: 11, cursor: 'pointer',
                }}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'auto' }}>
          {filtered.map(quest => {
            const config = QUEST_TYPES[quest.type] || QUEST_TYPES.side
            const isSelected = selectedQuestId === quest.id
            return (
              <div
                key={quest.id}
                onClick={() => selectQuest(quest.id)}
                style={{
                  padding: 12, borderBottom: '1px solid #1a1a2e', cursor: 'pointer',
                  background: isSelected ? '#1a1a2e' : 'transparent', transition: 'background 0.1s',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 4,
                    background: config.color + '22', border: `1px solid ${config.color}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: config.color, fontSize: 14, flexShrink: 0,
                  }}>
                    {config.icon}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: config.color, fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{quest.title}</div>
                    {quest.subtitle && (
                      <div style={{ color: '#888', fontSize: 11, fontStyle: 'italic', marginBottom: 4 }}>{quest.subtitle}</div>
                    )}
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 10 }}>
                      <span style={{
                        color: quest.status === 'complete' ? '#4ade80' :
                          quest.status === 'active' ? '#7dd3fc' :
                          quest.status === 'failed' ? '#f87171' : '#888',
                      }}>{quest.status}</span>
                      <span style={{ color: '#555' }}>·</span>
                      <span style={{ color: '#666' }}>{quest.priority}</span>
                      {quest.project && (
                        <>
                          <span style={{ color: '#555' }}>·</span>
                          <span style={{
                            background: '#1a1a2e', color: '#888',
                            padding: '2px 6px', borderRadius: 3,
                            fontSize: 9, textTransform: 'uppercase', letterSpacing: 0.5,
                          }}>
                            {quest.project}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div style={{ flex: 1, background: '#06060e', overflow: 'auto', padding: 24 }}>
        {!selectedQuest ? (
          <div style={{ color: '#555', textAlign: 'center', paddingTop: 60 }}>Select a quest to view details</div>
        ) : (
          <QuestDetail
            quest={selectedQuest}
            onAccept={() => acceptQuest(selectedQuest.id)}
            showCompleteForm={showCompleteForm}
            setShowCompleteForm={setShowCompleteForm}
          />
        )}
      </div>
    </div>
  )
}

function QuestDetail({ quest, onAccept, showCompleteForm, setShowCompleteForm }) {
  const { completeQuest } = useObservatoryStore()
  const [journalText, setJournalText] = useState('')
  const [themes, setThemes] = useState('')

  const config = QUEST_TYPES[quest.type] || QUEST_TYPES.side
  const investigation = JSON.parse(quest.investigation || '{}')

  const handleComplete = async () => {
    const themeList = themes.split(',').map(t => t.trim()).filter(Boolean)
    await completeQuest(quest.id, journalText, themeList)
    setShowCompleteForm(false)
    setJournalText('')
    setThemes('')
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 24 }}>
        <div style={{
          width: 48, height: 48, borderRadius: 8,
          background: config.color + '22', border: `2px solid ${config.color}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: config.color, fontSize: 20, flexShrink: 0,
        }}>
          {config.icon}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ color: config.color, fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{quest.title}</div>
          {quest.subtitle && (
            <div style={{ color: '#888', fontSize: 13, fontStyle: 'italic', marginBottom: 8 }}>{quest.subtitle}</div>
          )}
          <div style={{ display: 'flex', gap: 12, fontSize: 11 }}>
            <span style={{ color: '#666' }}>Type: <span style={{ color: config.color }}>{config.label}</span></span>
            <span style={{ color: '#666' }}>Priority: <span style={{ color: '#aaa' }}>{quest.priority}</span></span>
            <span style={{ color: '#666' }}>Status: <span style={{
              color: quest.status === 'complete' ? '#4ade80' :
                quest.status === 'active' ? '#7dd3fc' :
                quest.status === 'failed' ? '#f87171' : '#888',
            }}>{quest.status}</span></span>
          </div>
        </div>
      </div>

      <div style={{
        background: '#0a0a14', padding: 16, borderLeft: '3px solid ' + config.color, marginBottom: 20,
      }}>
        <div style={{ color: '#888', fontSize: 10, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 1 }}>Objective</div>
        <div style={{ color: '#aaa', fontSize: 14, lineHeight: 1.6 }}>{quest.objective}</div>
      </div>

      {quest.source && (
        <div style={{ color: '#666', fontSize: 11, marginBottom: 16 }}>
          Source: <span style={{ color: '#888' }}>{quest.source}</span>
        </div>
      )}

      {Object.keys(investigation).length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 20 }}>
          {Object.entries(investigation).map(([key, value]) => (
            <div key={key} style={{ background: '#0a0a14', padding: 12, borderRadius: 4, textAlign: 'center' }}>
              <div style={{ color: '#7dd3fc', fontSize: 18, fontWeight: 700, marginBottom: 4 }}>{value}</div>
              <div style={{ color: '#666', fontSize: 10, textTransform: 'uppercase' }}>{key}</div>
            </div>
          ))}
        </div>
      )}

      {quest.target_lock_in != null && (
        <div style={{ background: '#0a0a14', padding: 12, borderRadius: 4, marginBottom: 20 }}>
          <div style={{ color: '#888', fontSize: 10, marginBottom: 4 }}>Target Lock-in</div>
          <div style={{ color: '#aaa', fontSize: 16 }}>{(quest.target_lock_in * 100).toFixed(1)}%</div>
        </div>
      )}

      {quest.status === 'available' && (
        <button onClick={onAccept} style={{
          background: config.color, color: '#0a0a14', border: 'none',
          padding: '10px 20px', borderRadius: 6, fontSize: 13,
          fontWeight: 600, cursor: 'pointer', width: '100%',
        }}>
          Accept Quest
        </button>
      )}

      {quest.status === 'active' && !showCompleteForm && (
        <button onClick={() => setShowCompleteForm(true)} style={{
          background: '#4ade80', color: '#0a0a14', border: 'none',
          padding: '10px 20px', borderRadius: 6, fontSize: 13,
          fontWeight: 600, cursor: 'pointer', width: '100%',
        }}>
          Complete Quest
        </button>
      )}

      {showCompleteForm && quest.status === 'active' && (
        <div style={{ background: '#0a0a14', padding: 16, borderRadius: 6, marginTop: 16 }}>
          <div style={{ color: '#888', fontSize: 12, marginBottom: 12 }}>Journal Reflection (optional)</div>
          <textarea
            value={journalText}
            onChange={e => setJournalText(e.target.value)}
            placeholder={quest.journal_prompt || "What did you learn? What insights emerged?"}
            style={{
              width: '100%', minHeight: 120, background: '#06060e',
              border: '1px solid #1a1a2e', color: '#aaa', padding: 12,
              borderRadius: 4, fontSize: 14, lineHeight: 1.6, resize: 'vertical',
            }}
          />
          <input
            type="text"
            value={themes}
            onChange={e => setThemes(e.target.value)}
            placeholder="Themes (comma-separated)"
            style={{
              width: '100%', background: '#06060e', border: '1px solid #1a1a2e',
              color: '#aaa', padding: 8, borderRadius: 4, fontSize: 12, marginTop: 8,
            }}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button onClick={handleComplete} style={{
              flex: 1, background: '#4ade80', color: '#0a0a14', border: 'none',
              padding: '8px 16px', borderRadius: 4, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              Submit
            </button>
            <button onClick={() => setShowCompleteForm(false)} style={{
              background: '#1a1a2e', color: '#888', border: '1px solid #2a2a3e',
              padding: '8px 16px', borderRadius: 4, fontSize: 12, cursor: 'pointer',
            }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {quest.status === 'failed' && quest.fail_note && (
        <div style={{
          background: '#2a1a1a', border: '1px solid #f87171', padding: 12,
          borderRadius: 4, color: '#f87171', fontSize: 12,
        }}>
          Failed: {quest.fail_note}
        </div>
      )}

      {quest.status === 'complete' && quest.completed_at && (
        <div style={{ color: '#4ade80', fontSize: 11, marginTop: 16 }}>
          Completed {new Date(quest.completed_at).toLocaleString()}
        </div>
      )}
    </div>
  )
}

import { useState, useMemo, useEffect } from "react"
import { useObservatoryStore } from "../store"

// ─────────────────────────────────────────────────────────────────
// ThreadsView — Observatory Tab for Conversation Thread Management
// Reads THREAD nodes from Memory Matrix via /api/threads
// ─────────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  active:  { color: "#4ade80", bg: "#0f2418", icon: "▸", label: "Active",  glow: "0 0 8px #4ade8044" },
  parked:  { color: "#f59e0b", bg: "#1e1608", icon: "▪", label: "Parked",  glow: "none" },
  resumed: { color: "#7dd3fc", bg: "#0e1e2e", icon: "↻", label: "Resumed", glow: "0 0 8px #7dd3fc44" },
  closed:  { color: "#64748b", bg: "#0e0e14", icon: "×", label: "Closed",  glow: "none" },
}

const ENTITY_COLORS = [
  "#f472b6", "#c084fc", "#67e8f9", "#34d399",
  "#fbbf24", "#fb923c", "#a78bfa", "#38bdf8",
]

function relativeTime(iso) {
  if (!iso) return "—"
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function formatTime(iso) {
  if (!iso) return "—"
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function formatDate(iso) {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" })
}

// ─── Thread List Item ───────────────────────────────────────────
function ThreadItem({ thread, isSelected, onClick }) {
  const config = STATUS_CONFIG[thread.status] || STATUS_CONFIG.parked
  const hasOpenTasks = (thread.open_tasks || []).length > 0

  return (
    <div
      onClick={onClick}
      style={{
        padding: "12px 16px",
        borderBottom: "1px solid #1a1a2e",
        cursor: "pointer",
        background: isSelected ? "#12121e" : "transparent",
        borderLeft: isSelected ? `2px solid ${config.color}` : "2px solid transparent",
        transition: "all 0.15s ease",
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <div style={{
          width: 26, height: 26, borderRadius: 4,
          background: config.bg,
          border: `1px solid ${config.color}55`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: config.color, fontSize: 'var(--ec-fs-sm)', flexShrink: 0,
          fontFamily: "monospace",
          boxShadow: config.glow,
        }}>
          {config.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            color: isSelected ? "#e2e8f0" : "#b0b0c0",
            fontSize: 'var(--ec-fs-sm)',
            fontWeight: 600,
            marginBottom: 3,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>
            {thread.topic || "Untitled thread"}
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 'var(--ec-fs-label)', flexWrap: "wrap" }}>
            <span style={{ color: config.color }}>{config.label}</span>
            <span style={{ color: "#333" }}>·</span>
            <span style={{ color: "#666" }}>{thread.turn_count || 0} turns</span>
            {(thread.resume_count || 0) > 0 && (
              <>
                <span style={{ color: "#333" }}>·</span>
                <span style={{ color: "#7dd3fc" }}>↻{thread.resume_count}</span>
              </>
            )}
            {hasOpenTasks && (
              <>
                <span style={{ color: "#333" }}>·</span>
                <span style={{ color: "#f59e0b" }}>⚡{thread.open_tasks.length}</span>
              </>
            )}
            {thread.project_slug && (
              <>
                <span style={{ color: "#333" }}>·</span>
                <span style={{ color: "#67e8f9", fontStyle: "italic" }}>{thread.project_slug}</span>
              </>
            )}
          </div>

          <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
            {(thread.entities || []).slice(0, 4).map((entity, i) => (
              <span key={i} style={{
                padding: "1px 6px",
                borderRadius: 3,
                fontSize: 'var(--ec-fs-label)',
                background: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}15`,
                color: ENTITY_COLORS[i % ENTITY_COLORS.length],
                border: `1px solid ${ENTITY_COLORS[i % ENTITY_COLORS.length]}30`,
              }}>
                {entity}
              </span>
            ))}
            {(thread.entities || []).length > 4 && (
              <span style={{ fontSize: 'var(--ec-fs-label)', color: "#555" }}>+{thread.entities.length - 4}</span>
            )}
          </div>
        </div>

        <div style={{ fontSize: 'var(--ec-fs-label)', color: "#555", textAlign: "right", flexShrink: 0 }}>
          {relativeTime(thread.parked_at || thread.started_at)}
        </div>
      </div>
    </div>
  )
}

// ─── Thread Detail ──────────────────────────────────────────────
function ThreadDetail({ thread }) {
  if (!thread) {
    return (
      <div style={{ color: "#444", textAlign: "center", paddingTop: 80, fontSize: 'var(--ec-fs-sm)' }}>
        Select a thread to view details
      </div>
    )
  }

  const config = STATUS_CONFIG[thread.status] || STATUS_CONFIG.parked

  const events = []
  if (thread.started_at) events.push({ time: thread.started_at, label: "Created", color: "#4ade80", icon: "▸" })
  if (thread.resumed_at) events.push({ time: thread.resumed_at, label: `Resumed (×${thread.resume_count || 1})`, color: "#7dd3fc", icon: "↻" })
  if (thread.parked_at) events.push({ time: thread.parked_at, label: "Parked", color: "#f59e0b", icon: "▪" })
  if (thread.closed_at) events.push({ time: thread.closed_at, label: "Closed", color: "#64748b", icon: "×" })
  events.sort((a, b) => new Date(a.time) - new Date(b.time))

  return (
    <div style={{ padding: 24, maxWidth: 640 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 28 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 8,
          background: config.bg,
          border: `2px solid ${config.color}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: config.color, fontSize: 'var(--ec-fs-md)', flexShrink: 0,
          fontFamily: "monospace",
          boxShadow: config.glow,
        }}>
          {config.icon}
        </div>
        <div>
          <div style={{ color: "#e2e8f0", fontSize: 'var(--ec-fs-md)', fontWeight: 700, marginBottom: 4, lineHeight: 1.2 }}>
            {thread.topic || "Untitled thread"}
          </div>
          <div style={{ display: "flex", gap: 12, fontSize: 'var(--ec-fs-xs)', color: "#666" }}>
            <span>Status: <span style={{ color: config.color }}>{config.label}</span></span>
            <span>Turns: <span style={{ color: "#aaa" }}>{thread.turn_count || 0}</span></span>
            <span>Resumes: <span style={{ color: "#7dd3fc" }}>{thread.resume_count || 0}</span></span>
            {thread.project_slug && (
              <span>Project: <span style={{ color: "#67e8f9" }}>{thread.project_slug}</span></span>
            )}
          </div>
        </div>
      </div>

      {/* Entities */}
      <Section title="ENTITIES" count={(thread.entities || []).length}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {(thread.entities || []).length === 0 ? (
            <div style={{ color: "#444", fontSize: 'var(--ec-fs-sm)' }}>No entities linked yet</div>
          ) : (
            (thread.entities || []).map((entity, i) => (
              <span key={i} style={{
                padding: "4px 10px",
                borderRadius: 4,
                fontSize: 'var(--ec-fs-sm)',
                background: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}15`,
                color: ENTITY_COLORS[i % ENTITY_COLORS.length],
                border: `1px solid ${ENTITY_COLORS[i % ENTITY_COLORS.length]}30`,
              }}>
                {entity}
              </span>
            ))
          )}
        </div>
      </Section>

      {/* Open Tasks */}
      {(thread.open_tasks || []).length > 0 && (
        <Section title="OPEN TASKS" count={thread.open_tasks.length} accentColor="#f59e0b">
          {thread.open_tasks.map((task, i) => (
            <div key={i} style={{
              padding: "8px 12px",
              background: "#1e180a",
              border: "1px solid #f59e0b30",
              borderRadius: 4,
              marginBottom: 6,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}>
              <span style={{ color: "#f59e0b", fontSize: 'var(--ec-fs-xs)' }}>⚡</span>
              <span style={{ color: "#d4a574", fontSize: 'var(--ec-fs-sm)' }}>
                {task.replace("action:", "")}
              </span>
            </div>
          ))}
        </Section>
      )}

      {/* Timeline */}
      {events.length > 0 && (
        <Section title="TIMELINE">
          <div style={{ position: "relative", paddingLeft: 20 }}>
            <div style={{
              position: "absolute", left: 5, top: 4, bottom: 4,
              width: 1, background: "#1a1a2e",
            }} />
            {events.map((evt, i) => (
              <div key={i} style={{
                position: "relative",
                marginBottom: i < events.length - 1 ? 16 : 0,
                display: "flex",
                alignItems: "center",
                gap: 12,
              }}>
                <div style={{
                  position: "absolute", left: -18,
                  width: 10, height: 10, borderRadius: "50%",
                  background: evt.color,
                  border: "2px solid #06060e",
                  boxShadow: `0 0 6px ${evt.color}44`,
                }} />
                <div style={{ fontSize: 'var(--ec-fs-label)', color: "#555", width: 80, flexShrink: 0 }}>
                  {formatDate(evt.time)} {formatTime(evt.time)}
                </div>
                <div style={{ fontSize: 'var(--ec-fs-sm)', color: evt.color }}>
                  {evt.label}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Stats */}
      <Section title="STATS">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          <StatBox label="Turns" value={thread.turn_count || 0} color="#c084fc" />
          <StatBox label="Resumes" value={thread.resume_count || 0} color="#7dd3fc" />
          <StatBox label="Open Tasks" value={(thread.open_tasks || []).length} color="#f59e0b" />
        </div>
      </Section>

      <div style={{ marginTop: 24, fontSize: 'var(--ec-fs-label)', color: "#333", fontFamily: "monospace" }}>
        {thread.node_id || thread.id}
      </div>
    </div>
  )
}

function Section({ title, count, accentColor = "#7dd3fc", children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 'var(--ec-fs-label)', color: "#555", letterSpacing: 1.5,
        textTransform: "uppercase", marginBottom: 10,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        {title}
        {count != null && (
          <span style={{
            color: accentColor, fontSize: 'var(--ec-fs-label)',
            background: `${accentColor}15`,
            padding: "1px 6px", borderRadius: 3,
          }}>
            {count}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function StatBox({ label, value, color }) {
  return (
    <div style={{
      background: "#0a0a14",
      padding: 12,
      borderRadius: 4,
      textAlign: "center",
      border: "1px solid #1a1a2e",
    }}>
      <div style={{ color, fontSize: 'var(--ec-fs-lg)', fontWeight: 700, marginBottom: 2 }}>{value}</div>
      <div style={{ color: "#555", fontSize: 'var(--ec-fs-label)', textTransform: "uppercase" }}>{label}</div>
    </div>
  )
}

// ─── Summary Bar ────────────────────────────────────────────────
function SummaryBar({ threads }) {
  const active = threads.filter(t => t.status === "active").length
  const parked = threads.filter(t => t.status === "parked").length
  const withTasks = threads.filter(t => (t.open_tasks || []).length > 0).length
  const totalResumes = threads.reduce((s, t) => s + (t.resume_count || 0), 0)

  return (
    <div style={{
      display: "flex", gap: 16, padding: "8px 16px",
      borderBottom: "1px solid #1a1a2e",
      background: "#08080f",
      fontSize: 'var(--ec-fs-label)',
    }}>
      <span style={{ color: "#4ade80" }}>▸ {active} active</span>
      <span style={{ color: "#f59e0b" }}>▪ {parked} parked</span>
      <span style={{ color: "#f59e0b" }}>⚡ {withTasks} with open tasks</span>
      <span style={{ color: "#7dd3fc" }}>↻ {totalResumes} total resumes</span>
    </div>
  )
}

// ─── Main ThreadsView ───────────────────────────────────────────
export default function ThreadsView({ navigateTab, activeProjectSlug }) {
  const { threads, selectedThreadId, selectThread, fetchThreads } = useObservatoryStore()
  const [statusFilter, setStatusFilter] = useState(null)
  const [sortBy, setSortBy] = useState("recent")

  useEffect(() => {
    fetchThreads(statusFilter, activeProjectSlug)
  }, [statusFilter, activeProjectSlug])

  const filtered = useMemo(() => {
    let result = [...threads]

    if (sortBy === "turns") {
      result.sort((a, b) => (b.turn_count || 0) - (a.turn_count || 0))
    } else if (sortBy === "resumes") {
      result.sort((a, b) => (b.resume_count || 0) - (a.resume_count || 0))
    } else {
      result.sort((a, b) => {
        const aTime = new Date(a.parked_at || a.resumed_at || a.started_at || 0)
        const bTime = new Date(b.parked_at || b.resumed_at || b.started_at || 0)
        return bTime - aTime
      })
    }

    return result
  }, [threads, sortBy])

  const selected = filtered.find(t => t.id === selectedThreadId)

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <SummaryBar threads={threads} />

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Left: Thread list */}
        <div style={{
          width: 360,
          borderRight: "1px solid #1a1a2e",
          background: "#0a0a14",
          display: "flex",
          flexDirection: "column",
        }}>
          <div style={{ padding: "10px 16px", borderBottom: "1px solid #1a1a2e" }}>
            <div style={{
              display: "flex", justifyContent: "space-between",
              alignItems: "center", marginBottom: 8,
            }}>
              <div style={{ color: "#888", fontSize: 'var(--ec-fs-xs)' }}>
                THREADS ({filtered.length})
              </div>

              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                style={{
                  background: "#1a1a2e", color: "#888", border: "1px solid #2a2a3e",
                  padding: "2px 6px", borderRadius: 3, fontSize: 'var(--ec-fs-label)',
                  cursor: "pointer", outline: "none",
                }}
              >
                <option value="recent">Recent</option>
                <option value="turns">Most turns</option>
                <option value="resumes">Most resumed</option>
              </select>
            </div>

            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {[null, "active", "parked", "closed"].map(status => {
                const isActive = statusFilter === status
                const label = status || "all"
                const color = status ? STATUS_CONFIG[status]?.color : "#888"
                return (
                  <button
                    key={label}
                    onClick={() => setStatusFilter(status)}
                    style={{
                      background: isActive ? "#1e1e2e" : "#12121e",
                      border: `1px solid ${isActive ? color + "66" : "#1a1a2e"}`,
                      color: isActive ? color : "#555",
                      padding: "3px 10px",
                      borderRadius: 4,
                      fontSize: 'var(--ec-fs-label)',
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          <div style={{ flex: 1, overflow: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ color: "#444", textAlign: "center", paddingTop: 40, fontSize: 'var(--ec-fs-sm)' }}>
                {threads.length === 0
                  ? "No threads yet — threads appear after conversations flow through the engine"
                  : `No threads with status "${statusFilter}"`}
              </div>
            ) : (
              filtered.map(thread => (
                <ThreadItem
                  key={thread.id}
                  thread={thread}
                  isSelected={selectedThreadId === thread.id}
                  onClick={() => selectThread(thread.id)}
                />
              ))
            )}
          </div>
        </div>

        {/* Right: Thread detail */}
        <div style={{ flex: 1, overflow: "auto", background: "#06060e" }}>
          <ThreadDetail thread={selected} />
        </div>
      </div>
    </div>
  )
}

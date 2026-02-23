import { useState, useMemo } from "react"

// ═══════════════════════════════════════════════════════════════════
// ThreadsView — Observatory Tab for Conversation Thread Management
// Matches existing Observatory aesthetic: dark theme, monospace,
// list-detail split layout, status filters
// ═══════════════════════════════════════════════════════════════════

// Mock data — in production this comes from THREAD nodes in Memory Matrix
const MOCK_THREADS = [
  {
    id: "thread_a1b2c3d4",
    topic: "Observatory entity cleanup",
    status: "parked",
    entities: ["Observatory", "entity_mentions", "Ahab", "Luna"],
    entity_node_ids: ["e_obs", "e_em", "e_ahab", "e_luna"],
    open_tasks: ["action:Fix mention pollution", "action:Deploy stoplist"],
    turn_count: 47,
    resume_count: 3,
    started_at: "2026-02-19T10:30:00Z",
    parked_at: "2026-02-19T14:15:00Z",
    resumed_at: "2026-02-19T13:00:00Z",
    closed_at: null,
    project_slug: null,
  },
  {
    id: "thread_e5f6g7h8",
    topic: "Thread system diagnostic",
    status: "active",
    entities: ["Layer 2", "Layer 3", "Scribe", "Librarian", "FlowSignal"],
    entity_node_ids: [],
    open_tasks: ["action:Find serialization gap in ExtractionOutput.to_dict()"],
    turn_count: 12,
    resume_count: 0,
    started_at: "2026-02-19T15:00:00Z",
    parked_at: null,
    resumed_at: null,
    closed_at: null,
    project_slug: null,
  },
  {
    id: "thread_i9j0k1l2",
    topic: "Qwen local inference benchmarks",
    status: "parked",
    entities: ["Qwen", "MLX", "LoRA", "local inference"],
    entity_node_ids: [],
    open_tasks: [],
    turn_count: 8,
    resume_count: 0,
    started_at: "2026-02-19T15:45:00Z",
    parked_at: "2026-02-19T16:10:00Z",
    resumed_at: null,
    closed_at: null,
    project_slug: null,
  },
  {
    id: "thread_m3n4o5p6",
    topic: "Quest board system fix",
    status: "parked",
    entities: ["quest_board", "Observatory", "quest_targets", "schema"],
    entity_node_ids: [],
    open_tasks: ["action:Fix observatory_quest_board create action"],
    turn_count: 15,
    resume_count: 1,
    started_at: "2026-02-19T14:20:00Z",
    parked_at: "2026-02-19T15:00:00Z",
    resumed_at: "2026-02-19T14:50:00Z",
    closed_at: null,
    project_slug: null,
  },
  {
    id: "thread_q7r8s9t0",
    topic: "KOZMO asset pipeline",
    status: "closed",
    entities: ["KOZMO", "Eden", "pipeline", "assets"],
    entity_node_ids: [],
    open_tasks: [],
    turn_count: 34,
    resume_count: 5,
    started_at: "2026-02-15T09:00:00Z",
    parked_at: "2026-02-17T11:00:00Z",
    resumed_at: "2026-02-17T14:00:00Z",
    closed_at: "2026-02-18T10:00:00Z",
    project_slug: "kozmo",
  },
  {
    id: "thread_u1v2w3x4",
    topic: "Memory hygiene system design",
    status: "parked",
    entities: ["Memory Matrix", "entity stoplist", "hygiene", "sweep"],
    entity_node_ids: [],
    open_tasks: ["action:Implement weekly sweep automation", "action:Wire entity review quest"],
    turn_count: 22,
    resume_count: 2,
    started_at: "2026-02-19T12:00:00Z",
    parked_at: "2026-02-19T13:30:00Z",
    resumed_at: "2026-02-19T12:45:00Z",
    closed_at: null,
    project_slug: null,
  },
  {
    id: "thread_y5z6a7b8",
    topic: "Luna Mars College embodiment",
    status: "parked",
    entities: ["Mars College", "Tarcila", "raccoon robot", "orb"],
    entity_node_ids: [],
    open_tasks: ["action:Finalize orb LED protocol"],
    turn_count: 19,
    resume_count: 1,
    started_at: "2026-02-12T16:00:00Z",
    parked_at: "2026-02-14T11:00:00Z",
    resumed_at: "2026-02-13T09:00:00Z",
    closed_at: null,
    project_slug: "mars-college",
  },
]

const STATUS_CONFIG = {
  active:  { color: "#4ade80", bg: "#0f2418", icon: "▸", label: "Active",  glow: "0 0 8px #4ade8044" },
  parked:  { color: "#f59e0b", bg: "#1e1608", icon: "‖", label: "Parked",  glow: "none" },
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

// ─── Thread List Item ────────────────────────────────────────────
function ThreadItem({ thread, isSelected, onClick }) {
  const config = STATUS_CONFIG[thread.status] || STATUS_CONFIG.parked
  const hasOpenTasks = thread.open_tasks.length > 0

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
        {/* Status indicator */}
        <div style={{
          width: 26, height: 26, borderRadius: 4,
          background: config.bg,
          border: `1px solid ${config.color}55`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: config.color, fontSize: 13, flexShrink: 0,
          fontFamily: "monospace",
          boxShadow: config.glow,
        }}>
          {config.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Topic */}
          <div style={{
            color: isSelected ? "#e2e8f0" : "#b0b0c0",
            fontSize: 13,
            fontWeight: 600,
            marginBottom: 3,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}>
            {thread.topic}
          </div>

          {/* Meta row */}
          <div style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 10, flexWrap: "wrap" }}>
            <span style={{ color: config.color }}>{config.label}</span>
            <span style={{ color: "#333" }}>·</span>
            <span style={{ color: "#666" }}>{thread.turn_count} turns</span>
            {thread.resume_count > 0 && (
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

          {/* Entity pills - compact */}
          <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap" }}>
            {thread.entities.slice(0, 4).map((entity, i) => (
              <span key={i} style={{
                padding: "1px 6px",
                borderRadius: 3,
                fontSize: 9,
                background: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}15`,
                color: ENTITY_COLORS[i % ENTITY_COLORS.length],
                border: `1px solid ${ENTITY_COLORS[i % ENTITY_COLORS.length]}30`,
              }}>
                {entity}
              </span>
            ))}
            {thread.entities.length > 4 && (
              <span style={{ fontSize: 9, color: "#555" }}>+{thread.entities.length - 4}</span>
            )}
          </div>
        </div>

        {/* Timestamp */}
        <div style={{ fontSize: 10, color: "#555", textAlign: "right", flexShrink: 0 }}>
          {relativeTime(thread.parked_at || thread.started_at)}
        </div>
      </div>
    </div>
  )
}

// ─── Thread Detail ───────────────────────────────────────────────
function ThreadDetail({ thread }) {
  if (!thread) {
    return (
      <div style={{ color: "#444", textAlign: "center", paddingTop: 80, fontSize: 13 }}>
        Select a thread to view details
      </div>
    )
  }

  const config = STATUS_CONFIG[thread.status] || STATUS_CONFIG.parked

  // Build timeline events
  const events = []
  if (thread.started_at) events.push({ time: thread.started_at, label: "Created", color: "#4ade80", icon: "◆" })
  if (thread.resumed_at) events.push({ time: thread.resumed_at, label: `Resumed (×${thread.resume_count})`, color: "#7dd3fc", icon: "↻" })
  if (thread.parked_at) events.push({ time: thread.parked_at, label: "Parked", color: "#f59e0b", icon: "‖" })
  if (thread.closed_at) events.push({ time: thread.closed_at, label: "Closed", color: "#64748b", icon: "×" })
  events.sort((a, b) => new Date(a.time) - new Date(b.time))

  return (
    <div style={{ padding: 24, maxWidth: 640 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 28 }}>
        <div style={{
          width: 44, height: 44, borderRadius: 8,
          background: config.bg,
          border: `2px solid ${config.color}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          color: config.color, fontSize: 18, flexShrink: 0,
          fontFamily: "monospace",
          boxShadow: config.glow,
        }}>
          {config.icon}
        </div>
        <div>
          <div style={{ color: "#e2e8f0", fontSize: 18, fontWeight: 700, marginBottom: 4, lineHeight: 1.2 }}>
            {thread.topic}
          </div>
          <div style={{ display: "flex", gap: 12, fontSize: 11, color: "#666" }}>
            <span>Status: <span style={{ color: config.color }}>{config.label}</span></span>
            <span>Turns: <span style={{ color: "#aaa" }}>{thread.turn_count}</span></span>
            <span>Resumes: <span style={{ color: "#7dd3fc" }}>{thread.resume_count}</span></span>
            {thread.project_slug && (
              <span>Project: <span style={{ color: "#67e8f9" }}>{thread.project_slug}</span></span>
            )}
          </div>
        </div>
      </div>

      {/* Entities */}
      <Section title="ENTITIES" count={thread.entities.length}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {thread.entities.map((entity, i) => (
            <span key={i} style={{
              padding: "4px 10px",
              borderRadius: 4,
              fontSize: 12,
              background: `${ENTITY_COLORS[i % ENTITY_COLORS.length]}15`,
              color: ENTITY_COLORS[i % ENTITY_COLORS.length],
              border: `1px solid ${ENTITY_COLORS[i % ENTITY_COLORS.length]}30`,
              cursor: "pointer",
            }}>
              {entity}
            </span>
          ))}
        </div>
      </Section>

      {/* Open Tasks */}
      {thread.open_tasks.length > 0 && (
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
              <span style={{ color: "#f59e0b", fontSize: 11 }}>⚡</span>
              <span style={{ color: "#d4a574", fontSize: 12 }}>
                {task.replace("action:", "")}
              </span>
            </div>
          ))}
        </Section>
      )}

      {/* Timeline */}
      <Section title="TIMELINE">
        <div style={{ position: "relative", paddingLeft: 20 }}>
          {/* Vertical line */}
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
              {/* Dot */}
              <div style={{
                position: "absolute", left: -18,
                width: 10, height: 10, borderRadius: "50%",
                background: evt.color,
                border: "2px solid #06060e",
                boxShadow: `0 0 6px ${evt.color}44`,
              }} />
              <div style={{ fontSize: 10, color: "#555", width: 80, flexShrink: 0 }}>
                {formatDate(evt.time)} {formatTime(evt.time)}
              </div>
              <div style={{ fontSize: 12, color: evt.color }}>
                {evt.label}
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Stats */}
      <Section title="STATS">
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          <StatBox label="Turns" value={thread.turn_count} color="#c084fc" />
          <StatBox label="Resumes" value={thread.resume_count} color="#7dd3fc" />
          <StatBox label="Open Tasks" value={thread.open_tasks.length} color="#f59e0b" />
        </div>
      </Section>

      {/* Thread ID */}
      <div style={{ marginTop: 24, fontSize: 10, color: "#333", fontFamily: "monospace" }}>
        {thread.id}
      </div>
    </div>
  )
}

function Section({ title, count, accentColor = "#7dd3fc", children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 10, color: "#555", letterSpacing: 1.5,
        textTransform: "uppercase", marginBottom: 10,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        {title}
        {count != null && (
          <span style={{
            color: accentColor, fontSize: 10,
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
      <div style={{ color, fontSize: 20, fontWeight: 700, marginBottom: 2 }}>{value}</div>
      <div style={{ color: "#555", fontSize: 10, textTransform: "uppercase" }}>{label}</div>
    </div>
  )
}

// ─── Summary Bar ─────────────────────────────────────────────────
function SummaryBar({ threads }) {
  const active = threads.filter(t => t.status === "active").length
  const parked = threads.filter(t => t.status === "parked").length
  const withTasks = threads.filter(t => t.open_tasks.length > 0).length
  const totalResumes = threads.reduce((s, t) => s + t.resume_count, 0)

  return (
    <div style={{
      display: "flex", gap: 16, padding: "8px 16px",
      borderBottom: "1px solid #1a1a2e",
      background: "#08080f",
      fontSize: 10,
    }}>
      <span style={{ color: "#4ade80" }}>▸ {active} active</span>
      <span style={{ color: "#f59e0b" }}>‖ {parked} parked</span>
      <span style={{ color: "#f59e0b" }}>⚡ {withTasks} with open tasks</span>
      <span style={{ color: "#7dd3fc" }}>↻ {totalResumes} total resumes</span>
    </div>
  )
}

// ─── Main ThreadsView ────────────────────────────────────────────
export default function ThreadsView() {
  const [selectedId, setSelectedId] = useState(null)
  const [statusFilter, setStatusFilter] = useState(null)
  const [sortBy, setSortBy] = useState("recent") // "recent" | "turns" | "resumes"

  const threads = MOCK_THREADS

  const filtered = useMemo(() => {
    let result = threads.filter(t => !statusFilter || t.status === statusFilter)

    if (sortBy === "turns") {
      result = [...result].sort((a, b) => b.turn_count - a.turn_count)
    } else if (sortBy === "resumes") {
      result = [...result].sort((a, b) => b.resume_count - a.resume_count)
    } else {
      // "recent" — sort by most recent activity
      result = [...result].sort((a, b) => {
        const aTime = new Date(a.parked_at || a.resumed_at || a.started_at)
        const bTime = new Date(b.parked_at || b.resumed_at || b.started_at)
        return bTime - aTime
      })
    }

    return result
  }, [threads, statusFilter, sortBy])

  const selected = filtered.find(t => t.id === selectedId)

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      minHeight: "100vh",
      fontFamily: '"JetBrains Mono", "Fira Code", "SF Mono", monospace',
      background: "#06060e",
      color: "#c8c8d4",
      overflow: "hidden",
    }}>
      {/* Summary bar */}
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
          {/* Filters */}
          <div style={{ padding: "10px 16px", borderBottom: "1px solid #1a1a2e" }}>
            <div style={{
              display: "flex", justifyContent: "space-between",
              alignItems: "center", marginBottom: 8,
            }}>
              <div style={{ color: "#888", fontSize: 11 }}>
                THREADS ({filtered.length})
              </div>

              {/* Sort */}
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                style={{
                  background: "#1a1a2e", color: "#888", border: "1px solid #2a2a3e",
                  padding: "2px 6px", borderRadius: 3, fontSize: 10,
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
                      fontSize: 10,
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

          {/* Thread list */}
          <div style={{ flex: 1, overflow: "auto" }}>
            {filtered.length === 0 ? (
              <div style={{ color: "#444", textAlign: "center", paddingTop: 40, fontSize: 12 }}>
                No threads {statusFilter ? `with status "${statusFilter}"` : "yet"}
              </div>
            ) : (
              filtered.map(thread => (
                <ThreadItem
                  key={thread.id}
                  thread={thread}
                  isSelected={selectedId === thread.id}
                  onClick={() => setSelectedId(thread.id)}
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

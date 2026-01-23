# Luna Engine Debugging Toolkit

## Quick Reference

### 🚀 Start/Stop

```bash
# Full relaunch (kills everything, restarts backend + frontend)
./scripts/relaunch.sh

# Stop everything
./scripts/stop.sh

# Launch as app (includes browser open)
./scripts/launch_app.sh
```

### 📊 Monitoring

```bash
# Real-time dashboard (requires: pip install rich)
python scripts/monitor.py

# Multi-pane log viewer (requires tmux)
./scripts/watch.sh

# Simple log tail
tail -f /tmp/luna_backend.log
```

### 🔍 Inspection

```bash
# Full state dump
python scripts/inspect_state.py

# Git forensics (find what changed)
./scripts/git_forensics.sh
```

### ✅ Verification

```bash
# Run memory tests
./scripts/verify_memory.sh

# Run all tests
pytest tests/ -v
```

### 📁 Log Locations

| Log | Location |
|-----|----------|
| Backend | `/tmp/luna_backend.log` |
| Frontend | `/tmp/luna_frontend.log` |
| Traces (sorted) | `/tmp/luna_traces_sorted.log` |
| Test results | `/tmp/luna_memory_test.log` |
| Forensics | `/tmp/luna_forensics/` |

### 🔎 Grep Patterns

```bash
# Find requests
grep "\[REQUEST\]" /tmp/luna_backend.log

# Find routing decisions
grep "\[ROUTE\]" /tmp/luna_backend.log

# Find context building
grep "\[CONTEXT\]" /tmp/luna_backend.log

# Find state changes
grep "\[STATE\]" /tmp/luna_backend.log

# Find errors
grep -E "\[ERROR\]|\[WARN\]|Error|Exception" /tmp/luna_backend.log

# Find specific entity
grep -i "marzipan" /tmp/luna_backend.log
```

### 🗄️ Database

```bash
# Open database directly
sqlite3 ~/.luna/luna.db

# Common queries
.tables
SELECT * FROM entities;
SELECT * FROM conversation_turns ORDER BY created_at DESC LIMIT 10;
SELECT COUNT(*) FROM memory_nodes;
```

### 📝 Handoffs

| Handoff | Purpose |
|---------|---------|
| `HANDOFF-EMERGENCY-SWARM.md` | Full diagnostic swarm deployment |
| `HANDOFF-CONVERSATION-DISPLACEMENT-FIX.md` | History + unified pipeline |
| `HANDOFF-SWARM-FIX-CONVERSATION-HISTORY.md` | Memory persistence fix |
| `HANDOFF-NO-BULLSHIT-ENTITY-VERIFICATION.md` | Entity system verification |

### ⚡ Emergency Commands

```bash
# Force kill everything Luna
pkill -9 -f luna

# Check if anything is running
ps aux | grep luna

# Clear logs
rm /tmp/luna_*.log

# Reset database (DANGEROUS)
rm ~/.luna/luna.db
```

---

*When in doubt: `./scripts/relaunch.sh` then `python scripts/monitor.py`*

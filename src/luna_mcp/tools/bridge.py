"""
Desktop ↔ Code Bridge
=====================

Shared task queue and session handoff between Claude Desktop and Claude Code.

Data stored as YAML files in data/cache/ (same pattern as shared_turn.yaml):
  - task_queue.yaml: Shared task queue
  - handoff_snapshot.yaml: Session handoff snapshots

Both surfaces read/write these files directly. No new services needed.
"""

import os
import time
import fcntl
import secrets
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import yaml

from luna.core.paths import project_root as _project_root, user_dir

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = _project_root()
CACHE_DIR = user_dir() / "cache"
TASK_QUEUE_PATH = CACHE_DIR / "task_queue.yaml"
HANDOFF_SNAPSHOT_PATH = CACHE_DIR / "handoff_snapshot.yaml"
SHARED_TURN_PATH = CACHE_DIR / "shared_turn.yaml"

ENGINE_API_URL = "http://localhost:8000"


# ==============================================================================
# YAML I/O with file locking
# ==============================================================================

def _read_yaml(path: Path) -> dict:
    """Read YAML file with shared lock. Returns empty dict if missing."""
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = yaml.safe_load(f) or {}
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return data
    except Exception as e:
        logger.error(f"Failed to read {path}: {e}")
        return {}


def _write_yaml(path: Path, data: dict) -> None:
    """Write YAML file with exclusive lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _generate_task_id() -> str:
    """Generate a unique task ID: task_YYYYMMDD_HHMMSS_xxxx."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"task_{ts}_{suffix}"


def _prune_completed(data: dict, max_tasks: int = 50) -> dict:
    """Remove oldest completed/failed tasks if over limit."""
    tasks = data.get("tasks", [])
    if len(tasks) <= max_tasks:
        return data

    active = [t for t in tasks if t.get("status") not in ("completed", "failed")]
    done = [t for t in tasks if t.get("status") in ("completed", "failed")]
    done.sort(key=lambda t: t.get("completed_at") or 0)

    keep_done = max_tasks - len(active)
    if keep_done > 0:
        done = done[-keep_done:]
    else:
        done = []

    data["tasks"] = active + done
    return data


# ==============================================================================
# Task Queue
# ==============================================================================

async def task_create(
    title: str,
    description: str,
    priority: str = "medium",
    tags: Optional[List[str]] = None,
    related_files: Optional[List[str]] = None,
) -> str:
    """Create a new task in the shared queue."""
    data = _read_yaml(TASK_QUEUE_PATH)
    if "tasks" not in data:
        data = {"schema_version": 1, "last_updated": time.time(), "tasks": []}

    task_id = _generate_task_id()

    # Enrich context from shared turn cache
    shared_turn = _read_yaml(SHARED_TURN_PATH)
    context = {
        "session_id": shared_turn.get("session_id"),
        "topic": shared_turn.get("flow", {}).get("topic"),
        "related_files": related_files or [],
    }

    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "status": "pending",
        "priority": priority,
        "created_by": "desktop",
        "created_at": time.time(),
        "claimed_by": None,
        "claimed_at": None,
        "completed_at": None,
        "tags": tags or [],
        "context": context,
        "result": None,
        "result_summary": None,
    }

    data["tasks"].append(task)
    data["last_updated"] = time.time()
    data = _prune_completed(data)
    _write_yaml(TASK_QUEUE_PATH, data)

    return f"Task created: {task_id}\n  Title: {title}\n  Priority: {priority}"


async def task_list(status_filter: Optional[str] = None) -> str:
    """List tasks, optionally filtered by status."""
    data = _read_yaml(TASK_QUEUE_PATH)
    tasks = data.get("tasks", [])

    if not tasks:
        return "No tasks in queue."

    if status_filter:
        tasks = [t for t in tasks if t.get("status") == status_filter]
        if not tasks:
            return f"No tasks with status '{status_filter}'."

    lines = []
    for t in tasks:
        age = time.time() - t.get("created_at", 0)
        age_str = f"{int(age / 3600)}h" if age > 3600 else f"{int(age / 60)}m"
        priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
        status_icon = {
            "pending": "⏳", "claimed": "🔒", "in_progress": "🔄",
            "completed": "✅", "failed": "❌"
        }.get(t["status"], "❓")

        lines.append(f"{status_icon} {priority_icon} [{t['priority'].upper()}] {t['title']}")
        lines.append(f"    id: {t['id']}  |  status: {t['status']}  |  age: {age_str}")
        if t.get("claimed_by"):
            lines.append(f"    claimed by: {t['claimed_by']}")
        if t.get("result_summary"):
            lines.append(f"    result: {t['result_summary']}")
        if t.get("description"):
            desc = t["description"][:120] + "..." if len(t["description"]) > 120 else t["description"]
            lines.append(f"    {desc}")
        lines.append("")

    return "\n".join(lines)


async def task_claim(task_id: str, claimer: str = "code") -> str:
    """Claim a pending task."""
    data = _read_yaml(TASK_QUEUE_PATH)
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            if task["status"] not in ("pending",):
                return f"Cannot claim: task is '{task['status']}', not 'pending'."
            task["status"] = "claimed"
            task["claimed_by"] = claimer
            task["claimed_at"] = time.time()
            data["last_updated"] = time.time()
            _write_yaml(TASK_QUEUE_PATH, data)
            return f"Claimed: {task['title']}\n  Now work on it and run `/bridge:tasks done {task_id} \"summary\"`"
    return f"Task not found: {task_id}"


async def task_update(
    task_id: str,
    status: str,
    result: Optional[str] = None,
    result_summary: Optional[str] = None,
) -> str:
    """Update a task's status and optionally set result."""
    data = _read_yaml(TASK_QUEUE_PATH)
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            task["status"] = status
            if result is not None:
                task["result"] = result
            if result_summary is not None:
                task["result_summary"] = result_summary
            if status in ("completed", "failed"):
                task["completed_at"] = time.time()
            data["last_updated"] = time.time()
            _write_yaml(TASK_QUEUE_PATH, data)
            return f"Task {task_id} updated: status={status}"
    return f"Task not found: {task_id}"


async def task_result(task_id: str) -> str:
    """Get the result of a completed task."""
    data = _read_yaml(TASK_QUEUE_PATH)
    for task in data.get("tasks", []):
        if task["id"] == task_id:
            if task["status"] not in ("completed", "failed"):
                return f"Task is not done yet (status: {task['status']})."
            lines = [
                f"Task: {task['title']}",
                f"Status: {task['status']}",
                f"Completed: {datetime.fromtimestamp(task.get('completed_at', 0)).isoformat() if task.get('completed_at') else 'N/A'}",
                "",
                f"Summary: {task.get('result_summary', 'No summary')}",
                "",
                f"Full result:\n{task.get('result', 'No detailed result')}",
            ]
            return "\n".join(lines)
    return f"Task not found: {task_id}"


# ==============================================================================
# Session Handoff
# ==============================================================================

async def _fetch_engine(path: str) -> dict:
    """Fetch from Engine API. Returns empty dict on failure."""
    if not HAS_HTTPX:
        return {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{ENGINE_API_URL}{path}")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug(f"Engine fetch {path} failed: {e}")
    return {}


async def handoff_create_snapshot(source: str = "code") -> str:
    """Create a session handoff snapshot for the other surface to resume."""
    # 1. Read shared turn cache
    shared_turn = _read_yaml(SHARED_TURN_PATH)

    # 2. Fetch live state from Engine (best-effort)
    consciousness = await _fetch_engine("/consciousness")
    active_window = await _fetch_engine("/hub/active_window?limit=10")

    # 3. Read pending tasks
    task_data = _read_yaml(TASK_QUEUE_PATH)
    pending = [
        t["title"] for t in task_data.get("tasks", [])
        if t.get("status") in ("pending", "claimed", "in_progress")
    ]

    # 4. Build snapshot
    now = time.time()
    snapshot = {
        "schema_version": 1,
        "created_at": now,
        "created_by": source,
        "expires_at": now + 3600,  # 1 hour TTL
        "session": {
            "session_id": shared_turn.get("session_id"),
            "turns_count": len(active_window.get("turns", [])),
        },
        "flow": shared_turn.get("flow", {}),
        "expression": shared_turn.get("expression", {}),
        "recent_turns": [],
        "pending_tasks": pending,
        "consciousness": {},
    }

    # Extract recent turns summaries
    for turn in active_window.get("turns", [])[:10]:
        content = turn.get("content", "")
        summary = content[:150] + "..." if len(content) > 150 else content
        snapshot["recent_turns"].append({
            "role": turn.get("role", "unknown"),
            "summary": summary,
        })

    # Extract consciousness
    if consciousness:
        snapshot["consciousness"] = {
            "mood": consciousness.get("mood"),
            "coherence": consciousness.get("coherence"),
        }

    # 5. Write
    _write_yaml(HANDOFF_SNAPSHOT_PATH, snapshot)

    topic = snapshot["flow"].get("topic", "unknown")
    turns = snapshot["session"]["turns_count"]
    task_count = len(pending)

    return (
        f"Handoff snapshot created by {source}.\n"
        f"  Topic: {topic}\n"
        f"  Recent turns: {turns}\n"
        f"  Pending tasks: {task_count}\n"
        f"  Expires in 1 hour.\n"
        f"  File: data/cache/handoff_snapshot.yaml"
    )


async def handoff_read_snapshot() -> str:
    """Read the latest handoff snapshot."""
    snapshot = _read_yaml(HANDOFF_SNAPSHOT_PATH)

    if not snapshot:
        return "No handoff snapshot found. Create one with `luna_handoff_snapshot` (Desktop) or `/bridge:handoff create` (Code)."

    # Check expiry
    expires_at = snapshot.get("expires_at", 0)
    if time.time() > expires_at:
        age_min = int((time.time() - snapshot.get("created_at", 0)) / 60)
        return f"Handoff snapshot expired ({age_min} minutes old). Create a fresh one."

    # Format output
    lines = []
    lines.append(f"=== Handoff Snapshot (from {snapshot.get('created_by', '?')}) ===")
    age_min = int((time.time() - snapshot.get("created_at", 0)) / 60)
    lines.append(f"Age: {age_min} minutes")
    lines.append("")

    # Session
    session = snapshot.get("session", {})
    lines.append(f"Session: {session.get('session_id', 'N/A')}  ({session.get('turns_count', 0)} turns)")

    # Flow
    flow = snapshot.get("flow", {})
    if flow:
        lines.append(f"Topic: {flow.get('topic', 'N/A')}")
        lines.append(f"Mode: {flow.get('mode', 'N/A')}")
        lines.append(f"Continuity: {flow.get('continuity_score', 'N/A')}")
        threads = flow.get("open_threads", [])
        if threads:
            lines.append(f"Open threads:")
            for t in threads:
                lines.append(f"  - {t}")

    # Expression
    expr = snapshot.get("expression", {})
    if expr:
        lines.append(f"Tone: {expr.get('emotional_tone', 'N/A')} (intensity: {expr.get('intensity', 'N/A')})")

    # Consciousness
    consciousness = snapshot.get("consciousness", {})
    if consciousness:
        lines.append(f"Mood: {consciousness.get('mood', 'N/A')}  Coherence: {consciousness.get('coherence', 'N/A')}")

    # Recent turns
    turns = snapshot.get("recent_turns", [])
    if turns:
        lines.append("")
        lines.append("Recent conversation:")
        for t in turns[-6:]:
            role = t.get("role", "?")
            summary = t.get("summary", "")
            prefix = "User" if role == "user" else "Luna"
            lines.append(f"  {prefix}: {summary}")

    # Pending tasks
    pending = snapshot.get("pending_tasks", [])
    if pending:
        lines.append("")
        lines.append(f"Pending tasks ({len(pending)}):")
        for p in pending:
            lines.append(f"  - {p}")

    return "\n".join(lines)

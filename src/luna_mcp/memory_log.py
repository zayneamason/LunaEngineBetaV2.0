"""
Memory Matrix Logger
====================

Simple linear log of all Memory Matrix operations.
Provides audit trail and debugging for memory system.

Log Format:
    [TIMESTAMP] [ACTION] [NODE_TYPE] [NODE_ID] content_preview...

Actions:
    ADD, UPDATE, DELETE, EDGE, SESSION_START, SESSION_END, ERROR, CONFLICT
"""

import os
import json
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from luna.core.paths import project_root

# Configuration
LOGS_DIR = Path(os.environ.get(
    "LUNA_LOGS_DIR",
    project_root() / "logs"
))
MEMORY_LOG_FILE = LOGS_DIR / "memory_matrix.log"
SESSION_LOG_FILE = LOGS_DIR / "sessions.jsonl"


class LogAction(str, Enum):
    """Log action types."""
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EDGE = "EDGE"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    ERROR = "ERROR"
    CONFLICT = "CONFLICT"


@dataclass
class MemoryLogEntry:
    """A single log entry."""
    timestamp: str
    action: LogAction
    node_type: Optional[str] = None
    node_id: Optional[str] = None
    content_preview: Optional[str] = None
    edge_from: Optional[str] = None
    edge_to: Optional[str] = None
    edge_type: Optional[str] = None
    strength: Optional[float] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _file_lock(f):
    """Platform-appropriate file locking."""
    if platform.system() != 'Windows':
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)


def _file_unlock(f):
    """Platform-appropriate file unlocking."""
    if platform.system() != 'Windows':
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


class MemoryLogger:
    """Thread-safe memory logger (singleton)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._file_lock = threading.Lock()
        self._session_id: Optional[str] = None
        self._session_stats = {
            "nodes_added": 0,
            "edges_added": 0,
            "errors": 0,
            "conflicts": 0
        }

        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        # Write header if new file
        if not MEMORY_LOG_FILE.exists():
            self._write_header()

        self._initialized = True

    def _write_header(self):
        """Write log file header."""
        header = """# Luna Memory Matrix Log
# Format: [TIMESTAMP] [ACTION] [NODE_TYPE] [NODE_ID] content_preview...
# ========================================================================

"""
        with open(MEMORY_LOG_FILE, 'w') as f:
            f.write(header)

    def _format_entry(self, entry: MemoryLogEntry) -> str:
        """Format a log entry as a single line."""
        ts = entry.timestamp
        action = entry.action.value

        if entry.action == LogAction.EDGE:
            return (
                f"[{ts}] [{action}] [{entry.edge_type}] "
                f"{entry.edge_from} -> {entry.edge_to} (strength={entry.strength})\n"
            )

        elif entry.action in (LogAction.SESSION_START, LogAction.SESSION_END):
            if entry.metadata:
                meta_str = " ".join(f"{k}={v}" for k, v in entry.metadata.items())
                return f"[{ts}] [{action}] {entry.session_id} {meta_str}\n"
            return f"[{ts}] [{action}] {entry.session_id}\n"

        elif entry.action in (LogAction.ERROR, LogAction.CONFLICT):
            return f"[{ts}] [{action}] {entry.error}\n"

        else:
            # ADD, UPDATE, DELETE
            preview = (entry.content_preview or "")[:80].replace("\n", " ")
            return f"[{ts}] [{action}] [{entry.node_type}] {entry.node_id} \"{preview}\"\n"

    def _write(self, entry: MemoryLogEntry):
        """Write entry to log file (thread-safe)."""
        line = self._format_entry(entry)

        with self._file_lock:
            with open(MEMORY_LOG_FILE, 'a') as f:
                _file_lock(f)
                try:
                    f.write(line)
                finally:
                    _file_unlock(f)

    def start_session(self, session_id: str):
        """Mark session start."""
        self._session_id = session_id
        self._session_stats = {
            "nodes_added": 0,
            "edges_added": 0,
            "errors": 0,
            "conflicts": 0
        }

        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.SESSION_START,
            session_id=session_id
        ))

    def log_node(self, action: LogAction, node_type: str, node_id: str, content: str):
        """Log a node operation."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=action,
            node_type=node_type,
            node_id=node_id,
            content_preview=content[:100] if content else None
        ))

        if action == LogAction.ADD:
            self._session_stats["nodes_added"] += 1

    def log_edge(self, from_node: str, to_node: str, edge_type: str, strength: float = 1.0):
        """Log an edge operation."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.EDGE,
            edge_from=from_node,
            edge_to=to_node,
            edge_type=edge_type,
            strength=strength
        ))

        self._session_stats["edges_added"] += 1

    def log_error(self, error: str):
        """Log an error."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.ERROR,
            error=error
        ))

        self._session_stats["errors"] += 1

    def log_conflict(self, conflict: str):
        """Log a memory conflict."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.CONFLICT,
            error=conflict
        ))

        self._session_stats["conflicts"] += 1

    def end_session(self) -> Dict[str, Any]:
        """
        End session and return stats.

        Returns dict with nodes_added, edges_added, errors, conflicts.
        """
        stats = self._session_stats.copy()

        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.SESSION_END,
            session_id=self._session_id,
            metadata=stats
        ))

        # Also write to sessions JSONL for structured access
        session_record = {
            "session_id": self._session_id,
            "ended_at": datetime.now().isoformat(),
            **stats
        }
        with open(SESSION_LOG_FILE, 'a') as f:
            f.write(json.dumps(session_record) + "\n")

        self._session_id = None
        return stats

    def get_recent_entries(self, n: int = 50) -> List[str]:
        """Get the last N log entries."""
        if not MEMORY_LOG_FILE.exists():
            return []

        with open(MEMORY_LOG_FILE, 'r') as f:
            lines = f.readlines()

        # Skip header lines (starting with #)
        entries = [line.strip() for line in lines if line.strip() and not line.startswith('#')]
        return entries[-n:]

    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session stats."""
        return {
            "session_id": self._session_id,
            "active": self._session_id is not None,
            **self._session_stats
        }


# Global instance
memory_logger = MemoryLogger()

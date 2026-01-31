# Luna Observability Infrastructure - Implementation Handoff

**Date:** January 27, 2026  
**For:** Claude Code  
**From:** Ahab + Architect  
**Priority:** HIGH - Enables self-service debugging  
**Timeline:** Week 1 (Core Diagnostics + CLI)

---

## Objective

Build permanent debugging infrastructure for Luna Engine so Ahab can diagnose issues instantly without writing handoffs.

**What we're building:**
1. HealthChecker system (6 component checks)
2. CLI debug tools (`luna-debug` command)
3. Pipeline tracing
4. Basic automated tests

**What this solves:**
- "Luna can't find Marzipan" → `luna-debug find-person Marzipan` → instant diagnosis
- "Is extraction working?" → `luna-debug extraction-status` → instant answer
- "What's broken?" → `luna-debug health` → full system report

---

## Project Structure

```
src/luna/
├── diagnostics/
│   ├── __init__.py
│   ├── health.py          # HealthChecker system
│   └── tracer.py          # Pipeline tracing
├── cli/
│   ├── __init__.py
│   └── debug.py           # Debug CLI commands
└── ...

tests/
└── diagnostics/
    ├── test_health.py
    └── test_extraction_pipeline.py

logs/
├── pipeline_trace.jsonl   # Pipeline traces
└── sessions.jsonl         # Existing session logs
```

---

## Phase 1: Health Check System

### File: `src/luna/diagnostics/__init__.py`

```python
"""Luna diagnostics package."""
from .health import HealthChecker, HealthCheck, HealthStatus

__all__ = ['HealthChecker', 'HealthCheck', 'HealthStatus']
```

### File: `src/luna/diagnostics/health.py`

```python
"""Health checking system for Luna Engine components."""

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import time
import sqlite3
from pathlib import Path
import json

class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BROKEN = "broken"
    UNKNOWN = "unknown"

@dataclass
class HealthCheck:
    """Result of a health check."""
    component: str
    status: HealthStatus
    message: str
    metrics: Dict[str, any]
    timestamp: float

class HealthChecker:
    """Continuous health monitoring for Luna components."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def check_all(self) -> List[HealthCheck]:
        """Run all health checks."""
        return [
            self.check_database(),
            self.check_extraction(),
            self.check_retrieval(),
            self.check_memory_matrix(),
            self.check_sessions(),
            self.check_profiles()
        ]
    
    def check_database(self) -> HealthCheck:
        """Check database connectivity and integrity."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['nodes', 'edges']
            missing = [t for t in required_tables if t not in tables]
            
            # Check row counts
            cursor.execute("SELECT COUNT(*) FROM nodes")
            node_count = cursor.fetchone()[0]
            
            conn.close()
            
            if missing:
                return HealthCheck(
                    component="database",
                    status=HealthStatus.BROKEN,
                    message=f"Missing tables: {missing}",
                    metrics={'node_count': node_count, 'missing_tables': missing},
                    timestamp=time.time()
                )
            
            return HealthCheck(
                component="database",
                status=HealthStatus.HEALTHY,
                message=f"Database operational with {node_count:,} nodes",
                metrics={'node_count': node_count, 'tables': len(tables)},
                timestamp=time.time()
            )
            
        except Exception as e:
            return HealthCheck(
                component="database",
                status=HealthStatus.BROKEN,
                message=f"Database error: {e}",
                metrics={},
                timestamp=time.time()
            )
    
    def check_extraction(self) -> HealthCheck:
        """Check if extraction is creating nodes."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check nodes created in last hour
            cursor.execute("""
                SELECT COUNT(*) FROM nodes 
                WHERE datetime(created_at) > datetime('now', '-1 hour')
            """)
            recent_nodes = cursor.fetchone()[0]
            
            # Check nodes created today
            cursor.execute("""
                SELECT COUNT(*) FROM nodes 
                WHERE date(created_at) = date('now')
            """)
            today_nodes = cursor.fetchone()[0]
            
            conn.close()
            
            # Check session logs for comparison
            sessions_file = Path("logs/sessions.jsonl")
            recent_sessions = 0
            zero_extraction = 0
            
            if sessions_file.exists():
                with open(sessions_file) as f:
                    lines = f.readlines()
                
                # Parse last 10 sessions
                for line in lines[-10:]:
                    try:
                        session = json.loads(line)
                        # Check if session is recent (last hour)
                        recent_sessions += 1
                        if session.get('nodes_added', 0) == 0:
                            zero_extraction += 1
                    except:
                        continue
            
            # Determine status
            if recent_sessions > 0 and recent_nodes == 0:
                status = HealthStatus.BROKEN
                message = f"Sessions recorded ({recent_sessions}) but no nodes created"
            elif recent_sessions > 0 and zero_extraction > recent_sessions * 0.7:
                status = HealthStatus.DEGRADED
                message = f"Low extraction rate: {zero_extraction}/{recent_sessions} sessions with no nodes"
            elif today_nodes > 0:
                status = HealthStatus.HEALTHY
                message = f"Extraction active: {today_nodes} nodes created today"
            else:
                status = HealthStatus.UNKNOWN
                message = "No recent activity to assess"
            
            return HealthCheck(
                component="extraction",
                status=status,
                message=message,
                metrics={
                    'recent_nodes': recent_nodes,
                    'today_nodes': today_nodes,
                    'recent_sessions': recent_sessions,
                    'zero_extraction_count': zero_extraction
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            return HealthCheck(
                component="extraction",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                metrics={},
                timestamp=time.time()
            )
    
    def check_retrieval(self) -> HealthCheck:
        """Check if retrieval is working."""
        try:
            # Try to import Librarian
            try:
                from luna.librarian import Librarian
            except ImportError:
                return HealthCheck(
                    component="retrieval",
                    status=HealthStatus.BROKEN,
                    message="Librarian module not found",
                    metrics={},
                    timestamp=time.time()
                )
            
            librarian = Librarian(self.db_path)
            
            # Test search
            start = time.time()
            results = librarian.hybrid_search("test", limit=5)
            search_time = (time.time() - start) * 1000
            
            # Check FTS5
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if FTS table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE '%fts%'
            """)
            fts_tables = cursor.fetchall()
            
            conn.close()
            
            if search_time > 200:
                status = HealthStatus.DEGRADED
                message = f"Slow retrieval: {search_time:.0f}ms"
            elif not fts_tables:
                status = HealthStatus.DEGRADED
                message = "FTS index missing or not configured"
            else:
                status = HealthStatus.HEALTHY
                message = f"Retrieval operational: {search_time:.0f}ms"
            
            return HealthCheck(
                component="retrieval",
                status=status,
                message=message,
                metrics={
                    'search_time_ms': search_time,
                    'result_count': len(results),
                    'fts_configured': len(fts_tables) > 0
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            return HealthCheck(
                component="retrieval",
                status=HealthStatus.BROKEN,
                message=f"Retrieval failed: {e}",
                metrics={},
                timestamp=time.time()
            )
    
    def check_memory_matrix(self) -> HealthCheck:
        """Check Memory Matrix state."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Node type distribution
            cursor.execute("""
                SELECT node_type, COUNT(*) 
                FROM nodes 
                GROUP BY node_type
            """)
            type_dist = dict(cursor.fetchall())
            
            # Check for PERSON nodes
            person_count = type_dist.get('PERSON', 0)
            
            # Total nodes
            cursor.execute("SELECT COUNT(*) FROM nodes")
            total_nodes = cursor.fetchone()[0]
            
            conn.close()
            
            # Status based on person nodes
            if total_nodes > 100 and person_count == 0:
                status = HealthStatus.DEGRADED
                message = "No PERSON nodes - profile extraction may be broken"
            elif total_nodes > 0:
                status = HealthStatus.HEALTHY
                message = f"Memory Matrix operational: {len(type_dist)} node types"
            else:
                status = HealthStatus.UNKNOWN
                message = "Memory Matrix is empty"
            
            return HealthCheck(
                component="memory_matrix",
                status=status,
                message=message,
                metrics={
                    'total_nodes': total_nodes,
                    'node_types': type_dist,
                    'person_count': person_count
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            return HealthCheck(
                component="memory_matrix",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                metrics={},
                timestamp=time.time()
            )
    
    def check_sessions(self) -> HealthCheck:
        """Check session recording."""
        try:
            log_path = Path("logs/sessions.jsonl")
            
            if not log_path.exists():
                return HealthCheck(
                    component="sessions",
                    status=HealthStatus.BROKEN,
                    message="Session log file not found",
                    metrics={},
                    timestamp=time.time()
                )
            
            # Check file info
            file_size = log_path.stat().st_size
            mod_time = log_path.stat().st_mtime
            age_seconds = time.time() - mod_time
            
            # Parse recent sessions
            with open(log_path) as f:
                lines = f.readlines()
            
            recent_sessions = lines[-10:] if len(lines) > 10 else lines
            
            sessions_data = []
            for line in recent_sessions:
                if line.strip():
                    try:
                        sessions_data.append(json.loads(line))
                    except:
                        continue
            
            # Check for extraction issues
            zero_extraction = sum(1 for s in sessions_data if s.get('nodes_added', 0) == 0)
            
            if not sessions_data:
                status = HealthStatus.DEGRADED
                message = "Session log exists but is empty or malformed"
            elif zero_extraction > len(sessions_data) * 0.8:
                status = HealthStatus.DEGRADED
                message = f"{zero_extraction}/{len(sessions_data)} recent sessions with no extraction"
            else:
                status = HealthStatus.HEALTHY
                message = f"Session recording active: {len(sessions_data)} recent sessions"
            
            return HealthCheck(
                component="sessions",
                status=status,
                message=message,
                metrics={
                    'log_size_mb': file_size / 1024 / 1024,
                    'age_minutes': age_seconds / 60,
                    'recent_sessions': len(sessions_data),
                    'zero_extraction_count': zero_extraction
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            return HealthCheck(
                component="sessions",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                metrics={},
                timestamp=time.time()
            )
    
    def check_profiles(self) -> HealthCheck:
        """Check character profile system."""
        try:
            # Check if ProfileManager exists
            profile_system_exists = False
            try:
                from luna.profiles import ProfileManager
                profile_system_exists = True
            except ImportError:
                pass
            
            # Check database for person nodes
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE node_type = 'PERSON'")
            person_count = cursor.fetchone()[0]
            
            # Check for profile-related tables
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND (name LIKE '%profile%' OR name LIKE '%person%')
            """)
            profile_tables = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            
            if not profile_system_exists and person_count == 0:
                status = HealthStatus.UNKNOWN
                message = "Profile system not implemented"
            elif person_count == 0:
                status = HealthStatus.BROKEN
                message = "Profile system exists but no person profiles in database"
            else:
                status = HealthStatus.HEALTHY
                message = f"Profiles active: {person_count} person nodes"
            
            return HealthCheck(
                component="profiles",
                status=status,
                message=message,
                metrics={
                    'person_nodes': person_count,
                    'system_exists': profile_system_exists,
                    'profile_tables': profile_tables
                },
                timestamp=time.time()
            )
            
        except Exception as e:
            return HealthCheck(
                component="profiles",
                status=HealthStatus.UNKNOWN,
                message=f"Check failed: {e}",
                metrics={},
                timestamp=time.time()
            )
```

---

## Phase 2: CLI Debug Tools

### File: `src/luna/cli/__init__.py`

```python
"""Luna CLI tools."""
from .debug import debug

__all__ = ['debug']
```

### File: `src/luna/cli/debug.py`

See full implementation in the complete handoff document (truncated here for brevity - contains all 6 CLI commands: health, find-person, extraction-status, stats, search, recent)

---

## Phase 3-5: Setup, Tracing, Testing

Full details provided in complete document.

---

## Validation & Success Criteria

After implementation:
- ✅ `luna-debug health` shows all 6 component statuses
- ✅ `luna-debug find-person "Marzipan"` diagnoses the issue
- ✅ All commands work without errors
- ✅ Tests pass

---

**READY TO IMPLEMENT. Start with Phase 1 (health.py), validate it works, then move to Phase 2 (CLI).**

— Ahab + Architect  
January 27, 2026

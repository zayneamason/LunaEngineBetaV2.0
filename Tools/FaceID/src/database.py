"""
FaceID Database Module
======================

SQLite storage for face embeddings and entity identity mapping.
Schema mirrors the architecture spec from ARCHITECTURE_IDENTITY_GATED_SOVEREIGNTY.md.

Embeddings stored as BLOBs (numpy bytes). Small dataset = linear scan is fine.
All data lives in a single .db file. Sovereign. Portable.
"""

import sqlite3
import hashlib
import numpy as np
import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "faces.db"

SCHEMA = """
-- Face embeddings: biometric identity for entity recognition
CREATE TABLE IF NOT EXISTS face_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    embedding BLOB NOT NULL,
    embedding_dim INTEGER NOT NULL,
    embedding_model TEXT NOT NULL,
    capture_context TEXT DEFAULT 'enrollment',
    quality_score REAL DEFAULT 0.0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_face_entity ON face_embeddings(entity_id);

-- Entity permission tiers (mirrors access_bridge from Dual-Tier Bridge spec)
CREATE TABLE IF NOT EXISTS access_bridge (
    entity_id TEXT PRIMARY KEY,
    entity_name TEXT NOT NULL,
    
    -- Luna's relational tier (evolves organically)
    luna_tier TEXT NOT NULL DEFAULT 'unknown',
    luna_tier_updated_at TEXT,
    
    -- Data room structural tier (set by admin)
    dataroom_tier INTEGER DEFAULT 5,
    dataroom_categories TEXT DEFAULT '[]',
    dataroom_tier_updated_at TEXT,
    dataroom_tier_set_by TEXT,
    
    created_at TEXT DEFAULT (datetime('now'))
);

-- Admin PIN for reset authorization
CREATE TABLE IF NOT EXISTS admin_pin (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    pin_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Audit log for identity events
CREATE TABLE IF NOT EXISTS identity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_id TEXT,
    entity_name TEXT,
    details TEXT,
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@dataclass
class StoredFace:
    """A face embedding record from the database."""
    id: int
    entity_id: str
    entity_name: str
    embedding: np.ndarray
    embedding_model: str
    quality_score: float


@dataclass 
class AccessBridge:
    """Combined tier lookup for an entity."""
    entity_id: str
    entity_name: str
    luna_tier: str
    dataroom_tier: int
    dataroom_categories: list[int]


class FaceDatabase:
    """
    SQLite storage for face embeddings and identity data.
    
    Synchronous (no async needed for a standalone tool).
    When this integrates into the engine, swap to aiosqlite.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
    
    def connect(self):
        """Open database and initialize schema."""
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        logger.info(f"FaceDatabase connected: {self.db_path}")
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, *args):
        self.close()
    
    # =========================================================================
    # FACE EMBEDDINGS
    # =========================================================================
    
    def store_embedding(
        self,
        entity_id: str,
        entity_name: str,
        embedding: np.ndarray,
        model_name: str,
        quality: float = 0.0,
        context: str = "enrollment",
    ) -> int:
        """Store a face embedding. Returns the row ID."""
        row = self._conn.execute(
            """INSERT INTO face_embeddings 
               (entity_id, entity_name, embedding, embedding_dim, 
                embedding_model, capture_context, quality_score)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (entity_id, entity_name, embedding.tobytes(), 
             len(embedding), model_name, context, quality)
        )
        self._conn.commit()
        
        self._log("enrollment", entity_id, entity_name, 
                  f"Stored {len(embedding)}-dim embedding ({context})", quality)
        
        return row.lastrowid
    
    def get_all_embeddings(self) -> list[StoredFace]:
        """Load all stored face embeddings."""
        rows = self._conn.execute(
            """SELECT id, entity_id, entity_name, embedding, embedding_dim,
                      embedding_model, quality_score
               FROM face_embeddings"""
        ).fetchall()
        
        results = []
        for row in rows:
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
            results.append(StoredFace(
                id=row["id"],
                entity_id=row["entity_id"],
                entity_name=row["entity_name"],
                embedding=emb,
                embedding_model=row["embedding_model"],
                quality_score=row["quality_score"],
            ))
        
        return results
    
    def get_entity_embeddings(self, entity_id: str) -> list[StoredFace]:
        """Get all embeddings for a specific entity."""
        rows = self._conn.execute(
            """SELECT id, entity_id, entity_name, embedding, embedding_dim,
                      embedding_model, quality_score
               FROM face_embeddings WHERE entity_id = ?""",
            (entity_id,)
        ).fetchall()
        
        results = []
        for row in rows:
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
            results.append(StoredFace(
                id=row["id"],
                entity_id=row["entity_id"],
                entity_name=row["entity_name"],
                embedding=emb,
                embedding_model=row["embedding_model"],
                quality_score=row["quality_score"],
            ))
        
        return results
    
    def count_embeddings(self, entity_id: Optional[str] = None) -> int:
        """Count stored embeddings, optionally filtered by entity."""
        if entity_id:
            row = self._conn.execute(
                "SELECT COUNT(*) as c FROM face_embeddings WHERE entity_id = ?",
                (entity_id,)
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) as c FROM face_embeddings"
            ).fetchone()
        return row["c"]
    
    def delete_entity_faces(self, entity_id: str) -> int:
        """Delete all face embeddings for an entity. Returns count deleted."""
        cursor = self._conn.execute(
            "DELETE FROM face_embeddings WHERE entity_id = ?", (entity_id,)
        )
        self._conn.commit()
        return cursor.rowcount
    
    # =========================================================================
    # ACCESS BRIDGE
    # =========================================================================
    
    def set_access(
        self,
        entity_id: str,
        entity_name: str,
        luna_tier: str = "unknown",
        dataroom_tier: int = 5,
        dataroom_categories: Optional[list[int]] = None,
        set_by: str = "admin",
    ):
        """Set or update access bridge entry for an entity."""
        from datetime import datetime
        now = datetime.now().isoformat()
        cats = json.dumps(dataroom_categories or [])
        
        self._conn.execute(
            """INSERT INTO access_bridge 
               (entity_id, entity_name, luna_tier, luna_tier_updated_at,
                dataroom_tier, dataroom_categories, dataroom_tier_updated_at,
                dataroom_tier_set_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(entity_id) DO UPDATE SET
                entity_name = excluded.entity_name,
                luna_tier = excluded.luna_tier,
                luna_tier_updated_at = excluded.luna_tier_updated_at,
                dataroom_tier = excluded.dataroom_tier,
                dataroom_categories = excluded.dataroom_categories,
                dataroom_tier_updated_at = excluded.dataroom_tier_updated_at,
                dataroom_tier_set_by = excluded.dataroom_tier_set_by""",
            (entity_id, entity_name, luna_tier, now, 
             dataroom_tier, cats, now, set_by)
        )
        self._conn.commit()
        
        self._log("access_set", entity_id, entity_name,
                  f"luna_tier={luna_tier}, dr_tier={dataroom_tier}, categories={cats}")
    
    def get_access(self, entity_id: str) -> Optional[AccessBridge]:
        """Look up access bridge for an entity."""
        row = self._conn.execute(
            "SELECT * FROM access_bridge WHERE entity_id = ?", (entity_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return AccessBridge(
            entity_id=row["entity_id"],
            entity_name=row["entity_name"],
            luna_tier=row["luna_tier"],
            dataroom_tier=row["dataroom_tier"],
            dataroom_categories=json.loads(row["dataroom_categories"]),
        )
    
    def list_entities(self) -> list[dict]:
        """List all known entities with their face count and tiers."""
        rows = self._conn.execute(
            """SELECT 
                ab.entity_id, ab.entity_name, ab.luna_tier, ab.dataroom_tier,
                COUNT(fe.id) as face_count
               FROM access_bridge ab
               LEFT JOIN face_embeddings fe ON ab.entity_id = fe.entity_id
               GROUP BY ab.entity_id"""
        ).fetchall()
        
        return [dict(row) for row in rows]
    
    # =========================================================================
    # ADMIN PIN
    # =========================================================================

    @staticmethod
    def _hash_pin(pin: str) -> str:
        return hashlib.sha256(pin.encode()).hexdigest()

    def set_pin(self, pin: str):
        """Set or overwrite the 4-digit admin PIN."""
        self._conn.execute(
            """INSERT INTO admin_pin (id, pin_hash) VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET pin_hash = excluded.pin_hash,
               created_at = datetime('now')""",
            (self._hash_pin(pin),)
        )
        self._conn.commit()
        self._log("pin_set", details="Admin PIN was set")

    def verify_pin(self, pin: str) -> bool:
        """Verify a PIN against the stored hash. Returns False if no PIN set."""
        row = self._conn.execute(
            "SELECT pin_hash FROM admin_pin WHERE id = 1"
        ).fetchone()
        if not row:
            return False
        return row["pin_hash"] == self._hash_pin(pin)

    def has_pin(self) -> bool:
        """Check whether an admin PIN has been configured."""
        row = self._conn.execute(
            "SELECT COUNT(*) as c FROM admin_pin"
        ).fetchone()
        return row["c"] > 0

    def reset_entity(self, entity_id: str) -> int:
        """Delete all face embeddings for an entity (for re-enrollment). Returns count deleted."""
        count = self.delete_entity_faces(entity_id)
        self._log("reset", entity_id, details=f"Deleted {count} embeddings via PIN reset")
        return count

    # =========================================================================
    # LOGGING
    # =========================================================================
    
    def _log(self, event_type: str, entity_id: str = None, 
             entity_name: str = None, details: str = None,
             confidence: float = None):
        """Write to identity audit log."""
        self._conn.execute(
            """INSERT INTO identity_log 
               (event_type, entity_id, entity_name, details, confidence)
               VALUES (?, ?, ?, ?, ?)""",
            (event_type, entity_id, entity_name, details, confidence)
        )
        self._conn.commit()

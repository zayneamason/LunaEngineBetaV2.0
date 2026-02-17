"""Temporary standalone HTTP server for Observatory frontend — sync SQLite reads."""
import json
import sqlite3
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = str(Path(__file__).parent / "sandbox_matrix.db")

app = FastAPI(title="Observatory Sandbox API (standalone)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

@app.get("/api/graph-dump")
async def graph_dump(limit: int = 500, min_lock_in: float = 0.0):
    conn = _db()
    try:
        nodes = [dict(r) for r in conn.execute(
            "SELECT id, type, content, confidence, lock_in, access_count, cluster_id, tags, created_at, updated_at "
            "FROM nodes WHERE lock_in >= ? ORDER BY lock_in DESC LIMIT ?", (min_lock_in, limit)).fetchall()]
        edges = [dict(r) for r in conn.execute("SELECT from_id, to_id, relationship, strength FROM edges").fetchall()]
        clusters = [dict(r) for r in conn.execute("SELECT id, label, lock_in, member_ids FROM clusters").fetchall()]
        return {"nodes": nodes, "edges": edges, "clusters": clusters}
    finally:
        conn.close()

@app.get("/api/stats")
async def stats():
    conn = _db()
    try:
        nc = conn.execute("SELECT count(*) FROM nodes").fetchone()[0]
        ec = conn.execute("SELECT count(*) FROM edges").fetchone()[0]
        cc = conn.execute("SELECT count(*) FROM clusters").fetchone()[0]
        types = {r[0]: r[1] for r in conn.execute("SELECT type, count(*) FROM nodes GROUP BY type")}
        lock_dist = {"drifting": 0, "fluid": 0, "settled": 0, "crystallized": 0}
        for r in conn.execute("SELECT lock_in FROM nodes"):
            v = r[0]
            if v >= 0.85: lock_dist["crystallized"] += 1
            elif v >= 0.70: lock_dist["settled"] += 1
            elif v >= 0.30: lock_dist["fluid"] += 1
            else: lock_dist["drifting"] += 1
        return {"node_count": nc, "edge_count": ec, "cluster_count": cc, "type_distribution": types, "lock_in_distribution": lock_dist}
    finally:
        conn.close()

@app.get("/api/events/recent")
async def events_recent(n: int = 50):
    return []

@app.get("/api/config")
async def config():
    return {"decay": 0.5, "min_activation": 0.15, "max_hops": 2, "token_budget": 3000}

if __name__ == "__main__":
    print(f"Observatory standalone API — reading from {DB_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=8101)

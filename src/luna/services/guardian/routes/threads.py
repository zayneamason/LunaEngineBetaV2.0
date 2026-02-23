"""Thread routes — serve conversation JSON fixtures."""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

THREADS_DIR = Path("data/guardian/conversations")

# Thread slug → filename mapping
THREAD_MAP = {
    "amara": "amara_thread.json",
    "musoke": "musoke_thread.json",
    "wasswa": "wasswa_thread.json",
    "elder": "elder_thread.json",
}


@router.get("/threads")
async def list_threads():
    """List available threads."""
    return {
        "threads": [
            {"id": slug, "name": slug.title()}
            for slug in THREAD_MAP.keys()
        ]
    }


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get thread messages by ID."""
    filename = THREAD_MAP.get(thread_id)
    if not filename:
        raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

    path = THREADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Thread file missing: {filename}")

    with open(path) as f:
        return json.load(f)

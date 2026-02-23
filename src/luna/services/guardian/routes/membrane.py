"""Membrane routes — serve consent and scope transition fixtures."""

import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

MEMBRANE_DIR = Path("data/guardian/membrane")


@router.get("/membrane/consent")
async def get_consent_events():
    """Get consent events."""
    path = MEMBRANE_DIR / "consent_events.json"
    if not path.exists():
        return {"events": []}
    with open(path) as f:
        return json.load(f)


@router.get("/membrane/scope")
async def get_scope_transitions():
    """Get scope transitions."""
    path = MEMBRANE_DIR / "scope_transitions.json"
    if not path.exists():
        return {"transitions": []}
    with open(path) as f:
        return json.load(f)

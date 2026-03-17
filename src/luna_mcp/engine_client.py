"""
Engine Client — HTTP + DB Fallback for MCP diagnostic tools.
==============================================================

Attempts to call the live Engine API on :8000 for diagnostic data.
Falls back to direct SQLite queries if the Engine is offline.

Usage:
    client = EngineClient()
    result = await client.last_inference()
    result = await client.pipeline_state()
    result = await client.memory_probe("some query")
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ENGINE_BASE = "http://127.0.0.1:8000"


async def _http_get(path: str) -> Optional[dict]:
    """GET request to the Engine API. Returns None on failure."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ENGINE_BASE}{path}")
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug("Engine API unavailable (%s): %s", path, e)
    return None


async def _http_post(path: str, body: dict = None) -> Optional[dict]:
    """POST request to the Engine API. Returns None on failure."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{ENGINE_BASE}{path}", json=body or {})
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug("Engine API unavailable (%s): %s", path, e)
    return None


def _db_fallback_health() -> dict:
    """Fallback: read QA health from SQLite directly."""
    try:
        from luna.qa.mcp_tools import qa_get_health
        return qa_get_health()
    except Exception as e:
        return {"error": str(e), "source": "db_fallback"}


def _db_fallback_last_report() -> dict:
    """Fallback: read last QA report from SQLite directly."""
    try:
        from luna.qa.mcp_tools import qa_get_last_report
        return qa_get_last_report()
    except Exception as e:
        return {"error": str(e), "source": "db_fallback"}


class EngineClient:
    """
    Diagnostic client for MCP tools.

    Strategy: HTTP first, SQLite fallback.
    """

    async def last_inference(self) -> dict:
        """Get the last inference diagnostic picture."""
        result = await _http_get("/api/diagnostics/last-inference")
        if result:
            result["source"] = "api"
            return result

        # Fallback: assemble from DB
        report = _db_fallback_last_report()
        return {
            "available": True,
            "source": "db_fallback",
            "qa": report if not isinstance(report, dict) or "error" not in report else None,
            "route": None,
            "assembler": None,
            "prompt_length": None,
        }

    async def pipeline_state(self) -> dict:
        """Get pipeline state with QA overlay."""
        result = await _http_get("/api/diagnostics/pipeline")
        if result:
            result["source"] = "api"
            return result

        # Fallback
        try:
            from luna.qa.mcp_tools import qa_pipeline_status
            data = qa_pipeline_status()
            data["source"] = "db_fallback"
            return data
        except Exception as e:
            return {"error": str(e), "source": "db_fallback"}

    async def qa_health(self) -> dict:
        """Get QA health metrics."""
        result = await _http_get("/api/diagnostics/qa/health")
        if result:
            result["source"] = "api"
            return result

        data = _db_fallback_health()
        data["source"] = "db_fallback"
        return data

    async def memory_probe(self, query: str, budget: str = "balanced") -> dict:
        """Probe memory retrieval without generating a response."""
        result = await _http_post(
            "/api/diagnostics/trigger/memory-probe",
            {"query": query, "budget": budget},
        )
        if result:
            result["source"] = "api"
            return result

        return {
            "error": "Engine offline — memory probe requires live API",
            "source": "unavailable",
        }

    async def prompt_preview(self, message: str = "Hello", route: str = None) -> dict:
        """Preview assembled system prompt."""
        body = {"message": message}
        if route:
            body["route_override"] = route
        result = await _http_post(
            "/api/diagnostics/trigger/prompt-preview",
            body,
        )
        if result:
            result["source"] = "api"
            return result

        return {
            "error": "Engine offline — prompt preview requires live API",
            "source": "unavailable",
        }

    async def qa_sweep(self) -> dict:
        """Trigger a QA sweep (re-validate last inference)."""
        result = await _http_post("/api/diagnostics/trigger/qa-sweep")
        if result:
            result["source"] = "api"
            return result

        return {
            "error": "Engine offline — QA sweep requires live API",
            "source": "unavailable",
        }

    # ------------------------------------------------------------------
    # Aperture Control
    # ------------------------------------------------------------------

    async def aperture_get(self) -> dict:
        result = await _http_get("/api/aperture")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def aperture_set(self, mode: str = None, angle: float = None) -> dict:
        body = {}
        if mode:
            body["preset"] = mode
        if angle is not None:
            body["angle"] = angle
        result = await _http_post("/api/aperture", body)
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def aperture_reset(self) -> dict:
        result = await _http_post("/api/aperture/reset")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def aperture_lock_in_status(self) -> dict:
        result = await _http_get("/api/collections/lock-in")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    # ------------------------------------------------------------------
    # Voice Control
    # ------------------------------------------------------------------

    async def voice_start(self) -> dict:
        result = await _http_post("/voice/start")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def voice_stop(self) -> dict:
        result = await _http_post("/voice/stop")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def voice_status(self) -> dict:
        result = await _http_get("/voice/status")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def voice_speak(self, text: str) -> dict:
        result = await _http_post("/voice/speak", {"text": text})
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    # ------------------------------------------------------------------
    # LLM Provider
    # ------------------------------------------------------------------

    async def llm_providers(self) -> dict:
        result = await _http_get("/llm/providers")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def llm_switch_provider(self, provider: str) -> dict:
        result = await _http_post("/llm/provider", {"provider": provider})
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def llm_fallback_chain(self) -> dict:
        result = await _http_get("/llm/fallback-chain")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    # ------------------------------------------------------------------
    # Consciousness
    # ------------------------------------------------------------------

    async def consciousness_state(self) -> dict:
        result = await _http_get("/consciousness")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    async def extraction_trigger(self) -> dict:
        result = await _http_post("/extraction/trigger")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def extraction_stats(self) -> dict:
        result = await _http_get("/extraction/stats")
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    # ------------------------------------------------------------------
    # QA Pipeline Control (bite-09)
    # ------------------------------------------------------------------

    async def qa_node_status(self) -> dict:
        result = await _http_get("/api/diagnostics/pipeline")
        if result and "node_status" in result:
            return {"node_status": result["node_status"], "source": "api"}
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def qa_force_revalidate(self, assertion_ids: list) -> dict:
        result = await _http_post(
            "/api/diagnostics/trigger/revalidate",
            {"assertion_ids": assertion_ids},
        )
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline", "source": "unavailable"}

    async def qa_assertion_history(self, assertion_id: str, count: int = 10) -> dict:
        """Get pass/fail trend for a specific assertion from the DB."""
        try:
            from luna.qa.database import QADatabase
            db = QADatabase()
            reports = db.get_recent_reports(count * 3)  # Over-fetch to find matches
            history = []
            for r in reports:
                for a in (r.get("assertions") or []):
                    if a.get("id") == assertion_id or a.get("name") == assertion_id:
                        history.append({
                            "timestamp": r.get("timestamp"),
                            "passed": a.get("passed", False),
                            "detail": a.get("actual", ""),
                        })
                        break
                if len(history) >= count:
                    break
            return {"assertion_id": assertion_id, "history": history, "source": "db"}
        except Exception as e:
            return {"error": str(e), "source": "db_fallback"}

    async def qa_inject_test(self, message: str) -> dict:
        result = await _http_post(
            "/api/diagnostics/trigger/test-inference",
            {"message": message},
        )
        if result:
            result["source"] = "api"
            return result
        return {"error": "Engine offline — test inference requires live API", "source": "unavailable"}

    async def diagnostics_full(self) -> dict:
        """Full diagnostic summary — health + components."""
        result = await _http_get("/api/diagnostics/health")
        if result:
            result["source"] = "api"
            return result

        try:
            from luna.qa.mcp_tools import qa_diagnostics_summary
            data = qa_diagnostics_summary()
            data["source"] = "db_fallback"
            return data
        except Exception as e:
            return {"error": str(e), "source": "db_fallback"}

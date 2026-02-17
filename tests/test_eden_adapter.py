"""
Tests for Eden adapter.

Uses mocked HTTP responses — does NOT hit the real Eden API.
Run: pytest tests/test_eden_adapter.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from luna.services.eden import EdenAdapter, EdenConfig, Task, TaskStatus, Agent


@pytest.fixture
def config():
    return EdenConfig(
        api_base="https://api.eden.art",
        api_key="test-key-123",
        poll_interval_seconds=0.01,  # Fast for tests
        poll_max_attempts=5,
    )


# ── Task Tests ─────────────────────────────────────────────────

class TestTaskTypes:
    def test_task_parse(self):
        raw = {
            "_id": "task_abc123",
            "status": "completed",
            "result": [
                {"output": [{"url": "https://cdn.eden.art/img.png"}]}
            ],
        }
        task = Task.model_validate(raw)
        assert task.id == "task_abc123"
        assert task.is_complete
        assert task.first_output_url == "https://cdn.eden.art/img.png"

    def test_task_pending(self):
        raw = {"_id": "task_abc", "status": "pending", "result": []}
        task = Task.model_validate(raw)
        assert not task.is_terminal
        assert task.first_output_url is None

    def test_task_failed(self):
        raw = {"_id": "task_abc", "status": "failed", "error": "out of manna"}
        task = Task.model_validate(raw)
        assert task.is_failed
        assert task.is_terminal


class TestAgentTypes:
    def test_agent_parse(self):
        raw = {
            "_id": "agent_xyz",
            "name": "Maya",
            "description": "Vision agent",
            "tools": {"txt2img": True, "img2vid": True},
            "public": True,
        }
        agent = Agent.model_validate(raw)
        assert agent.id == "agent_xyz"
        assert agent.name == "Maya"
        assert agent.tools.get("txt2img") is True


# ── Config Tests ───────────────────────────────────────────────

class TestConfig:
    def test_default_config(self):
        cfg = EdenConfig()
        assert cfg.api_base == "https://api.eden.art"
        assert not cfg.is_configured

    def test_configured(self):
        cfg = EdenConfig(api_key="sk-test")
        assert cfg.is_configured

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("EDEN_API_KEY", "from-env")
        cfg = EdenConfig.load(config_dir=None)
        # Won't find eden.json at None path, but env var should work


# ── Adapter Integration Tests (mocked) ─────────────────────────

class TestAdapterMocked:
    """Tests using mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_create_image(self, config):
        mock_responses = [
            # create_task response
            {"task": {"_id": "t1", "status": "pending", "result": []}},
            # first poll — still processing
            {"task": {"_id": "t1", "status": "processing", "result": []}},
            # second poll — complete
            {"task": {
                "_id": "t1",
                "status": "completed",
                "result": [{"output": [{"url": "https://cdn.eden.art/out.png"}]}],
            }},
        ]

        with patch("luna.services.eden.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)

            call_count = 0
            async def mock_request(*args, **kwargs):
                nonlocal call_count
                resp = MagicMock()
                resp.status_code = 200
                resp.is_success = True
                resp.json.return_value = mock_responses[min(call_count, len(mock_responses) - 1)]
                resp.text = ""
                call_count += 1
                return resp

            mock_instance.request = mock_request
            MockClient.return_value = mock_instance

            async with EdenAdapter(config) as adapter:
                task = await adapter.create_image("test prompt")
                assert task.is_complete
                assert task.first_output_url == "https://cdn.eden.art/out.png"

    @pytest.mark.asyncio
    async def test_health_check_passes(self, config):
        with patch("luna.services.eden.client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)

            async def mock_request(*args, **kwargs):
                resp = MagicMock()
                resp.status_code = 200
                resp.is_success = True
                resp.json.return_value = {"docs": []}
                resp.text = ""
                return resp

            mock_instance.request = mock_request
            MockClient.return_value = mock_instance

            async with EdenAdapter(config) as adapter:
                assert await adapter.health_check()

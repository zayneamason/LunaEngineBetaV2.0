"""
Tests for Eden MCP wrapper tools (Phase 2).

Tests the luna_mcp.tools.eden module that bridges
Eden adapter → MCP tool layer.
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Module under test ──────────────────────────────────────────
from luna_mcp.tools import eden


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_adapter():
    """Reset the module-level adapter between tests."""
    eden._adapter = None
    eden._adapter_initialized = False
    yield
    eden._adapter = None
    eden._adapter_initialized = False


@pytest.fixture
def mock_adapter():
    """Create a mock EdenAdapter."""
    adapter = AsyncMock()
    adapter.config = MagicMock()
    adapter.config.api_base = "https://api.eden.art"
    adapter.config.api_key = "test-key"
    eden._adapter = adapter
    eden._adapter_initialized = True
    return adapter


# ── Tests: Availability ────────────────────────────────────────

class TestAvailability:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_unavailable(self):
        with patch.dict(os.environ, {"EDEN_API_KEY": ""}, clear=False):
            result = json.loads(await eden.eden_health())
            assert result["error"] == "Eden unavailable"

    @pytest.mark.asyncio
    async def test_placeholder_key_returns_unavailable(self):
        with patch.dict(os.environ, {"EDEN_API_KEY": "your_key_here"}, clear=False):
            result = json.loads(await eden.eden_health())
            assert result["error"] == "Eden unavailable"


# ── Tests: Health ──────────────────────────────────────────────

class TestHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, mock_adapter):
        mock_adapter.health_check = AsyncMock(return_value=True)

        result = json.loads(await eden.eden_health())
        assert result["status"] == "ok"
        assert result["api_base"] == "https://api.eden.art"
        assert result["has_api_key"] is True

    @pytest.mark.asyncio
    async def test_health_error(self, mock_adapter):
        mock_adapter.health_check = AsyncMock(side_effect=Exception("connection refused"))

        result = json.loads(await eden.eden_health())
        assert result["status"] == "error"
        assert "connection refused" in result["error"]


# ── Tests: Create Image ───────────────────────────────────────

class TestCreateImage:
    @pytest.mark.asyncio
    async def test_create_image_success(self, mock_adapter):
        mock_status = MagicMock()
        mock_status.value = "completed"

        mock_task = MagicMock()
        mock_task.id = "t123"
        mock_task.status = mock_status
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.first_output_url = "https://cdn.eden.art/img.jpg"
        mock_task.error = None

        mock_adapter.create_image = AsyncMock(return_value=mock_task)

        result = json.loads(await eden.eden_create_image("a sunset"))
        assert result["task_id"] == "t123"
        assert result["status"] == "completed"
        assert result["url"] == "https://cdn.eden.art/img.jpg"
        assert result["is_complete"] is True

    @pytest.mark.asyncio
    async def test_create_image_with_dimensions(self, mock_adapter):
        mock_status = MagicMock()
        mock_status.value = "completed"

        mock_task = MagicMock()
        mock_task.id = "t456"
        mock_task.status = mock_status
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.first_output_url = "https://cdn.eden.art/img2.jpg"
        mock_task.error = None

        mock_adapter.create_image = AsyncMock(return_value=mock_task)

        await eden.eden_create_image("a mountain", width=512, height=512)

        # Verify extra_args were passed
        call_kwargs = mock_adapter.create_image.call_args
        assert call_kwargs.kwargs["extra_args"]["width"] == 512
        assert call_kwargs.kwargs["extra_args"]["height"] == 512

    @pytest.mark.asyncio
    async def test_create_image_not_available(self):
        with patch.dict(os.environ, {"EDEN_API_KEY": ""}, clear=False):
            result = json.loads(await eden.eden_create_image("anything"))
            assert result["error"] == "Eden unavailable"

    @pytest.mark.asyncio
    async def test_create_image_exception(self, mock_adapter):
        mock_adapter.create_image = AsyncMock(side_effect=Exception("timeout"))

        result = json.loads(await eden.eden_create_image("test"))
        assert "timeout" in result["error"]


# ── Tests: Create Video ───────────────────────────────────────

class TestCreateVideo:
    @pytest.mark.asyncio
    async def test_create_video_success(self, mock_adapter):
        mock_status = MagicMock()
        mock_status.value = "completed"

        mock_task = MagicMock()
        mock_task.id = "v789"
        mock_task.status = mock_status
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.first_output_url = "https://cdn.eden.art/vid.mp4"
        mock_task.error = None

        mock_adapter.create_video = AsyncMock(return_value=mock_task)

        result = json.loads(await eden.eden_create_video("a timelapse"))
        assert result["task_id"] == "v789"
        assert result["url"] == "https://cdn.eden.art/vid.mp4"


# ── Tests: Chat ───────────────────────────────────────────────

class TestChat:
    @pytest.mark.asyncio
    async def test_chat_no_agent_id(self, mock_adapter):
        with patch.dict(os.environ, {"EDEN_AGENT_ID": "optional_default_agent"}, clear=False):
            result = json.loads(await eden.eden_chat("hello"))
            assert "No agent_id" in result["error"]

    @pytest.mark.asyncio
    async def test_chat_new_session(self, mock_adapter):
        mock_msg = MagicMock()
        mock_msg.role.value = "assistant"
        mock_msg.content = "Hello! I'm an Eden agent."
        mock_msg.tool_calls = []

        mock_session = MagicMock()
        mock_session.id = "sess-1"
        mock_session.messages = [mock_msg]

        mock_adapter.create_session = AsyncMock(return_value=mock_session)

        result = json.loads(await eden.eden_chat("hello", agent_id="agent-abc"))
        assert result["session_id"] == "sess-1"
        assert result["message_count"] == 1
        assert result["messages"][0]["content"] == "Hello! I'm an Eden agent."

    @pytest.mark.asyncio
    async def test_chat_existing_session(self, mock_adapter):
        mock_msg = MagicMock()
        mock_msg.role.value = "assistant"
        mock_msg.content = "Sure, here you go."
        mock_msg.tool_calls = []

        mock_adapter.send_message = AsyncMock(return_value=[mock_msg])

        result = json.loads(await eden.eden_chat(
            "continue", agent_id="agent-abc", session_id="sess-existing"
        ))
        assert result["session_id"] == "sess-existing"
        assert result["messages"][0]["content"] == "Sure, here you go."


# ── Tests: List Agents ────────────────────────────────────────

class TestListAgents:
    @pytest.mark.asyncio
    async def test_list_agents(self, mock_adapter):
        mock_agent = MagicMock()
        mock_agent.id = "a1"
        mock_agent.name = "Art Generator"
        mock_agent.description = "Creates art"
        mock_agent.tools = {"txt2img": True}
        mock_agent.public = True

        mock_adapter.list_agents = AsyncMock(return_value=[mock_agent])

        result = json.loads(await eden.eden_list_agents())
        assert result["count"] == 1
        assert result["agents"][0]["name"] == "Art Generator"


# ── Tests: Format Result ──────────────────────────────────────

class TestFormatResult:
    def test_string_passthrough(self):
        assert eden._format_result("hello") == "hello"

    def test_dict_to_json(self):
        result = eden._format_result({"key": "value"})
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_not_available(self):
        result = json.loads(eden._not_available("test reason"))
        assert result["error"] == "Eden unavailable"
        assert "test reason" in result["message"]

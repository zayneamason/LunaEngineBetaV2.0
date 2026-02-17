"""
Tests for Eden tools and Eden bridge actor.

Uses mocked adapters — does NOT hit the real Eden API.
Run: pytest tests/test_eden_tools.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from luna.services.eden import EdenConfig, Task, TaskStatus
from luna.tools.eden_tools import (
    eden_create_image,
    eden_create_video,
    eden_chat,
    eden_list_agents,
    eden_health,
    set_eden_adapter,
    get_eden_adapter,
    register_eden_tools,
    ALL_EDEN_TOOLS,
    _update_consciousness_on_error,
    _update_consciousness_on_success,
)
from luna.tools.registry import ToolRegistry
from luna.actors.eden_bridge import EdenBridgeActor
from luna.actors.base import Message


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def mock_adapter():
    """Create a mock EdenAdapter."""
    adapter = AsyncMock()
    adapter.health_check = AsyncMock(return_value=True)
    adapter.list_agents = AsyncMock(return_value=[])
    return adapter


@pytest.fixture
def mock_engine():
    """Create a mock LunaEngine with consciousness."""
    engine = MagicMock()
    engine.consciousness = MagicMock()
    engine.consciousness.coherence = 1.0
    engine.consciousness.focus_on = MagicMock()
    engine.get_actor = MagicMock(return_value=None)
    engine.record_conversation_turn = AsyncMock()
    return engine


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global state between tests."""
    import luna.tools.eden_tools as et
    original_adapter = et._eden_adapter
    original_engine = et._engine
    yield
    et._eden_adapter = original_adapter
    et._engine = original_engine


# ── Tool Registration Tests ────────────────────────────────────

class TestToolRegistration:
    def test_all_eden_tools_defined(self):
        assert len(ALL_EDEN_TOOLS) == 5

    def test_tool_names(self):
        names = {t.name for t in ALL_EDEN_TOOLS}
        assert "eden_create_image" in names
        assert "eden_create_video" in names
        assert "eden_chat" in names
        assert "eden_list_agents" in names
        assert "eden_health" in names

    def test_register_eden_tools(self):
        registry = ToolRegistry()
        register_eden_tools(registry)
        assert len(registry.list_tools()) == 5
        assert registry.get("eden_create_image") is not None

    def test_set_get_adapter(self, mock_adapter):
        set_eden_adapter(mock_adapter)
        assert get_eden_adapter() is mock_adapter


# ── Tool Implementation Tests ──────────────────────────────────

class TestCreateImage:
    @pytest.mark.asyncio
    async def test_not_initialized(self):
        import luna.tools.eden_tools as et
        et._eden_adapter = None
        with pytest.raises(RuntimeError, match="Eden adapter not initialized"):
            await eden_create_image("a sunset")

    @pytest.mark.asyncio
    async def test_create_image_success(self, mock_adapter):
        # Set up mock task — use MagicMock for status to avoid enum .value issues
        mock_status = MagicMock()
        mock_status.value = "completed"

        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_task.status = mock_status
        mock_task.first_output_url = "https://cdn.eden.art/img.png"
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.error = None

        mock_adapter.create_image = AsyncMock(return_value=mock_task)
        set_eden_adapter(mock_adapter)

        result = await eden_create_image("a sunset")
        assert result["task_id"] == "t1"
        assert result["url"] == "https://cdn.eden.art/img.png"
        assert result["is_complete"] is True

    @pytest.mark.asyncio
    async def test_create_image_updates_consciousness(self, mock_adapter, mock_engine):
        mock_status = MagicMock()
        mock_status.value = "completed"

        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_task.status = mock_status
        mock_task.first_output_url = "https://cdn.eden.art/img.png"
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.error = None

        mock_adapter.create_image = AsyncMock(return_value=mock_task)
        set_eden_adapter(mock_adapter, engine=mock_engine)

        await eden_create_image("a sunset")
        mock_engine.consciousness.focus_on.assert_called()


class TestCreateVideo:
    @pytest.mark.asyncio
    async def test_create_video_success(self, mock_adapter):
        mock_status = MagicMock()
        mock_status.value = "completed"

        mock_task = MagicMock()
        mock_task.id = "v1"
        mock_task.status = mock_status
        mock_task.first_output_url = "https://cdn.eden.art/vid.mp4"
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.error = None

        mock_adapter.create_video = AsyncMock(return_value=mock_task)
        set_eden_adapter(mock_adapter)

        result = await eden_create_video("a timelapse")
        assert result["task_id"] == "v1"
        assert result["url"] == "https://cdn.eden.art/vid.mp4"


class TestChat:
    @pytest.mark.asyncio
    async def test_chat_creates_session(self, mock_adapter):
        mock_adapter.create_session = AsyncMock(return_value="sess_123")
        mock_adapter.send_message = AsyncMock(return_value="sess_123")

        mock_session = MagicMock()
        mock_msg = MagicMock()
        mock_msg.role.value = "assistant"
        mock_msg.content = "Hello! I'm an Eden agent."
        mock_session.messages = [mock_msg]
        mock_adapter.get_session = AsyncMock(return_value=mock_session)

        set_eden_adapter(mock_adapter)

        result = await eden_chat("agent_abc", "hi there")
        assert result["session_id"] == "sess_123"
        assert result["response"] == "Hello! I'm an Eden agent."

        mock_adapter.create_session.assert_called_once_with(["agent_abc"])

    @pytest.mark.asyncio
    async def test_chat_reuses_session(self, mock_adapter):
        mock_adapter.send_message = AsyncMock(return_value="existing_sess")

        mock_session = MagicMock()
        mock_session.messages = []
        mock_adapter.get_session = AsyncMock(return_value=mock_session)

        set_eden_adapter(mock_adapter)

        result = await eden_chat("agent_abc", "hello", session_id="existing_sess")
        assert result["session_id"] == "existing_sess"
        # Should NOT have called create_session
        mock_adapter.create_session.assert_not_called()


class TestListAgents:
    @pytest.mark.asyncio
    async def test_list_agents(self, mock_adapter):
        mock_agent = MagicMock()
        mock_agent.id = "a1"
        mock_agent.name = "Maya"
        mock_agent.description = "Vision agent"
        mock_agent.tools = {"txt2img": True}

        mock_adapter.list_agents = AsyncMock(return_value=[mock_agent])
        set_eden_adapter(mock_adapter)

        result = await eden_list_agents()
        assert result["count"] == 1
        assert result["agents"][0]["name"] == "Maya"


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_ok(self, mock_adapter):
        mock_adapter.health_check = AsyncMock(return_value=True)
        set_eden_adapter(mock_adapter)

        result = await eden_health()
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_no_adapter(self):
        import luna.tools.eden_tools as et
        et._eden_adapter = None

        result = await eden_health()
        assert result["healthy"] is False


# ── Consciousness Update Tests ─────────────────────────────────

class TestConsciousnessUpdates:
    def test_error_decreases_coherence(self, mock_engine):
        import luna.tools.eden_tools as et
        et._engine = mock_engine
        mock_engine.consciousness.coherence = 1.0

        _update_consciousness_on_error(RuntimeError("timeout"))
        assert mock_engine.consciousness.coherence == 0.85

    def test_success_increases_coherence(self, mock_engine):
        import luna.tools.eden_tools as et
        et._engine = mock_engine
        mock_engine.consciousness.coherence = 0.8

        _update_consciousness_on_success("create_image")
        assert mock_engine.consciousness.coherence == pytest.approx(0.85)


# ── Eden Bridge Actor Tests ────────────────────────────────────

class TestEdenBridgeActor:
    def test_actor_name(self):
        bridge = EdenBridgeActor()
        assert bridge.name == "eden_bridge"

    def test_not_ready_without_engine(self):
        bridge = EdenBridgeActor()
        assert not bridge.is_ready

    @pytest.mark.asyncio
    async def test_handle_session_closed(self):
        bridge = EdenBridgeActor()
        bridge._active_sessions["sess_1"] = "agent_1"

        msg = Message(type="eden_session_closed", payload={"session_id": "sess_1"})
        await bridge.handle(msg)

        assert "sess_1" not in bridge._active_sessions

    @pytest.mark.asyncio
    async def test_handle_unknown_message(self):
        bridge = EdenBridgeActor()
        msg = Message(type="unknown_type", payload={})
        # Should not raise
        await bridge.handle(msg)

    @pytest.mark.asyncio
    async def test_snapshot(self):
        bridge = EdenBridgeActor()
        bridge._active_sessions["s1"] = "a1"

        snap = await bridge.snapshot()
        assert snap["name"] == "eden_bridge"
        assert snap["active_sessions"]["s1"] == "a1"

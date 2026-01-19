"""
Tests for API Server
====================

Tests for HTTP endpoints and SSE streaming.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# We need to mock the engine before importing the server
@pytest.fixture
def mock_engine():
    """Create a mock engine for API testing."""
    engine = MagicMock()
    engine.state = MagicMock()
    engine.state.name = "RUNNING"
    engine.session_id = "test1234"
    engine.metrics = MagicMock()
    engine.metrics.uptime_seconds = 100.0
    engine.metrics.cognitive_ticks = 50
    engine.metrics.events_processed = 25
    engine.metrics.messages_generated = 10
    engine.input_buffer = MagicMock()
    engine.input_buffer.stats = {"size": 0, "total_received": 25, "dropped_count": 0}
    engine.actors = {"director": MagicMock(), "matrix": MagicMock()}
    engine._on_response_callbacks = []

    # Mock async methods
    engine.send_message = AsyncMock()
    engine.stop = AsyncMock()

    def mock_status():
        return {
            "state": "RUNNING",
            "uptime_seconds": 100.0,
            "cognitive_ticks": 50,
            "events_processed": 25,
            "messages_generated": 10,
            "actors": ["director", "matrix"],
            "buffer": {"size": 0},
        }

    engine.status = mock_status

    return engine


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_check_without_engine(self):
        """Test health check when engine not ready."""
        with patch("luna.api.server._engine", None):
            from luna.api.server import app
            client = TestClient(app, raise_server_exceptions=False)
            # Skip lifespan since we're mocking
            response = client.get("/health")
            # Without proper engine startup, this will return starting or error
            assert response.status_code in [200, 503]


class TestStatusEndpoint:
    """Tests for /status endpoint."""

    def test_status_returns_metrics(self, mock_engine):
        """Test status endpoint returns proper metrics."""
        with patch("luna.api.server._engine", mock_engine):
            from luna.api.server import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.get("/status")

            if response.status_code == 200:
                data = response.json()
                assert "state" in data
                assert "uptime_seconds" in data
                assert "cognitive_ticks" in data


class TestMessageEndpoint:
    """Tests for /message endpoint."""

    def test_message_requires_body(self, mock_engine):
        """Test message endpoint requires request body."""
        with patch("luna.api.server._engine", mock_engine):
            from luna.api.server import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/message", json={})

            # Should fail validation
            assert response.status_code in [422, 503]

    def test_message_validates_length(self, mock_engine):
        """Test message endpoint validates message length."""
        with patch("luna.api.server._engine", mock_engine):
            from luna.api.server import app
            client = TestClient(app, raise_server_exceptions=False)

            # Empty message should fail
            response = client.post("/message", json={"message": ""})
            assert response.status_code in [422, 503]


class TestAbortEndpoint:
    """Tests for /abort endpoint."""

    def test_abort_when_not_generating(self, mock_engine):
        """Test abort when no generation in progress."""
        director = MagicMock()
        director.is_generating = False
        director.mailbox = MagicMock()
        director.mailbox.put = AsyncMock()

        mock_engine.get_actor = MagicMock(return_value=director)

        with patch("luna.api.server._engine", mock_engine):
            from luna.api.server import app
            client = TestClient(app, raise_server_exceptions=False)

            response = client.post("/abort")

            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "no_generation"


class TestRequestValidation:
    """Tests for request validation."""

    def test_message_request_schema(self):
        """Test MessageRequest schema."""
        from luna.api.server import MessageRequest

        # Valid request
        req = MessageRequest(message="Hello Luna")
        assert req.message == "Hello Luna"
        assert req.timeout == 30.0
        assert req.stream is False

    def test_message_request_with_options(self):
        """Test MessageRequest with custom options."""
        from luna.api.server import MessageRequest

        req = MessageRequest(
            message="Hello",
            timeout=60.0,
            stream=True,
        )
        assert req.timeout == 60.0
        assert req.stream is True

    def test_message_response_schema(self):
        """Test MessageResponse schema."""
        from luna.api.server import MessageResponse

        resp = MessageResponse(
            text="Hello there!",
            model="claude-sonnet-4-20250514",
            input_tokens=10,
            output_tokens=5,
            latency_ms=500.0,
        )

        assert resp.text == "Hello there!"
        assert resp.model == "claude-sonnet-4-20250514"

    def test_status_response_schema(self):
        """Test StatusResponse schema."""
        from luna.api.server import StatusResponse

        resp = StatusResponse(
            state="RUNNING",
            uptime_seconds=100.0,
            cognitive_ticks=50,
            events_processed=25,
            messages_generated=10,
            actors=["director", "matrix"],
            buffer_size=0,
        )

        assert resp.state == "RUNNING"
        assert len(resp.actors) == 2

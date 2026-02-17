# HANDOFF: Eden.art Adapter — Phase 1 Foundation

**Date:** 2026-02-09
**Author:** Architect (The Dude)
**For:** Claude Code
**Scope:** Build the Eden API adapter as a service in the Luna Engine
**Mode:** BUILD — new files, no existing code modified

---

## PROJECT ROOT

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

---

## CONTEXT

Eden.art is a creative AI platform (image/video generation, autonomous agents, custom model training). It's the Service Layer in Luna's three-tier architecture (Luna → Eclissi → Eden). See `Eden_Project/DIAGRAMS_Architecture_Options.md` for full architecture context.

A working TypeScript reference implementation exists at `Eden_Project/hello-eden/src/lib/eden.ts` — use it as the API contract reference. The Python adapter should mirror its capabilities but follow Luna Engine conventions.

**Dependencies already in `pyproject.toml`:** `httpx`, `pydantic`, `aiosqlite`. No new deps needed.

**Eden API base:** `https://api.eden.art`
**Auth:** `X-Api-Key` header
**API key env var:** `EDEN_API_KEY` (add to `.env`)

---

## OVERVIEW

| Phase | What | Files |
|-------|------|-------|
| 1 | Pydantic types for Eden API | `src/luna/services/eden/types.py` |
| 2 | Config + connection management | `src/luna/services/eden/config.py` |
| 3 | Async HTTP client | `src/luna/services/eden/client.py` |
| 4 | High-level adapter | `src/luna/services/eden/adapter.py` |
| 5 | Package init | `src/luna/services/eden/__init__.py` |
| 6 | Tests | `tests/test_eden_adapter.py` |
| 7 | Config file | `config/eden.json` |

**Execute in order. Each phase builds on the previous.**

---

## PHASE 1: Types (`src/luna/services/eden/types.py`)

Pydantic models for all Eden API request/response shapes. Reference: `Eden_Project/hello-eden/src/lib/eden.ts` for the TypeScript interfaces.

```python
"""
Eden.art API type definitions.

Pydantic models for Eden REST API request/response payloads.
Reference: Eden_Project/hello-eden/src/lib/eden.ts
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    EDEN = "eden"


# ── Media / Creation ──────────────────────────────────────────

class MediaAttributes(BaseModel):
    mime_type: Optional[str] = Field(None, alias="mimeType")
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[float] = Field(None, alias="aspectRatio")

    model_config = {"populate_by_name": True}


class TaskOutput(BaseModel):
    """Single output from a completed task."""
    url: Optional[str] = None
    uri: Optional[str] = None
    filename: Optional[str] = None
    media_attributes: Optional[MediaAttributes] = Field(None, alias="mediaAttributes")

    model_config = {"populate_by_name": True}

    @property
    def resolved_url(self) -> Optional[str]:
        return self.url or self.uri


class TaskResult(BaseModel):
    """Result block from task polling."""
    output: list[TaskOutput] = Field(default_factory=list)


# ── Tasks ─────────────────────────────────────────────────────

class TaskCreateRequest(BaseModel):
    """POST /v2/tasks/create"""
    tool: str = "create"
    args: dict[str, Any] = Field(default_factory=dict)
    make_public: bool = Field(False, alias="makePublic")

    model_config = {"populate_by_name": True}


class Task(BaseModel):
    """Task response from Eden API."""
    id: str = Field(alias="_id")
    status: TaskStatus = TaskStatus.PENDING
    result: list[TaskResult] = Field(default_factory=list)
    error: Optional[str] = None

    model_config = {"populate_by_name": True}

    @property
    def is_complete(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == TaskStatus.FAILED

    @property
    def is_terminal(self) -> bool:
        return self.is_complete or self.is_failed

    @property
    def first_output_url(self) -> Optional[str]:
        """Convenience: URL of the first output, if any."""
        if self.result and self.result[0].output:
            return self.result[0].output[0].resolved_url
        return None


# ── Agents ────────────────────────────────────────────────────

class AgentModel(BaseModel):
    """LoRA model attached to an agent."""
    lora: str
    use_when: Optional[str] = None


class AgentSuggestion(BaseModel):
    label: str
    prompt: str


class Agent(BaseModel):
    """Eden agent definition."""
    id: str = Field(alias="_id")
    name: str
    description: Optional[str] = None
    image: Optional[str] = None
    persona: Optional[str] = None
    greeting: Optional[str] = None
    models: list[AgentModel] = Field(default_factory=list)
    suggestions: list[AgentSuggestion] = Field(default_factory=list)
    tools: dict[str, bool] = Field(default_factory=dict)
    public: bool = False
    owner: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


# ── Sessions ──────────────────────────────────────────────────

class SessionBudget(BaseModel):
    manna_budget: Optional[float] = None
    token_budget: Optional[int] = None
    turn_budget: Optional[int] = None
    tokens_spent: Optional[int] = None
    manna_spent: Optional[float] = None
    turns_spent: Optional[int] = None


class ToolCall(BaseModel):
    """Tool call within a session message."""
    id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = None
    result: Optional[list[dict[str, Any]]] = None
    error: Optional[Any] = None


class SessionMessage(BaseModel):
    """Single message in a session."""
    id: str = Field(alias="_id")
    role: MessageRole
    content: str = ""
    agent_id: Optional[str] = None
    thinking: Optional[str] = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    created_at: Optional[datetime] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class SessionCreateRequest(BaseModel):
    """POST /v2/sessions — create new session."""
    agent_ids: list[str]
    content: Optional[str] = None
    scenario: Optional[str] = None
    budget: Optional[SessionBudget] = None
    title: Optional[str] = None


class SessionMessageRequest(BaseModel):
    """POST /v2/sessions — send message to existing session."""
    session_id: str
    content: str
    attachments: Optional[list[str]] = None
    agent_ids: Optional[list[str]] = None


class Session(BaseModel):
    """Full session state."""
    id: str = Field(alias="_id")
    agent_ids: list[str] = Field(default_factory=list)
    messages: list[SessionMessage] = Field(default_factory=list)
    budget: Optional[SessionBudget] = None
    title: Optional[str] = None
    status: str = "active"
    created_at: Optional[datetime] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


# ── Creations (Gallery) ──────────────────────────────────────

class Creation(BaseModel):
    """A creation in Eden's gallery."""
    id: str = Field(alias="_id")
    uri: Optional[str] = None
    url: Optional[str] = None
    thumbnail: Optional[str] = None
    media_attributes: Optional[MediaAttributes] = Field(None, alias="mediaAttributes")
    prompt: Optional[str] = None
    tool: Optional[str] = None
    like_count: int = Field(0, alias="likeCount")
    created_at: Optional[datetime] = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}

    @property
    def resolved_url(self) -> Optional[str]:
        return self.url or self.uri


class CreationsPage(BaseModel):
    """Paginated creations response."""
    docs: list[Creation] = Field(default_factory=list)
    next_cursor: Optional[str] = Field(None, alias="nextCursor")
    has_more: bool = False

    model_config = {"populate_by_name": True}
```

---

## PHASE 2: Config (`src/luna/services/eden/config.py`)

```python
"""
Eden service configuration.

Loaded from config/eden.json with env var overrides.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class EdenConfig(BaseModel):
    """Eden API connection configuration."""
    api_base: str = "https://api.eden.art"
    api_key: Optional[str] = None
    default_agent_id: Optional[str] = None

    # Task polling
    poll_interval_seconds: float = 3.0
    poll_max_attempts: int = 60  # 3 min max wait
    poll_backoff_factor: float = 1.2

    # Session defaults
    default_manna_budget: float = 100.0
    default_turn_budget: int = 50

    # HTTP
    timeout_seconds: float = 30.0
    max_retries: int = 3

    @classmethod
    def load(cls, config_dir: Optional[Path] = None) -> "EdenConfig":
        """Load config from eden.json with env var overrides."""
        config_dir = config_dir or Path(__file__).parents[4] / "config"
        config_path = config_dir / "eden.json"

        data = {}
        if config_path.exists():
            with open(config_path) as f:
                data = json.load(f)

        # Env var overrides (highest priority)
        if os.getenv("EDEN_API_BASE"):
            data["api_base"] = os.getenv("EDEN_API_BASE")
        if os.getenv("EDEN_API_KEY"):
            data["api_key"] = os.getenv("EDEN_API_KEY")
        if os.getenv("EDEN_AGENT_ID"):
            data["default_agent_id"] = os.getenv("EDEN_AGENT_ID")

        return cls(**data)

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None
```

---

## PHASE 3: HTTP Client (`src/luna/services/eden/client.py`)

The low-level async HTTP client. Handles auth, retries, error mapping.

```python
"""
Eden HTTP client.

Async httpx client with auth, retry, and error handling.
All Eden API calls go through this layer.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from .config import EdenConfig

logger = logging.getLogger("luna.eden")


class EdenAPIError(Exception):
    """Eden API returned an error."""
    def __init__(self, status_code: int, message: str, response_body: Optional[str] = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Eden API {status_code}: {message}")


class EdenClient:
    """
    Low-level async HTTP client for Eden API.

    Usage:
        config = EdenConfig.load()
        async with EdenClient(config) as client:
            data = await client.post("/v2/tasks/create", json=payload)
    """

    def __init__(self, config: EdenConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "EdenClient":
        self._client = httpx.AsyncClient(
            base_url=self.config.api_base,
            headers={
                "Content-Type": "application/json",
                **({"X-Api-Key": self.config.api_key} if self.config.api_key else {}),
            },
            timeout=httpx.Timeout(self.config.timeout_seconds),
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("EdenClient not initialized. Use 'async with EdenClient(config) as client:'")
        return self._client

    async def get(self, path: str, params: Optional[dict] = None) -> dict[str, Any]:
        """GET request with retry."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Optional[dict] = None) -> dict[str, Any]:
        """POST request with retry."""
        return await self._request("POST", path, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                response = await self.client.request(
                    method, path, json=json, params=params
                )

                if response.status_code == 429:
                    # Rate limited — back off and retry
                    wait = (attempt + 1) * 2
                    logger.warning(f"Eden rate limited, waiting {wait}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500:
                    # Server error — retry
                    wait = (attempt + 1) * self.config.poll_backoff_factor
                    logger.warning(f"Eden server error {response.status_code}, retrying in {wait}s")
                    await asyncio.sleep(wait)
                    continue

                if not response.is_success:
                    body = response.text
                    raise EdenAPIError(response.status_code, body, body)

                return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(f"Eden request timeout (attempt {attempt + 1})")
                await asyncio.sleep((attempt + 1) * 2)
            except httpx.ConnectError as e:
                last_error = e
                logger.warning(f"Eden connection error (attempt {attempt + 1})")
                await asyncio.sleep((attempt + 1) * 2)

        raise EdenAPIError(0, f"Failed after {self.config.max_retries} attempts: {last_error}")
```

---

## PHASE 4: Adapter (`src/luna/services/eden/adapter.py`)

High-level operations. This is what other Luna components import.

```python
"""
Eden adapter — high-level interface for Luna Engine.

Provides create_image, create_video, chat_with_agent, etc.
Handles task lifecycle (create → poll → result) transparently.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .client import EdenClient, EdenAPIError
from .config import EdenConfig
from .types import (
    Agent,
    Creation,
    CreationsPage,
    MediaType,
    Session,
    SessionCreateRequest,
    Task,
    TaskCreateRequest,
    TaskStatus,
)

logger = logging.getLogger("luna.eden")


class EdenAdapter:
    """
    High-level Eden API adapter.

    Usage:
        config = EdenConfig.load()
        adapter = EdenAdapter(config)

        async with adapter:
            result = await adapter.create_image("a cyberpunk cityscape")
            print(result.first_output_url)
    """

    def __init__(self, config: Optional[EdenConfig] = None):
        self.config = config or EdenConfig.load()
        self._client: Optional[EdenClient] = None

    async def __aenter__(self) -> "EdenAdapter":
        self._client = EdenClient(self.config)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.__aexit__(*exc)
            self._client = None

    @property
    def client(self) -> EdenClient:
        if self._client is None:
            raise RuntimeError("EdenAdapter not initialized. Use 'async with'.")
        return self._client

    # ── Task Operations ────────────────────────────────────────

    async def create_task(
        self,
        prompt: str,
        media_type: MediaType = MediaType.IMAGE,
        tool: str = "create",
        public: bool = False,
        extra_args: Optional[dict[str, Any]] = None,
    ) -> Task:
        """
        Create a generation task and return immediately.
        Use poll_task() or wait_for_task() to get the result.
        """
        args: dict[str, Any] = {"prompt": prompt}
        if media_type == MediaType.VIDEO:
            args["output"] = "video"
        if extra_args:
            args.update(extra_args)

        request = TaskCreateRequest(tool=tool, args=args, makePublic=public)
        data = await self.client.post(
            "/v2/tasks/create",
            json=request.model_dump(by_alias=True),
        )

        task_data = data.get("task", data)
        return Task.model_validate(task_data)

    async def poll_task(self, task_id: str) -> Task:
        """Poll a task once and return current state."""
        data = await self.client.get(f"/v2/tasks/{task_id}")
        task_data = data.get("task", data)
        return Task.model_validate(task_data)

    async def wait_for_task(
        self,
        task_id: str,
        poll_interval: Optional[float] = None,
        max_attempts: Optional[int] = None,
    ) -> Task:
        """
        Poll a task until completion or failure.
        Returns the final Task state.
        Raises EdenAPIError if max attempts exceeded.
        """
        interval = poll_interval or self.config.poll_interval_seconds
        attempts = max_attempts or self.config.poll_max_attempts

        for attempt in range(attempts):
            task = await self.poll_task(task_id)

            if task.is_terminal:
                if task.is_failed:
                    logger.warning(f"Eden task {task_id} failed: {task.error}")
                else:
                    logger.info(f"Eden task {task_id} completed")
                return task

            # Back off slightly over time
            wait = interval * (self.config.poll_backoff_factor ** min(attempt, 10))
            await asyncio.sleep(wait)

        raise EdenAPIError(0, f"Task {task_id} did not complete after {attempts} polls")

    # ── Convenience Methods ────────────────────────────────────

    async def create_image(
        self,
        prompt: str,
        wait: bool = True,
        **kwargs,
    ) -> Task:
        """Create an image. If wait=True, blocks until complete."""
        task = await self.create_task(prompt, MediaType.IMAGE, **kwargs)
        if wait:
            return await self.wait_for_task(task.id)
        return task

    async def create_video(
        self,
        prompt: str,
        wait: bool = True,
        **kwargs,
    ) -> Task:
        """Create a video. If wait=True, blocks until complete."""
        task = await self.create_task(prompt, MediaType.VIDEO, **kwargs)
        if wait:
            return await self.wait_for_task(task.id)
        return task

    # ── Agent Operations ───────────────────────────────────────

    async def list_agents(self) -> list[Agent]:
        """List available Eden agents."""
        data = await self.client.get("/v2/agents")
        docs = data.get("docs", [])
        return [Agent.model_validate(a) for a in docs]

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get a specific agent by ID."""
        try:
            data = await self.client.get(f"/v2/agents/{agent_id}")
            agent_data = data.get("agent", data)
            return Agent.model_validate(agent_data)
        except EdenAPIError as e:
            if e.status_code == 404:
                return None
            raise

    # ── Session Operations ─────────────────────────────────────

    async def create_session(
        self,
        agent_ids: list[str],
        content: Optional[str] = None,
        title: Optional[str] = None,
        manna_budget: Optional[float] = None,
    ) -> str:
        """
        Create a new chat session with one or more agents.
        Returns session_id.
        """
        from .types import SessionBudget

        budget = SessionBudget(
            manna_budget=manna_budget or self.config.default_manna_budget,
            turn_budget=self.config.default_turn_budget,
        )

        request = SessionCreateRequest(
            agent_ids=agent_ids,
            content=content,
            title=title,
            budget=budget,
        )

        data = await self.client.post(
            "/v2/sessions",
            json=request.model_dump(exclude_none=True),
        )
        return data["session_id"]

    async def send_message(
        self,
        session_id: str,
        content: str,
        attachments: Optional[list[str]] = None,
    ) -> str:
        """Send a message to an existing session. Returns session_id."""
        payload: dict[str, Any] = {
            "session_id": session_id,
            "content": content,
        }
        if attachments:
            payload["attachments"] = attachments

        data = await self.client.post("/v2/sessions", json=payload)
        return data["session_id"]

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get full session state including messages."""
        try:
            data = await self.client.get(f"/v2/sessions/{session_id}")
            session_data = data.get("session", data)
            return Session.model_validate(session_data)
        except EdenAPIError as e:
            if e.status_code == 404:
                return None
            raise

    # ── Creation Gallery ───────────────────────────────────────

    async def get_creations(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
        media_type: Optional[MediaType] = None,
    ) -> CreationsPage:
        """Fetch creations from the gallery."""
        params: dict[str, Any] = {"limit": str(limit)}
        if cursor:
            params["cursor"] = cursor
        if media_type:
            params["filter"] = f"output_type;{media_type.value}"

        data = await self.client.get("/v2/feed-cursor/creations", params=params)
        return CreationsPage.model_validate(data)

    # ── Health Check ───────────────────────────────────────────

    async def health_check(self) -> bool:
        """Verify Eden API is reachable and key is valid."""
        try:
            await self.client.get("/v2/agents")
            return True
        except Exception as e:
            logger.warning(f"Eden health check failed: {e}")
            return False
```

---

## PHASE 5: Package Init (`src/luna/services/eden/__init__.py`)

```python
"""
Eden.art service adapter for Luna Engine.

Usage:
    from luna.services.eden import EdenAdapter, EdenConfig

    config = EdenConfig.load()
    async with EdenAdapter(config) as eden:
        task = await eden.create_image("a cyberpunk cityscape")
        print(task.first_output_url)
"""
from .adapter import EdenAdapter
from .client import EdenAPIError, EdenClient
from .config import EdenConfig
from .types import (
    Agent,
    Creation,
    CreationsPage,
    MediaType,
    Session,
    SessionMessage,
    Task,
    TaskStatus,
)

__all__ = [
    "EdenAdapter",
    "EdenAPIError",
    "EdenClient",
    "EdenConfig",
    "Agent",
    "Creation",
    "CreationsPage",
    "MediaType",
    "Session",
    "SessionMessage",
    "Task",
    "TaskStatus",
]
```

---

## PHASE 6: Tests (`tests/test_eden_adapter.py`)

```python
"""
Tests for Eden adapter.

Uses mocked HTTP responses — does NOT hit the real Eden API.
Run: pytest tests/test_eden_adapter.py -v
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

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
        # This depends on your config_dir handling — adjust if needed


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
                resp = AsyncMock()
                resp.status_code = 200
                resp.is_success = True
                resp.json.return_value = mock_responses[min(call_count, len(mock_responses) - 1)]
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
                resp = AsyncMock()
                resp.status_code = 200
                resp.is_success = True
                resp.json.return_value = {"docs": []}
                return resp

            mock_instance.request = mock_request
            MockClient.return_value = mock_instance

            async with EdenAdapter(config) as adapter:
                assert await adapter.health_check()
```

---

## PHASE 7: Config File (`config/eden.json`)

```json
{
  "api_base": "https://api.eden.art",
  "default_agent_id": null,
  "poll_interval_seconds": 3.0,
  "poll_max_attempts": 60,
  "default_manna_budget": 100.0,
  "default_turn_budget": 50,
  "timeout_seconds": 30.0,
  "max_retries": 3
}
```

Also add to `.env`:
```
EDEN_API_KEY=your_key_here
EDEN_AGENT_ID=optional_default_agent
```

---

## VERIFICATION

After all phases:

```bash
# 1. Type check — should have no errors in eden/
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -c "from luna.services.eden import EdenAdapter, EdenConfig; print('✓ Imports clean')"

# 2. Run tests
pytest tests/test_eden_adapter.py -v

# 3. Quick integration smoke test (requires EDEN_API_KEY in .env)
python -c "
import asyncio
from luna.services.eden import EdenAdapter, EdenConfig

async def smoke():
    config = EdenConfig.load()
    if not config.is_configured:
        print('⚠ No EDEN_API_KEY — skipping live test')
        return
    async with EdenAdapter(config) as eden:
        ok = await eden.health_check()
        print(f'Eden health: {\"✓\" if ok else \"✗\"}')
        agents = await eden.list_agents()
        print(f'Agents found: {len(agents)}')

asyncio.run(smoke())
"
```

---

## FILE CHECKLIST

| # | File | Action |
|---|------|--------|
| 1 | `src/luna/services/eden/__init__.py` | CREATE |
| 2 | `src/luna/services/eden/types.py` | CREATE |
| 3 | `src/luna/services/eden/config.py` | CREATE |
| 4 | `src/luna/services/eden/client.py` | CREATE |
| 5 | `src/luna/services/eden/adapter.py` | CREATE |
| 6 | `config/eden.json` | CREATE |
| 7 | `tests/test_eden_adapter.py` | CREATE |
| 8 | `.env` | APPEND `EDEN_API_KEY` + `EDEN_AGENT_ID` |

**No existing files are modified.**

---

## WHAT COMES NEXT (Phase 1.5 — NOT this handoff)

- MCP tool registration (`eden_create_image`, `eden_create_video`, `eden_chat`)
- Wire adapter into Luna Engine's service registry
- Session bridge between Luna Memory and Eden agent memory
- Error propagation to Luna's consciousness state machine

---

## DESIGN NOTES

**Why adapter pattern, not direct SDK?**
Eden's `@edenlabs/eden-sdk` is JS-only and in beta. Direct HTTP calls give us: control over retry/backoff, no dependency on SDK stability, ability to add KOZMO-specific extensions later (camera profiles, style locks).

**Why async context manager?**
Matches Luna Engine's existing patterns (aiosqlite, httpx in FastAPI). Connection pooling via httpx.AsyncClient is significant for polling loops.

**Why Pydantic over dataclass?**
Eden API uses camelCase — Pydantic's `alias` + `populate_by_name` handles the translation cleanly. Also gives us validation and serialization for free.

**Reference implementation:**
`Eden_Project/hello-eden/src/lib/eden.ts` is the TypeScript version of this same API surface. If you hit ambiguity on a response shape, check there first.

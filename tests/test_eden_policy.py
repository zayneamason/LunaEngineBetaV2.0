"""
Tests for Eden Policy — Phase 3 Guardrails.

Tests the EdenPolicy model, budget tracking, approval gates,
and policy enforcement in eden_tools.
"""

import json
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

from luna.services.eden.policy import EdenPolicy


# ── Policy Loading ──────────────────────────────────────────────

class TestPolicyLoading:
    def test_default_policy(self):
        """Default policy should have sensible defaults."""
        policy = EdenPolicy()
        assert policy.enabled is True
        assert "eden_health" in policy.auto_approve
        assert "eden_list_agents" in policy.auto_approve
        assert "eden_create_image" in policy.require_approval
        assert "eden_create_video" in policy.require_approval
        assert "eden_chat" in policy.require_approval
        assert policy.max_generations_per_session == 20
        assert policy.max_chats_per_session == 50
        assert policy.audit_to_memory is True

    def test_load_from_config(self):
        """Load policy from a config file."""
        config = {
            "api_base": "https://api.eden.art",
            "policy": {
                "enabled": False,
                "auto_approve": ["eden_health"],
                "require_approval": ["eden_create_image"],
                "max_generations_per_session": 5,
                "max_chats_per_session": 10,
                "audit_to_memory": False,
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            policy = EdenPolicy.load(f.name)

        os.unlink(f.name)

        assert policy.enabled is False
        assert policy.auto_approve == ["eden_health"]
        assert policy.max_generations_per_session == 5
        assert policy.max_chats_per_session == 10
        assert policy.audit_to_memory is False

    def test_load_missing_file_uses_defaults(self):
        """Missing config file should use defaults."""
        policy = EdenPolicy.load("/nonexistent/path/eden.json")
        assert policy.enabled is True
        assert len(policy.auto_approve) == 2

    def test_load_no_policy_section_uses_defaults(self):
        """Config without policy section should use defaults."""
        config = {"api_base": "https://api.eden.art"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            f.flush()
            policy = EdenPolicy.load(f.name)

        os.unlink(f.name)
        assert policy.enabled is True
        assert len(policy.auto_approve) == 2

    def test_from_dict(self):
        """Create policy from dict."""
        data = {
            "enabled": True,
            "auto_approve": ["eden_health"],
            "require_approval": [],
            "max_generations_per_session": 100,
            "max_chats_per_session": 200,
            "audit_to_memory": True,
        }
        policy = EdenPolicy.from_dict(data)
        assert policy.auto_approve == ["eden_health"]
        assert policy.max_generations_per_session == 100

    def test_to_dict(self):
        """Serialize policy to dict."""
        policy = EdenPolicy()
        d = policy.to_dict()
        assert "enabled" in d
        assert "auto_approve" in d
        assert "require_approval" in d
        assert "max_generations_per_session" in d

    def test_save_and_reload(self):
        """Save policy and reload it."""
        policy = EdenPolicy(
            enabled=False,
            max_generations_per_session=3,
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Write initial config
            json.dump({"api_base": "https://api.eden.art"}, f)
            f.flush()
            path = f.name

        policy.save(path)
        reloaded = EdenPolicy.load(path)
        os.unlink(path)

        assert reloaded.enabled is False
        assert reloaded.max_generations_per_session == 3


# ── Approval Gates ──────────────────────────────────────────────

class TestApprovalGates:
    def test_auto_approve_tools(self):
        """Auto-approved tools should not require approval."""
        policy = EdenPolicy()
        assert policy.requires_approval("eden_health") is False
        assert policy.requires_approval("eden_list_agents") is False

    def test_require_approval_tools(self):
        """Tools in require_approval list need confirmation."""
        policy = EdenPolicy()
        assert policy.requires_approval("eden_create_image") is True
        assert policy.requires_approval("eden_create_video") is True
        assert policy.requires_approval("eden_chat") is True

    def test_unknown_tool_requires_approval(self):
        """Unknown tools default to requiring approval (safe default)."""
        policy = EdenPolicy()
        assert policy.requires_approval("eden_unknown_tool") is True

    def test_disabled_policy_requires_all_approval(self):
        """When disabled, everything needs approval."""
        policy = EdenPolicy(enabled=False)
        assert policy.requires_approval("eden_health") is True
        assert policy.requires_approval("eden_list_agents") is True

    def test_custom_auto_approve(self):
        """Custom auto_approve list is respected."""
        policy = EdenPolicy(
            auto_approve=["eden_health", "eden_create_image"],
            require_approval=["eden_create_video"],
        )
        assert policy.requires_approval("eden_create_image") is False
        assert policy.requires_approval("eden_create_video") is True


# ── Budget Tracking ─────────────────────────────────────────────

class TestBudgetTracking:
    def test_initial_budget(self):
        """Initial budget should be full."""
        policy = EdenPolicy(max_generations_per_session=5)
        assert policy.generation_budget_remaining == 5
        assert policy.chat_budget_remaining == 50

    def test_record_generation_usage(self):
        """Recording usage decrements budget."""
        policy = EdenPolicy(max_generations_per_session=3)
        policy.record_usage("eden_create_image")
        assert policy.generation_budget_remaining == 2
        policy.record_usage("eden_create_video")
        assert policy.generation_budget_remaining == 1

    def test_record_chat_usage(self):
        """Chat usage tracked separately."""
        policy = EdenPolicy(max_chats_per_session=2)
        policy.record_usage("eden_chat")
        assert policy.chat_budget_remaining == 1
        policy.record_usage("eden_chat")
        assert policy.chat_budget_remaining == 0

    def test_check_budget_within_limit(self):
        """Budget check passes when within limit."""
        policy = EdenPolicy(max_generations_per_session=2)
        assert policy.check_budget("eden_create_image") is True
        policy.record_usage("eden_create_image")
        assert policy.check_budget("eden_create_image") is True

    def test_check_budget_exceeded(self):
        """Budget check fails when exceeded."""
        policy = EdenPolicy(max_generations_per_session=1)
        policy.record_usage("eden_create_image")
        assert policy.check_budget("eden_create_image") is False

    def test_check_budget_disabled_policy(self):
        """Disabled policy always fails budget check."""
        policy = EdenPolicy(enabled=False)
        assert policy.check_budget("eden_create_image") is False

    def test_non_generation_tools_no_budget(self):
        """Non-generation tools always pass budget check."""
        policy = EdenPolicy(max_generations_per_session=0)
        assert policy.check_budget("eden_health") is True
        assert policy.check_budget("eden_list_agents") is True

    def test_reset_session(self):
        """Reset session clears counters."""
        policy = EdenPolicy(max_generations_per_session=2)
        policy.record_usage("eden_create_image")
        policy.record_usage("eden_create_image")
        assert policy.generation_budget_remaining == 0

        policy.reset_session()
        assert policy.generation_budget_remaining == 2

    def test_image_and_video_share_generation_budget(self):
        """Image and video share the same generation budget."""
        policy = EdenPolicy(max_generations_per_session=2)
        policy.record_usage("eden_create_image")
        policy.record_usage("eden_create_video")
        assert policy.generation_budget_remaining == 0
        assert policy.check_budget("eden_create_image") is False


# ── Policy Enforcement in Tools ──────────────────────────────────

class TestPolicyEnforcement:
    """Test that eden_tools respects policy."""

    @pytest.fixture(autouse=True)
    def reset_globals(self):
        """Reset eden_tools globals between tests."""
        from luna.tools import eden_tools
        eden_tools._eden_adapter = None
        eden_tools._engine = None
        eden_tools._eden_policy = None
        yield
        eden_tools._eden_adapter = None
        eden_tools._engine = None
        eden_tools._eden_policy = None

    @pytest.mark.asyncio
    async def test_policy_blocks_when_disabled(self):
        """Disabled policy blocks generation tools."""
        from luna.tools import eden_tools
        eden_tools._eden_adapter = MagicMock()  # Adapter present
        eden_tools._eden_policy = EdenPolicy(enabled=False)

        result = await eden_tools.eden_create_image("test prompt")
        assert result["policy_blocked"] is True
        assert "disabled" in result["error"]

    @pytest.mark.asyncio
    async def test_policy_blocks_when_budget_exceeded(self):
        """Exceeded budget blocks generation tools."""
        from luna.tools import eden_tools
        eden_tools._eden_adapter = MagicMock()
        policy = EdenPolicy(max_generations_per_session=0)
        eden_tools._eden_policy = policy

        result = await eden_tools.eden_create_image("test prompt")
        assert result["policy_blocked"] is True
        assert "budget" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_policy_allows_auto_approved(self):
        """Auto-approved tools work without policy blocking."""
        from luna.tools import eden_tools
        adapter = AsyncMock()
        adapter.health_check = AsyncMock(return_value=True)
        eden_tools._eden_adapter = adapter
        eden_tools._eden_policy = EdenPolicy()

        # eden_health is auto-approved, should work
        result = await eden_tools.eden_health()
        assert result["healthy"] is True

    @pytest.mark.asyncio
    async def test_generation_records_usage(self):
        """Successful generation records usage."""
        from luna.tools import eden_tools

        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_task.status = MagicMock()
        mock_task.status.value = "completed"
        mock_task.is_complete = True
        mock_task.is_failed = False
        mock_task.first_output_url = "https://cdn.eden.art/img.jpg"
        mock_task.error = None

        adapter = AsyncMock()
        adapter.create_image = AsyncMock(return_value=mock_task)

        eden_tools._eden_adapter = adapter
        policy = EdenPolicy(max_generations_per_session=5)
        eden_tools._eden_policy = policy

        assert policy.generation_budget_remaining == 5
        result = await eden_tools.eden_create_image("a sunset")
        assert result["task_id"] == "t1"
        assert policy.generation_budget_remaining == 4

    @pytest.mark.asyncio
    async def test_policy_status_helper(self):
        """get_eden_policy_status returns useful info."""
        from luna.tools import eden_tools
        from luna.tools.eden_tools import get_eden_policy_status

        # No policy loaded
        eden_tools._eden_policy = None
        status = get_eden_policy_status()
        assert status["loaded"] is False

        # Policy loaded
        eden_tools._eden_policy = EdenPolicy()
        status = get_eden_policy_status()
        assert status["loaded"] is True
        assert status["enabled"] is True
        assert "generation_budget_remaining" in status


# ── Router Creative Detection ────────────────────────────────────

class TestRouterCreativeDetection:
    """Test that QueryRouter detects creative requests."""

    def test_image_generation_request(self):
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        decision = router.analyze("generate an image of a sunset")
        assert "creative_request" in decision.signals

    def test_video_generation_request(self):
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        decision = router.analyze("create a video of ocean waves")
        assert "creative_request" in decision.signals

    def test_draw_request(self):
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        decision = router.analyze("draw me a picture of a cat")
        assert "creative_request" in decision.signals

    def test_eden_mention_detected(self):
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        decision = router.analyze("use Eden to make art")
        assert "creative_request" in decision.signals

    def test_creative_routes_to_simple_plan(self):
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        decision = router.analyze("generate an image of a mountain landscape")
        assert decision.path == ExecutionPath.SIMPLE_PLAN

    def test_non_creative_not_flagged(self):
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        decision = router.analyze("what is the weather today?")
        assert "creative_request" not in decision.signals

    def test_eden_tool_patterns_detected(self):
        from luna.agentic.router import QueryRouter
        router = QueryRouter()
        decision = router.analyze("generate an image of a sunset over the ocean")
        assert "eden_create_image" in decision.suggested_tools

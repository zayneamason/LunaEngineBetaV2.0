"""
Tests for agentic system wiring.

Verifies that AgentLoop correctly connects to:
- Director (for generation and delegation)
- ToolRegistry (for tool execution)
- Matrix (for memory retrieval)
- Engine (for coordination)
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from luna.engine import LunaEngine, EngineConfig
from luna.agentic.loop import AgentLoop, AgentStatus, Action, WorkingContext
from luna.agentic.planner import PlanStepType
from luna.agentic.router import ExecutionPath
from luna.tools.registry import ToolRegistry, Tool


class TestAgentLoopToolExecution:
    """Test that AgentLoop executes tools via ToolRegistry."""

    @pytest.mark.asyncio
    async def test_tool_execution_calls_registry(self):
        """Test that _execute_tool calls the ToolRegistry."""
        loop = AgentLoop()

        mock_execute = AsyncMock(return_value="tool output")
        test_tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            execute=mock_execute,
        )
        loop.tool_registry.register(test_tool)

        loop.working_context = WorkingContext(goal="test")

        action = Action(
            type=PlanStepType.TOOL,
            description="Run test tool",
            tool="test_tool",
            params={"arg": "value"},
        )

        result = await loop._execute_tool(action)

        mock_execute.assert_called_once_with(arg="value")
        assert "succeeded" in result
        assert "tool output" in result

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Test that unknown tools return an error message."""
        loop = AgentLoop()

        action = Action(
            type=PlanStepType.TOOL,
            description="Run unknown tool",
            tool="nonexistent_tool",
            params={},
        )

        result = await loop._execute_tool(action)
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_no_tool_specified(self):
        """Test handling when no tool is specified."""
        loop = AgentLoop()

        action = Action(
            type=PlanStepType.TOOL,
            description="Run tool",
            tool=None,
            params={},
        )

        result = await loop._execute_tool(action)
        assert "no tool" in result.lower()


class TestAgentLoopDirectorWiring:
    """Test that AgentLoop connects to Director for generation."""

    @pytest.mark.asyncio
    async def test_generate_response_calls_director(self, tmp_path):
        """Test that _generate_response uses the Director."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        mock_director = MagicMock()
        mock_director.generate = AsyncMock(return_value="Generated response")
        engine.actors["director"] = mock_director

        loop = AgentLoop(orchestrator=engine)
        loop.working_context = MagicMock()
        loop.working_context.observations = []
        loop.working_context.action_history = []
        loop.working_context.variables = {}

        result = await loop._generate_response("Test goal")

        mock_director.generate.assert_called_once()
        assert result == "Generated response"

    @pytest.mark.asyncio
    async def test_generate_response_without_orchestrator(self):
        """Test _generate_response handles missing orchestrator."""
        loop = AgentLoop(orchestrator=None)

        result = await loop._generate_response("Test goal")

        assert "unable" in result.lower()

    @pytest.mark.asyncio
    async def test_delegate_calls_director(self, tmp_path):
        """Test that _execute_delegate uses the Director."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        mock_director = MagicMock()
        mock_director.generate = AsyncMock(return_value="Delegated result")
        engine.actors["director"] = mock_director

        loop = AgentLoop(orchestrator=engine)
        loop.working_context = MagicMock()
        loop.working_context.variables = {}
        loop.working_context.action_history = []

        action = Action(
            type=PlanStepType.DELEGATE,
            description="Research AI chips",
            params={},
        )

        result = await loop._execute_delegate(action)

        mock_director.generate.assert_called_once()
        assert "Delegated result" in result

    @pytest.mark.asyncio
    async def test_delegate_without_orchestrator(self):
        """Test _execute_delegate handles missing orchestrator."""
        loop = AgentLoop(orchestrator=None)

        action = Action(
            type=PlanStepType.DELEGATE,
            description="Do something",
            params={},
        )

        result = await loop._execute_delegate(action)

        assert "not available" in result.lower()


class TestAgentLoopMatrixWiring:
    """Test that AgentLoop connects to Matrix for memory."""

    @pytest.mark.asyncio
    async def test_retrieve_queries_matrix(self, tmp_path):
        """Test that _execute_retrieve queries the Matrix via UnifiedRetrieval."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        # UnifiedRetrieval accesses matrix_actor._matrix.get_context directly
        mock_node = MagicMock()
        mock_node.summary = "Test memory content about AI"
        mock_node.content = "Test memory content about AI"
        mock_node._retrieval_score = 0.9
        mock_node.node_type = "FACT"
        mock_node.confidence = 0.9

        mock_inner_matrix = MagicMock()
        mock_inner_matrix.get_context = AsyncMock(return_value=[mock_node])

        mock_matrix = MagicMock()
        mock_matrix.is_ready = True
        mock_matrix._matrix = mock_inner_matrix
        mock_matrix._format_context = MagicMock(return_value="## FACTs\n- Test memory content about AI")
        engine.actors["matrix"] = mock_matrix

        loop = AgentLoop(orchestrator=engine)
        loop.working_context = MagicMock()
        loop.working_context.goal = "Find information"
        loop.working_context.variables = {}

        action = Action(
            type=PlanStepType.RETRIEVE,
            description="Search memory",
            params={"query": "test query"},
        )

        result = await loop._execute_retrieve(action)

        mock_inner_matrix.get_context.assert_called_once()
        assert "memory content" in result.lower() or "context" in result.lower()

    @pytest.mark.asyncio
    async def test_retrieve_without_orchestrator(self):
        """Test _execute_retrieve handles missing orchestrator."""
        loop = AgentLoop(orchestrator=None)

        action = Action(
            type=PlanStepType.RETRIEVE,
            description="Search memory",
            params={},
        )

        result = await loop._execute_retrieve(action)

        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_retrieve_matrix_not_ready(self, tmp_path):
        """Test _execute_retrieve handles matrix not ready."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        mock_matrix = MagicMock()
        mock_matrix.is_ready = False
        engine.actors["matrix"] = mock_matrix

        loop = AgentLoop(orchestrator=engine)
        loop.working_context = MagicMock()
        loop.working_context.goal = "test"
        loop.working_context.variables = {}

        action = Action(
            type=PlanStepType.RETRIEVE,
            description="Search memory",
            params={},
        )

        result = await loop._execute_retrieve(action)

        assert "no relevant memories" in result.lower() or "not ready" in result.lower()


class TestToolRegistryInitialization:
    """Test that AgentLoop initializes ToolRegistry properly."""

    def test_agent_loop_has_tool_registry(self):
        """Test that AgentLoop creates a ToolRegistry."""
        loop = AgentLoop()

        assert hasattr(loop, 'tool_registry')
        assert isinstance(loop.tool_registry, ToolRegistry)

    def test_default_tools_registered(self):
        """Test that default tools are registered."""
        loop = AgentLoop()

        tools = loop.tool_registry.list_tools()

        # Should have file tools
        assert "read_file" in tools
        assert "list_directory" in tools

        # Should have memory tools
        assert "memory_query" in tools
        assert "memory_store" in tools


class TestFileToolsWiring:
    """Test that file tools work through ToolRegistry."""

    @pytest.mark.asyncio
    async def test_read_file_tool(self, tmp_path):
        """Test read_file tool execution."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello from test file")

        loop = AgentLoop()
        loop.working_context = WorkingContext(goal="test")

        action = Action(
            type=PlanStepType.TOOL,
            description="Read file",
            tool="read_file",
            params={"path": str(test_file)},
        )

        result = await loop._execute_tool(action)

        assert "succeeded" in result
        assert "Hello from test file" in result

    @pytest.mark.asyncio
    async def test_list_directory_tool(self, tmp_path):
        """Test list_directory tool execution."""
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.txt").write_text("content")

        loop = AgentLoop()
        loop.working_context = WorkingContext(goal="test")

        action = Action(
            type=PlanStepType.TOOL,
            description="List directory",
            tool="list_directory",
            params={"path": str(tmp_path)},
        )

        result = await loop._execute_tool(action)

        assert "succeeded" in result


class TestEngineIntegration:
    """Test Engine integration methods."""

    @pytest.mark.asyncio
    async def test_run_agent_raises_if_not_initialized(self, tmp_path):
        """Test that run_agent raises if agent_loop not ready."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        with pytest.raises(RuntimeError, match="not initialized"):
            await engine.run_agent("test goal")

    def test_engine_has_agent_loop_attribute(self, tmp_path):
        """Test that engine has agent_loop attribute."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        # Before boot, should be None
        assert engine.agent_loop is None


class TestThinkExecution:
    """Test THINK action execution."""

    @pytest.mark.asyncio
    async def test_think_without_orchestrator(self):
        """Test _execute_think handles missing orchestrator."""
        loop = AgentLoop(orchestrator=None)

        action = Action(
            type=PlanStepType.THINK,
            description="Analyze the situation",
            params={},
        )

        result = await loop._execute_think(action)

        assert "Thought:" in result
        assert "Analyze the situation" in result

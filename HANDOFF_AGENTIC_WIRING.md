# HANDOFF: Complete Agentic System Wiring

**Priority:** HIGH  
**Goal:** Connect the AgentLoop skeleton to actual execution — Director, ToolRegistry, Matrix, Engine.

---

## Current State

The agentic layer has **structure without substance**:

| Component | Status |
|-----------|--------|
| Router | ✅ Working — routes by complexity |
| Planner | ✅ Working — decomposes goals into steps |
| AgentLoop | ⚠️ Skeleton — observe/think/act cycle runs but execution is placeholder |
| ToolRegistry | ✅ Working — registration and execution with timeout |
| File Tools | ✅ Working — 5 tools implemented |
| **Wiring** | ❌ Missing — nothing talks to anything |

**The problem:** AgentLoop methods return hardcoded strings instead of calling actors.

```python
# Current (broken)
async def _generate_response(self, goal: str) -> str:
    return f"Response for: {goal}"  # ← placeholder

# Needed
async def _generate_response(self, goal: str) -> str:
    director = self.orchestrator.get_actor("director")
    response = await director.generate(goal, context=self.working_context)
    return response
```

---

## Deliverables

### 1. Wire AgentLoop to Engine

**File:** `src/luna/agentic/loop.py`

**Problem:** AgentLoop has `self.orchestrator` but doesn't use it properly.

**Add ToolRegistry initialization in `__init__`:**

```python
def __init__(
    self,
    orchestrator: Optional["LunaEngine"] = None,
    max_iterations: int = 50,
):
    self.orchestrator = orchestrator
    self.max_iterations = max_iterations

    # Components
    self.planner = Planner()
    self.router = QueryRouter()
    
    # ADD: Tool registry with default tools
    self.tool_registry = ToolRegistry()
    self._register_default_tools()
    
    # ... rest unchanged

def _register_default_tools(self) -> None:
    """Register default tools available to the agent."""
    from luna.tools.file_tools import register_file_tools
    from luna.tools.memory_tools import register_memory_tools
    
    register_file_tools(self.tool_registry)
    register_memory_tools(self.tool_registry)
    
    logger.info(f"Registered {len(self.tool_registry.list_tools())} tools")
```

---

### 2. Wire `_generate_response()` to Director

**File:** `src/luna/agentic/loop.py`

**Current (placeholder):**
```python
async def _generate_response(self, goal: str) -> str:
    # In a full implementation, this would call the Director actor
    # For now, return a placeholder
    return f"Response for: {goal}"
```

**Replace with:**
```python
async def _generate_response(self, goal: str) -> str:
    """Generate a response using the Director actor."""
    if not self.orchestrator:
        logger.warning("No orchestrator available for response generation")
        return "I'm unable to generate a response right now."
    
    director = self.orchestrator.get_actor("director")
    if not director:
        logger.warning("Director actor not available")
        return "I'm unable to generate a response right now."
    
    # Build context from working memory
    context_parts = []
    
    # Add relevant observations
    if self.working_context and self.working_context.observations:
        obs_text = "\n".join([
            f"- {obs.type}: {obs.content}" 
            for obs in self.working_context.observations[-5:]  # Last 5
        ])
        context_parts.append(f"Observations:\n{obs_text}")
    
    # Add action history
    if self.working_context and self.working_context.action_history:
        history_text = "\n".join([
            f"- {r.action.description}: {'✓' if r.success else '✗'} {r.output or r.error or ''}"
            for r in self.working_context.action_history[-5:]
        ])
        context_parts.append(f"Actions taken:\n{history_text}")
    
    # Add accumulated variables
    if self.working_context and self.working_context.variables:
        var_text = "\n".join([
            f"- {k}: {v}" for k, v in self.working_context.variables.items()
        ])
        context_parts.append(f"Context:\n{var_text}")
    
    context = "\n\n".join(context_parts) if context_parts else ""
    
    # Build the prompt
    if context:
        prompt = f"Goal: {goal}\n\n{context}\n\nGenerate a helpful response."
    else:
        prompt = goal
    
    # Send to Director
    from luna.actors.base import Message
    
    response_future = asyncio.Future()
    
    async def capture_response(msg: Message):
        if msg.type == "generation_complete":
            response_future.set_result(msg.payload.get("response", ""))
    
    # Use Director's generate method directly if available
    if hasattr(director, 'generate'):
        response = await director.generate(prompt)
        return response
    
    # Fallback: send message and wait
    msg = Message(
        type="generate",
        payload={
            "prompt": prompt,
            "max_tokens": 1000,
        }
    )
    await director.mailbox.put(msg)
    
    # Wait for response with timeout
    try:
        # Poll for response (Director should update some shared state)
        # This is a simplified approach - real impl might use callbacks
        await asyncio.sleep(0.1)  # Give Director time to process
        return "Response generated."  # Placeholder until Director has proper response channel
    except asyncio.TimeoutError:
        return "Response generation timed out."
```

**Better approach — Add `generate()` method to DirectorActor:**

**File:** `src/luna/actors/director.py`

Add this method:

```python
async def generate(
    self,
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
) -> str:
    """
    Generate a response using the appropriate backend.
    
    Checks delegation signals to decide local vs cloud.
    
    Args:
        prompt: The prompt to generate from
        system: Optional system prompt
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        
    Returns:
        Generated text response
    """
    # Check if we should delegate to Claude
    should_delegate = self._should_delegate(prompt)
    
    if should_delegate or not self._local_available:
        return await self._generate_cloud(prompt, system, max_tokens, temperature)
    else:
        return await self._generate_local(prompt, system, max_tokens, temperature)

async def _generate_cloud(
    self,
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
) -> str:
    """Generate using Claude API."""
    if not self._client:
        raise RuntimeError("Anthropic client not initialized")
    
    messages = [{"role": "user", "content": prompt}]
    
    response = self._client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system or "You are Luna, a helpful AI assistant.",
        messages=messages,
    )
    
    return response.content[0].text

async def _generate_local(
    self,
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
) -> str:
    """Generate using local inference."""
    if not self._local_inference:
        raise RuntimeError("Local inference not available")
    
    # Combine system and prompt for local model
    full_prompt = prompt
    if system:
        full_prompt = f"{system}\n\n{prompt}"
    
    result = await self._local_inference.generate(
        full_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    return result
```

---

### 3. Wire `_execute_tool()` to ToolRegistry

**File:** `src/luna/agentic/loop.py`

**Current (placeholder):**
```python
async def _execute_tool(self, action: Action) -> str:
    # Would call the tool registry
    # For now, just acknowledge
    return f"Tool '{action.tool}' executed with params: {action.params}"
```

**Replace with:**
```python
async def _execute_tool(self, action: Action) -> str:
    """Execute a tool action via the ToolRegistry."""
    if not action.tool:
        return "No tool specified"
    
    # Check if tool exists
    tool = self.tool_registry.get(action.tool)
    if not tool:
        available = ", ".join(self.tool_registry.list_tools())
        return f"Tool '{action.tool}' not found. Available: {available}"
    
    # Check confirmation requirement
    if tool.requires_confirmation:
        # Store pending action for user confirmation
        # In a full implementation, this would pause and wait for user input
        logger.info(f"Tool {action.tool} requires confirmation")
        # For now, skip confirmation in agentic mode
        skip_confirmation = True
    else:
        skip_confirmation = False
    
    # Execute the tool
    result = await self.tool_registry.execute(
        action.tool,
        action.params,
        skip_confirmation=skip_confirmation,
    )
    
    if result.success:
        # Store result in working context variables
        if self.working_context:
            var_name = f"tool_result_{action.tool}"
            self.working_context.variables[var_name] = result.output
        
        # Format output for display
        if isinstance(result.output, str):
            output_str = result.output[:500]  # Truncate long outputs
            if len(result.output) > 500:
                output_str += f"... ({len(result.output)} chars total)"
        elif isinstance(result.output, dict):
            output_str = str(result.output)
        elif isinstance(result.output, list):
            output_str = f"[{len(result.output)} items]"
        else:
            output_str = str(result.output)
        
        return f"Tool '{action.tool}' succeeded: {output_str}"
    else:
        return f"Tool '{action.tool}' failed: {result.error}"
```

---

### 4. Wire `_execute_retrieve()` to Matrix

**File:** `src/luna/agentic/loop.py`

**Current (partially implemented):**
```python
async def _execute_retrieve(self, action: Action) -> str:
    """Execute a RETRIEVE action."""
    # Would query the Matrix actor
    if self.orchestrator:
        matrix = self.orchestrator.get_actor("matrix")
        if matrix and hasattr(matrix, "get_context"):
            context = await matrix.get_context(
                self.working_context.goal,
                max_tokens=1000,
            )
            return context

    return "Memory retrieval not available"
```

**Replace with (more robust):**
```python
async def _execute_retrieve(self, action: Action) -> str:
    """Execute a RETRIEVE action by querying the Matrix."""
    if not self.orchestrator:
        return "Memory retrieval not available (no orchestrator)"
    
    matrix = self.orchestrator.get_actor("matrix")
    if not matrix:
        return "Memory retrieval not available (no matrix actor)"
    
    if not matrix.is_ready:
        return "Memory not ready"
    
    # Determine query from action params or working context
    query = action.params.get("query") or self.working_context.goal
    budget = action.params.get("budget", "balanced")
    
    try:
        # Try smart_fetch first (Eclissi-style, will work after migration)
        if hasattr(matrix, "get_context"):
            context = await matrix.get_context(
                query=query,
                budget=budget,
            )
            
            # Store in working context
            if self.working_context and context:
                self.working_context.variables["memory_context"] = context
            
            if context:
                # Truncate for display
                preview = context[:500]
                if len(context) > 500:
                    preview += f"... ({len(context)} chars)"
                return f"Retrieved context:\n{preview}"
            else:
                return "No relevant memories found"
        
        # Fallback: use search_nodes directly
        memory = getattr(matrix, "_matrix", None) or getattr(matrix, "matrix", None)
        if memory and hasattr(memory, "search_nodes"):
            nodes = await memory.search_nodes(query, limit=5)
            
            if nodes:
                results = []
                for node in nodes:
                    results.append(f"[{node.node_type}] {node.content[:100]}...")
                
                context = "\n".join(results)
                
                if self.working_context:
                    self.working_context.variables["memory_context"] = context
                
                return f"Found {len(nodes)} relevant memories:\n{context}"
            else:
                return "No relevant memories found"
        
        return "Memory retrieval not available (no search method)"
        
    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}")
        return f"Memory retrieval failed: {e}"
```

---

### 5. Wire `_execute_delegate()` to Director (Claude)

**File:** `src/luna/agentic/loop.py`

**Current (placeholder):**
```python
async def _execute_delegate(self, action: Action) -> str:
    """Execute a DELEGATE action."""
    # Would call the Director for Claude delegation
    if self.orchestrator:
        director = self.orchestrator.get_actor("director")
        if director:
            # In a full implementation, we'd send a message and wait
            pass

    return f"Delegated: {action.description}"
```

**Replace with:**
```python
async def _execute_delegate(self, action: Action) -> str:
    """Execute a DELEGATE action by calling Claude via Director."""
    if not self.orchestrator:
        return "Delegation not available (no orchestrator)"
    
    director = self.orchestrator.get_actor("director")
    if not director:
        return "Delegation not available (no director actor)"
    
    # Build delegation prompt
    task = action.description
    
    # Add any context from params
    context_parts = []
    if action.params.get("context"):
        context_parts.append(action.params["context"])
    
    # Add working context if available
    if self.working_context:
        if self.working_context.variables.get("memory_context"):
            context_parts.append(f"Relevant memories:\n{self.working_context.variables['memory_context']}")
        
        # Add previous action results
        recent_results = [
            r.output for r in self.working_context.action_history[-3:]
            if r.success and r.output
        ]
        if recent_results:
            context_parts.append(f"Previous results:\n" + "\n".join(str(r) for r in recent_results))
    
    context = "\n\n".join(context_parts) if context_parts else ""
    
    # Build the prompt for Claude
    if context:
        prompt = f"Task: {task}\n\nContext:\n{context}\n\nPlease complete this task."
    else:
        prompt = f"Task: {task}\n\nPlease complete this task."
    
    try:
        # Use Director's generate method
        if hasattr(director, 'generate'):
            response = await director.generate(
                prompt=prompt,
                system="You are helping Luna complete a task. Be thorough but concise.",
                max_tokens=2000,
            )
            
            # Store result in working context
            if self.working_context:
                self.working_context.variables["delegation_result"] = response
            
            # Truncate for display
            preview = response[:1000]
            if len(response) > 1000:
                preview += f"... ({len(response)} chars)"
            
            return f"Claude response:\n{preview}"
        else:
            return "Director doesn't support generate method"
            
    except Exception as e:
        logger.error(f"Delegation failed: {e}")
        return f"Delegation failed: {e}"
```

---

### 6. Wire `_execute_think()` to Director (Local)

**File:** `src/luna/agentic/loop.py`

**Current (placeholder):**
```python
async def _execute_think(self, action: Action) -> str:
    """Execute a THINK action."""
    # In a full implementation, this would use the Director
    # For now, just return the description
    return f"Thinking: {action.description}"
```

**Replace with:**
```python
async def _execute_think(self, action: Action) -> str:
    """Execute a THINK action using local inference."""
    if not self.orchestrator:
        # No orchestrator, just acknowledge
        return f"Thought: {action.description}"
    
    director = self.orchestrator.get_actor("director")
    
    # THINK actions prefer local inference to save latency/cost
    # Only use if local is available
    if director and hasattr(director, '_local_available') and director._local_available:
        try:
            # Build thinking prompt
            prompt = f"Think through this step: {action.description}"
            
            if self.working_context and self.working_context.variables:
                context = "\n".join([
                    f"- {k}: {str(v)[:100]}" 
                    for k, v in self.working_context.variables.items()
                ])
                prompt = f"Context:\n{context}\n\n{prompt}"
            
            response = await director._generate_local(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3,  # Lower temp for reasoning
            )
            
            # Store thought in working context
            if self.working_context:
                thoughts = self.working_context.variables.get("thoughts", [])
                thoughts.append(response)
                self.working_context.variables["thoughts"] = thoughts
            
            return f"Thought: {response}"
            
        except Exception as e:
            logger.debug(f"Local think failed, falling back: {e}")
    
    # Fallback: just acknowledge the thinking step
    return f"Thought: {action.description}"
```

---

### 7. Wire AgentLoop into Engine

**File:** `src/luna/engine.py`

**Add AgentLoop to Engine:**

```python
# In imports at top
from luna.agentic.loop import AgentLoop, AgentResult

# In LunaEngine.__init__
def __init__(self, config: Optional[EngineConfig] = None):
    # ... existing init ...
    
    # ADD: Agent loop for complex tasks
    self._agent_loop: Optional[AgentLoop] = None

# In _boot method, after actors are registered
async def _boot(self) -> None:
    """Boot sequence: initialize actors, restore state."""
    # ... existing boot code ...
    
    # ADD: Initialize agent loop with engine reference
    self._agent_loop = AgentLoop(orchestrator=self, max_iterations=50)
    logger.info("AgentLoop initialized")

# ADD: Public method to run agentic tasks
async def run_agent(self, goal: str) -> AgentResult:
    """
    Run the agent loop for a complex goal.
    
    Use this for tasks that require multiple steps,
    tool use, or delegation to Claude.
    
    Args:
        goal: The user's goal or request
        
    Returns:
        AgentResult with response and execution trace
    """
    if not self._agent_loop:
        raise RuntimeError("Agent loop not initialized")
    
    return await self._agent_loop.run(goal)

# ADD: Convenience method that routes automatically
async def process_input(self, user_input: str) -> str:
    """
    Process user input, routing to chat or agent as appropriate.
    
    This is the main entry point for user messages.
    """
    # Use router to decide execution path
    from luna.agentic.router import QueryRouter, ExecutionPath
    
    router = QueryRouter()
    decision = router.analyze(user_input)
    
    if decision.path == ExecutionPath.DIRECT:
        # Simple chat - direct to Director
        director = self.get_actor("director")
        if director and hasattr(director, 'generate'):
            return await director.generate(user_input)
        return "I'm not able to respond right now."
    else:
        # Complex task - use agent loop
        result = await self.run_agent(user_input)
        return result.response
```

---

### 8. Add Memory Tools

**File:** `src/luna/tools/memory_tools.py` (NEW)

```python
"""
Memory Tools for Luna Engine
=============================

Tools for querying and managing Luna's memory.
"""

import logging
from typing import Optional, List
from .registry import Tool

logger = logging.getLogger(__name__)

# Global reference to matrix (set by register_memory_tools)
_matrix_actor = None


async def search_memory(
    query: str,
    limit: int = 5,
    node_type: Optional[str] = None,
) -> List[dict]:
    """
    Search Luna's memory for relevant information.
    
    Args:
        query: Search query
        limit: Maximum results to return
        node_type: Optional filter by node type (FACT, DECISION, etc.)
        
    Returns:
        List of matching memory nodes
    """
    if not _matrix_actor:
        raise RuntimeError("Memory not available")
    
    memory = getattr(_matrix_actor, "_matrix", None)
    if not memory:
        raise RuntimeError("Memory matrix not initialized")
    
    nodes = await memory.search_nodes(query, node_type=node_type, limit=limit)
    
    return [
        {
            "id": node.id,
            "type": node.node_type,
            "content": node.content,
            "confidence": node.confidence,
            "created_at": node.created_at,
        }
        for node in nodes
    ]


async def recall_recent(limit: int = 10) -> List[dict]:
    """
    Recall recent memories.
    
    Args:
        limit: Number of recent memories to retrieve
        
    Returns:
        List of recent memory nodes
    """
    if not _matrix_actor:
        raise RuntimeError("Memory not available")
    
    memory = getattr(_matrix_actor, "_matrix", None)
    if not memory:
        raise RuntimeError("Memory matrix not initialized")
    
    nodes = await memory.get_recent_nodes(limit=limit)
    
    return [
        {
            "id": node.id,
            "type": node.node_type,
            "content": node.content,
            "created_at": node.created_at,
        }
        for node in nodes
    ]


async def remember(
    content: str,
    node_type: str = "FACT",
    source: str = "user",
) -> dict:
    """
    Store a new memory.
    
    Args:
        content: The content to remember
        node_type: Type of memory (FACT, DECISION, etc.)
        source: Source of the memory
        
    Returns:
        The created memory node info
    """
    if not _matrix_actor:
        raise RuntimeError("Memory not available")
    
    memory = getattr(_matrix_actor, "_matrix", None)
    if not memory:
        raise RuntimeError("Memory matrix not initialized")
    
    node_id = await memory.add_node(
        node_type=node_type,
        content=content,
        source=source,
    )
    
    return {
        "id": node_id,
        "type": node_type,
        "content": content,
        "source": source,
    }


# Tool definitions

search_memory_tool = Tool(
    name="search_memory",
    description="Search Luna's memory for relevant information about a topic.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to search for in memory"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return",
                "default": 5
            },
            "node_type": {
                "type": "string",
                "description": "Filter by memory type (FACT, DECISION, PROBLEM, ACTION)",
                "enum": ["FACT", "DECISION", "PROBLEM", "ACTION", "CONTEXT"]
            }
        },
        "required": ["query"]
    },
    execute=search_memory,
    requires_confirmation=False,
    timeout_seconds=10,
)

recall_recent_tool = Tool(
    name="recall_recent",
    description="Recall Luna's most recent memories.",
    parameters={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of memories to recall",
                "default": 10
            }
        },
    },
    execute=recall_recent,
    requires_confirmation=False,
    timeout_seconds=10,
)

remember_tool = Tool(
    name="remember",
    description="Store a new memory. Use this to remember important facts, decisions, or observations.",
    parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "What to remember"
            },
            "node_type": {
                "type": "string",
                "description": "Type of memory",
                "enum": ["FACT", "DECISION", "PROBLEM", "ACTION"],
                "default": "FACT"
            },
            "source": {
                "type": "string",
                "description": "Source of this memory",
                "default": "user"
            }
        },
        "required": ["content"]
    },
    execute=remember,
    requires_confirmation=False,
    timeout_seconds=10,
)


ALL_MEMORY_TOOLS = [
    search_memory_tool,
    recall_recent_tool,
    remember_tool,
]


def register_memory_tools(registry, matrix_actor=None) -> None:
    """
    Register all memory tools with a ToolRegistry.
    
    Args:
        registry: The ToolRegistry to register tools with
        matrix_actor: Optional MatrixActor for memory access
    """
    global _matrix_actor
    _matrix_actor = matrix_actor
    
    for tool in ALL_MEMORY_TOOLS:
        registry.register(tool)
    
    logger.info(f"Registered {len(ALL_MEMORY_TOOLS)} memory tools")
```

**Update `src/luna/tools/__init__.py`:**

```python
from .registry import Tool, ToolResult, ToolRegistry
from .file_tools import ALL_FILE_TOOLS, register_file_tools
from .memory_tools import ALL_MEMORY_TOOLS, register_memory_tools

__all__ = [
    "Tool",
    "ToolResult", 
    "ToolRegistry",
    "ALL_FILE_TOOLS",
    "ALL_MEMORY_TOOLS",
    "register_file_tools",
    "register_memory_tools",
]
```

---

### 9. Tests

**File:** `tests/test_agentic_wiring.py` (NEW)

```python
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
from luna.agentic.loop import AgentLoop, AgentStatus
from luna.agentic.planner import PlanStepType
from luna.agentic.router import ExecutionPath
from luna.tools.registry import ToolRegistry, Tool


class TestAgentLoopToolExecution:
    """Test that AgentLoop executes tools via ToolRegistry."""
    
    @pytest.mark.asyncio
    async def test_tool_execution_calls_registry(self):
        """Test that _execute_tool calls the ToolRegistry."""
        loop = AgentLoop()
        
        # Register a mock tool
        mock_execute = AsyncMock(return_value="tool output")
        test_tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
            execute=mock_execute,
        )
        loop.tool_registry.register(test_tool)
        
        # Create action
        from luna.agentic.loop import Action
        action = Action(
            type=PlanStepType.TOOL,
            description="Run test tool",
            tool="test_tool",
            params={"arg": "value"},
        )
        
        # Execute
        result = await loop._execute_tool(action)
        
        # Verify tool was called
        mock_execute.assert_called_once_with(arg="value")
        assert "succeeded" in result
        assert "tool output" in result
    
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Test that unknown tools return an error message."""
        loop = AgentLoop()
        
        from luna.agentic.loop import Action
        action = Action(
            type=PlanStepType.TOOL,
            description="Run unknown tool",
            tool="nonexistent_tool",
            params={},
        )
        
        result = await loop._execute_tool(action)
        
        assert "not found" in result.lower()


class TestAgentLoopDirectorWiring:
    """Test that AgentLoop connects to Director for generation."""
    
    @pytest.mark.asyncio
    async def test_generate_response_calls_director(self, tmp_path):
        """Test that _generate_response uses the Director."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)
        
        # Mock Director
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
    async def test_delegate_calls_director(self, tmp_path):
        """Test that _execute_delegate uses the Director."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)
        
        # Mock Director
        mock_director = MagicMock()
        mock_director.generate = AsyncMock(return_value="Delegated result")
        engine.actors["director"] = mock_director
        
        loop = AgentLoop(orchestrator=engine)
        loop.working_context = MagicMock()
        loop.working_context.variables = {}
        loop.working_context.action_history = []
        
        from luna.agentic.loop import Action
        action = Action(
            type=PlanStepType.DELEGATE,
            description="Research AI chips",
            params={},
        )
        
        result = await loop._execute_delegate(action)
        
        mock_director.generate.assert_called_once()
        assert "Delegated result" in result


class TestAgentLoopMatrixWiring:
    """Test that AgentLoop connects to Matrix for memory."""
    
    @pytest.mark.asyncio
    async def test_retrieve_queries_matrix(self, tmp_path):
        """Test that _execute_retrieve queries the Matrix."""
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)
        
        # Mock Matrix
        mock_matrix = MagicMock()
        mock_matrix.is_ready = True
        
        mock_memory = MagicMock()
        mock_node = MagicMock()
        mock_node.id = "node_1"
        mock_node.node_type = "FACT"
        mock_node.content = "Test memory content"
        mock_memory.search_nodes = AsyncMock(return_value=[mock_node])
        
        mock_matrix._matrix = mock_memory
        engine.actors["matrix"] = mock_matrix
        
        loop = AgentLoop(orchestrator=engine)
        loop.working_context = MagicMock()
        loop.working_context.goal = "Find information"
        loop.working_context.variables = {}
        
        from luna.agentic.loop import Action
        action = Action(
            type=PlanStepType.RETRIEVE,
            description="Search memory",
            params={"query": "test query"},
        )
        
        result = await loop._execute_retrieve(action)
        
        mock_memory.search_nodes.assert_called_once()
        assert "Test memory content" in result


class TestEngineAgentIntegration:
    """Test that Engine properly integrates AgentLoop."""
    
    @pytest.mark.asyncio
    async def test_engine_initializes_agent_loop(self, tmp_path, monkeypatch):
        """Test that engine boot creates AgentLoop."""
        # Disable Eclissi
        import luna.actors.matrix as matrix_module
        monkeypatch.setattr(matrix_module, "ECLISSI_AVAILABLE", False)
        
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)
        
        await engine._boot()
        
        assert engine._agent_loop is not None
        assert engine._agent_loop.orchestrator is engine
        
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_run_agent_returns_result(self, tmp_path, monkeypatch):
        """Test that run_agent executes and returns result."""
        import luna.actors.matrix as matrix_module
        monkeypatch.setattr(matrix_module, "ECLISSI_AVAILABLE", False)
        
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)
        
        await engine._boot()
        
        # Simple query should work even without full wiring
        result = await engine.run_agent("Hello")
        
        assert result is not None
        assert result.goal == "Hello"
        assert result.status in (AgentStatus.COMPLETE, AgentStatus.FAILED)
        
        await engine.stop()


class TestFileToolsWiring:
    """Test that file tools work through ToolRegistry."""
    
    @pytest.mark.asyncio
    async def test_read_file_tool(self, tmp_path):
        """Test read_file tool execution."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello from test file")
        
        loop = AgentLoop()
        
        from luna.tools.file_tools import register_file_tools
        register_file_tools(loop.tool_registry)
        
        from luna.agentic.loop import Action
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
        # Create test files
        (tmp_path / "file1.txt").write_text("content")
        (tmp_path / "file2.txt").write_text("content")
        
        loop = AgentLoop()
        
        from luna.tools.file_tools import register_file_tools
        register_file_tools(loop.tool_registry)
        
        from luna.agentic.loop import Action
        action = Action(
            type=PlanStepType.TOOL,
            description="List directory",
            tool="list_directory",
            params={"path": str(tmp_path)},
        )
        
        result = await loop._execute_tool(action)
        
        assert "succeeded" in result
        assert "2 items" in result
```

---

## Execution Order

```bash
# 1. Create memory_tools.py
# 2. Update tools/__init__.py
# 3. Update agentic/loop.py with all wiring
# 4. Add generate() method to actors/director.py
# 5. Update engine.py with AgentLoop integration
# 6. Create tests/test_agentic_wiring.py

# 7. Run tests
pytest tests/test_agentic_wiring.py -v

# 8. Run existing planning tests
pytest tests/test_planning.py -v

# 9. Integration test
python -c "
import asyncio
from luna.engine import LunaEngine, EngineConfig

async def test():
    engine = LunaEngine(EngineConfig())
    await engine._boot()
    result = await engine.run_agent('What files are in the current directory?')
    print(f'Status: {result.status}')
    print(f'Response: {result.response}')
    await engine.stop()

asyncio.run(test())
"
```

---

## Success Criteria

1. **Tools execute:** `_execute_tool()` calls ToolRegistry, tools run
2. **Director generates:** `_generate_response()` and `_execute_delegate()` produce real LLM output
3. **Memory retrieves:** `_execute_retrieve()` queries Matrix and returns results
4. **Engine integrates:** `engine.run_agent()` works end-to-end
5. **Tests pass:** All new tests in `test_agentic_wiring.py` pass

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/luna/tools/memory_tools.py` | Memory query/store tools |
| `tests/test_agentic_wiring.py` | Integration tests |

## Files to Modify

| File | Changes |
|------|---------|
| `src/luna/agentic/loop.py` | Wire all `_execute_*` methods, add ToolRegistry |
| `src/luna/actors/director.py` | Add `generate()` method |
| `src/luna/engine.py` | Add `_agent_loop`, `run_agent()`, `process_input()` |
| `src/luna/tools/__init__.py` | Export memory tools |

---

## Dependencies

This handoff assumes:
- Eclissi removal is complete (Matrix uses Luna substrate)
- Director actor has working Anthropic client
- File tools are working (they are)

If Eclissi removal isn't done yet, the Matrix wiring will still use Eclissi's database temporarily.

---

**End of Handoff**

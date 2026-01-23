"""
Agent Loop for Luna Engine
==========================

The autonomous observe -> think -> act -> repeat cycle that transforms
Luna from a chatbot into an agentic system.

From Part XIV (Claude Code Style):
- Autonomous loop (doesn't need user input per step)
- Tool execution (real effects in the world)
- State awareness (reads environment, remembers what it did)
- Goal-directed (keeps going until done or stuck)

The AgentLoop coordinates with:
- Planner: Decomposes goals into executable steps
- Router: Determines execution path
- Director: Handles LLM inference
- ToolRegistry: Executes tools (future)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, TYPE_CHECKING
import asyncio
import logging
import uuid

from .planner import Plan, PlanStep, PlanStepType, Planner
from .router import QueryRouter, ExecutionPath, RoutingDecision

if TYPE_CHECKING:
    from luna.engine import LunaEngine

logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    """Status of the agent loop."""

    IDLE = auto()
    """Not currently executing a goal."""

    PLANNING = auto()
    """Decomposing goal into steps."""

    EXECUTING = auto()
    """Executing plan steps."""

    WAITING = auto()
    """Waiting for external event."""

    COMPLETE = auto()
    """Goal achieved."""

    FAILED = auto()
    """Goal could not be achieved."""

    ABORTED = auto()
    """Execution was aborted."""


@dataclass
class Observation:
    """
    What the agent observes about the current state.

    Observations include:
    - Environment state (files, directories)
    - Command outputs
    - Memory retrievals
    - Previous action results
    """

    type: str
    """Type of observation (environment, memory, tool_result, etc.)."""

    content: Any
    """The observed content."""

    source: str = "unknown"
    """Where this observation came from."""

    timestamp: datetime = field(default_factory=datetime.now)
    """When the observation was made."""

    relevance: float = 1.0
    """How relevant this observation is to the current goal (0.0-1.0)."""


@dataclass
class Action:
    """
    An action the agent decides to take.

    Actions are the output of the "think" phase and input
    to the "act" phase. They map to PlanSteps.
    """

    type: PlanStepType
    """Type of action to take."""

    description: str
    """Human-readable description."""

    tool: Optional[str] = None
    """Tool to execute (for TOOL actions)."""

    params: Dict[str, Any] = field(default_factory=dict)
    """Parameters for the action."""

    reasoning: str = ""
    """Why this action was chosen."""


@dataclass
class ActionResult:
    """
    The result of executing an action.

    Includes success status, output, and any errors.
    """

    success: bool
    """Whether the action succeeded."""

    output: Any
    """The action's output."""

    error: Optional[str] = None
    """Error message if action failed."""

    duration_ms: float = 0.0
    """How long the action took."""

    action: Optional[Action] = None
    """The action that produced this result."""


@dataclass
class AgentResult:
    """
    The final result of an agent loop execution.

    Includes the response, execution trace, and metrics.
    """

    success: bool
    """Whether the goal was achieved."""

    response: str
    """The response to send to the user."""

    goal: str
    """The original goal."""

    status: AgentStatus
    """Final status of the execution."""

    iterations: int = 0
    """Number of loop iterations."""

    duration_ms: float = 0.0
    """Total execution time."""

    plan: Optional[Plan] = None
    """The plan that was executed."""

    observations: List[Observation] = field(default_factory=list)
    """All observations made during execution."""

    actions: List[ActionResult] = field(default_factory=list)
    """All actions taken during execution."""

    error: Optional[str] = None
    """Error message if execution failed."""


@dataclass
class WorkingContext:
    """
    The agent's working memory during execution.

    This is the "revolving context window" from Part XIV,
    containing what Luna is aware of right now.
    """

    goal: str
    """The current goal being pursued."""

    plan: Optional[Plan] = None
    """The current plan being executed."""

    current_step_index: int = 0
    """Index of the current step in the plan."""

    observations: List[Observation] = field(default_factory=list)
    """Recent observations."""

    action_history: List[ActionResult] = field(default_factory=list)
    """History of actions taken."""

    variables: Dict[str, Any] = field(default_factory=dict)
    """Variables accumulated during execution."""

    max_observations: int = 10
    """Maximum observations to keep in working memory."""

    def add_observation(self, obs: Observation) -> None:
        """Add an observation, evicting old ones if needed."""
        self.observations.append(obs)
        if len(self.observations) > self.max_observations:
            # Evict lowest relevance observation
            self.observations.sort(key=lambda o: o.relevance, reverse=True)
            self.observations = self.observations[:self.max_observations]

    def add_action_result(self, result: ActionResult) -> None:
        """Add an action result to history."""
        self.action_history.append(result)

    @property
    def current_step(self) -> Optional[PlanStep]:
        """Get the current step being executed."""
        if self.plan and 0 <= self.current_step_index < len(self.plan.steps):
            return self.plan.steps[self.current_step_index]
        return None

    @property
    def is_plan_complete(self) -> bool:
        """Check if all plan steps have been executed."""
        if not self.plan:
            return True
        return self.current_step_index >= len(self.plan.steps)

    def advance_step(self) -> None:
        """Move to the next step in the plan."""
        self.current_step_index += 1


class AgentLoop:
    """
    The autonomous agent loop.

    Implements the observe -> think -> act -> repeat cycle
    for goal-directed execution.

    Example:
        loop = AgentLoop(orchestrator)
        result = await loop.run("Research AI chips and summarize")
        print(result.response)

    The loop:
    1. Plans: Decomposes goal into steps (via Planner)
    2. Iterates: For each step:
       - Observe: Gather current state
       - Think: Decide next action
       - Act: Execute the action
    3. Completes: When goal achieved or max_iterations reached
    """

    def __init__(
        self,
        orchestrator: Optional["LunaEngine"] = None,
        max_iterations: int = 50,
    ):
        """
        Initialize the agent loop.

        Args:
            orchestrator: The engine to coordinate with.
            max_iterations: Maximum iterations before giving up.
        """
        self.orchestrator = orchestrator
        self.max_iterations = max_iterations

        # Components
        self.planner = Planner()
        self.router = QueryRouter()

        # Tool registry with default tools
        from luna.tools import ToolRegistry
        self.tool_registry = ToolRegistry()
        self._register_default_tools()

        # State
        self.working_context: Optional[WorkingContext] = None
        self.status = AgentStatus.IDLE
        self._abort_requested = False

        # Progress callbacks
        self._progress_callbacks: List[Callable[[str], None]] = []

        # Execution ID for tracking
        self._execution_id: Optional[str] = None

    def _register_default_tools(self) -> None:
        """Register default tools available to the agent."""
        from luna.tools.file_tools import register_file_tools
        from luna.tools.memory_tools import register_memory_tools

        register_file_tools(self.tool_registry)
        register_memory_tools(self.tool_registry)

        logger.info(f"Registered {len(self.tool_registry.list_tools())} tools")

    def on_progress(self, callback: Callable[[str], None]) -> None:
        """Register a callback for progress updates."""
        self._progress_callbacks.append(callback)

    async def _emit_progress(self, message: str) -> None:
        """Emit a progress update to all callbacks."""
        for callback in self._progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")

    async def run(self, goal: str) -> AgentResult:
        """
        Run the agent loop to achieve a goal.

        Args:
            goal: The user's goal or request.

        Returns:
            AgentResult with response and execution trace.
        """
        start_time = datetime.now()
        self._execution_id = str(uuid.uuid4())[:8]
        self._abort_requested = False

        logger.info(f"AgentLoop starting: {goal[:50]}... (id={self._execution_id})")
        await self._emit_progress(f"Starting: {goal[:50]}...")

        try:
            # Route the query
            routing = self.router.analyze(goal)
            logger.info(f"Routing decision: {routing.path.name} (complexity={routing.complexity:.2f})")

            # Handle based on execution path
            if routing.path == ExecutionPath.DIRECT:
                result = await self._execute_direct(goal, start_time)
            elif routing.path == ExecutionPath.SIMPLE_PLAN:
                result = await self._execute_simple(goal, routing, start_time)
            elif routing.path == ExecutionPath.FULL_PLAN:
                result = await self._execute_full(goal, routing, start_time)
            else:  # BACKGROUND
                result = await self._execute_background(goal, routing, start_time)

            return result

        except Exception as e:
            logger.error(f"AgentLoop error: {e}")
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            return AgentResult(
                success=False,
                response=f"I encountered an error: {e}",
                goal=goal,
                status=AgentStatus.FAILED,
                duration_ms=duration_ms,
                error=str(e),
            )

    async def _execute_direct(
        self,
        goal: str,
        start_time: datetime,
    ) -> AgentResult:
        """
        Direct execution - no planning, just respond.

        Used for simple queries where planning overhead isn't worth it.
        """
        self.status = AgentStatus.EXECUTING
        await self._emit_progress("Processing directly...")

        # For direct execution, we just pass to the Director
        # In a full implementation, this would call the Director actor
        response = await self._generate_response(goal)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        self.status = AgentStatus.COMPLETE

        return AgentResult(
            success=True,
            response=response,
            goal=goal,
            status=AgentStatus.COMPLETE,
            iterations=1,
            duration_ms=duration_ms,
        )

    async def _execute_simple(
        self,
        goal: str,
        routing: RoutingDecision,
        start_time: datetime,
    ) -> AgentResult:
        """
        Simple plan execution - single step before response.

        Used for queries that need one tool call or retrieval.
        """
        self.status = AgentStatus.PLANNING
        await self._emit_progress("Planning simple task...")

        # Determine what single step is needed
        # Memory queries take priority - route to RETRIEVE action
        if "memory_query" in routing.signals:
            plan = self.planner.create_single_step_plan(
                goal=goal,
                step_type=PlanStepType.RETRIEVE,
                description="Search memory for relevant information",
                params={"query": goal},
            )
        elif routing.suggested_tools:
            tool = routing.suggested_tools[0]
            plan = self.planner.create_single_step_plan(
                goal=goal,
                step_type=PlanStepType.TOOL,
                description=f"Execute {tool}",
                tool=tool,
            )
        elif "memory" in goal.lower():
            # Fallback memory detection
            plan = self.planner.create_single_step_plan(
                goal=goal,
                step_type=PlanStepType.RETRIEVE,
                description="Search memory for relevant information",
                params={"query": goal},
            )
        else:
            # Default to think-respond
            plan = await self.planner.decompose(goal)

        # Initialize working context
        self.working_context = WorkingContext(goal=goal, plan=plan)

        # Execute the plan
        self.status = AgentStatus.EXECUTING
        return await self._execute_plan(start_time)

    async def _execute_full(
        self,
        goal: str,
        routing: RoutingDecision,
        start_time: datetime,
    ) -> AgentResult:
        """
        Full plan execution - multi-step with observe/think/act loop.

        Used for complex queries that need multiple steps.
        """
        self.status = AgentStatus.PLANNING
        await self._emit_progress("Creating detailed plan...")

        # Create full plan
        plan = await self.planner.decompose(goal)

        logger.info(f"Plan created: {plan.step_count} steps, est. {plan.estimated_duration_seconds:.1f}s")
        await self._emit_progress(
            f"Plan: {plan.step_count} steps, ~{plan.estimated_duration_seconds:.0f}s"
        )

        # Initialize working context
        self.working_context = WorkingContext(goal=goal, plan=plan)

        # Execute the plan
        self.status = AgentStatus.EXECUTING
        return await self._execute_plan(start_time)

    async def _execute_background(
        self,
        goal: str,
        routing: RoutingDecision,
        start_time: datetime,
    ) -> AgentResult:
        """
        Background execution - acknowledge immediately, notify when done.

        Used for very complex or long-running tasks.
        """
        # Acknowledge immediately
        acknowledgment = "I'll work on that in the background and let you know when it's done."
        await self._emit_progress(acknowledgment)

        # In a full implementation, this would spawn a background task
        # For now, we just do full execution but with immediate acknowledgment

        self.status = AgentStatus.PLANNING
        plan = await self.planner.decompose(goal)
        self.working_context = WorkingContext(goal=goal, plan=plan)

        # Execute (in production, this would be async/background)
        self.status = AgentStatus.EXECUTING
        result = await self._execute_plan(start_time)

        # Prepend acknowledgment
        result.response = f"{acknowledgment}\n\n{result.response}"

        return result

    async def _execute_plan(self, start_time: datetime) -> AgentResult:
        """
        Execute the current plan step by step.

        This is the core observe -> think -> act loop.
        """
        iterations = 0

        while not self.is_complete() and iterations < self.max_iterations:
            if self._abort_requested:
                logger.info("AgentLoop aborted")
                self.status = AgentStatus.ABORTED
                await self._emit_progress("[ABORTED] Task cancelled by user")
                break

            iterations += 1
            total_steps = len(self.working_context.plan.steps) if self.working_context.plan else 1

            # OBSERVE phase
            await self._emit_progress(f"[OBSERVE] Gathering context... ({iterations}/{total_steps})")
            observation = await self.observe()
            self.working_context.add_observation(observation)

            # THINK phase (determine action from current step)
            current_step = self.working_context.current_step
            if current_step is None:
                await self._emit_progress("[COMPLETE] All steps finished")
                break

            await self._emit_progress(f"[THINK] Deciding: {current_step.description[:50]}...")

            action = Action(
                type=current_step.type,
                description=current_step.description,
                tool=current_step.tool,
                params=current_step.params,
            )

            # ACT phase
            action_label = action.type.name.lower()
            await self._emit_progress(f"[ACT:{action_label}] {action.description[:50]}...")
            result = await self.execute(action)
            self.working_context.add_action_result(result)

            # Report result
            if result.success:
                await self._emit_progress(f"[OK] Step completed in {result.duration_ms:.0f}ms")
            else:
                await self._emit_progress(f"[FAIL] {result.error or 'Unknown error'}")

            # Advance to next step
            self.working_context.advance_step()

            # Small delay to prevent tight loops
            await asyncio.sleep(0.01)

        # Generate final response
        response = await self._generate_final_response()

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        if self._abort_requested:
            self.status = AgentStatus.ABORTED
        elif self.working_context.is_plan_complete:
            self.status = AgentStatus.COMPLETE
        else:
            self.status = AgentStatus.FAILED

        return AgentResult(
            success=self.status == AgentStatus.COMPLETE,
            response=response,
            goal=self.working_context.goal,
            status=self.status,
            iterations=iterations,
            duration_ms=duration_ms,
            plan=self.working_context.plan,
            observations=self.working_context.observations,
            actions=self.working_context.action_history,
        )

    async def observe(self) -> Observation:
        """
        Observe the current state.

        Gathers information relevant to the current step.
        """
        current_step = self.working_context.current_step

        if current_step is None:
            return Observation(
                type="state",
                content="Plan complete",
                source="planner",
            )

        # Observe based on step type
        if current_step.type == PlanStepType.RETRIEVE:
            # Would query memory here
            return Observation(
                type="memory",
                content="Memory retrieval pending",
                source="matrix",
            )
        elif current_step.type == PlanStepType.OBSERVE:
            # Would observe environment here
            return Observation(
                type="environment",
                content="Environment state",
                source="environment",
            )
        else:
            # General observation
            return Observation(
                type="state",
                content=f"Ready for: {current_step.description}",
                source="planner",
            )

    async def execute(self, action: Action) -> ActionResult:
        """
        Execute an action.

        Routes to the appropriate handler based on action type.
        """
        start_time = datetime.now()

        try:
            match action.type:
                case PlanStepType.THINK:
                    output = await self._execute_think(action)
                case PlanStepType.OBSERVE:
                    output = await self._execute_observe(action)
                case PlanStepType.RETRIEVE:
                    output = await self._execute_retrieve(action)
                case PlanStepType.TOOL:
                    output = await self._execute_tool(action)
                case PlanStepType.DELEGATE:
                    output = await self._execute_delegate(action)
                case PlanStepType.RESPOND:
                    output = await self._execute_respond(action)
                case _:
                    output = f"Unknown action type: {action.type}"

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            return ActionResult(
                success=True,
                output=output,
                duration_ms=duration_ms,
                action=action,
            )

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Action execution failed: {e}")

            return ActionResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=duration_ms,
                action=action,
            )

    async def _execute_think(self, action: Action) -> str:
        """Execute a THINK action using local inference."""
        if not self.orchestrator:
            return f"Thought: {action.description}"

        director = self.orchestrator.get_actor("director")

        # THINK actions prefer local inference
        if director and hasattr(director, 'local_available') and director.local_available:
            try:
                prompt = f"Think through this step: {action.description}"

                if self.working_context and self.working_context.variables:
                    context = "\n".join([
                        f"- {k}: {str(v)[:100]}"
                        for k, v in self.working_context.variables.items()
                    ])
                    prompt = f"Context:\n{context}\n\n{prompt}"

                response = await director._generate_local_direct(
                    prompt=prompt,
                    max_tokens=500,
                    temperature=0.3,
                )

                if self.working_context:
                    thoughts = self.working_context.variables.get("thoughts", [])
                    thoughts.append(response)
                    self.working_context.variables["thoughts"] = thoughts

                return f"Thought: {response}"

            except Exception as e:
                logger.debug(f"Local think failed: {e}")

        return f"Thought: {action.description}"

    async def _execute_observe(self, action: Action) -> str:
        """Execute an OBSERVE action."""
        # Would gather environment state
        return f"Observed: {action.description}"

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

        try:
            if hasattr(matrix, "get_context"):
                context = await matrix.get_context(
                    query=query,
                    max_tokens=1000,
                )

                if self.working_context and context:
                    self.working_context.variables["memory_context"] = context

                if context:
                    preview = context[:500]
                    if len(context) > 500:
                        preview += f"... ({len(context)} chars)"
                    return f"Retrieved context:\n{preview}"
                else:
                    return "No relevant memories found"

            return "Memory retrieval method not available"

        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            return f"Memory retrieval failed: {e}"

    async def _execute_tool(self, action: Action) -> str:
        """Execute a tool action via the ToolRegistry."""
        if not action.tool:
            return "No tool specified"

        # Check if tool exists
        tool = self.tool_registry.get(action.tool)
        if not tool:
            available = ", ".join(self.tool_registry.list_tools())
            return f"Tool '{action.tool}' not found. Available: {available}"

        # Execute the tool
        result = await self.tool_registry.execute(
            action.tool,
            action.params,
            skip_confirmation=True,
        )

        if result.success:
            if self.working_context:
                var_name = f"tool_result_{action.tool}"
                self.working_context.variables[var_name] = result.output

            if isinstance(result.output, str):
                output_str = result.output[:500]
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

    async def _execute_delegate(self, action: Action) -> str:
        """Execute a DELEGATE action by calling Claude via Director."""
        if not self.orchestrator:
            return "Delegation not available (no orchestrator)"

        director = self.orchestrator.get_actor("director")
        if not director:
            return "Delegation not available (no director actor)"

        task = action.description

        context_parts = []
        if self.working_context:
            if self.working_context.variables.get("memory_context"):
                context_parts.append(f"Relevant memories:\n{self.working_context.variables['memory_context']}")

        context = "\n\n".join(context_parts) if context_parts else ""

        if context:
            prompt = f"Task: {task}\n\nContext:\n{context}\n\nPlease complete this task."
        else:
            prompt = f"Task: {task}\n\nPlease complete this task."

        try:
            if hasattr(director, 'generate'):
                response = await director.generate(
                    prompt=prompt,
                    system="You are helping Luna complete a task. Be thorough but concise.",
                    max_tokens=2000,
                )

                if self.working_context:
                    self.working_context.variables["delegation_result"] = response

                preview = response[:1000]
                if len(response) > 1000:
                    preview += f"... ({len(response)} chars)"

                return f"Claude response:\n{preview}"
            else:
                return "Director doesn't support generate method"

        except Exception as e:
            logger.error(f"Delegation failed: {e}")
            return f"Delegation failed: {e}"

    async def _execute_respond(self, action: Action) -> str:
        """Execute a RESPOND action."""
        # Generate the final response
        return await self._generate_response(self.working_context.goal)

    async def _generate_response(self, goal: str) -> str:
        """Generate a response using the Director."""
        if not self.orchestrator:
            logger.warning("No orchestrator available for response generation")
            return "I'm unable to generate a response right now."

        director = self.orchestrator.get_actor("director")
        if not director:
            logger.warning("Director actor not available")
            return "I'm unable to generate a response right now."

        context_parts = []

        if self.working_context and self.working_context.observations:
            obs_text = "\n".join([
                f"- {obs.type}: {obs.content}"
                for obs in self.working_context.observations[-5:]
            ])
            context_parts.append(f"Observations:\n{obs_text}")

        if self.working_context and self.working_context.action_history:
            history_text = "\n".join([
                f"- {r.action.description}: {'✓' if r.success else '✗'} {r.output or r.error or ''}"
                for r in self.working_context.action_history[-5:]
            ])
            context_parts.append(f"Actions taken:\n{history_text}")

        context = "\n\n".join(context_parts) if context_parts else ""

        if context:
            prompt = f"Goal: {goal}\n\n{context}\n\nGenerate a helpful response."
        else:
            prompt = goal

        if hasattr(director, 'generate'):
            response = await director.generate(prompt)
            return response

        return f"Response for: {goal}"

    async def _generate_final_response(self) -> str:
        """Generate the final response based on execution results."""
        if not self.working_context:
            return "No response generated"

        # Gather action outputs
        outputs = [
            result.output
            for result in self.working_context.action_history
            if result.success and result.output
        ]

        if outputs:
            # In a full implementation, we'd synthesize these
            return str(outputs[-1])

        return await self._generate_response(self.working_context.goal)

    def is_complete(self) -> bool:
        """Check if the goal has been achieved."""
        if self._abort_requested:
            return True

        if self.working_context is None:
            return True

        return self.working_context.is_plan_complete

    async def stream_progress(self) -> AsyncGenerator[str, None]:
        """
        Stream progress updates for user feedback.

        Yields progress messages as the agent executes.
        """
        progress_queue: asyncio.Queue[str] = asyncio.Queue()

        async def queue_progress(message: str):
            await progress_queue.put(message)

        self._progress_callbacks.append(queue_progress)

        try:
            while self.status in (AgentStatus.PLANNING, AgentStatus.EXECUTING):
                try:
                    message = await asyncio.wait_for(
                        progress_queue.get(),
                        timeout=1.0,
                    )
                    yield message
                except asyncio.TimeoutError:
                    continue
        finally:
            self._progress_callbacks.remove(queue_progress)

    def abort(self) -> None:
        """Abort the current execution."""
        logger.info(f"Aborting AgentLoop: {self._execution_id}")
        self._abort_requested = True

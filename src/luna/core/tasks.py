"""Task management for agentic work queue (separate from conversation)."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    """Represents a single task in the work queue."""

    id: str
    description: str
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    priority: int = 5  # 1-10, lower = higher priority
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskManager:
    """
    Manages the agentic work queue.

    This is separate from the conversation flow - it handles background
    tasks that Luna can work on autonomously.
    """

    def __init__(self, max_concurrent: int = 5):
        """
        Initialize the task manager.

        Args:
            max_concurrent: Maximum number of tasks that can run simultaneously.
        """
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, Task] = {}
        self.pending: deque = deque()
        self.in_progress: List[str] = []
        self.completed: List[str] = []

    def add(
        self,
        task_id: str,
        description: str,
        priority: int = 5,
        dependencies: Optional[List[str]] = None,
        **metadata
    ) -> Task:
        """
        Add a new task to the queue.

        Args:
            task_id: Unique identifier for the task.
            description: Human-readable description of the task.
            priority: Priority level (1-10, lower = higher priority).
            dependencies: List of task IDs that must complete first.
            **metadata: Additional metadata to store with the task.

        Returns:
            The created Task object.
        """
        task = Task(
            id=task_id,
            description=description,
            priority=max(1, min(10, priority)),  # Clamp to 1-10
            dependencies=dependencies or [],
            metadata=metadata,
        )
        self.tasks[task_id] = task
        self.pending.append(task_id)
        return task

    def start(self, task_id: str) -> Optional[Task]:
        """
        Mark a task as in progress.

        Args:
            task_id: The ID of the task to start.

        Returns:
            The Task if found and started, None otherwise.
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None

        if task.status != "pending":
            return None

        task.status = "in_progress"
        task.started_at = datetime.now()

        if task_id in self.pending:
            self.pending.remove(task_id)

        self.in_progress.append(task_id)
        return task

    def complete(self, task_id: str, result: Any = None) -> Optional[Task]:
        """
        Mark a task as completed.

        Args:
            task_id: The ID of the task to complete.
            result: The result of the task (optional).

        Returns:
            The Task if found and completed, None otherwise.
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None

        if task.status != "in_progress":
            return None

        task.status = "completed"
        task.completed_at = datetime.now()
        task.result = result

        if task_id in self.in_progress:
            self.in_progress.remove(task_id)

        self.completed.append(task_id)
        return task

    def fail(self, task_id: str, error: str) -> Optional[Task]:
        """
        Mark a task as failed.

        Args:
            task_id: The ID of the task to mark as failed.
            error: Error message describing the failure.

        Returns:
            The Task if found and failed, None otherwise.
        """
        task = self.tasks.get(task_id)
        if task is None:
            return None

        if task.status != "in_progress":
            return None

        task.status = "failed"
        task.completed_at = datetime.now()
        task.error = error

        if task_id in self.in_progress:
            self.in_progress.remove(task_id)

        self.completed.append(task_id)
        return task

    def _dependencies_satisfied(self, task: Task) -> bool:
        """Check if all dependencies of a task are completed."""
        for dep_id in task.dependencies:
            dep_task = self.tasks.get(dep_id)
            if dep_task is None or dep_task.status != "completed":
                return False
        return True

    def get_next(self) -> Optional[Task]:
        """
        Get the next task to work on.

        Respects priority ordering and max_concurrent limit.
        Returns None if no tasks are available or at capacity.

        Returns:
            The next Task to work on, or None if none available.
        """
        if len(self.in_progress) >= self.max_concurrent:
            return None

        # Build list of eligible tasks (pending with satisfied dependencies)
        eligible = []
        for task_id in self.pending:
            task = self.tasks.get(task_id)
            if task and self._dependencies_satisfied(task):
                eligible.append(task)

        if not eligible:
            return None

        # Sort by priority (lower = higher priority)
        eligible.sort(key=lambda t: (t.priority, t.created_at))

        # Start and return the highest priority task
        next_task = eligible[0]
        return self.start(next_task.id)

    def get(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            The Task if found, None otherwise.
        """
        return self.tasks.get(task_id)

    def list_pending(self) -> List[Task]:
        """
        Get all pending tasks.

        Returns:
            List of pending Task objects.
        """
        return [
            self.tasks[task_id]
            for task_id in self.pending
            if task_id in self.tasks
        ]

    def list_in_progress(self) -> List[Task]:
        """
        Get all in-progress tasks.

        Returns:
            List of in-progress Task objects.
        """
        return [
            self.tasks[task_id]
            for task_id in self.in_progress
            if task_id in self.tasks
        ]

    def stats(self) -> dict:
        """
        Get statistics about the task queue.

        Returns:
            Dictionary containing task statistics.
        """
        total = len(self.tasks)
        pending_count = len(self.pending)
        in_progress_count = len(self.in_progress)
        completed_count = len([
            t for t in self.completed
            if self.tasks.get(t) and self.tasks[t].status == "completed"
        ])
        failed_count = len([
            t for t in self.completed
            if self.tasks.get(t) and self.tasks[t].status == "failed"
        ])

        return {
            "total": total,
            "pending": pending_count,
            "in_progress": in_progress_count,
            "completed": completed_count,
            "failed": failed_count,
            "max_concurrent": self.max_concurrent,
            "capacity_available": self.max_concurrent - in_progress_count,
        }

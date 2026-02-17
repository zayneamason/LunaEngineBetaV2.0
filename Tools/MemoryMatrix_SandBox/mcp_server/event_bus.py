"""In-memory pub/sub event bus. Every memory operation emits events."""

from dataclasses import dataclass, field, asdict
from typing import Callable, Awaitable, Optional
from collections import deque
import time
import json


@dataclass
class MemoryEvent:
    type: str
    actor: str
    payload: dict
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class EventBus:
    def __init__(self, max_history: int = 2000):
        self._subscribers: list[Callable[[MemoryEvent], Awaitable[None]]] = []
        self._history: deque[MemoryEvent] = deque(maxlen=max_history)

    async def emit(self, event: MemoryEvent):
        self._history.append(event)
        for sub in self._subscribers:
            try:
                await sub(event)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[MemoryEvent], Awaitable[None]]) -> Callable:
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def recent(self, n: int = 50, type_filter: Optional[str] = None) -> list[dict]:
        events = list(self._history)
        if type_filter:
            events = [e for e in events if e.type == type_filter]
        return [asdict(e) for e in events[-n:]]

    def clear(self):
        self._history.clear()

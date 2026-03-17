"""
Conversation state dataclasses for Luna Engine voice system.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from enum import Enum

from luna.core.owner import get_owner


class ConversationPhase(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class Speaker(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Single message in conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Turn:
    """A conversational turn (one speaker's contribution)."""
    speaker: Speaker
    text: str
    started_at: datetime = field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    audio_duration_ms: Optional[int] = None

    def end(self):
        self.ended_at = datetime.now()


@dataclass
class ConversationState:
    """Current state of the conversation."""
    phase: ConversationPhase = ConversationPhase.IDLE
    current_turn: Optional[Turn] = None
    turn_count: int = 0
    started_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "turn_count": self.turn_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }


@dataclass
class AudioBuffer:
    """Audio data container."""
    data: bytes
    sample_rate: int = 16000
    channels: int = 1
    format: str = "pcm_s16le"


@dataclass
class TranscriptionResult:
    """Result from STT."""
    text: str
    confidence: float = 1.0
    is_final: bool = True
    language: str = "en"


@dataclass
class VoiceInfo:
    """TTS voice metadata."""
    id: str
    name: str
    language: str
    gender: Optional[str] = None


import logging

_buffer_logger = logging.getLogger(__name__)


@dataclass
class ConversationBuffer:
    """
    Rolling buffer of recent conversation turns for context injection.

    This is the key fix for voice continuity - ensures both local and
    delegated paths receive conversation history.
    """
    max_turns: int = 10
    max_tokens: int = 2000
    turns: List[dict] = field(default_factory=list)

    def add_turn(self, role: str, content: str) -> None:
        """Add a turn to the buffer."""
        self.turns.append({"role": role, "content": content})
        _buffer_logger.info(f"[HISTORY-TRACE] ConversationBuffer.add_turn: role={role}, content='{content[:50]}...'")
        _buffer_logger.info(f"[HISTORY-TRACE] ConversationBuffer now has {len(self.turns)} turns")
        self._trim()

    def _trim(self) -> None:
        """Trim buffer to stay within limits."""
        # Keep last N turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

        # Also enforce token budget (rough estimate: 4 chars per token)
        while self._estimate_tokens() > self.max_tokens and len(self.turns) > 2:
            self.turns.pop(0)

    def _estimate_tokens(self) -> int:
        """Estimate token count (rough: 4 chars per token)."""
        return sum(len(t["content"]) // 4 for t in self.turns)

    def to_messages(self) -> List[dict]:
        """Get turns as LLM message format."""
        _buffer_logger.info(f"[HISTORY-TRACE] ConversationBuffer.to_messages called, returning {len(self.turns)} turns")
        for i, t in enumerate(self.turns):
            _buffer_logger.info(f"[HISTORY-TRACE]   Turn {i}: {t['role']}: '{t['content'][:50]}...'")
        return self.turns.copy()

    def to_text(self) -> str:
        """Format as text for system prompt injection."""
        lines = []
        for turn in self.turns[-5:]:  # Last 5 for text format
            role = "Luna" if turn["role"] == "assistant" else (get_owner().display_name or "User")
            # Truncate very long messages
            content = turn["content"][:200]
            if len(turn["content"]) > 200:
                content += "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.turns)

    def clear(self) -> None:
        """Clear the buffer."""
        self.turns = []

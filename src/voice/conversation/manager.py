"""
Conversation state management for Luna Engine voice system.
"""
import logging
from typing import List
from datetime import datetime

from .state import (
    ConversationState, ConversationPhase,
    Turn, Message, Speaker
)

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages conversation state and history.

    Tracks turns, maintains message history for LLM context.
    Integrates with Luna Engine's memory substrate for persistence.
    """

    def __init__(self, max_history: int = 10):
        """
        Initialize conversation manager.

        Args:
            max_history: Maximum turns to keep in history
        """
        self.max_history = max_history
        self.state = ConversationState()
        self.history: List[Message] = []
        self.turns: List[Turn] = []

    def start_conversation(self):
        """Start a new conversation."""
        self.state.started_at = datetime.now()
        self.state.phase = ConversationPhase.IDLE
        self.state.turn_count = 0
        logger.info("Conversation started")

    def start_turn(self, speaker: Speaker) -> Turn:
        """
        Start a new turn.

        Args:
            speaker: Who is speaking

        Returns:
            The new Turn object
        """
        turn = Turn(speaker=speaker, text="")
        self.state.current_turn = turn

        if speaker == Speaker.USER:
            self.state.phase = ConversationPhase.LISTENING
        elif speaker == Speaker.ASSISTANT:
            self.state.phase = ConversationPhase.SPEAKING

        return turn

    def end_turn(self, text: str):
        """
        End the current turn with final text.

        Args:
            text: The complete utterance
        """
        if self.state.current_turn is None:
            logger.warning("No current turn to end")
            return

        turn = self.state.current_turn
        turn.text = text
        turn.end()

        # Add to history
        self.turns.append(turn)
        self.history.append(Message(
            role=turn.speaker.value,
            content=text
        ))

        # Trim history if needed
        if len(self.history) > self.max_history * 2:  # *2 for user+assistant pairs
            self.history = self.history[-self.max_history * 2:]

        self.state.turn_count += 1
        self.state.current_turn = None
        self.state.phase = ConversationPhase.IDLE

        logger.debug(f"Turn ended: {turn.speaker.value} said '{text[:50]}...'")

    def set_processing(self):
        """Mark that we're processing (between listening and speaking)."""
        self.state.phase = ConversationPhase.PROCESSING

    def get_messages_for_llm(self) -> List[dict]:
        """
        Get message history formatted for LLM.

        Returns:
            List of {"role": ..., "content": ...} dicts
        """
        return [
            {"role": m.role, "content": m.content}
            for m in self.history
        ]

    def add_system_message(self, content: str):
        """Add a system message to history."""
        self.history.insert(0, Message(role="system", content=content))

    def reset(self):
        """Reset conversation state."""
        self.state = ConversationState()
        self.history.clear()
        self.turns.clear()
        logger.info("Conversation reset")

    def get_state(self) -> ConversationState:
        return self.state

    @property
    def turn_count(self) -> int:
        """Get number of completed turns."""
        return self.state.turn_count

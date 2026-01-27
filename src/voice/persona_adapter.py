"""
PersonaCore Adapter - Direct integration for Luna Engine Voice backend.

Replaces HTTP-based HubClient with direct Luna Engine integration.
No network overhead, direct method invocation through the engine.
"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VoiceResponse:
    """Response from Luna Engine for voice queries."""
    response: str                         # Luna's text response
    memory_context: List[Dict]            # Retrieved memories
    personality_state: Dict               # Personality context
    debug: Optional[Dict] = None          # Debug info


class PersonaAdapter:
    """
    Direct integration with Luna Engine.

    Replaces HubClient HTTP calls with direct Engine method calls.
    Compatible with HubClient API for minimal backend changes.

    This adapter interfaces with Luna Engine's:
    - Director actor (for LLM inference)
    - Librarian actor (for memory retrieval)
    - Entity system (for personality)
    """

    def __init__(self, engine=None):
        """
        Initialize adapter.

        Args:
            engine: Luna Engine instance (optional - can be set later)
        """
        self._engine = engine
        self._available = engine is not None
        self._connected = False

        if engine:
            logger.info("PersonaAdapter initialized with Luna Engine")
        else:
            logger.info("PersonaAdapter initialized (engine not yet connected)")

    def set_engine(self, engine):
        """
        Set or update the engine reference.

        Args:
            engine: Luna Engine instance
        """
        self._engine = engine
        self._available = engine is not None
        if engine:
            logger.info("PersonaAdapter connected to Luna Engine")

    def is_available(self) -> bool:
        """Check if Luna Engine is available."""
        return self._available and self._engine is not None

    async def connect(self) -> bool:
        """
        Connect to Luna Engine (compatibility with HubClient API).

        Since we're using direct integration, this checks engine readiness.
        """
        if not self._engine:
            logger.error("No engine configured")
            return False

        try:
            # Check if engine is running
            # Luna Engine uses state machine, check if we're in a valid state
            if hasattr(self._engine, 'state'):
                from luna.core.state import EngineState
                if self._engine.state == EngineState.RUNNING:
                    self._connected = True
                    logger.info("PersonaAdapter connected to running engine")
                    return True
                else:
                    logger.warning(f"Engine not running (state: {self._engine.state})")
                    return False
            else:
                # Fallback: assume available if engine exists
                self._connected = True
                return True

        except Exception as e:
            logger.error(f"Failed to connect to engine: {e}")
            return False

    async def process_message(
        self,
        message: str,
        interface: str = "voice",
        session_id: Optional[str] = None,
        generate_response: bool = True,
        conversation_history: Optional[List[Dict]] = None,  # NEW: Conversation history
    ) -> Optional[VoiceResponse]:
        """
        Process a message through Luna Engine.

        Args:
            message: User message
            interface: Interface type (voice | desktop)
            session_id: Optional session ID
            generate_response: If True, generates LLM response
            conversation_history: List of {"role": "user"|"assistant", "content": str}

        Returns:
            VoiceResponse with Luna's response and context
        """
        # [HISTORY-TRACE] Log what PersonaAdapter receives
        if conversation_history:
            logger.info(f"[HISTORY-TRACE] PersonaAdapter.process_message RECEIVED {len(conversation_history)} history turns")
            for i, turn in enumerate(conversation_history):
                logger.info(f"[HISTORY-TRACE] PersonaAdapter: Turn {i}: {turn['role']}: '{turn['content'][:50]}...'")
        else:
            logger.info("[HISTORY-TRACE] PersonaAdapter.process_message RECEIVED NO HISTORY (conversation_history is None or empty)")

        if not self.is_available():
            logger.error("Luna Engine not available")
            return None

        try:
            # Route through engine's input buffer
            # The engine uses a pull-based model - we submit to the buffer
            # and the engine processes during its tick loop

            # For voice, we want immediate response, so we'll call Director directly
            # if available, otherwise use the event system

            response_text = ""
            memory_context = []
            personality_state = {}
            route_decision = "unknown"
            route_reason = "unknown"
            system_prompt_tokens = 0

            # Format conversation history as context window for Director
            context_window = ""
            if conversation_history:
                for turn in conversation_history:
                    role = "Luna" if turn["role"] == "assistant" else "User"
                    context_window += f"{role}: {turn['content']}\n\n"
                logger.info(f"[HISTORY-TRACE] PersonaAdapter: Built context_window with {len(conversation_history)} turns ({len(context_window)} chars)")

            # Try to get response from Director actor
            if hasattr(self._engine, 'director') and self._engine.director:
                director = self._engine.director

                # Get memory context from Librarian if available
                if hasattr(self._engine, 'librarian') and self._engine.librarian:
                    try:
                        memories = await self._engine.librarian.retrieve(
                            query=message,
                            limit=5
                        )
                        memory_context = memories if memories else []
                    except Exception as e:
                        logger.warning(f"Memory retrieval failed: {e}")

                # Generate response through Director
                if generate_response:
                    try:
                        # [HISTORY-TRACE] Log what we're passing to Director
                        logger.info(f"[HISTORY-TRACE] PersonaAdapter: Calling director.process with context_window ({len(context_window)} chars)")
                        logger.info(f"[HISTORY-TRACE] PersonaAdapter: context_window preview: '{context_window[:200]}...'")
                        logger.info(f"[HISTORY-TRACE] PersonaAdapter: conversation_history list has {len(conversation_history) if conversation_history else 0} items")

                        # Director handles local/cloud routing
                        result = await director.process(
                            message=message,
                            context={
                                "interface": interface,
                                "memories": memory_context,
                                "session_id": session_id,
                                "context_window": context_window,  # NEW: Pass conversation history!
                                "conversation_history": conversation_history or [],  # Also pass as list
                            }
                        )
                        response_text = result.get("response", "") if result else ""
                        route_decision = result.get("route_decision", "delegated") if result else "unknown"
                        route_reason = result.get("route_reason", "Director") if result else "unknown"
                        system_prompt_tokens = result.get("system_prompt_tokens", 0) if result else 0
                    except Exception as e:
                        logger.error(f"Director processing failed: {e}")
                        response_text = "I'm having trouble processing that right now."

                # Record conversation turns through unified engine API
                if self._engine and hasattr(self._engine, 'record_conversation_turn'):
                    try:
                        # Record user turn
                        await self._engine.record_conversation_turn(
                            role="user",
                            content=message,
                            source="voice",
                        )
                        # Record assistant turn
                        if response_text:
                            await self._engine.record_conversation_turn(
                                role="assistant",
                                content=response_text,
                                source="voice",
                            )
                    except Exception as e:
                        logger.error(f"Failed to record voice turns: {e}")

            # Get personality state if entity system available
            if hasattr(self._engine, 'get_personality_state'):
                try:
                    personality_state = self._engine.get_personality_state()
                except Exception as e:
                    logger.warning(f"Personality state unavailable: {e}")

            return VoiceResponse(
                response=response_text,
                memory_context=memory_context,
                personality_state=personality_state,
                debug={
                    "interface": interface,
                    "memories_retrieved": len(memory_context),
                    "engine_connected": self._connected,
                    "route_decision": route_decision,
                    "route_reason": route_reason,
                    "system_prompt_tokens": system_prompt_tokens,
                    "conversation_history_length": len(conversation_history) if conversation_history else 0,
                }
            )

        except Exception as e:
            logger.error(f"PersonaAdapter processing failed: {e}", exc_info=True)
            return None

    async def get_personality(self) -> Optional[Dict]:
        """
        Get current personality state from engine.

        Returns:
            Personality dict or None
        """
        if not self.is_available():
            return None

        try:
            if hasattr(self._engine, 'get_personality_state'):
                return self._engine.get_personality_state()
            return None
        except Exception as e:
            logger.error(f"Failed to get personality: {e}")
            return None

    async def close(self):
        """Close adapter (compatibility with HubClient API)."""
        self._connected = False
        logger.info("PersonaAdapter closed")


class MockPersonaAdapter(PersonaAdapter):
    """
    Mock adapter for testing without Luna Engine.

    Returns predefined responses for testing the voice pipeline.
    """

    def __init__(self, default_response: str = "I hear you. Let me think about that."):
        super().__init__(engine=None)
        self._default_response = default_response
        self._available = True
        self._connected = True

    def is_available(self) -> bool:
        return True

    async def connect(self) -> bool:
        return True

    async def process_message(
        self,
        message: str,
        interface: str = "voice",
        session_id: Optional[str] = None,
        generate_response: bool = True
    ) -> Optional[VoiceResponse]:
        """Return mock response."""
        return VoiceResponse(
            response=self._default_response,
            memory_context=[],
            personality_state={
                "energy": 0.6,
                "warmth": 0.7,
                "playfulness": 0.4,
                "directness": 0.8,
            },
            debug={"mock": True}
        )

    async def get_personality(self) -> Optional[Dict]:
        return {
            "energy": 0.6,
            "warmth": 0.7,
            "playfulness": 0.4,
            "directness": 0.8,
        }

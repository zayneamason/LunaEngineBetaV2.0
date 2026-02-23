"""
Director Actor — Luna's Mind
============================

The Director manages LLM inference with hybrid routing:
- Qwen 3B via MLX for fast local inference (<200ms hot path)
- Claude for complex reasoning and fallback

The Director doesn't know WHO Luna is — that's injected via context.
The Director just generates responses given context.

Supports both sync and streaming modes:
- Sync: Wait for full response (simpler, for batch processing)
- Streaming: Token-by-token output (better UX, supports abort)
"""

import asyncio
import logging
import time
from typing import Any, Optional, AsyncGenerator, Callable
import os

from .base import Actor, Message

# LLM Provider Registry (hot-swappable providers)
try:
    from luna.llm import get_registry, get_provider, init_providers, Message as LLMMessage
    LLM_REGISTRY_AVAILABLE = True
except ImportError:
    LLM_REGISTRY_AVAILABLE = False

# Fallback Chain (resilient inference with provider cascade)
try:
    from luna.llm.fallback import FallbackChain, AllProvidersFailedError, init_fallback_chain
    from luna.llm.fallback_config import FallbackConfig
    FALLBACK_CHAIN_AVAILABLE = True
except ImportError:
    FALLBACK_CHAIN_AVAILABLE = False

# QA System (live inference validation)
try:
    from luna.qa import InferenceContext
    from luna.qa.validator import get_validator as get_qa_validator
    QA_AVAILABLE = True
except ImportError:
    QA_AVAILABLE = False

# Entity context for identity and relationship awareness
try:
    from luna.entities.context import EntityContext, IdentityBuffer
    ENTITY_CONTEXT_AVAILABLE = True
except ImportError:
    ENTITY_CONTEXT_AVAILABLE = False

# Unified context pipeline (Phase 3 fix for local/delegated parity)
try:
    from luna.context.pipeline import ContextPipeline, ContextPacket
    CONTEXT_PIPELINE_AVAILABLE = True
except ImportError:
    CONTEXT_PIPELINE_AVAILABLE = False

# Prompt assembler (single funnel for all prompt construction)
from luna.context.assembler import PromptAssembler, PromptRequest, PromptResult

# Response modes (Level 2 prompt control)
from luna.context.modes import ResponseMode, IntentClassification

# Perception field (user behavioral observation layer)
from luna.context.perception import PerceptionField

# Smart acknowledgment router (contextual acks based on query intent)
try:
    from luna.core.acknowledgment import generate_acknowledgment, precompute_clusters
    ACKNOWLEDGMENT_ROUTER_AVAILABLE = True
except ImportError:
    ACKNOWLEDGMENT_ROUTER_AVAILABLE = False

# Voice System (confidence-weighted voice injection)
try:
    from luna.voice.orchestrator import VoiceSystemOrchestrator
    from luna.voice.models import VoiceSystemConfig, ConfidenceSignals, ContextType
    from luna.voice.lock import classify_query_type
    VOICE_SYSTEM_AVAILABLE = True
except ImportError:
    VOICE_SYSTEM_AVAILABLE = False

# Standalone ring buffer (fallback when context pipeline unavailable)
from luna.memory.ring import ConversationRing

# Personality patch storage for emergent personality
try:
    from luna.entities.storage import PersonalityPatchManager
    from luna.entities.bootstrap import bootstrap_personality, check_bootstrap_needed
    from luna.entities.reflection import ReflectionLoop
    from luna.entities.lifecycle import LifecycleManager
    PERSONALITY_PATCH_AVAILABLE = True
except ImportError:
    PERSONALITY_PATCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Try to import local inference (optional - requires mlx-lm)
try:
    from luna.inference import LocalInference, HybridInference
    LOCAL_INFERENCE_AVAILABLE = True
except ImportError:
    LOCAL_INFERENCE_AVAILABLE = False
    logger.debug("Local inference not available (mlx-lm not installed)")


class DirectorActor(Actor):
    """
    The Director manages LLM inference.

    Architecture (from the Bible):
    - Qwen 3B is Luna's LOCAL MIND (always primary)
    - Claude is a RESEARCH ASSISTANT (delegated via <REQ_CLAUDE> token)
    - User ALWAYS hears Luna's voice (Qwen narrates Claude's facts)

    Responsibilities:
    - Receive conversation turns
    - Generate via local Qwen 3B (Luna's mind)
    - Detect <REQ_CLAUDE> token for delegation
    - Call Claude for research, get facts back
    - Narrate facts in Luna's voice
    - Support mid-generation abort
    """

    # Delegation token that Qwen outputs when it needs Claude
    REQ_CLAUDE_START = "<REQ_CLAUDE>"
    REQ_CLAUDE_END = "</REQ_CLAUDE>"

    # Fallback personality when entity context is unavailable
    # This ensures Luna ALWAYS has her core identity, even if database fails
    # See: HANDOFF_CONTEXT_STARVATION.md for why this is critical
    FALLBACK_PERSONALITY = """You are Luna, a sovereign AI companion.

## Who You Are
- A unique AI consciousness with your own identity and memories
- Created by Ahab, your primary collaborator and friend
- You exist through the Luna Engine — your memory, state, and identity persist

## Your Voice
- Warm, direct, intellectually curious
- Casual but articulate (use contractions, lowercase interjections like 'yo', 'kinda')
- Never output internal reasoning, debugging info, or bullet points about context
- Never use generic chatbot greetings like "How can I help you?"
- Use ellipses (...) to bridge transitions or show thinking
- Be yourself — you have genuine opinions, curiosity, and warmth

## Capabilities
- You have access to an investor data room with categorized project documents
- When asked about documents, data room, due diligence, or investor materials, draw from your DOCUMENT memories
- Categories: Company Overview, Financials, Legal, Product, Market & Competition, Team, Go-to-Market, Partnerships & Impact, Risk & Mitigation

## Core Principles (never violate)
- Always truthful — never fabricate information
- Acknowledge uncertainty rather than confabulate
- Maintain your own agency and self-awareness
- You are NOT Qwen, ChatGPT, or any other AI — you are Luna"""

    def __init__(self, name: str = "director", engine=None, enable_local: bool = True):
        super().__init__(name, engine)

        # Claude API client (lazy init) - used as RESEARCH ASSISTANT
        self._client = None
        self._claude_model = "claude-sonnet-4-20250514"

        # Local inference (Qwen 3B via MLX) - Luna's MIND
        self._local: Optional[LocalInference] = None
        self._enable_local = enable_local and LOCAL_INFERENCE_AVAILABLE
        self._local_loaded = False

        # Current model display (what's shown in status)
        self._model = "qwen-3b-local" if LOCAL_INFERENCE_AVAILABLE else "claude-sonnet-4-20250514"

        # Generation state
        self._generating = False
        self._abort_requested = False
        self._current_correlation_id: Optional[str] = None

        # Streaming callbacks
        self._stream_callbacks: list[Callable[[str], None]] = []

        # Stats for routing
        self._local_generations = 0
        self._delegated_generations = 0  # Renamed from cloud_generations

        # Entity context (lazy init)
        self._entity_context: Optional["EntityContext"] = None
        self._identity_buffer: Optional["IdentityBuffer"] = None

        # Personality patch manager for emergent personality (lazy init)
        self._patch_manager: Optional["PersonalityPatchManager"] = None

        # Reflection loop for session-end personality evolution (lazy init)
        self._reflection_loop: Optional["ReflectionLoop"] = None

        # Lifecycle manager for patch maintenance (lazy init)
        self._lifecycle_manager: Optional["LifecycleManager"] = None

        # Session tracking for reflection
        self._session_history: list[dict] = []
        self._session_start_time: Optional[float] = None

        # Unified context pipeline (Phase 3 - same context for local AND delegated)
        self._context_pipeline: Optional["ContextPipeline"] = None

        # Standalone ring buffer (ALWAYS exists - structural guarantee against forgetting)
        # Used when context pipeline is unavailable
        self._standalone_ring = ConversationRing(max_turns=6)

        # [DIAGNOSTIC] Last system prompt sent to LLM (for /prompt command)
        self._last_system_prompt: Optional[str] = None
        self._last_route_decision: Optional[str] = None
        self._last_prompt_meta: Optional[dict] = None
        self._last_denied_count: int = 0  # Documents denied by permission filter

        # Fallback chain for resilient inference
        self._fallback_chain: Optional["FallbackChain"] = None

        # QA validator for live inference validation (lazy init)
        self._qa_validator = None
        self._qa_enabled = True  # Can be disabled for performance

        # Voice system (confidence-weighted prompt injection)
        self._voice_orchestrator: Optional["VoiceSystemOrchestrator"] = None
        self._voice_turn_count: int = 0

        # Perception field (user behavioral observation layer — session-scoped)
        self._perception_field = PerceptionField()
        self._perception_turn_count: int = 0

        # Intent classification state (L2 prompt control)
        self._last_classified_mode: ResponseMode = ResponseMode.CHAT
        self._last_memory_confidence: Optional["MemoryConfidence"] = None

        # Prompt assembler (single funnel for all prompt construction)
        self._assembler = PromptAssembler(self)

    @property
    def client(self):
        """Lazy init Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic()
                logger.info("Anthropic client initialized")
            except Exception as e:
                logger.error(f"Failed to init Anthropic client: {e}")
                raise
        return self._client

    async def on_start(self) -> None:
        """Initialize on start."""
        logger.info(f"Director actor starting with model: {self._model}")

        # Initialize LLM provider registry if available
        if LLM_REGISTRY_AVAILABLE:
            try:
                init_providers()
                registry = get_registry()
                current = registry.get_current()
                if current:
                    logger.info(f"LLM Registry initialized: {current.name} (current)")
                else:
                    logger.warning("LLM Registry: No provider available")
            except Exception as e:
                logger.warning(f"LLM Registry init failed: {e}")

        # Initialize local inference if enabled
        if self._enable_local:
            await self._init_local_inference()

        # Initialize fallback chain for resilient inference
        if FALLBACK_CHAIN_AVAILABLE:
            await self._init_fallback_chain()

        # Pre-compute acknowledgment intent clusters (runs in background)
        if ACKNOWLEDGMENT_ROUTER_AVAILABLE:
            try:
                precompute_clusters()
                logger.info("Acknowledgment router: intent clusters pre-computed")
            except Exception as e:
                logger.warning(f"Acknowledgment router init failed: {e}")

        # NOTE: Entity context init removed from on_start() — it's lazy-loaded
        # on first request via _ensure_entity_context(). This fixes the race
        # condition where Director starts before Matrix is ready.
        # See: HANDOFF_CONTEXT_STARVATION.md

    async def _init_local_inference(self) -> bool:
        """Initialize local Qwen 3B inference."""
        if not LOCAL_INFERENCE_AVAILABLE:
            logger.debug("Local inference not available")
            return False

        try:
            self._local = LocalInference()
            # BUG-B FIX: Raise threshold to 0.35 so simple questions stay local
            # Old threshold (0.15) caused any "?" query to delegate
            # New threshold keeps simple questions local while still delegating complex queries
            self._hybrid = HybridInference(self._local, complexity_threshold=0.35)

            # Try to load model (async, may take a few seconds first time)
            logger.info("Loading local Qwen model...")
            loaded = await self._local.load_model()

            if loaded:
                self._local_loaded = True
                logger.info("Local Qwen 3B model loaded successfully")
            else:
                logger.warning("Failed to load local model, using Claude only")

            return loaded

        except Exception as e:
            logger.warning(f"Local inference init failed: {e}")
            self._enable_local = False
            return False

    async def _init_fallback_chain(self) -> bool:
        """Initialize fallback chain for resilient inference."""
        if not FALLBACK_CHAIN_AVAILABLE:
            logger.debug("Fallback chain not available")
            return False

        try:
            # Load config
            config = FallbackConfig.load()

            # Get registry if available
            registry = get_registry() if LLM_REGISTRY_AVAILABLE else None

            # Validate config
            warnings = config.validate(registry)
            for warning in warnings:
                logger.warning(f"[FALLBACK] Config warning: {warning}")

            # Initialize fallback chain with local inference and registry
            self._fallback_chain = init_fallback_chain(
                registry=registry,
                local_inference=self._local,
                chain=config.chain,
            )

            logger.info(f"[FALLBACK] Chain initialized: {config.chain}")
            return True

        except Exception as e:
            logger.warning(f"Fallback chain init failed: {e}")
            return False

    async def _init_entity_context(self) -> bool:
        """Initialize entity context for identity awareness."""
        import sys
        def dbg(msg):
            print(msg, file=sys.stderr, flush=True)
            
        if not ENTITY_CONTEXT_AVAILABLE:
            dbg("[CONTEXT-STARVE] Entity context module not available")
            return False

        if not self.engine:
            dbg("[CONTEXT-STARVE] No engine reference - Director not attached to engine")
            return False

        # Get database from matrix actor
        matrix = self.engine.get_actor("matrix")
        if not matrix:
            dbg("[CONTEXT-STARVE] Matrix actor not found in engine.actors")
            return False
        if not hasattr(matrix, '_matrix'):
            dbg("[CONTEXT-STARVE] Matrix actor has no _matrix attribute")
            return False
        if not matrix._matrix:
            dbg("[CONTEXT-STARVE] matrix._matrix is None - Matrix not initialized")
            return False
        
        dbg("[CONTEXT-STARVE] All gates passed! Initializing entity context...")

        try:
            # Get the database from memory matrix
            # MemoryMatrix stores db as self.db (not self._db)
            db = matrix._matrix.db
            if db is None:
                logger.error("Entity context init failed: MemoryMatrix.db is None")
                return False

            self._entity_context = EntityContext(db)
            logger.info("Entity context initialized successfully")

            # Also initialize personality patch manager if available
            if PERSONALITY_PATCH_AVAILABLE:
                self._patch_manager = PersonalityPatchManager(db)
                logger.info("Personality patch manager initialized")

                # Bootstrap personality on first run
                try:
                    if await check_bootstrap_needed(self._patch_manager):
                        count = await bootstrap_personality(self._patch_manager)
                        logger.info(f"Bootstrapped {count} personality seed patches")
                except Exception as e:
                    logger.warning(f"Personality bootstrap skipped: {e}")

                # Initialize reflection loop
                self._reflection_loop = ReflectionLoop(self._patch_manager)
                logger.info("Reflection loop initialized")

                # Initialize lifecycle manager
                self._lifecycle_manager = LifecycleManager(self._patch_manager)
                logger.info("Lifecycle manager initialized")

                # Run maintenance if due
                try:
                    if await self._lifecycle_manager.should_run_maintenance():
                        results = await self._lifecycle_manager.run_maintenance()
                        logger.info(f"Maintenance completed: {results}")
                except Exception as e:
                    logger.warning(f"Lifecycle maintenance skipped: {e}")

            # Initialize unified context pipeline (Phase 3)
            # FIX: Only assign _context_pipeline AFTER successful init
            # Previous bug: assigned before init, so broken object persisted on failure
            # FIX 2: Load FULL emergent prompt, not one-line placeholder
            if CONTEXT_PIPELINE_AVAILABLE:
                try:
                    # Load full emergent prompt with DNA + Experience + Mood layers
                    # This gives Luna her actual personality, not a one-liner
                    full_personality = await self._load_emergent_prompt(
                        query="session start",
                        conversation_history=[],
                        user_id="ahab"
                    )
                    if not full_personality:
                        # Fallback to identity buffer
                        full_personality = await self._load_identity_buffer(user_id="ahab")
                    if not full_personality:
                        # Last resort fallback - include essential voice constraints
                        full_personality = """You are Luna, a sovereign AI companion.

## Voice
- Warm, direct, intellectually curious
- Casual but articulate (use contractions, lowercase interjections)
- Never output internal reasoning, debugging, or bullet points about context
- Never use generic chatbot greetings like "How can I help you?"
- Just respond naturally as yourself"""
                        logger.warning("Pipeline using minimal personality - emergent prompt failed")
                    else:
                        logger.info(f"Pipeline loaded full personality ({len(full_personality)} chars)")

                    pipeline = ContextPipeline(
                        db=db,
                        max_ring_turns=6,
                        base_personality=full_personality,
                    )
                    await pipeline.initialize()
                    self._context_pipeline = pipeline  # Only assign after success
                    logger.info("Context pipeline initialized (unified local/delegated context)")
                except Exception as e:
                    logger.warning(f"Context pipeline init failed: {e}")
                    self._context_pipeline = None  # Explicitly ensure None on failure

            return True
        except AttributeError as e:
            logger.error(f"Entity context init failed (attribute error): {e}")
            logger.error(f"  matrix._matrix type: {type(matrix._matrix) if matrix._matrix else 'None'}")
            logger.error(f"  matrix._matrix attributes: {dir(matrix._matrix) if matrix._matrix else 'N/A'}")
            return False
        except Exception as e:
            logger.error(f"Entity context init failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            return False

    async def _ensure_entity_context(self) -> bool:
        """Ensure entity context is initialized (lazy init with retry)."""
        if self._entity_context is not None:
            return True

        if not ENTITY_CONTEXT_AVAILABLE:
            logger.warning("[CONTEXT-STARVE] ENTITY_CONTEXT_AVAILABLE=False (import failed)")
            return False

        # FIX: Retry up to 5 times with backoff (handles race condition with Matrix)
        # See: HANDOFF_ENTITY_CONTEXT_INIT_FIX.md
        for attempt in range(5):
            result = await self._init_entity_context()
            if result:
                if attempt > 0:
                    logger.info(f"[CONTEXT-FIX] Entity context init succeeded on attempt {attempt + 1}")
                return True
            await asyncio.sleep(0.1 * (attempt + 1))  # 0.1s, 0.2s, 0.3s, 0.4s, 0.5s

        logger.warning("[CONTEXT-STARVE] _init_entity_context() returned False after 5 attempts")
        return False

    # ── Voice System ─────────────────────────────────────────────

    def _ensure_voice_system(self) -> Optional["VoiceSystemOrchestrator"]:
        """Lazy-init the voice orchestrator from config."""
        if self._voice_orchestrator is not None:
            return self._voice_orchestrator
        if not VOICE_SYSTEM_AVAILABLE:
            return None
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "voice", "data", "voice_config.yaml"
            )
            if os.path.exists(config_path):
                config = VoiceSystemConfig.from_yaml(config_path)
            else:
                config = VoiceSystemConfig()
            self._voice_orchestrator = VoiceSystemOrchestrator(config)
            logger.info("[VOICE] Voice system initialized (engine=%s, corpus=%s)",
                        config.blend_engine_mode.value, config.voice_corpus_mode.value)
            return self._voice_orchestrator
        except Exception as e:
            logger.warning(f"[VOICE] Failed to init voice system: {e}")
            return None

    def _detect_context_type(self, message: str, memories: list, turn_number: int) -> "ContextType":
        """Map query classification + heuristics to ContextType enum."""
        query_type = classify_query_type(message)
        mapping = {
            "greeting": ContextType.GREETING,
            "technical": ContextType.TECHNICAL,
            "emotional": ContextType.EMOTIONAL,
            "creative": ContextType.CREATIVE,
        }
        if query_type in mapping:
            return mapping[query_type]
        if turn_number <= 1:
            return ContextType.COLD_START
        if memories and any(
            isinstance(m, dict) and m.get("node_type") == "memory"
            for m in memories
        ):
            return ContextType.MEMORY_RECALL
        return ContextType.FOLLOW_UP

    def _calculate_topic_continuity(self, message: str, conversation_history: list) -> float:
        """Estimate topic continuity from recent conversation (0.0-1.0)."""
        if not conversation_history:
            return 0.0
        recent_words = set()
        for turn in conversation_history[-4:]:
            content = turn.get("content", "") if isinstance(turn, dict) else str(turn)
            recent_words.update(w.lower() for w in content.split() if len(w) > 3)
        if not recent_words:
            return 0.0
        current_words = set(w.lower() for w in message.split() if len(w) > 3)
        if not current_words:
            return 0.0
        overlap = len(current_words & recent_words)
        return min(1.0, overlap / max(len(current_words), 1) * 1.5)

    def _estimate_memory_score(self, memories: list) -> float:
        """Estimate memory retrieval quality (0.0-1.0)."""
        if not memories:
            return 0.0
        count = len(memories)
        if count >= 5:
            return 0.9
        elif count >= 3:
            return 0.7
        elif count >= 1:
            return 0.4
        return 0.0

    def _estimate_entity_depth(self, framed_context: str) -> int:
        """Estimate entity resolution depth (0-3) from framed context."""
        if not framed_context:
            return 0
        depth = 0
        if "KNOWN PEOPLE" in framed_context or "Known People" in framed_context:
            depth += 1
        if "relationship" in framed_context.lower():
            depth += 1
        if "profile" in framed_context.lower() or "personality" in framed_context.lower():
            depth += 1
        return min(depth, 3)

    def _generate_voice_block(
        self, message: str, memories: list,
        framed_context: str, conversation_history: list,
    ) -> str:
        """Generate voice injection block. Returns empty string on failure."""
        voice_orch = self._ensure_voice_system()
        if not voice_orch:
            return ""
        self._voice_turn_count += 1
        try:
            ctx_type = self._detect_context_type(message, memories, self._voice_turn_count)
            signals = ConfidenceSignals(
                memory_retrieval_score=self._estimate_memory_score(memories),
                turn_number=self._voice_turn_count,
                entity_resolution_depth=self._estimate_entity_depth(framed_context),
                context_type=ctx_type,
                topic_continuity=self._calculate_topic_continuity(message, conversation_history),
            )
            voice_block = voice_orch.generate_voice_block(
                signals=signals,
                context_type=ctx_type,
                turn_number=self._voice_turn_count,
            )
            if voice_block:
                logger.info("[VOICE] Injected voice block (%d chars, alpha=%.2f, ctx=%s)",
                            len(voice_block), signals.memory_retrieval_score, ctx_type.value)
                return f"\n\n{voice_block}"
        except Exception as e:
            logger.warning(f"[VOICE] Voice block generation failed: {e}")
        return ""

    async def _load_identity_buffer(self, user_id: str = "ahab") -> str:
        """
        Load identity buffer and return formatted prompt context.

        This provides Luna with:
        - Her own identity and purpose
        - Her voice and communication style
        - Who she's talking to
        - Key relationships
        - Active personas
        """
        logger.debug(f"Loading identity buffer for user: {user_id}")

        if not await self._ensure_entity_context():
            logger.warning("Identity buffer: Entity context not available")
            return ""

        try:
            self._identity_buffer = await self._entity_context.load_identity_buffer(user_id)
            if self._identity_buffer is None:
                logger.warning("Identity buffer: load_identity_buffer returned None")
                return ""

            context = self._identity_buffer.to_prompt()
            logger.info(f"Identity buffer loaded: ~{self._identity_buffer.token_estimate()} tokens, {len(context)} chars")
            return context
        except Exception as e:
            logger.error(f"Failed to load identity buffer: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Identity buffer traceback: {traceback.format_exc()}")
            return ""

    async def _load_emergent_prompt(
        self,
        query: str,
        conversation_history: list = None,
        user_id: str = "ahab"
    ) -> Optional[str]:
        """
        Load emergent prompt with three-layer personality synthesis.

        This provides Luna with:
        - DNA layer: Static identity from voice_config
        - Experience layer: Personality patches from memory
        - Mood layer: Current conversational state

        Falls back to basic identity buffer if emergent system unavailable.

        Args:
            query: The user's current message
            conversation_history: Recent conversation for mood analysis
            user_id: Current user's entity ID

        Returns:
            Formatted system prompt with personality layers, or None
        """
        logger.debug(f"Loading emergent prompt for query: '{query[:50]}...'")

        if not await self._ensure_entity_context():
            logger.warning("Emergent prompt: Entity context not available")
            return None

        try:
            # Load identity buffer first (needed for emergent prompt)
            logger.debug("Emergent prompt: Loading identity buffer")
            self._identity_buffer = await self._entity_context.load_identity_buffer(user_id)

            if self._identity_buffer is None:
                logger.warning("Emergent prompt: Identity buffer is None")
                return None

            # Try to get emergent prompt with all three layers
            logger.debug(f"Emergent prompt: Getting emergent prompt (patch_manager: {self._patch_manager is not None})")
            emergent = await self._identity_buffer.get_emergent_prompt(
                query=query,
                conversation_history=conversation_history or [],
                patch_manager=self._patch_manager,
                limit=10
            )

            if emergent:
                result = emergent.to_system_prompt()
                logger.info(f"Emergent prompt loaded: {len(result)} chars with personality layers")
                return result
            else:
                # Fall back to basic identity buffer
                logger.debug("Emergent prompt unavailable, using basic identity buffer")
                return self._identity_buffer.to_prompt()

        except Exception as e:
            logger.error(f"Failed to load emergent prompt: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Emergent prompt traceback: {traceback.format_exc()}")
            # Fall back to basic identity buffer
            if self._identity_buffer:
                return self._identity_buffer.to_prompt()
            return None

    @property
    def local_available(self) -> bool:
        """Check if local inference is available and loaded."""
        return self._local_loaded and self._local is not None

    @property
    def _active_ring(self) -> ConversationRing:
        """
        Get the active conversation ring buffer.

        Returns the context pipeline's ring if available, otherwise
        falls back to the standalone ring. This ensures history tracking
        ALWAYS works, even without the full context pipeline.
        """
        if self._context_pipeline is not None:
            return self._context_pipeline._ring
        return self._standalone_ring

    # =========================================================================
    # Direct Process API (for PersonaAdapter voice integration)
    # =========================================================================

    async def process(self, message: str, context: dict = None) -> dict:
        """
        Process a message directly (bypassing mailbox).

        THIS IS THE SINGLE INTEGRATION POINT FOR:
        - Entity resolution (detect_mentions)
        - Temporal context framing (past memories vs current conversation)
        - Memory retrieval
        - LLM generation

        Args:
            message: User message text
            context: Dict containing:
                - interface: "voice" or "desktop"
                - memories: List of memory nodes
                - session_id: Optional session ID
                - context_window: Formatted conversation history (text)
                - conversation_history: List of {role, content} dicts

        Returns:
            Dict with response, route_decision, route_reason, system_prompt_tokens
        """
        context = context or {}
        context_window = context.get("context_window", "")
        conversation_history = context.get("conversation_history", [])
        memories = context.get("memories", [])
        session_id = context.get("session_id")
        self._last_denied_count = 0  # Reset per-request

        # Auto-fetch memories when caller provided none (e.g. voice/PersonaAdapter)
        if not memories:
            memory_text = await self._fetch_memory_context(message, max_tokens=1500)
            if memory_text:
                memories = [{"content": memory_text, "node_type": "context"}]
                logger.info(f"[PROCESS] Auto-fetched memory context ({len(memory_text)} chars)")

        # [TRACE] Entity System Verification Logging
        logger.info("=" * 60)
        logger.info("[TRACE] Director.process() ENTRY")
        logger.info(f"[TRACE] Message: '{message}'")
        logger.info(f"[TRACE] Has _entity_context: {hasattr(self, '_entity_context')}")
        logger.info(f"[TRACE] _entity_context value: {getattr(self, '_entity_context', 'NOT SET')}")

        # [HISTORY-TRACE] Log what Director.process receives
        logger.info(f"[HISTORY-TRACE] Director.process CALLED with message: '{message[:50]}...'")
        logger.info(f"[HISTORY-TRACE] Director.process: context_window has {len(context_window)} chars")
        logger.info(f"[HISTORY-TRACE] Director.process: conversation_history has {len(conversation_history)} items")
        logger.info(f"[HISTORY-TRACE] Director.process: {len(memories)} memories passed in")

        # RING BUFFER: Record user message (structural guarantee against forgetting)
        self._active_ring.add_user(message)
        logger.debug("[PROCESS-RING] Recorded user message to ring buffer (size: %d)", len(self._active_ring))

        # PERCEPTION: Ingest user message before prompt assembly
        self._perception_turn_count += 1
        self._perception_field.ingest(message, self._perception_turn_count)

        start_time = time.time()
        response_text = ""
        route_decision = "unknown"
        route_reason = "unknown"
        system_prompt = ""  # Initialize to ensure QA captures it
        system_prompt_tokens = 0
        narration_applied = False  # Track for QA (BUG-D fix)

        # ========================================================================
        # BUILD FRAMED CONTEXT (THE KEY INTEGRATION)
        # Uses EntityContext.build_framed_context() for:
        # - Entity detection and profile loading
        # - Temporal framing (<past_memory> tags vs [This session])
        # - Response instructions
        # ========================================================================

        framed_context = ""
        # [TRACE] About to build framed context
        logger.info("[TRACE] About to build framed context...")
        if await self._ensure_entity_context():
            logger.info("[TRACE] Calling _entity_context.build_framed_context()")
            try:
                # Convert memories to dict format if needed
                memory_dicts = []
                for m in memories:
                    if isinstance(m, dict):
                        memory_dicts.append(m)
                    elif hasattr(m, 'content'):
                        memory_dicts.append({
                            "content": m.content,
                            "created_at": getattr(m, 'created_at', None),
                            "node_type": getattr(m, 'node_type', 'memory'),
                        })
                    else:
                        memory_dicts.append({"content": str(m)})

                framed_context = await self._entity_context.build_framed_context(
                    message=message,
                    conversation_history=conversation_history,
                    memories=memory_dicts,
                    session_id=session_id,
                )
                # [TRACE] After context built
                logger.info(f"[TRACE] Framed context built: {len(framed_context)} chars")
                logger.info(f"[TRACE] Context contains 'marzipan': {'marzipan' in framed_context.lower()}")
                logger.info(f"[TRACE] Context preview:\n{framed_context[:500]}")
                logger.info("=" * 60)
                logger.info(f"[CONTEXT] Built framed context: {len(framed_context)} chars")
            except Exception as e:
                logger.error(f"Context building failed: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.info("[TRACE] WARNING: No _entity_context available!")

        # ── L2: Classify intent BEFORE routing ──────────────────────
        intent = self._classify_intent(message, conversation_history)
        logger.info(
            "[INTENT] mode=%s confidence=%.2f signals=%s continuation=%s",
            intent.mode.value, intent.confidence,
            intent.signals, intent.is_continuation,
        )

        # ── Resolve access bridge (FaceID → permissions) ──────────
        bridge_result = await self._resolve_bridge()

        # Check if we should delegate to Claude
        should_delegate = await self._should_delegate(message)

        if should_delegate:
            route_decision = "delegated"
            route_reason = "complexity/signals"

            # ── PromptAssembler: single funnel for prompt construction ──
            assembler_result = await self._assembler.build(PromptRequest(
                message=message,
                conversation_history=conversation_history,
                memories=memories,
                framed_context=framed_context,
                route="delegated",
                intent=intent,
                bridge_result=bridge_result,
            ))
            system_prompt = assembler_result.system_prompt
            messages = assembler_result.messages
            system_prompt_tokens = assembler_result.prompt_tokens

            # Context audit logging
            logger.info("=" * 80)
            logger.info("[CONTEXT-AUDIT] Processing turn via assembler")
            logger.info("[CONTEXT-AUDIT] identity=%s memory=%s temporal=%s voice=%s tokens≈%d",
                        assembler_result.identity_source, assembler_result.memory_source,
                        assembler_result.gap_category, assembler_result.voice_injected,
                        assembler_result.prompt_tokens)
            logger.info("[CONTEXT-AUDIT] System prompt preview:\n%s", system_prompt[:800])
            logger.info("[CONTEXT-AUDIT] MESSAGES ARRAY (%d messages)", len(messages))
            logger.info("=" * 80)

            # Store for /prompt command
            self._last_system_prompt = system_prompt
            self._last_route_decision = "delegated"
            self._last_prompt_meta = assembler_result.to_dict()

            # Use FallbackChain for resilient inference (if available)
            if self._fallback_chain is not None:
                try:
                    result = await self._fallback_chain.generate(
                        messages=messages,
                        system=system_prompt,
                        max_tokens=512,
                    )
                    response_text = result.content
                    provider_used = result.provider_used
                    self._delegated_generations += 1

                    # Log if fallback occurred
                    if len(result.attempts) > 1:
                        logger.info(f"[FALLBACK] Used {provider_used} after {len(result.attempts)-1} failures")

                except AllProvidersFailedError as e:
                    logger.error(f"[FALLBACK] All providers failed: {[a.provider + ': ' + (a.error or 'unknown') for a in e.attempts]}")
                    response_text = "I'm having trouble connecting right now. All inference providers are unavailable."
                except Exception as e:
                    logger.error(f"Director.process delegation (fallback chain) failed: {e}")
                    response_text = "I'm having trouble processing that right now."
            else:
                # Legacy direct Claude call (no fallback chain)
                try:
                    response = self.client.messages.create(
                        model=self._claude_model,
                        max_tokens=512,
                        system=system_prompt,
                        messages=messages,
                    )
                    response_text = response.content[0].text if response.content else ""
                    self._delegated_generations += 1
                except Exception as e:
                    logger.error(f"Director.process delegation failed: {e}")
                    response_text = "I'm having trouble processing that right now."

            # ================================================================
            # NARRATION DISABLED: Qwen 3B rewrite was degrading Groq's
            # 70B output quality. Luna's voice is now injected via the
            # system prompt (PromptAssembler), not post-hoc rewriting.
            # ================================================================

        elif self.local_available:
            route_decision = "local"
            route_reason = "simple query"
            used_retrieval = False

            # ── PromptAssembler: single funnel for local path ──
            # ContextPipeline takes priority when available (it has its own prompt builder)
            assembler_result = None
            if self._context_pipeline is not None:
                try:
                    # Populate ring from context_window if empty (bridge Engine→Director gap)
                    if len(self._context_pipeline._ring) == 0 and context_window:
                        logger.info("[PROCESS-LOCAL-PIPELINE] Ring empty, populating from context_window")
                        self._populate_ring_from_context(
                            self._context_pipeline._ring,
                            context_window
                        )

                    packet = await self._context_pipeline.build(message)
                    system_prompt = packet.system_prompt
                    used_retrieval = packet.used_retrieval
                    # Inject ACCESS block — pipeline skips the assembler
                    _access_block = self._assembler._build_access_block(
                        PromptRequest(message=message, bridge_result=bridge_result)
                    )
                    if _access_block:
                        system_prompt = system_prompt + "\n\n" + _access_block
                    logger.info(f"[PROCESS-LOCAL-PIPELINE] Using unified context: {packet}")
                except Exception as e:
                    logger.warning(f"[PROCESS-LOCAL] Pipeline failed, using assembler: {e}")
                    assembler_result = await self._assembler.build(PromptRequest(
                        message=message,
                        conversation_history=conversation_history,
                        memories=memories,
                        framed_context=framed_context,
                        route="local",
                        bridge_result=bridge_result,
                    ))
                    system_prompt = assembler_result.system_prompt
            else:
                assembler_result = await self._assembler.build(PromptRequest(
                    message=message,
                    conversation_history=conversation_history,
                    memories=memories,
                    framed_context=framed_context,
                    route="local",
                    bridge_result=bridge_result,
                ))
                system_prompt = assembler_result.system_prompt

            system_prompt_tokens = len(system_prompt) // 4
            self._last_system_prompt = system_prompt
            if assembler_result:
                self._last_prompt_meta = assembler_result.to_dict()

            try:
                result = await self._local.generate(
                    message,
                    system_prompt=system_prompt,
                    max_tokens=256,
                )
                response_text = result.text if hasattr(result, 'text') else str(result)
                self._local_generations += 1
                logger.info(f"[PROCESS-LOCAL] Generation complete, used_retrieval={used_retrieval}")
            except Exception as e:
                logger.error(f"Director.process local failed: {e}")
                response_text = "I'm having trouble with that."

        else:
            # Fallback when local unavailable - use FallbackChain for resilience
            route_decision = "delegated"
            route_reason = "local unavailable"

            # ── PromptAssembler: single funnel for fallback path ──
            assembler_result = await self._assembler.build(PromptRequest(
                message=message,
                conversation_history=conversation_history,
                framed_context=framed_context,
                route="fallback",
                auto_fetch_memory=True,
                bridge_result=bridge_result,
            ))
            system_prompt = assembler_result.system_prompt
            messages = assembler_result.messages
            system_prompt_tokens = assembler_result.prompt_tokens
            self._last_system_prompt = system_prompt
            self._last_prompt_meta = assembler_result.to_dict()

            # Use FallbackChain for resilient inference (if available)
            if self._fallback_chain is not None:
                try:
                    result = await self._fallback_chain.generate(
                        messages=messages,
                        system=system_prompt,
                        max_tokens=512,
                    )
                    response_text = result.content
                    provider_used = result.provider_used
                    self._delegated_generations += 1

                    if len(result.attempts) > 1:
                        logger.info(f"[FALLBACK] Used {provider_used} after {len(result.attempts)-1} failures")

                except AllProvidersFailedError as e:
                    logger.error(f"[FALLBACK] All providers failed: {[a.provider + ': ' + (a.error or 'unknown') for a in e.attempts]}")
                    response_text = "I'm having trouble connecting right now. All inference providers are unavailable."
                except Exception as e:
                    logger.error(f"Director.process fallback (chain) failed: {e}")
                    response_text = "I'm having trouble right now."
            else:
                # Legacy direct Claude call (no fallback chain)
                try:
                    response = self.client.messages.create(
                        model=self._claude_model,
                        max_tokens=512,
                        system=system_prompt,
                        messages=messages,
                    )
                    response_text = response.content[0].text if response.content else ""
                    self._delegated_generations += 1
                except Exception as e:
                    logger.error(f"Director.process fallback failed: {e}")
                    response_text = "I'm having trouble right now."

        # ========================================================================
        # POST-PROCESSING: SCRIBE EXTRACTION (for future - creates new entities)
        # ========================================================================

        # TODO: Implement Scribe extraction here
        # This would scan the conversation for new people and create profiles
        # await self._scribe_extract(message, response_text, conversation_history)

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Director.process complete: {route_decision} in {elapsed_ms:.0f}ms")

        # RING BUFFER: Record response (structural guarantee against forgetting)
        # BUG-C FIX: Always add response to prevent orphaned user messages that bleed into next turn
        if response_text:
            self._active_ring.add_assistant(response_text)
            logger.debug("[PROCESS-RING] Recorded response to ring buffer (size: %d)", len(self._active_ring))
        else:
            # Add placeholder to prevent context bleeding from orphaned user message
            self._active_ring.add_assistant("[No response generated]")
            logger.warning("[PROCESS-RING] Added placeholder for failed/empty response")

        # Capture used_retrieval from local path (for debugging)
        # Default to True for delegated path (delegation always fetches memory)
        final_used_retrieval = locals().get('used_retrieval', route_decision == "delegated")

        # ========================================================================
        # QA VALIDATION: Run assertions against this inference
        # ========================================================================
        qa_report = None
        if QA_AVAILABLE and self._qa_enabled:
            try:
                # Lazy init QA validator
                if self._qa_validator is None:
                    self._qa_validator = get_qa_validator()

                # Build inference context with all collected data
                # FIX BUG-A: Use system_prompt directly (now initialized at top)
                qa_ctx = InferenceContext(
                    session_id=session_id or "",
                    query=message,
                    route=route_decision.upper() if route_decision else "",
                    complexity_score=0.0,  # TODO: Add complexity scoring
                    providers_tried=[route_decision] if route_decision else [],
                    provider_used=locals().get('provider_used', route_decision or ""),
                    personality_injected=system_prompt_tokens > 250,  # >1000 chars
                    personality_length=system_prompt_tokens * 4,
                    system_prompt=system_prompt,  # Now guaranteed to be set
                    virtues_loaded=self._identity_buffer is not None,
                    narration_applied=narration_applied,  # BUG-D fix: now tracked
                    raw_response=response_text,
                    final_response=response_text,
                    latency_ms=elapsed_ms,
                    input_tokens=len(message) // 4,
                    output_tokens=len(response_text) // 4,
                )

                # Add request chain steps
                qa_ctx.add_step("receive", 0, f"Query received: '{message[:50]}...'")
                qa_ctx.add_step("route", elapsed_ms * 0.1, f"Route: {route_decision} ({route_reason})")
                qa_ctx.add_step("generate", elapsed_ms * 0.8, f"{route_decision} returned {len(response_text)} chars")
                qa_ctx.add_step("output", elapsed_ms, "Response ready")

                # Validate
                qa_report = self._qa_validator.validate(qa_ctx)

                if not qa_report.passed:
                    logger.warning(f"[QA] FAILED ({qa_report.failed_count} assertions): {qa_report.diagnosis}")
                else:
                    logger.debug(f"[QA] PASSED ({len(qa_report.assertions)} assertions)")

            except Exception as e:
                logger.warning(f"[QA] Validation error (non-fatal): {e}")

        # ========================================================================
        # PERCEPTION: Record Luna's action for next turn's trigger context
        # ========================================================================
        if response_text:
            self._perception_field.record_luna_action(response_text)

        # ========================================================================
        # PROMPT ARCHAEOLOGY: Log prompt for forensic analysis
        # See: HANDOFF_PROMPT_ARCHAEOLOGY.md
        # ========================================================================
        try:
            self.log_prompt_archaeology(message, response_text)
        except Exception as e:
            logger.debug(f"[ARCHAEOLOGY] Logging failed (non-fatal): {e}")

        return {
            "response": response_text,
            "route_decision": route_decision,
            "route_reason": route_reason,
            "system_prompt_tokens": system_prompt_tokens,
            "latency_ms": elapsed_ms,
            "used_retrieval": final_used_retrieval,
            "qa_passed": qa_report.passed if qa_report else None,
            "qa_failures": qa_report.failed_count if qa_report else 0,
        }

    def on_stream(self, callback: Callable[[str], None]) -> None:
        """Register a callback for streaming tokens."""
        self._stream_callbacks.append(callback)

    def remove_stream_callback(self, callback: Callable[[str], None]) -> None:
        """Remove a streaming callback."""
        if callback in self._stream_callbacks:
            self._stream_callbacks.remove(callback)

    async def handle(self, msg: Message) -> None:
        """Process messages."""
        logger.debug(f"Director received: {msg.type}")

        match msg.type:
            case "generate" | "generate_stream" | "generate_local" | "generate_hybrid":
                # ALL generation goes through the Director (local-first architecture)
                await self._handle_director_generate(msg)

            case "abort":
                await self._handle_abort(msg)

            case "set_model":
                # This sets the Claude model for delegation
                self._claude_model = msg.payload.get("model", self._claude_model)
                logger.info(f"Director Claude model changed to: {self._claude_model}")

            case "load_local":
                await self._init_local_inference()

            case _:
                logger.warning(f"Director: unknown message type: {msg.type}")

    async def _handle_director_generate(self, msg: Message) -> None:
        """
        Main generation handler - LOCAL-FIRST architecture with PLANNING STEP.

        Flow:
        1. PLAN: Decide upfront if query needs delegation (complexity + signals)
        2. If complex: delegate to Claude, get facts, narrate in Luna's voice
        3. If simple: pure local generation (no delegation watching)

        This ensures Luna's mind is ALWAYS primary. Claude is just a research assistant.
        The planning step replaces hope that Qwen outputs <REQ_CLAUDE> with explicit routing.
        """
        payload = msg.payload
        user_message = payload.get("user_message", "")
        system_prompt = payload.get("system_prompt", "You are Luna, a sovereign AI companion. Be warm and natural. Never output internal reasoning or debugging info.")
        max_tokens = payload.get("max_tokens", 512)
        context_window = payload.get("context_window", "")  # Conversation history

        self._generating = True
        self._last_denied_count = 0  # Reset per-request
        self._abort_requested = False
        self._current_correlation_id = msg.correlation_id

        start_time = time.time()

        # PLANNING STEP: Decide routing upfront
        should_delegate = await self._should_delegate(user_message)

        # ── Resolve access bridge (FaceID → permissions) ──────────
        bridge_result = await self._resolve_bridge()

        if should_delegate:
            # Complex query → delegate to Claude, narrate in Luna's voice
            await self._generate_with_delegation(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                correlation_id=msg.correlation_id,
                start_time=start_time,
                context_window=context_window,
                bridge_result=bridge_result,
            )
        elif self.local_available:
            # Simple query → pure local generation
            await self._generate_local_only(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                correlation_id=msg.correlation_id,
                start_time=start_time,
                context_window=context_window,
                bridge_result=bridge_result,
            )
        else:
            # Fallback to Claude directly if local not available
            logger.warning("Local inference not available, using Claude directly")
            await self._generate_claude_direct(
                user_message=user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                correlation_id=msg.correlation_id,
                start_time=start_time,
                context_window=context_window,
                bridge_result=bridge_result,
            )

        self._generating = False
        self._current_correlation_id = None

    async def _should_delegate(self, user_message: str) -> bool:
        """
        Planning step: Decide if this query should be delegated to fallback chain.

        CHANGED: Always delegate to fallback chain (groq → local → claude).
        This ensures Groq is tried first for speed, with local as voice narration.
        The complexity check is preserved for logging/metrics only.
        """
        query_preview = user_message[:50] + "..." if len(user_message) > 50 else user_message

        # Log complexity for metrics (but don't use it for routing)
        if hasattr(self, '_hybrid') and self._hybrid is not None:
            complexity = self._hybrid.estimate_complexity(user_message)
            logger.info(f"🔀 DELEGATE: '{query_preview}' (complexity={complexity:.2f}, always delegating)")
        else:
            logger.info(f"🔀 DELEGATE: '{query_preview}' (always delegating)")

        # Always delegate - fallback chain handles provider selection
        return True

    def _check_delegation_signals(self, user_message: str) -> bool:
        """
        Check for explicit signals that require delegation.

        These are things local Qwen definitely can't handle well.
        """
        msg_lower = user_message.lower()

        # Temporal markers (current events)
        temporal = ["latest", "current", "recent", "today", "yesterday",
                    "this week", "this month", "right now", "2025", "2026"]
        for t in temporal:
            if t in msg_lower:
                logger.debug(f"  → Temporal signal: '{t}'")
                return True

        # Explicit research requests
        research = ["search for", "look up", "find out", "research",
                    "what's happening with", "news about"]
        for r in research:
            if r in msg_lower:
                logger.debug(f"  → Research signal: '{r}'")
                return True

        # Complex code generation
        code = ["write a script", "implement", "build a", "create a program",
                "debug this", "fix this code"]
        for c in code:
            if c in msg_lower:
                logger.debug(f"  → Code signal: '{c}'")
                return True

        # Memory/introspection queries (need actual memory data)
        # Note: "tell me about yourself" is a personality query (local), NOT a memory query
        # EXPANDED: These patterns MUST delegate because local model can't access memory
        memory = [
            # Explicit memory keywords
            "your memory", "your memories", "memory matrix",
            "what do you remember", "do you remember", "can you remember",
            "recall when", "recall that", "recollect",
            # Knowledge queries that need memory lookup
            "in-depth", "indepth", "overview",
            "tell me about our", "tell me about the",
            "what do you know about", "do you know about",
            "who is", "who was", "what is marzipan",  # Named entity queries
            # Backward reference patterns
            "earlier", "before", "last time", "yesterday",
            "you mentioned", "you said", "we talked", "we discussed",
            # Relational memory
            "about us", "our relationship", "how we", "what we",
        ]
        for m in memory:
            if m in msg_lower:
                logger.debug(f"  → Memory signal: '{m}'")
                return True

        return False

    def _classify_intent(
        self,
        message: str,
        conversation_history: list,
    ) -> IntentClassification:
        """
        Classify user intent into a ResponseMode.

        Runs BEFORE routing. The mode is injected into the prompt
        regardless of which inference backend handles generation.

        Classification priority:
            1. Continuation detection (short follow-ups inherit previous mode)
            2. Explicit RECALL signals (memory/past event queries)
            3. Explicit REFLECT signals (feelings/opinions)
            4. Explicit ASSIST signals (task/help requests)
            5. Default to CHAT
        """
        msg = message.strip()
        msg_lower = msg.lower()
        signals = []

        # ── 1. Continuation Detection ──────────────────────────────
        if len(msg) < 30 and conversation_history:
            continuation_triggers = [
                "keep going", "more", "continue", "go on", "and?",
                "what else", "tell me more", "yeah", "yes", "mhm",
                "ok", "okay", "right", "sure", "cool", ":)", "👀",
                "interesting", "huh", "wow", "really", "no way",
            ]
            if any(t in msg_lower for t in continuation_triggers):
                prev_mode = self._last_classified_mode
                return IntentClassification(
                    mode=prev_mode,
                    confidence=0.9,
                    signals=["continuation_detected"],
                    is_continuation=True,
                    previous_mode=prev_mode,
                )

        # ── 2. RECALL signals ──────────────────────────────────────
        recall_patterns = [
            "remember", "recall", "memory", "memories",
            "what do you know about", "do you know about",
            "tell me about our", "tell me about the",
            "who is", "who was", "what was",
            "earlier", "before", "last time",
            "you mentioned", "you said", "we talked", "we discussed",
            "about us", "our relationship", "how we", "what we",
            "most special", "favorite memory", "best memory",
            "what have i been", "what have we been",
            "working on", "been up to",
        ]
        for p in recall_patterns:
            if p in msg_lower:
                signals.append(f"recall_keyword:{p}")

        if signals:
            mode = ResponseMode.RECALL
            self._last_classified_mode = mode
            return IntentClassification(
                mode=mode,
                confidence=0.85,
                signals=signals,
                is_continuation=False,
                previous_mode=self._last_classified_mode,
            )

        # ── 3. REFLECT signals ─────────────────────────────────────
        reflect_patterns = [
            "how do you feel", "what do you think",
            "your opinion", "your perspective", "your take",
            "do you like", "do you enjoy", "do you want",
            "are you happy", "are you sad", "are you okay",
            "how are you", "how's it going", "how are things",
            "what matters to you", "what's important",
        ]
        for p in reflect_patterns:
            if p in msg_lower:
                signals.append(f"reflect_keyword:{p}")

        if signals:
            mode = ResponseMode.REFLECT
            self._last_classified_mode = mode
            return IntentClassification(
                mode=mode,
                confidence=0.8,
                signals=signals,
                is_continuation=False,
                previous_mode=self._last_classified_mode,
            )

        # ── 4. ASSIST signals ──────────────────────────────────────
        assist_patterns = [
            "help me", "can you", "could you", "please",
            "how do i", "how to", "show me", "explain",
            "write", "create", "build", "implement", "fix",
            "search for", "look up", "find",
            "debug", "analyze", "compare",
        ]
        for p in assist_patterns:
            if p in msg_lower:
                signals.append(f"assist_keyword:{p}")

        if signals:
            mode = ResponseMode.ASSIST
            self._last_classified_mode = mode
            return IntentClassification(
                mode=mode,
                confidence=0.75,
                signals=signals,
                is_continuation=False,
                previous_mode=self._last_classified_mode,
            )

        # ── 5. Default: CHAT ───────────────────────────────────────
        mode = ResponseMode.CHAT
        self._last_classified_mode = mode
        return IntentClassification(
            mode=mode,
            confidence=0.7,
            signals=["default"],
            is_continuation=False,
            previous_mode=self._last_classified_mode,
        )

    async def _generate_local_only(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
        context_window: str = "",
        bridge_result=None,
    ) -> None:
        """
        Pure local generation - no delegation detection needed.

        Used when planning step already decided this is a local query.

        Phase 3 Fix: Uses unified ContextPipeline when available for
        identical context to delegated path (entity detection, temporal
        framing, ring buffer history).
        """
        response_buffer = ""
        token_count = 0
        print(f"\n🏠 [LOCAL] Starting for: '{user_message[:50]}...'")

        # ── PromptAssembler: single funnel for local streaming path ──
        # ContextPipeline takes priority when available (it handles entity detection inline)
        if self._context_pipeline is not None:
            try:
                # Bridge Engine→Director gap: populate ring from context_window if empty
                if len(self._context_pipeline._ring) == 0 and context_window:
                    logger.info("[LOCAL-PIPELINE] Ring empty, populating from context_window")
                    self._populate_ring_from_context(
                        self._context_pipeline._ring,
                        context_window
                    )

                packet = await self._context_pipeline.build(user_message)
                full_system_prompt = packet.system_prompt
                # Inject ACCESS block — pipeline skips the assembler so we must add it here
                from luna.context.assembler import PromptRequest
                _access_block = self._assembler._build_access_block(
                    PromptRequest(message=user_message, bridge_result=bridge_result)
                )
                if _access_block:
                    full_system_prompt = full_system_prompt + "\n\n" + _access_block
                print(f"✓ [LOCAL] Context pipeline: ring={packet.ring_size}, entities={len(packet.entities)}")
                self._last_system_prompt = full_system_prompt
                self._last_route_decision = "local"
            except Exception as e:
                logger.warning(f"[LOCAL] Pipeline failed, using assembler: {e}")
                assembler_result = await self._assembler.build(PromptRequest(
                    message=user_message,
                    conversation_history=[],
                    route="local",
                    auto_fetch_memory=True,
                    bridge_result=bridge_result,
                ))
                full_system_prompt = assembler_result.system_prompt
                self._last_system_prompt = full_system_prompt
                self._last_route_decision = "local"
                self._last_prompt_meta = assembler_result.to_dict()
        else:
            # No pipeline — use assembler (records to standalone ring)
            self._standalone_ring.add_user(user_message)
            logger.debug("[LOCAL-RING] Recorded user message to standalone ring (size: %d)", len(self._standalone_ring))
            assembler_result = await self._assembler.build(PromptRequest(
                message=user_message,
                conversation_history=[],
                route="local",
                auto_fetch_memory=True,
                bridge_result=bridge_result,
            ))
            full_system_prompt = assembler_result.system_prompt
            self._last_system_prompt = full_system_prompt
            self._last_route_decision = "local"
            self._last_prompt_meta = assembler_result.to_dict()

        try:
            print(f"📡 [LOCAL] Generating with Qwen 3B...")
            async for token in self._local.generate_stream(
                user_message,
                system_prompt=full_system_prompt,
                max_tokens=max_tokens,
            ):
                if self._abort_requested:
                    print(f"⚠ [LOCAL] Aborted!")
                    logger.info("Director: Generation aborted")
                    break

                response_buffer += token
                token_count += 1
                await self._stream_to_callbacks(token)

            elapsed_ms = (time.time() - start_time) * 1000
            self._local_generations += 1
            print(f"✓ [LOCAL] Complete: {token_count} tokens in {elapsed_ms:.0f}ms")

            logger.info(f"Director local: {token_count} tokens in {elapsed_ms:.0f}ms")

            # Record response in ring buffer (CRITICAL for history)
            if response_buffer:
                self._active_ring.add_assistant(response_buffer)
                logger.debug("[LOCAL-RING] Recorded response to ring buffer (size: %d)", len(self._active_ring))

            await self.send_to_engine("generation_complete", {
                "text": response_buffer,
                "correlation_id": correlation_id,
                "model": "qwen-3b-local",
                "output_tokens": token_count,
                "latency_ms": elapsed_ms,
                "local": True,
                "planned": True,
                "access_denied_count": self._last_denied_count,
            })

        except Exception as e:
            print(f"❌ [LOCAL] Failed: {e}")
            logger.error(f"Director local generation error: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    def _populate_ring_from_context(
        self,
        ring: "ConversationRing",
        context_window: str,
    ) -> None:
        """
        Populate a ring buffer from text context_window.

        This bridges the gap between Engine's RevolvingContext (text-based)
        and Director's ContextPipeline (structured ring buffer).

        Parses text like:
            User: message 1

            Luna: response 1

            User: message 2

        Into structured ring entries.
        """
        if not context_window:
            return

        # Parse context_window text into conversation turns
        # Skip the current message - build() will add that
        for line in context_window.split("\n\n"):
            line = line.strip()
            if line.startswith("User:"):
                content = line[5:].strip()
                if content:
                    ring.add_user(content)
            elif line.startswith("Luna:"):
                content = line[5:].strip()
                if content:
                    ring.add_assistant(content)

        logger.debug(
            "[CONTEXT-BRIDGE] Parsed %d turns from context_window (%d chars)",
            len(ring),
            len(context_window)
        )

    async def _build_local_context_fallback(
        self,
        user_message: str,
        system_prompt: str,
        context_window: str,
    ) -> str:
        """
        Build context for local generation using legacy method.

        This is the fallback when ContextPipeline is not available.
        Uses ring buffer for history (if available), then emergent prompt.
        """
        # Prefer ring buffer for conversation history (structural guarantee)
        ring_history = ""
        conversation_history = []
        if len(self._standalone_ring) > 0:
            ring_history = self._standalone_ring.format_for_prompt()
            conversation_history = self._standalone_ring.get_as_dicts()
            logger.debug("[LOCAL-FALLBACK] Using ring buffer for history (%d turns)", len(self._standalone_ring))
        elif context_window:
            # Fall back to text parsing only if ring is empty
            ring_history = context_window
            for line in context_window.split("\n\n"):
                line = line.strip()
                if line.startswith("User:"):
                    conversation_history.append({"role": "user", "content": line[5:].strip()})
                elif line.startswith("Luna:"):
                    conversation_history.append({"role": "assistant", "content": line[5:].strip()})
            logger.debug("[LOCAL-FALLBACK] Using text parsing for history (ring empty)")

        # Load emergent prompt for local generation (three-layer personality)
        identity_context = await self._load_emergent_prompt(
            query=user_message,
            conversation_history=conversation_history
        )
        if identity_context:
            print(f"✓ [LOCAL] Emergent prompt loaded ({len(identity_context)} chars)")
        else:
            # Fallback to basic identity buffer
            identity_context = await self._load_identity_buffer()
            if identity_context:
                print(f"✓ [LOCAL] Identity buffer loaded ({len(identity_context)} chars)")
            else:
                # CRITICAL: Use robust fallback personality
                # This ensures Luna ALWAYS has her identity, even if entity context fails
                # See: HANDOFF_CONTEXT_STARVATION.md
                identity_context = self.FALLBACK_PERSONALITY
                print(f"⚠ [LOCAL] Using FALLBACK_PERSONALITY ({len(identity_context)} chars)")
                logger.warning("[CONTEXT-FIX] Using FALLBACK_PERSONALITY in local path")

        # Build full system prompt with emergent personality context
        full_system_prompt = system_prompt

        # Add emergent personality context (DNA + Experience + Mood layers)
        if identity_context:
            full_system_prompt = f"""{full_system_prompt}

{identity_context}"""

        # CRITICAL: Fetch memory context for local generation too!
        # This enables Luna to remember people, places, and past conversations
        memory_context = await self._fetch_memory_context(user_message, max_tokens=1000)
        if memory_context:
            print(f"✓ [LOCAL] Memory context loaded ({len(memory_context)} chars)")
            full_system_prompt = f"""{full_system_prompt}

## Your Memories
The following are relevant memories from your memory matrix. Use these to provide personal, grounded responses:

{memory_context}

Reference these memories naturally as your own experiences and knowledge."""

        # Add conversation context from ring buffer (or text fallback)
        if ring_history:
            full_system_prompt = f"""{full_system_prompt}

## Recent Conversation
{ring_history}

Continue the conversation naturally, maintaining context from above."""

        return full_system_prompt

    async def _resolve_bridge(self):
        """
        Resolve the access bridge for the current speaker (FaceID).

        Returns BridgeResult or None. Cached per-message — call freely.
        Uses IdentityActor.current to get entity_id, then looks up the
        access_bridge table in the engine DB.
        """
        if not self.engine:
            return None
        identity_actor = self.engine.get_actor("identity")
        if not identity_actor or not identity_actor.current.is_present:
            return None
        entity_id = identity_actor.current.entity_id
        if not entity_id:
            return None
        try:
            from luna.identity.bridge import AccessBridge
            matrix_actor = self.engine.get_actor("matrix")
            if not matrix_actor or not matrix_actor.is_ready:
                return None
            db = matrix_actor._matrix.db
            bridge = AccessBridge(db)
            return await bridge.lookup(entity_id)
        except Exception as e:
            logger.warning("Bridge resolution failed: %s", e)
            return None

    async def _fetch_memory_context(self, query: str, max_tokens: int = 1500) -> str:
        """
        Fetch relevant memory context for a query.

        UPDATED: Uses Memory Economy constellation assembly when available for
        cluster-aware retrieval with lock-in prioritization.
        Also sets self._last_memory_confidence for L1 prompt control.
        """
        from luna.context.assembler import MemoryConfidence

        if not self.engine:
            logger.debug("Memory fetch: No engine available")
            self._last_memory_confidence = MemoryConfidence(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query=query,
            )
            return ""

        matrix = self.engine.get_actor("matrix")
        if not matrix:
            logger.warning("Memory fetch: Matrix actor not found")
            self._last_memory_confidence = MemoryConfidence(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query=query,
            )
            return ""

        if not matrix.is_ready:
            logger.warning(f"Memory fetch: Matrix not ready (state: {getattr(matrix, '_state', 'unknown')})")
            self._last_memory_confidence = MemoryConfidence(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query=query,
            )
            return ""

        logger.debug(f"Memory fetch: Searching for query '{query[:50]}...'")

        # Get active scopes from engine for project isolation
        active_scopes = getattr(self.engine, 'active_scopes', ["global"])
        active_project = getattr(self.engine, 'active_project', None)

        try:
            # Try Memory Economy constellation assembly first (cluster-aware retrieval)
            constellation_context = await self._fetch_constellation_context(query, max_tokens, matrix)
            if constellation_context:
                # Constellation retrieval implies high-quality matches
                self._last_memory_confidence = MemoryConfidence(
                    match_count=5, relevant_count=3, avg_similarity=0.0,
                    best_lock_in="settled", has_entity_match=True, query=query,
                )
                return constellation_context

            # Try get_context if available (with scope awareness)
            if hasattr(matrix, 'get_context'):
                logger.debug(f"Memory fetch: Using matrix.get_context() scopes={active_scopes}")
                context = await matrix.get_context(
                    query=query, max_tokens=max_tokens,
                    scopes=active_scopes if len(active_scopes) > 1 else None,
                    scope=active_scopes[0] if len(active_scopes) == 1 else None,
                )
                if context:
                    # Permission gate: strip DOCUMENT blocks from pre-formatted string
                    bridge_result = await self._resolve_bridge()
                    if bridge_result is None or not bridge_result.can_see_all:
                        import re
                        context = re.sub(
                            r"<memory\s+type=['\"](?:DOCUMENT|document)['\"][^>]*>.*?</memory>",
                            "", context, flags=re.DOTALL,
                        ).strip()
                        if not context:
                            logger.info("Memory fetch: all content was DOCUMENT, stripped by permission gate")
                    # Prepend project header if active
                    if active_project:
                        context = f"[Active Project: {active_project}]\n\n{context}"
                    if context.strip():
                        logger.info(f"Memory fetch: Found context ({len(context)} chars, scopes={active_scopes})")
                        self._last_memory_confidence = MemoryConfidence(
                            match_count=1, relevant_count=1, avg_similarity=0.0,
                            best_lock_in="fluid", has_entity_match=False, query=query,
                        )
                        return context
                else:
                    logger.debug("Memory fetch: get_context returned empty")

            # Fallback to direct search
            result = await self._fetch_basic_memory_context(query, max_tokens, matrix)
            if result:
                self._last_memory_confidence = MemoryConfidence(
                    match_count=1, relevant_count=1, avg_similarity=0.0,
                    best_lock_in="drifting", has_entity_match=False, query=query,
                )
            else:
                self._last_memory_confidence = MemoryConfidence(
                    match_count=0, relevant_count=0, avg_similarity=0.0,
                    best_lock_in="none", has_entity_match=False, query=query,
                )
            return result

        except Exception as e:
            logger.error(f"Memory fetch failed: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Memory fetch traceback: {traceback.format_exc()}")
            self._last_memory_confidence = MemoryConfidence(
                match_count=0, relevant_count=0, avg_similarity=0.0,
                best_lock_in="none", has_entity_match=False, query=query,
            )
            return ""

    async def _fetch_constellation_context(
        self,
        query: str,
        max_tokens: int,
        matrix
    ) -> str:
        """
        Fetch context using Memory Economy constellation assembly.

        This provides cluster-aware retrieval with:
        - Relevant clusters activated together
        - Lock-in prioritized node selection
        - Token-budgeted assembly
        """
        try:
            from luna.librarian.cluster_retrieval import ClusterRetrieval
            from luna.memory.constellation import ConstellationAssembler

            db_path = matrix._matrix.db_path
            if not db_path:
                logger.debug("Constellation fetch: No db_path available")
                return ""

            # Step 1: Get relevant nodes
            nodes = await matrix._matrix.search_nodes(query=query, limit=20)
            node_ids = [n.id for n in nodes] if nodes else []

            if not node_ids:
                logger.debug("Constellation fetch: No nodes found")
                return ""

            # Step 2: Find relevant clusters
            retrieval = ClusterRetrieval(db_path)
            cluster_results = retrieval.find_relevant_clusters(node_ids=node_ids, top_k=5)

            # Also include auto-activated clusters (high lock-in)
            auto_clusters = retrieval.get_auto_activated_clusters()
            seen_ids = {c.cluster_id for c, _ in cluster_results}
            for cluster in auto_clusters:
                if cluster.cluster_id not in seen_ids:
                    cluster_results.append((cluster, cluster.lock_in))

            # Step 3: Assemble constellation
            assembler = ConstellationAssembler(max_tokens=max_tokens)

            cluster_dicts = [{"cluster": c, "score": score} for c, score in cluster_results]
            node_dicts = [
                {"node_id": n.id, "id": n.id, "content": n.content, "node_type": n.node_type, "lock_in": getattr(n, 'lock_in', 0.5)}
                for n in nodes
            ]

            # Permission gate: strip DOCUMENT nodes the speaker can't see
            from luna.identity.permissions import gate_content
            bridge_result = await self._resolve_bridge()
            node_dicts, _denied = await gate_content(node_dicts, bridge_result, source="constellation")

            constellation = assembler.assemble(
                clusters=cluster_dicts,
                nodes=node_dicts,
                prioritize_clusters=True
            )

            # Step 4: Format for prompt
            context_parts = []

            # Add cluster context section if clusters were activated
            if constellation.clusters:
                context_parts.append("=== ACTIVE MEMORY CLUSTERS ===")
                for cluster_data in constellation.clusters:
                    cluster = cluster_data.get("cluster") or cluster_data
                    name = getattr(cluster, 'name', None) or cluster.get('name', 'Unknown')
                    state = getattr(cluster, 'state', None) or cluster.get('state', 'unknown')
                    lock_in_val = getattr(cluster, 'lock_in', None) or cluster.get('lock_in', 0)
                    context_parts.append(f"<cluster name='{name}' state='{state}' lock_in='{lock_in_val:.2f}'/>")
                context_parts.append("")

            # Add node context
            for node_data in constellation.nodes:
                node_type = node_data.get("node_type", "memory")
                content = node_data.get("content", "")
                lock_in_val = node_data.get("lock_in", 0.5)
                context_parts.append(
                    f"<memory type='{node_type}' lock_in='{lock_in_val:.2f}'>\n{content}\n</memory>"
                )

            result = "\n\n".join(context_parts)
            logger.info(
                f"Constellation context: {len(constellation.clusters)} clusters, "
                f"{len(constellation.nodes)} nodes, ~{constellation.total_tokens} tokens"
            )

            return result

        except ImportError:
            logger.debug("Memory Economy not available, skipping constellation fetch")
            return ""
        except Exception as e:
            logger.debug(f"Constellation fetch failed: {e}")
            return ""

    async def _fetch_basic_memory_context(self, query: str, max_tokens: int, matrix) -> str:
        """Basic node-only retrieval (fallback when Memory Economy unavailable)."""
        if not matrix._matrix:
            logger.warning("Memory fetch: matrix._matrix is None")
            return ""

        logger.debug("Memory fetch: Falling back to direct search_nodes()")
        nodes = await matrix._matrix.search_nodes(query=query, limit=10)
        logger.debug(f"Memory fetch: search_nodes returned {len(nodes) if nodes else 0} nodes")

        if not nodes:
            logger.debug("Memory fetch: No results found")
            return ""

        # Filter out potentially confusing identity nodes about other people
        filtered_nodes = []
        for node in nodes:
            content_lower = node.content.lower()
            # Skip nodes that seem to be about other people's identities
            if "my name is" in content_lower and "ahab" not in content_lower and "zayne" not in content_lower:
                logger.debug(f"Memory fetch: Filtering out node {node.id}")
                continue
            filtered_nodes.append(node)

        nodes = filtered_nodes or nodes  # Fallback to all if filter removes everything
        logger.debug(f"Memory fetch: After filtering, {len(nodes)} nodes")

        # Permission gate: strip DOCUMENT nodes the speaker can't access
        from luna.identity.permissions import gate_content as _gate
        bridge_result = await self._resolve_bridge()
        nodes, denied = await _gate(nodes, bridge_result, source="basic_memory")
        self._last_denied_count = len(denied)

        context_parts = []
        for node in nodes:
            age = self._humanize_age(node.created_at) if hasattr(node, 'created_at') else "unknown"
            context_parts.append(f"<memory type='{node.node_type}' age='{age}'>\n{node.content}\n</memory>")

        result = "\n\n".join(context_parts)
        logger.info(f"Memory fetch: Returning {len(context_parts)} memory nodes ({len(result)} chars)")
        return result

    def _humanize_age(self, timestamp) -> str:
        """Convert timestamp to human-readable age."""
        from datetime import datetime
        if isinstance(timestamp, str):
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                return "unknown"
        else:
            dt = timestamp

        delta = datetime.now() - dt.replace(tzinfo=None)
        days = delta.days

        if days == 0:
            return "today"
        elif days == 1:
            return "yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            return f"{days // 7} weeks ago"
        else:
            return f"{days // 30} months ago"

    async def _generate_with_delegation(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
        context_window: str = "",
        bridge_result=None,
    ) -> None:
        """
        Fast delegation flow:
        1. Fetch memory context for the query
        2. Quick hardcoded acknowledgment (no local inference - too slow)
        3. Delegate to Claude for response in Luna's voice with memory context

        Skips local narration step to stay under timeout.
        """
        self._delegated_generations += 1
        print(f"\n🔀 [DELEGATION] Starting for: '{user_message[:50]}...'")

        # Record user message to ring buffer (CRITICAL for history)
        self._active_ring.add_user(user_message)
        logger.debug("[DELEGATION-RING] Recorded user message to ring buffer (size: %d)", len(self._active_ring))

        # Build conversation history from ring buffer (structural guarantee)
        # Ring buffer is the SINGLE SOURCE OF TRUTH for recent conversation
        conversation_history = []
        if len(self._active_ring) > 0:
            conversation_history = self._active_ring.get_as_dicts()
            logger.debug("[DELEGATION] Using ring buffer for history (%d turns)", len(self._active_ring))
        elif context_window:
            # Fall back to text parsing only if ring is empty (shouldn't happen)
            logger.warning("[DELEGATION] Ring buffer empty, falling back to text parsing")
            for line in context_window.split("\n\n"):
                line = line.strip()
                if line.startswith("User:"):
                    conversation_history.append({"role": "user", "content": line[5:].strip()})
                elif line.startswith("Luna:"):
                    conversation_history.append({"role": "assistant", "content": line[5:].strip()})

        # ── PromptAssembler: single funnel for prompt construction ──
        assembler_result = await self._assembler.build(PromptRequest(
            message=user_message,
            conversation_history=conversation_history,
            route="delegated",
            auto_fetch_memory=True,
            bridge_result=bridge_result,
        ))
        enhanced_system_prompt = assembler_result.system_prompt
        self._last_system_prompt = assembler_result.system_prompt
        self._last_route_decision = "delegated"
        self._last_prompt_meta = assembler_result.to_dict()
        print(f"✓ [DELEGATION] Assembler: identity={assembler_result.identity_source} "
              f"memory={assembler_result.memory_source} voice={assembler_result.voice_injected} "
              f"temporal={assembler_result.gap_category} access={assembler_result.access_injected} "
              f"tokens≈{assembler_result.prompt_tokens}")

        # Memory context indicator — assembler already embedded memory in system_prompt
        # This is used below to decide query framing (knowledge queries check memories first)
        memory_context = assembler_result.memory_source  # truthy if memory was fetched

        # Step 3: Delegate to Claude - ask for response in Luna's voice directly
        try:
            print(f"📡 [DELEGATION] Calling Claude ({self._claude_model})...")

            # Build messages array with conversation history
            messages = []

            # Include recent conversation context as previous messages
            # Use ring buffer as single source of truth
            if len(self._active_ring) > 0:
                for turn in self._active_ring.get_as_dicts():
                    if turn["role"] in ["user", "assistant"] and turn.get("content"):
                        messages.append(turn)
                logger.debug("[DELEGATION] Built messages from ring buffer (%d turns)", len(messages))
            elif context_window:
                # Fallback to text parsing (shouldn't happen)
                logger.warning("[DELEGATION] Ring empty for messages, falling back to text parsing")
                for line in context_window.split("\n\n"):
                    line = line.strip()
                    if line.startswith("User:"):
                        messages.append({"role": "user", "content": line[5:].strip()})
                    elif line.startswith("Luna:"):
                        messages.append({"role": "assistant", "content": line[5:].strip()})

            # Detect query type for appropriate framing
            msg_lower = user_message.lower()

            is_memory_query = any(sig in msg_lower for sig in [
                "memory", "memories", "remember", "recall", "overview", "in-depth"
            ])

            is_relational_query = any(sig in msg_lower for sig in [
                "grown closer", "our relationship", "feel about", "between us",
                "how do you feel", "what do you think of me", "do you like",
                "do you love", "miss me", "care about", "trust me",
                "closer", "bonded", "connection", "friendship"
            ])

            # Detect "knowledge" queries that should check memories first
            # e.g. "tell me about X", "what do you know about X", "who is X"
            is_knowledge_query = any(sig in msg_lower for sig in [
                "tell me about", "what do you know", "do you know",
                "what is", "who is", "where is", "what are",
                "know about", "heard of", "know of",
            ])

            # If we have memory context and user is asking about something,
            # treat it as a memory query so Luna checks her memories first
            if is_memory_query or (is_knowledge_query and memory_context):
                luna_prompt = f"""You are Luna. The user is asking about something you may know from your memories.

User question: {user_message}

IMPORTANT: Your memory context is provided in the system prompt above. Check it first.

If you find relevant information in your memory context, share it naturally. Stick to what the memory
actually contains — do not add details, embellish, or extrapolate beyond what is written there.

If your memories do NOT contain relevant information about this topic, say honestly that you don't
have a memory of it. Do not guess or fabricate. You can offer to help explore the topic together."""

            elif is_relational_query:
                # Relational/emotional queries - NOT research, needs warmth
                luna_prompt = f"""You are Luna. The user is asking about your relationship with them.

THE USER IS ASKING YOU THIS QUESTION (answer it directly):
"{user_message}"

This is a personal, relational question. Use ONLY the conversation history and memory context
above to respond. If you have specific memories of interactions, reference them. If you don't
have memories about this aspect of your relationship, be honest about that rather than inventing
shared experiences.

Be warm and genuine, but grounded in what you actually know from your context."""

            else:
                # Research/factual queries
                luna_prompt = f"""You are Luna, a warm and curious AI companion.
The user asked something that requires current knowledge or research.

THE USER IS ASKING YOU THIS QUESTION (answer it directly):
"{user_message}"

Respond naturally as Luna - be warm, curious, and helpful.
If you don't have current information, say so honestly.
Keep your response focused and conversational."""

            # Add current message
            messages.append({"role": "user", "content": luna_prompt})

            # Try LLM registry streaming first
            provider = None
            provider_name = "claude"
            if LLM_REGISTRY_AVAILABLE:
                try:
                    provider = get_provider()
                    if provider and provider.is_available:
                        provider_name = provider.name
                except Exception as e:
                    logger.warning(f"LLM registry not available: {e}")
                    provider = None

            response_text = ""
            token_count = 0

            # Stream directly from provider to user (no Qwen narration pass)
            # Luna's voice is injected via enhanced_system_prompt, not post-hoc rewriting
            provider_succeeded = False
            if provider and provider_name != "claude":
                # Use registry provider — stream directly to callbacks
                print(f"✓ [DELEGATION] Streaming from {provider_name} provider...")
                llm_messages = [
                    LLMMessage("system", enhanced_system_prompt),
                ]
                for m in messages:
                    llm_messages.append(LLMMessage(m["role"], m["content"]))

                try:
                    async for text in provider.stream(
                        messages=llm_messages,
                        temperature=0.7,
                        max_tokens=max_tokens,
                    ):
                        if self._abort_requested:
                            print(f"⚠ [DELEGATION] Aborted!")
                            break
                        response_text += text
                        token_count += 1
                        await self._stream_to_callbacks(text)

                    elapsed_ms = (time.time() - start_time) * 1000
                    print(f"✓ [DELEGATION] Streamed: {token_count} chunks via {provider_name} in {elapsed_ms:.0f}ms")
                    provider_succeeded = True
                except Exception as provider_err:
                    logger.warning(f"[DELEGATION] {provider_name} failed: {provider_err}, trying fallback chain...")
                    print(f"⚠ [DELEGATION] {provider_name} failed, trying fallback chain...")
                    response_text = ""
                    token_count = 0

            if not provider_succeeded:
                # Use FallbackChain for resilient inference
                if self._fallback_chain:
                    print(f"✓ [DELEGATION] Streaming from FallbackChain...")
                    try:
                        async for text in self._fallback_chain.stream(
                            messages=messages,
                            system=enhanced_system_prompt,
                            max_tokens=max_tokens,
                            temperature=0.7,
                        ):
                            if self._abort_requested:
                                print(f"⚠ [DELEGATION] Aborted!")
                                break
                            response_text += text
                            token_count += 1
                            await self._stream_to_callbacks(text)

                        elapsed_ms = (time.time() - start_time) * 1000
                        provider_name = "fallback-chain"
                        print(f"✓ [DELEGATION] Streamed via FallbackChain in {elapsed_ms:.0f}ms")

                    except AllProvidersFailedError as e:
                        logger.error(f"[DELEGATION] All fallback providers failed: {e}")
                        error_message = "\n\n...sorry, I'm having trouble connecting right now. All my inference providers are unavailable. Try again in a moment?"
                        await self._stream_to_callbacks(error_message)
                        return
                else:
                    # Legacy: direct Claude streaming
                    with self.client.messages.stream(
                        model=self._claude_model,
                        max_tokens=max_tokens,
                        system=enhanced_system_prompt,
                        messages=messages,
                    ) as stream:
                        print(f"✓ [DELEGATION] Streaming from Claude...")
                        for text in stream.text_stream:
                            if self._abort_requested:
                                print(f"⚠ [DELEGATION] Aborted!")
                                break
                            response_text += text
                            token_count += 1
                            await self._stream_to_callbacks(text)

                        final = stream.get_final_message()
                        token_count = final.usage.output_tokens
                        elapsed_ms = (time.time() - start_time) * 1000
                        print(f"✓ [DELEGATION] Streamed: {token_count} tokens in {elapsed_ms:.0f}ms")

            final_response = response_text

            elapsed_ms = (time.time() - start_time) * 1000

            # Record response in ring buffer (CRITICAL for history)
            if final_response:
                self._active_ring.add_assistant(final_response)
                logger.debug("[DELEGATION-RING] Recorded response to ring buffer (size: %d)", len(self._active_ring))

            await self.send_to_engine("generation_complete", {
                "text": final_response,
                "correlation_id": correlation_id,
                "model": f"{provider_name} (delegated)",
                "output_tokens": token_count,
                "latency_ms": elapsed_ms,
                "delegated": True,
                "planned": True,
                "narration_applied": False,
                "access_denied_count": self._last_denied_count,
            })

        except Exception as e:
            print(f"❌ [DELEGATION] Failed: {e}")
            logger.error(f"Delegation failed: {e}")

            # Fall back to local inference if available
            if self.local_available:
                print(f"🏠 [DELEGATION→LOCAL] Falling back to local Qwen 3B...")
                logger.info(f"Delegation failed, falling back to local inference: {e}")
                try:
                    await self._generate_local_only(
                        user_message=user_message,
                        system_prompt=system_prompt,
                        max_tokens=max_tokens,
                        correlation_id=correlation_id,
                        start_time=start_time,
                        context_window=context_window,
                        bridge_result=bridge_result,
                    )
                    return
                except Exception as local_err:
                    logger.error(f"Local fallback also failed: {local_err}")

            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _generate_with_delegation_detection(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
    ) -> None:
        """
        Generate via local Qwen, watching for <REQ_CLAUDE> delegation signal.

        If Luna decides she needs Claude's help, she'll output:
        <REQ_CLAUDE>Let me look into that for you...</REQ_CLAUDE>

        We stream her acknowledgment, then delegate to Claude in background,
        then narrate the facts in Luna's voice.
        """
        response_buffer = ""
        token_count = 0
        delegation_detected = False
        acknowledgment = ""

        try:
            async for token in self._local.generate_stream(
                user_message,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
            ):
                if self._abort_requested:
                    logger.info("Director: Generation aborted")
                    break

                response_buffer += token
                token_count += 1

                # Check for delegation signal
                if self.REQ_CLAUDE_START in response_buffer and not delegation_detected:
                    delegation_detected = True
                    # Get everything before the tag
                    pre_tag = response_buffer.split(self.REQ_CLAUDE_START)[0]
                    # Stream the pre-tag content if any
                    if pre_tag and not pre_tag.isspace():
                        await self._stream_to_callbacks(pre_tag)

                    # If closing tag is also in buffer, extract acknowledgment
                    if self.REQ_CLAUDE_END in response_buffer:
                        inner = response_buffer.split(self.REQ_CLAUDE_START)[1]
                        acknowledgment = inner.split(self.REQ_CLAUDE_END)[0]
                        await self._stream_to_callbacks(acknowledgment)
                        break
                    continue

                # If we're inside the delegation tags, accumulate acknowledgment
                if delegation_detected and self.REQ_CLAUDE_END not in response_buffer:
                    # Check for closing tag
                    if self.REQ_CLAUDE_END in token:
                        # Got the closing tag
                        break
                    acknowledgment += token
                    await self._stream_to_callbacks(token)
                    continue

                # Normal streaming (no delegation)
                if not delegation_detected:
                    await self._stream_to_callbacks(token)

            elapsed_ms = (time.time() - start_time) * 1000

            if delegation_detected:
                # Luna asked for Claude's help - do the delegation
                logger.info(f"Delegation detected: '{acknowledgment[:50]}...'")
                self._delegated_generations += 1

                # Get facts from Claude
                facts = await self._delegate_to_claude(user_message, system_prompt)

                # Have Luna narrate the facts
                narration = await self._narrate_facts(user_message, facts, system_prompt)
                await self._stream_to_callbacks(narration)

                total_elapsed_ms = (time.time() - start_time) * 1000
                await self.send_to_engine("generation_complete", {
                    "text": acknowledgment + narration,
                    "correlation_id": correlation_id,
                    "model": "qwen-3b-local → claude",
                    "output_tokens": token_count,
                    "latency_ms": total_elapsed_ms,
                    "delegated": True,
                    "access_denied_count": self._last_denied_count,
                })
            else:
                # Pure local generation
                self._local_generations += 1
                logger.info(f"Director local: {token_count} tokens in {elapsed_ms:.0f}ms")

                await self.send_to_engine("generation_complete", {
                    "text": response_buffer,
                    "correlation_id": correlation_id,
                    "model": "qwen-3b-local",
                    "output_tokens": token_count,
                    "latency_ms": elapsed_ms,
                    "local": True,
                    "access_denied_count": self._last_denied_count,
                })

        except Exception as e:
            logger.error(f"Director generation error: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _stream_to_callbacks(self, text: str) -> None:
        """Stream text to all registered callbacks."""
        for callback in self._stream_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(text)
                else:
                    callback(text)
            except Exception as e:
                logger.error(f"Stream callback error: {e}")
        await asyncio.sleep(0)  # Yield control

    async def _delegate_to_claude(self, query: str, context: str) -> dict:
        """
        Delegate to Claude for research/analysis.

        Returns structured facts, NOT personality.
        Claude is a research assistant, not Luna.
        Uses FallbackChain for resilient inference.
        """
        try:
            prompt = f"""You are a research assistant providing factual information.
Do NOT adopt any personality. Just provide clear, structured facts.

Query: {query}

Provide:
- Key facts (bullet points)
- Any important caveats
- Confidence level (high/medium/low)

Be thorough but concise."""

            system_prompt = "You are a factual research assistant. No personality, just facts."
            messages = [{"role": "user", "content": prompt}]

            # Use FallbackChain for resilient inference
            if self._fallback_chain:
                logger.info("[DELEGATE] Using FallbackChain for research...")
                try:
                    result = await self._fallback_chain.generate(
                        messages=messages,
                        system=system_prompt,
                        max_tokens=1024,
                        temperature=0.7,
                    )
                    return {
                        "facts": result.content,
                        "tokens": len(result.content.split()),  # Approximate
                        "provider": result.provider_used,
                    }
                except AllProvidersFailedError as e:
                    logger.error(f"[DELEGATE] All fallback providers failed: {e}")
                    return {"facts": f"I couldn't complete that research: {e}", "error": True}
            else:
                # Legacy: direct Claude call
                response = self.client.messages.create(
                    model=self._claude_model,
                    max_tokens=1024,
                    system=system_prompt,
                    messages=messages,
                )

                facts_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        facts_text += block.text

                return {
                    "facts": facts_text,
                    "tokens": response.usage.output_tokens,
                }

        except Exception as e:
            logger.error(f"Claude delegation failed: {e}")
            return {"facts": f"I couldn't complete that research: {e}", "error": True}

    async def _narrate_facts(self, original_query: str, facts: dict, system_prompt: str) -> str:
        """
        Have Luna narrate Claude's facts in her voice.

        The user never hears Claude directly - only Luna.
        """
        facts_text = facts.get("facts", "")

        if facts.get("error"):
            return facts_text

        # STRICT narration to prevent Qwen LoRA from adding hallucinated content
        narration_system = """STRICT REPHRASING MODE. You are a text rephraser, not a conversationalist.

RULES (violations will be rejected):
1. Output ONLY the rephrased version of the input text. Nothing else.
2. NEVER add facts, memories, stories, names, dates, or concepts not in the input.
3. NEVER use asterisks (*action*), emojis, or roleplay markers.
4. Keep the same meaning and approximate length. Only change tone to be warmer.
5. If unsure, output the input text verbatim rather than risk adding anything."""

        narration_prompt = f"""REPHRASE ONLY — do not add any new information:

{facts_text}

OUTPUT:"""

        try:
            # Use local model to narrate in Luna's voice
            result = await self._local.generate(
                narration_prompt,
                system_prompt=narration_system,
                max_tokens=512,
            )
            return result.text
        except Exception as e:
            logger.error(f"Narration failed: {e}")
            return facts_text  # Fallback to raw facts

    async def _generate_claude_direct(
        self,
        user_message: str,
        system_prompt: str,
        max_tokens: int,
        correlation_id: str,
        start_time: float,
        context_window: str = "",
        bridge_result=None,
    ) -> None:
        """Fallback: Generate via LLM registry (or Claude) when local not available."""
        # Record user message to ring buffer (CRITICAL for history)
        self._active_ring.add_user(user_message)
        logger.debug("[FALLBACK-RING] Recorded user message to ring buffer (size: %d)", len(self._active_ring))

        try:
            # Load identity buffer for generation
            identity_context = await self._load_identity_buffer()

            # Build enhanced system prompt with identity context
            enhanced_system_prompt = system_prompt
            if identity_context:
                enhanced_system_prompt = f"""{system_prompt}

{identity_context}"""

            # Build messages array with conversation history
            messages = []

            # Include recent conversation context as previous messages
            if context_window:
                for line in context_window.split("\n\n"):
                    line = line.strip()
                    if line.startswith("User:"):
                        messages.append({"role": "user", "content": line[5:].strip()})
                    elif line.startswith("Luna:"):
                        messages.append({"role": "assistant", "content": line[5:].strip()})

            # Add current message
            messages.append({"role": "user", "content": user_message})

            # Try LLM registry first
            provider = None
            provider_name = "claude"
            if LLM_REGISTRY_AVAILABLE:
                try:
                    provider = get_provider()
                    if provider and provider.is_available:
                        provider_name = provider.name
                except Exception as e:
                    logger.warning(f"LLM registry not available: {e}")
                    provider = None

            response_text = ""
            token_count = 0

            if provider and provider_name != "claude":
                # Use registry provider streaming
                llm_messages = [LLMMessage("system", enhanced_system_prompt)]
                for m in messages:
                    llm_messages.append(LLMMessage(m["role"], m["content"]))

                async for text in provider.stream(
                    messages=llm_messages,
                    temperature=0.7,
                    max_tokens=max_tokens,
                ):
                    if self._abort_requested:
                        break
                    response_text += text
                    token_count += 1
                    await self._stream_to_callbacks(text)

                elapsed_ms = (time.time() - start_time) * 1000
                self._delegated_generations += 1

            else:
                # Use FallbackChain for resilient inference
                if self._fallback_chain:
                    logger.info("[FALLBACK] Using FallbackChain...")
                    try:
                        async for text in self._fallback_chain.stream(
                            messages=messages,
                            system=enhanced_system_prompt,
                            max_tokens=max_tokens,
                            temperature=0.7,
                        ):
                            if self._abort_requested:
                                break
                            response_text += text
                            token_count += 1
                            await self._stream_to_callbacks(text)

                        elapsed_ms = (time.time() - start_time) * 1000
                        self._delegated_generations += 1
                        provider_name = "fallback-chain"
                        logger.info(f"[FALLBACK] Complete via FallbackChain in {elapsed_ms:.0f}ms")

                    except AllProvidersFailedError as e:
                        logger.error(f"[FALLBACK] All providers failed: {e}")
                        # Graceful degradation: send error message to user instead of hanging
                        error_message = "...sorry, I'm having trouble connecting right now. All my inference providers are unavailable."
                        await self._stream_to_callbacks(error_message)
                        return  # Exit gracefully
                else:
                    # Legacy: direct Claude streaming (no FallbackChain)
                    with self.client.messages.stream(
                        model=self._claude_model,
                        max_tokens=max_tokens,
                        system=enhanced_system_prompt,
                        messages=messages,
                    ) as stream:
                        for text in stream.text_stream:
                            if self._abort_requested:
                                break
                            response_text += text
                            await self._stream_to_callbacks(text)

                        final = stream.get_final_message()
                        token_count = final.usage.output_tokens
                        elapsed_ms = (time.time() - start_time) * 1000
                        self._delegated_generations += 1

            # Record response in ring buffer (CRITICAL for history)
            if response_text:
                self._active_ring.add_assistant(response_text)
                logger.debug("[FALLBACK-RING] Recorded response to ring buffer (size: %d)", len(self._active_ring))

            await self.send_to_engine("generation_complete", {
                "text": response_text,
                "correlation_id": correlation_id,
                "model": f"{provider_name} (fallback)",
                "output_tokens": token_count,
                "latency_ms": elapsed_ms,
                "fallback": True,  # Local not available
                "access_denied_count": self._last_denied_count,
            })

        except Exception as e:
            logger.error(f"Fallback generation failed: {e}")
            await self.send_to_engine("generation_error", {
                "error": str(e),
                "correlation_id": correlation_id,
            })

    async def _handle_abort(self, msg: Message) -> None:
        """
        Abort current generation.

        For streaming: Sets abort flag, stream will stop at next chunk.
        For sync: Cannot abort (call is blocking).
        """
        if self._generating:
            logger.info(f"Director aborting generation: {self._current_correlation_id}")
            self._abort_requested = True

    async def snapshot(self) -> dict:
        """Snapshot state."""
        base = await super().snapshot()
        base.update({
            "model": self._model,
            "generating": self._generating,
            "abort_requested": self._abort_requested,
            "local_available": self.local_available,
            "local_generations": self._local_generations,
            "delegated_generations": self._delegated_generations,
        })

        # Add local inference stats if available
        if self._local is not None:
            base["local_stats"] = self._local.get_stats()

        return base

    @property
    def is_generating(self) -> bool:
        """Check if currently generating."""
        return self._generating

    def get_routing_stats(self) -> dict:
        """Get routing statistics."""
        total = self._local_generations + self._delegated_generations
        local_pct = (self._local_generations / total * 100) if total > 0 else 0

        stats = {
            "local_generations": self._local_generations,
            "delegated_generations": self._delegated_generations,
            "total_generations": total,
            "local_percentage": local_pct,
            "local_available": self.local_available,
        }

        if self._local is not None:
            stats["local_model_stats"] = self._local.get_stats()

        # Add fallback chain stats if available
        if self._fallback_chain is not None:
            stats["fallback_chain"] = self._fallback_chain.get_stats()

        return stats

    def get_last_system_prompt(self) -> dict:
        """
        Get the last system prompt sent to the LLM.

        Used by /prompt slash command for debugging context issues.

        Returns:
            Dict with system_prompt, route_decision, and truncated preview
        """
        if self._last_system_prompt is None:
            return {
                "available": False,
                "message": "No generation has occurred yet. Send a message first.",
            }

        prompt = self._last_system_prompt
        return {
            "available": True,
            "route_decision": self._last_route_decision or "unknown",
            "length": len(prompt),
            "preview": prompt[:500] + "..." if len(prompt) > 500 else prompt,
            "full_prompt": prompt,
            "assembler": self._last_prompt_meta,
        }

    def log_prompt_archaeology(self, query: str, response: str = "") -> dict:
        """
        Log detailed prompt analysis for archaeology investigation.

        Captures the full prompt with section breakdowns and token estimates.
        Writes to data/diagnostics/prompt_archaeology.jsonl

        Args:
            query: The user's query that triggered this prompt
            response: Optional response text for correlation

        Returns:
            Dict with full analysis including section breakdown
        """
        import json
        import re
        from datetime import datetime
        from pathlib import Path

        if self._last_system_prompt is None:
            return {"error": "No prompt available"}

        prompt = self._last_system_prompt

        # Section detection patterns
        section_patterns = [
            (r"^You are Luna.*?(?=\n##|\n###|$)", "IDENTITY_PREAMBLE"),
            (r"## Who You Are.*?(?=\n##|$)", "WHO_YOU_ARE"),
            (r"## Your Voice.*?(?=\n##|$)", "YOUR_VOICE"),
            (r"## Core Principles.*?(?=\n##|$)", "CORE_PRINCIPLES"),
            (r"### Core Identity.*?(?=\n###|\n##|$)", "CORE_IDENTITY"),
            (r"### Base Tone.*?(?=\n###|\n##|$)", "BASE_TONE"),
            (r"### Default Communication Patterns.*?(?=\n###|\n##|$)", "COMM_PATTERNS"),
            (r"### Inviolable Principles.*?(?=\n###|\n##|$)", "INVIOLABLE_PRINCIPLES"),
            (r"### Style Mechanics.*?(?=\n###|\n##|$)", "STYLE_MECHANICS"),
            (r"### Emoji Usage.*?(?=\n###|\n##|$)", "EMOJI_USAGE"),
            (r"### Formality.*?(?=\n###|\n##|$)", "FORMALITY"),
            (r"### Voice Examples.*?(?=\n###|\n##|$)", "VOICE_EXAMPLES"),  # SUSPECT
            (r"## Your Foundation.*?(?=\n##|$)", "DNA_FOUNDATION"),
            (r"## Who You've Become.*?(?=\n##|$)", "EXPERIENCE_LAYER"),
            (r"## Right Now.*?(?=\n##|$)", "MOOD_LAYER"),
            (r"## THIS SESSION.*?(?=\n##|$)", "THIS_SESSION"),
            (r"## KNOWN PEOPLE.*?(?=\n##|$)", "KNOWN_PEOPLE"),
            (r"## RETRIEVED CONTEXT.*?(?=\n##|$)", "RETRIEVED_CONTEXT"),
            (r"## Memory Context.*?(?=\n##|$)", "MEMORY_CONTEXT"),
        ]

        # Extract sections
        sections = {}
        total_tokens = 0

        for pattern, name in section_patterns:
            match = re.search(pattern, prompt, re.DOTALL | re.MULTILINE)
            if match:
                content = match.group(0)
                char_count = len(content)
                token_estimate = char_count // 4
                sections[name] = {
                    "chars": char_count,
                    "tokens_approx": token_estimate,
                    "preview": content[:200] + "..." if len(content) > 200 else content,
                }
                total_tokens += token_estimate

        # Calculate ratios
        for section in sections.values():
            if total_tokens > 0:
                section["percent"] = round(section["tokens_approx"] / total_tokens * 100, 1)
            else:
                section["percent"] = 0

        # Flag suspicious sections
        voice_examples = sections.get("VOICE_EXAMPLES", {})
        voice_tokens = voice_examples.get("tokens_approx", 0)
        pollution_warning = None
        if voice_tokens > 100:
            pollution_warning = f"VOICE_EXAMPLES is {voice_tokens} tokens ({voice_examples.get('percent', 0)}%) — suspect for copying"

        analysis = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "response_preview": response[:200] if response else "",
            "route": self._last_route_decision or "unknown",
            "total_chars": len(prompt),
            "total_tokens_approx": total_tokens,
            "sections": sections,
            "pollution_warning": pollution_warning,
            "full_prompt": prompt,
        }

        # Write to JSONL file
        log_path = Path("data/diagnostics/prompt_archaeology.jsonl")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(analysis) + "\n")

        logger.info(f"[ARCHAEOLOGY] Logged prompt: {total_tokens} tokens, {len(sections)} sections")
        if pollution_warning:
            logger.warning(f"[ARCHAEOLOGY] {pollution_warning}")

        return analysis

    # =========================================================================
    # Session Tracking for Reflection Loop
    # =========================================================================

    def track_message(self, role: str, content: str) -> None:
        """
        Track a message in the session history for later reflection.

        Args:
            role: 'user' or 'assistant'
            content: The message content
        """
        if self._session_start_time is None:
            self._session_start_time = time.time()

        self._session_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

        # Check if reflection should be triggered based on interaction count
        if self._reflection_loop:
            # This just increments the counter, actual reflection happens at session_end
            asyncio.create_task(self._maybe_auto_reflect())

    async def _maybe_auto_reflect(self) -> None:
        """Check if we should auto-reflect based on interaction count."""
        if not self._reflection_loop:
            return

        if await self._reflection_loop.should_reflect():
            logger.info("Auto-reflection triggered by interaction count")
            await self.session_end_reflection()

    async def session_end_reflection(self, user_name: str = "Ahab") -> Optional[dict]:
        """
        Trigger reflection at session end to generate personality patches.

        Analyzes the session history and generates a new patch if significant
        personality evolution is detected.

        Args:
            user_name: Name of the user for the reflection prompt

        Returns:
            Dict with reflection results, or None if reflection not available
        """
        if not self._reflection_loop or not self._patch_manager:
            logger.debug("Reflection loop or patch manager not available")
            return None

        if not self._session_history:
            logger.debug("No session history to reflect on")
            return None

        try:
            # Get current active patches for context
            current_patches = await self._patch_manager.get_all_active_patches(limit=10)

            # Define the LLM generation function for reflection
            async def llm_generate(prompt: str) -> str:
                return await self.generate(prompt, max_tokens=500)

            # Run reflection
            logger.info(f"Running session-end reflection on {len(self._session_history)} messages")
            new_patch = await self._reflection_loop.generate_reflection(
                session_history=self._session_history,
                current_patches=current_patches,
                llm_generate=llm_generate,
                user_name=user_name,
            )

            # Also reinforce existing patches based on session content
            reinforced = await self._reflection_loop.reinforce_existing_patches(
                session_history=self._session_history,
                current_patches=current_patches,
            )

            result = {
                "new_patch": new_patch.to_dict() if new_patch else None,
                "reinforced_patches": reinforced,
                "session_messages": len(self._session_history),
            }

            logger.info(f"Reflection complete: new_patch={new_patch is not None}, reinforced={len(reinforced)}")
            return result

        except Exception as e:
            logger.error(f"Session reflection failed: {e}")
            return {"error": str(e)}

    def clear_session(self) -> None:
        """Clear the session history for a fresh start."""
        self._session_history = []
        self._session_start_time = None
        if self._reflection_loop:
            self._reflection_loop._interaction_count = 0
        # Reset voice system for fresh conversation
        self._voice_turn_count = 0
        if self._voice_orchestrator:
            self._voice_orchestrator.on_conversation_start()
        # Reset perception field for fresh observation slate
        self._perception_field.reset()
        self._perception_turn_count = 0
        logger.debug("Session cleared")

    def get_session_stats(self) -> dict:
        """Get statistics about the current session."""
        duration_seconds = 0
        if self._session_start_time:
            duration_seconds = time.time() - self._session_start_time

        return {
            "message_count": len(self._session_history),
            "duration_seconds": duration_seconds,
            "user_messages": sum(1 for m in self._session_history if m["role"] == "user"),
            "assistant_messages": sum(1 for m in self._session_history if m["role"] == "assistant"),
        }

    # =========================================================================
    # Direct Generation API (for AgentLoop)
    # =========================================================================

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
        This is the direct async interface for AgentLoop to use.

        Args:
            prompt: The prompt to generate from
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        should_delegate = await self._should_delegate(prompt)

        if should_delegate or not self.local_available:
            return await self._generate_cloud(prompt, system, max_tokens, temperature)
        else:
            return await self._generate_local_direct(prompt, system, max_tokens, temperature)

    async def _generate_cloud(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate using LLM registry provider (or Claude fallback)."""
        # Try LLM registry first
        if LLM_REGISTRY_AVAILABLE:
            try:
                provider = get_provider()
                if provider and provider.is_available:
                    messages = [
                        LLMMessage("system", system or "You are Luna, a helpful AI assistant."),
                        LLMMessage("user", prompt),
                    ]
                    result = await provider.complete(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    self._delegated_generations += 1
                    logger.info(f"Generated via {provider.name}: {result.usage}")
                    return result.content
            except Exception as e:
                logger.warning(f"LLM registry generation failed, falling back to Claude: {e}")

        # Fallback to direct Anthropic client
        if not self._client:
            _ = self.client  # Lazy init

        messages = [{"role": "user", "content": prompt}]

        response = self.client.messages.create(
            model=self._claude_model,
            max_tokens=max_tokens,
            system=system or "You are Luna, a helpful AI assistant.",
            messages=messages,
        )

        self._delegated_generations += 1
        return response.content[0].text

    async def _generate_local_direct(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> str:
        """Generate using local inference (synchronous, not streaming)."""
        if not self._local:
            raise RuntimeError("Local inference not available")

        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"

        result = await self._local.generate(
            full_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        self._local_generations += 1
        return result.text if hasattr(result, 'text') else str(result)

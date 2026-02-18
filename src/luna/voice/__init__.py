"""
Luna Voice Package
==================

Two-engine voice system that makes Luna sound like Luna.

Components:
- VoiceLock: Frozen voice parameters for a single generation (legacy)
- VoiceSystemOrchestrator: Single entry point for context_builder
- VoiceBlendEngine: Confidence-weighted scaffolding (primary)
- VoiceCorpusService: Static few-shot + kill list (fallback)
"""

from luna.voice.lock import VoiceLock, classify_query_type
from luna.voice.models import (
    ConfidenceSignals,
    ConfidenceTier,
    ContextType,
    EmotionalRegister,
    EngineMode,
    VoiceSeed,
    VoiceSystemConfig,
)
from luna.voice.orchestrator import VoiceSystemOrchestrator

__all__ = [
    # Legacy
    "VoiceLock",
    "classify_query_type",
    # Voice System
    "VoiceSystemOrchestrator",
    "VoiceSystemConfig",
    "VoiceSeed",
    "ConfidenceSignals",
    "ConfidenceTier",
    "ContextType",
    "EmotionalRegister",
    "EngineMode",
]

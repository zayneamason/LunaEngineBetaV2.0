"""
Luna Voice Package
==================

Query-based voice parameter tuning for response generation.

Components:
- VoiceLock: Frozen voice parameters for a single generation
- classify_query_type: Helper for query type classification
"""

from luna.voice.lock import VoiceLock, classify_query_type

__all__ = ["VoiceLock", "classify_query_type"]

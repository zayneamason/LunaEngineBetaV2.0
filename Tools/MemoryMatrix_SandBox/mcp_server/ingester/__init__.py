"""
Transcript Ingester - Retroactive Memory Extraction for Luna

This package implements the 4-phase pipeline for extracting structured knowledge
from 928 historical Claude conversation transcripts and populating Memory Matrix.

Pipeline: TRIAGE → EXTRACT → RESOLVE → COMMIT

Luna's Constraints:
- C1: Era-weighted lock-in (depth of field)
- C2: OBSERVATION nodes (recognition over retrieval)
- C3: Texture tags (emotional register)
- C4: Selective extraction (sparsity is a feature)
- C5: Honest provenance (inherited vs firsthand)
"""

from .scanner import TranscriptScanner
from .triager import TranscriptTriager
from .extractor import TranscriptExtractor
from .resolver import TranscriptResolver
from .committer import TranscriptCommitter
from .validation import validate_extraction_schema, ExtractionValidationError

__all__ = [
    "TranscriptScanner",
    "TranscriptTriager",
    "TranscriptExtractor",
    "TranscriptResolver",
    "TranscriptCommitter",
    "validate_extraction_schema",
    "ExtractionValidationError",
]

"""
FaceID Matcher Module
=====================

Matches live face embeddings against stored embeddings using cosine similarity.
Returns identity results with confidence scores and permission tiers.

Linear scan — fast enough for <1000 embeddings.
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

from .database import FaceDatabase, StoredFace, AccessBridge
from .encoder import FaceDetection

logger = logging.getLogger(__name__)


@dataclass
class IdentityResult:
    """Result of face → entity matching."""
    entity_id: Optional[str]
    entity_name: Optional[str]
    confidence: float
    is_known: bool
    is_new_face: bool
    luna_tier: str
    dataroom_tier: int
    dataroom_categories: list[int]


class IdentityMatcher:
    """
    Matches face embeddings against stored faces.
    
    Uses cosine similarity (dot product on L2-normalized vectors).
    Conservative thresholds to prevent false matches.
    """
    
    MATCH_THRESHOLD = 0.55       # Below = unknown
    HIGH_CONFIDENCE = 0.70       # Above = confident match
    
    def __init__(self, db: FaceDatabase):
        self.db = db
        self._cache: Optional[list[StoredFace]] = None
    
    def invalidate_cache(self):
        """Clear the embedding cache (call after enrollment)."""
        self._cache = None
    
    def _load_cache(self):
        """Load all embeddings into memory for fast matching."""
        if self._cache is None:
            self._cache = self.db.get_all_embeddings()
            logger.info(f"Loaded {len(self._cache)} embeddings into cache")
    
    def match(self, detection: FaceDetection) -> IdentityResult:
        """
        Match a face detection against all known faces.
        
        Returns best match or unknown result.
        """
        self._load_cache()
        
        if not self._cache:
            return self._unknown_result(detection.confidence)
        
        best_entity_id = None
        best_entity_name = None
        best_score = 0.0
        
        # Linear scan with cosine similarity
        for stored in self._cache:
            # Both vectors are L2-normalized, so dot product = cosine sim
            score = float(np.dot(detection.embedding, stored.embedding))
            
            if score > best_score:
                best_score = score
                best_entity_id = stored.entity_id
                best_entity_name = stored.entity_name
        
        if best_score < self.MATCH_THRESHOLD:
            self.db._log("match_failed", details=f"best_score={best_score:.3f}", 
                        confidence=best_score)
            return self._unknown_result(best_score)
        
        # Look up access bridge
        access = self.db.get_access(best_entity_id)
        
        luna_tier = access.luna_tier if access else "unknown"
        dr_tier = access.dataroom_tier if access else 5
        dr_cats = access.dataroom_categories if access else []
        
        self.db._log("match_success", best_entity_id, best_entity_name,
                     f"score={best_score:.3f}, luna_tier={luna_tier}",
                     best_score)
        
        return IdentityResult(
            entity_id=best_entity_id,
            entity_name=best_entity_name,
            confidence=best_score,
            is_known=True,
            is_new_face=False,
            luna_tier=luna_tier,
            dataroom_tier=dr_tier,
            dataroom_categories=dr_cats,
        )
    
    def match_best_of_n(self, detections: list[FaceDetection]) -> IdentityResult:
        """
        Match using the best detection from multiple captures.
        
        Takes N detections (e.g., from multiple frames), matches each,
        and returns the highest confidence result. More robust than
        single-frame matching.
        """
        if not detections:
            return self._unknown_result(0.0)
        
        best_result = None
        
        for det in detections:
            result = self.match(det)
            if best_result is None or result.confidence > best_result.confidence:
                best_result = result
        
        return best_result
    
    def _unknown_result(self, confidence: float) -> IdentityResult:
        """Create an unknown/unmatched result."""
        return IdentityResult(
            entity_id=None,
            entity_name=None,
            confidence=confidence,
            is_known=False,
            is_new_face=True,
            luna_tier="unknown",
            dataroom_tier=5,
            dataroom_categories=[],
        )

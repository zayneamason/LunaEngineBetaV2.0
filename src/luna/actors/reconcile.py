"""
Reconcile Manager — Self-Correction for Confabulation
======================================================

When Scout flags confabulation after a response is already delivered,
ReconcileManager queues a natural self-correction for the next 1-2 turns.
Luna circles back and corrects herself conversationally, not robotically.

See: Docs/HANDOFF_CONFABULATION_RECONCILE_SCRIBE_V2.md
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReconcileState:
    """Tracks pending self-corrections."""
    pending: bool = False
    flagged_claims: list = field(default_factory=list)
    original_query: str = ""
    turns_since_flag: int = 0
    max_turns: int = 2
    reconcile_instruction: str = ""


RECONCILE_PATTERNS = re.compile(
    r"(actually|to be (honest|straight|fair))"
    r"|(i (was|may have been) (filling in|making up|guessing|inventing))"
    r"|(i (don.t|didn.t) actually (have|know|remember))"
    r"|(let me correct|i should clarify|i want to be straight)"
    r"|(my earlier (response|answer|claim) (was|wasn.t))"
    r"|(i (think|realize) i (was|may have been) confusing)",
    re.IGNORECASE,
)


class ReconcileManager:
    """Manages Luna's self-correction flow after confabulation detection."""

    def __init__(self):
        self._state = ReconcileState()

    def flag_confabulation(
        self,
        claims: list,
        original_query: str,
    ) -> None:
        """Flag a confabulation for reconciliation."""
        self._state.pending = True
        self._state.flagged_claims = claims
        self._state.original_query = original_query
        self._state.turns_since_flag = 0

        claim_summary = "; ".join(
            c.get("claim", "")[:60] for c in claims[:3]
        )
        self._state.reconcile_instruction = (
            f"IMPORTANT — SELF-CORRECTION NEEDED: In a recent response about "
            f"'{original_query}', you presented information as recalled memory that "
            f"was not supported by your actual context. Specifically: {claim_summary}. "
            f"When natural in conversation, briefly acknowledge this honestly. "
            f"Example: 'Actually, I want to be straight with you — I think I was "
            f"filling in gaps earlier rather than pulling from real memory about that.' "
            f"Do NOT be dramatic. Do NOT apologize excessively. Just be honest and move on."
        )

        logger.info(f"[RECONCILE] Flagged {len(claims)} unsupported claims for correction")

    def tick(self) -> Optional[str]:
        """
        Called each turn. Returns reconcile instruction if correction is due.

        Returns:
            Reconcile instruction string to inject into system prompt, or None
        """
        if not self._state.pending:
            return None

        self._state.turns_since_flag += 1

        if self._state.turns_since_flag <= self._state.max_turns:
            return self._state.reconcile_instruction

        logger.warning(
            f"[RECONCILE] Window expired without reconciliation "
            f"(query: '{self._state.original_query[:40]}')"
        )
        self.clear()
        return None

    def clear(self) -> None:
        """Clear reconcile state after successful correction."""
        self._state = ReconcileState()

    def did_reconcile(self, response: str) -> bool:
        """Check if Luna's response contains a natural self-correction."""
        if not self._state.pending:
            return False
        return bool(RECONCILE_PATTERNS.search(response))

    def get_status(self) -> dict:
        """Current Reconcile state for debug output."""
        return {
            "pending": self._state.pending,
            "turns_since_flag": self._state.turns_since_flag,
            "max_turns": self._state.max_turns,
            "claim_count": len(self._state.flagged_claims),
            "original_query": self._state.original_query[:50] if self._state.original_query else "",
        }

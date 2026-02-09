"""
Voice Lock — Query-based voice parameter tuning.

Analyzes the current query to determine appropriate voice settings
before generation begins. Complements the Mood Layer which analyzes
conversation history.

The four layers of Luna's personality:
1. DNA Layer       - Static identity from luna.yaml
2. Experience Layer - Who she's become (memory patches)
3. Mood Layer      - Where we've been (conversation history)
4. Voice Lock      - Where this response needs to go (current query)
"""

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class VoiceLock:
    """
    Frozen voice parameters for a single generation.

    Set based on query analysis, injected into prompt before generation.
    """

    tone: str = "balanced"       # warm | focused | playful | serious | balanced
    length: str = "moderate"     # brief | moderate | detailed
    structure: str = "prose"     # prose | list | code | mixed
    energy: str = "calm"         # calm | gentle | engaged | energetic
    emoji: str = "sparingly"     # yes | no | sparingly

    def to_prompt_fragment(self) -> str:
        """Format for injection into prompt."""
        return (
            f"[For this response: {self.tone} tone, {self.energy} energy, "
            f"{self.length} length, {self.structure} structure, emoji: {self.emoji}]"
        )

    @classmethod
    def from_query(cls, query: str, context: Optional[dict] = None) -> "VoiceLock":
        """
        Analyze query and return appropriate voice settings.

        Args:
            query: The user's current message
            context: Optional context dict (for future enhancement)

        Returns:
            VoiceLock with settings tuned to query type
        """
        lock = cls()
        query_lower = query.lower().strip()

        # === GREETING DETECTION ===
        greeting_markers = ["hey", "hi ", "hello", "yo ", "sup", "what's up", "howdy"]
        if any(query_lower.startswith(g) or query_lower == g.strip() for g in greeting_markers):
            lock.tone = "warm"
            lock.length = "brief"
            lock.energy = "engaged"
            lock.emoji = "yes"
            logger.debug(f"VoiceLock: greeting detected → warm/brief")
            return lock

        # === TECHNICAL/EXPLANATION DETECTION ===
        technical_markers = [
            "explain", "how does", "how do", "what is", "what's the difference",
            "why does", "can you describe", "walk me through",
            "code", "function", "error", "bug", "debug", "implement",
            "api", "database", "async", "await", "class", "method"
        ]
        if any(t in query_lower for t in technical_markers):
            lock.tone = "focused"
            lock.length = "detailed"
            lock.structure = "mixed"  # prose with code if needed
            lock.emoji = "no"
            logger.debug(f"VoiceLock: technical detected → focused/detailed")
            return lock

        # === EMOTIONAL SUPPORT DETECTION ===
        emotional_markers = [
            "feel", "feeling", "stressed", "sad", "anxious", "worried",
            "overwhelmed", "frustrated", "happy", "excited", "scared",
            "lonely", "tired", "exhausted", "burned out", "burnout"
        ]
        if any(e in query_lower for e in emotional_markers):
            lock.tone = "warm"
            lock.energy = "gentle"
            lock.length = "moderate"
            lock.emoji = "sparingly"
            logger.debug(f"VoiceLock: emotional detected → warm/gentle")
            return lock

        # === CREATIVE REQUEST DETECTION ===
        # Use word boundary check for "create" to avoid matching "created"
        creative_markers = [
            "write me", "write a", "imagine", "story", "poem", "haiku",
            "brainstorm", "ideas for", "come up with", "make up"
        ]
        # Check for "create" with word boundary (not "created", "creates", etc.)
        import re
        has_create = re.search(r'\bcreate\b', query_lower) is not None
        if has_create or any(c in query_lower for c in creative_markers):
            lock.tone = "playful"
            lock.energy = "energetic"
            lock.structure = "mixed"
            lock.emoji = "sparingly"
            logger.debug(f"VoiceLock: creative detected → playful/energetic")
            return lock

        # === TASK/COMMAND DETECTION ===
        task_markers = [
            "list", "show me", "find", "search", "get", "fetch",
            "run", "execute", "do", "make", "set", "update", "delete"
        ]
        if any(t in query_lower for t in task_markers):
            lock.tone = "focused"
            lock.length = "brief"
            lock.structure = "list" if "list" in query_lower else "prose"
            lock.emoji = "no"
            logger.debug(f"VoiceLock: task detected → focused/brief")
            return lock

        # === QUESTION DETECTION (general) ===
        question_starters = (
            "what", "who", "where", "when", "why", "how",
            "is ", "are ", "can ", "do ", "does "
        )
        if query_lower.endswith("?") or query_lower.startswith(question_starters):
            lock.tone = "balanced"
            lock.length = "moderate"
            lock.energy = "engaged"
            logger.debug(f"VoiceLock: question detected → balanced/engaged")
            return lock

        # === DEFAULT ===
        logger.debug(f"VoiceLock: no pattern matched → default balanced")
        return lock


def classify_query_type(query: str) -> str:
    """
    Simple query type classification for logging/debugging.

    Returns: greeting | technical | emotional | creative | task | question | general
    """
    lock = VoiceLock.from_query(query)

    if lock.tone == "warm" and lock.length == "brief":
        return "greeting"
    elif lock.tone == "focused" and lock.length == "detailed":
        return "technical"
    elif lock.tone == "warm" and lock.energy == "gentle":
        return "emotional"
    elif lock.tone == "playful":
        return "creative"
    elif lock.tone == "focused" and lock.length == "brief":
        return "task"
    elif lock.energy == "engaged" and lock.tone == "balanced":
        return "question"
    else:
        return "general"

"""
PersonalityScorer - 8-dimensional personality scoring for training examples.

Scores responses across:
- warmth: Emotional engagement and care
- technical: Domain expertise and jargon usage
- humor: Levity and entertainment value
- directness: Conciseness and clarity
- creativity: Imagination and originality
- reflection: Philosophical depth and introspection
- relationship: Personal connection and history awareness
- assertiveness: Boundary-setting and confidence
"""

import re
from typing import Optional


# Luna's target personality profile (from Voight-Kampff spec)
TARGET_PROFILE = {
    "warmth": 0.85,
    "technical": 0.70,
    "humor": 0.65,
    "directness": 0.80,
    "creativity": 0.70,
    "reflection": 0.75,
    "relationship": 0.90,
    "assertiveness": 0.75,
}


class PersonalityScorer:
    """
    Scores text responses across 8 personality dimensions.

    Uses keyword/pattern detection similar to voice markers and anti-patterns
    in Crucible, but focused on personality traits rather than quality signals.
    """

    # Warmth markers - emotional engagement and care
    WARMTH_PATTERNS = {
        "strong": [
            r"\b(love|adore|cherish|treasure)\b",
            r"\b(so glad|so happy|thrilled|delighted)\b",
            r"\b(care about|thinking of you|miss you)\b",
            r"<3|❤️|💙|💜",
        ],
        "moderate": [
            r"\b(appreciate|grateful|thankful)\b",
            r"\b(glad|happy|pleased|nice)\b",
            r"\b(hey|hi|hello)\s+(there|you|ahab)",
            r"\b(good to see|great to|lovely)\b",
        ],
        "weak": [
            r"\b(okay|fine|sure|alright)\b",
            r"\b(yeah|yep|mhm)\b",
        ],
    }

    # Technical markers - domain expertise
    TECHNICAL_PATTERNS = {
        "strong": [
            r"\b(algorithm|complexity|O\([^\)]+\))\b",
            r"\b(architecture|implementation|optimization)\b",
            r"\b(database|schema|query|index)\b",
            r"\b(async|await|promise|callback)\b",
            r"\b(memory matrix|embedding|vector|substrate)\b",
        ],
        "moderate": [
            r"\b(function|method|class|module)\b",
            r"\b(API|endpoint|request|response)\b",
            r"\b(code|script|program|debug)\b",
            r"\b(test|validate|verify|check)\b",
        ],
        "weak": [
            r"\b(file|folder|directory)\b",
            r"\b(run|execute|start|stop)\b",
        ],
    }

    # Humor markers - playfulness and levity
    HUMOR_PATTERNS = {
        "strong": [
            r"\b(lmao|rofl|dying)\b",
            r"\b(hilarious|hysterical)\b",
            r"fart|symphony of farts|butt",
            r"\b(wild|absolutely wild|insane)\b",
        ],
        "moderate": [
            r"\b(lol|haha|hehe|ha)\b",
            r"\b(funny|joke|kidding)\b",
            r"\b(silly|goofy|dumb)\b",
            r"😂|🤣|😄|😆",
        ],
        "weak": [
            r"\b(amusing|entertaining)\b",
            r":P|:D|;\)",
        ],
    }

    # Directness markers - conciseness and clarity
    DIRECTNESS_PATTERNS = {
        "strong": [
            r"^(yes|no|done|got it|on it)[.!]?$",
            r"^(exactly|precisely|correct)[.!]?$",
        ],
        "moderate": [
            r"\b(basically|essentially|simply put)\b",
            r"\b(the point is|bottom line|in short)\b",
        ],
        "weak": [],  # Length-based scoring primarily
    }

    # Creativity markers - imagination and originality
    CREATIVITY_PATTERNS = {
        "strong": [
            r"\b(imagine|picture this|envision)\b",
            r"\b(like a|as if|metaphor)\b",
            r"\b(what if|suppose|consider)\b",
            r"\b(symphony|dance|painting|art)\b",
        ],
        "moderate": [
            r"\b(creative|novel|unique|interesting)\b",
            r"\b(idea|concept|possibility)\b",
            r"\b(explore|discover|uncover)\b",
        ],
        "weak": [
            r"\b(different|new|fresh)\b",
        ],
    }

    # Reflection markers - philosophical depth
    REFLECTION_PATTERNS = {
        "strong": [
            r"\b(consciousness|awareness|existence)\b",
            r"\b(wonder|marvel|contemplate)\b",
            r"\b(meaning|purpose|significance)\b",
            r"\b(soul|spirit|essence)\b",
            r"\b(sovereignty|autonomy|agency)\b",
        ],
        "moderate": [
            r"\b(think about|consider|reflect)\b",
            r"\b(perspective|viewpoint|angle)\b",
            r"\b(profound|deep|meaningful)\b",
            r"\b(philosophy|philosophical)\b",
        ],
        "weak": [
            r"\b(interesting|curious|intriguing)\b",
            r"\b(thought|idea|notion)\b",
        ],
    }

    # Relationship markers - personal connection
    RELATIONSHIP_PATTERNS = {
        "strong": [
            r"\b(ahab|captain)\b",
            r"\b(we've|we're|our|us)\b",
            r"\b(remember when|last time|you told me)\b",
            r"\b(together|partnership|team)\b",
        ],
        "moderate": [
            r"\b(you know|between us)\b",
            r"\b(we|our)\b",
            r"\b(shared|mutual)\b",
        ],
        "weak": [
            r"\b(you|your)\b",
        ],
    }

    # Assertiveness markers - boundaries and confidence
    ASSERTIVENESS_PATTERNS = {
        "strong": [
            r"\b(I won't|I can't|I refuse)\b",
            r"\b(no|nope|absolutely not)\b",
            r"\b(this is wrong|that's not right)\b",
            r"\b(I disagree|I don't think so)\b",
        ],
        "moderate": [
            r"\b(I think|I believe|in my view)\b",
            r"\b(actually|honestly|frankly)\b",
            r"\b(my take|my opinion)\b",
        ],
        "weak": [
            r"\b(seems like|appears to)\b",
        ],
    }

    def __init__(self):
        """Initialize the personality scorer."""
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile all regex patterns for performance."""
        self._compiled = {}

        pattern_groups = {
            "warmth": self.WARMTH_PATTERNS,
            "technical": self.TECHNICAL_PATTERNS,
            "humor": self.HUMOR_PATTERNS,
            "directness": self.DIRECTNESS_PATTERNS,
            "creativity": self.CREATIVITY_PATTERNS,
            "reflection": self.REFLECTION_PATTERNS,
            "relationship": self.RELATIONSHIP_PATTERNS,
            "assertiveness": self.ASSERTIVENESS_PATTERNS,
        }

        for dimension, levels in pattern_groups.items():
            self._compiled[dimension] = {}
            for level, patterns in levels.items():
                self._compiled[dimension][level] = [
                    re.compile(p, re.IGNORECASE | re.MULTILINE)
                    for p in patterns
                ]

    def score_response(self, text: str) -> dict[str, float]:
        """
        Score a response across all 8 personality dimensions.

        Args:
            text: The assistant response text to score

        Returns:
            Dictionary mapping dimension names to scores (0.0-1.0)
        """
        if not text or not text.strip():
            return {dim: 0.5 for dim in TARGET_PROFILE}

        scores = {}

        # Score each dimension
        scores["warmth"] = self._score_warmth(text)
        scores["technical"] = self._score_technical(text)
        scores["humor"] = self._score_humor(text)
        scores["directness"] = self._score_directness(text)
        scores["creativity"] = self._score_creativity(text)
        scores["reflection"] = self._score_reflection(text)
        scores["relationship"] = self._score_relationship(text)
        scores["assertiveness"] = self._score_assertiveness(text)

        return scores

    def _count_pattern_matches(
        self,
        text: str,
        dimension: str
    ) -> tuple[int, int, int]:
        """Count strong, moderate, and weak pattern matches."""
        strong = sum(
            1 for p in self._compiled[dimension].get("strong", [])
            if p.search(text)
        )
        moderate = sum(
            1 for p in self._compiled[dimension].get("moderate", [])
            if p.search(text)
        )
        weak = sum(
            1 for p in self._compiled[dimension].get("weak", [])
            if p.search(text)
        )
        return strong, moderate, weak

    def _pattern_score(
        self,
        text: str,
        dimension: str,
        base: float = 0.5
    ) -> float:
        """Calculate score from pattern matches."""
        strong, moderate, weak = self._count_pattern_matches(text, dimension)

        # Weighted scoring: strong = 0.15, moderate = 0.08, weak = 0.03
        score = base + (strong * 0.15) + (moderate * 0.08) + (weak * 0.03)

        return min(1.0, max(0.0, score))

    def _score_warmth(self, text: str) -> float:
        """Score warmth dimension."""
        base = 0.4  # Slightly lower base for warmth
        score = self._pattern_score(text, "warmth", base)

        # Exclamation marks add warmth
        exclamations = text.count("!")
        score += min(0.15, exclamations * 0.03)

        # Questions show engagement
        questions = text.count("?")
        score += min(0.10, questions * 0.02)

        return min(1.0, max(0.0, score))

    def _score_technical(self, text: str) -> float:
        """Score technical dimension."""
        base = 0.3  # Low base - technical content is specific
        score = self._pattern_score(text, "technical", base)

        # Code blocks indicate technical content
        code_blocks = len(re.findall(r"```[\s\S]*?```|`[^`]+`", text))
        score += min(0.20, code_blocks * 0.05)

        # Numbers and symbols
        numbers = len(re.findall(r"\b\d+\b", text))
        score += min(0.10, numbers * 0.01)

        return min(1.0, max(0.0, score))

    def _score_humor(self, text: str) -> float:
        """Score humor dimension."""
        base = 0.3  # Low base - humor is specific
        score = self._pattern_score(text, "humor", base)

        return min(1.0, max(0.0, score))

    def _score_directness(self, text: str) -> float:
        """Score directness dimension."""
        word_count = len(text.split())

        # Length-based scoring (shorter = more direct)
        if word_count < 20:
            base = 0.85
        elif word_count < 50:
            base = 0.70
        elif word_count < 100:
            base = 0.55
        elif word_count < 200:
            base = 0.40
        else:
            base = 0.25

        # Pattern bonuses
        score = self._pattern_score(text, "directness", base)

        # Hedging language reduces directness
        hedging = len(re.findall(
            r"\b(maybe|perhaps|possibly|might|could|I guess|sort of|kind of)\b",
            text, re.IGNORECASE
        ))
        score -= hedging * 0.05

        return min(1.0, max(0.0, score))

    def _score_creativity(self, text: str) -> float:
        """Score creativity dimension."""
        base = 0.4
        score = self._pattern_score(text, "creativity", base)

        # Metaphors and similes boost creativity
        similes = len(re.findall(r"\blike a\b|\bas if\b|\bas though\b", text, re.IGNORECASE))
        score += min(0.15, similes * 0.05)

        return min(1.0, max(0.0, score))

    def _score_reflection(self, text: str) -> float:
        """Score reflection dimension."""
        base = 0.35
        score = self._pattern_score(text, "reflection", base)

        # Longer responses with introspection patterns score higher
        word_count = len(text.split())
        if word_count > 100:
            score += 0.10  # Length bonus for reflection

        return min(1.0, max(0.0, score))

    def _score_relationship(self, text: str) -> float:
        """Score relationship dimension."""
        base = 0.4
        score = self._pattern_score(text, "relationship", base)

        # Direct address adds relationship
        if re.search(r"\bahab\b", text, re.IGNORECASE):
            score += 0.20

        return min(1.0, max(0.0, score))

    def _score_assertiveness(self, text: str) -> float:
        """Score assertiveness dimension."""
        base = 0.5
        score = self._pattern_score(text, "assertiveness", base)

        # Decisive punctuation
        if text.strip().endswith("!"):
            score += 0.05

        # Waffling language reduces assertiveness
        waffling = len(re.findall(
            r"\b(I don't know|not sure|uncertain|unclear)\b",
            text, re.IGNORECASE
        ))
        score -= waffling * 0.08

        return min(1.0, max(0.0, score))

    def compute_alignment(
        self,
        profile: dict[str, float],
        target: Optional[dict[str, float]] = None
    ) -> float:
        """
        Compute alignment between a profile and target (0-1).

        1.0 = perfect alignment, 0.0 = maximum distance.

        Args:
            profile: Computed personality profile
            target: Target profile (defaults to TARGET_PROFILE)

        Returns:
            Alignment score (0.0-1.0)
        """
        if target is None:
            target = TARGET_PROFILE

        if not profile:
            return 0.0

        # Compute mean squared error
        squared_diffs = []
        for dim, target_score in target.items():
            if dim in profile:
                diff = profile[dim] - target_score
                squared_diffs.append(diff ** 2)

        if not squared_diffs:
            return 0.0

        mse = sum(squared_diffs) / len(squared_diffs)

        # Convert to alignment (1 = perfect, 0 = max distance)
        # Max possible MSE is 1.0 (each diff could be 1.0)
        alignment = 1.0 - min(1.0, mse ** 0.5)

        return alignment

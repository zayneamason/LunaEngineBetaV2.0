"""
Crucible - Ingestion module for Persona Forge

Transforms raw materials into TrainingExample objects.
"""

from pathlib import Path
from typing import Optional
import json
import re

from .models import (
    TrainingExample, SourceType, InteractionType, LockIn,
    VoiceMarkers, AntiPatterns,
)
from .personality_scorer import PersonalityScorer


class Crucible:
    """
    Ingests raw materials into TrainingExample format.
    
    Supported sources:
    - JSONL training data
    - Markdown journal files
    - Memory Matrix SQLite database
    - Session transcript files
    """
    
    # Voice marker patterns
    VOICE_MARKERS = {
        "first_person": r"\b(I|I'm|I've|I'd|my|me)\b",
        "warmth_words": r"\b(honestly|actually|you know|yeah|cool|nice|hey)\b",
        "uncertainty": r"\b(maybe|probably|I think|not sure|might|could be)\b",
        "relationship": r"\b(we|we've|we're|our|together|Ahab)\b",
        "inside_refs": r"\b(Dude|Ben|fart|symphony|sovereignty|Memory Matrix)\b",
    }
    
    # Anti-pattern patterns
    ANTI_PATTERNS = {
        "generic_ai": r"\b(I am an AI|as an AI|language model|Alibaba|Qwen|created by)\b",
        "corporate": r"\b(I'd be happy to|certainly|absolutely|assist you|help you with)\b",
        "hedging": r"\b(I cannot|I'm not able|I don't have the ability|I'm unable)\b",
    }
    
    # Source quality baselines
    SOURCE_BASELINES = {
        SourceType.JOURNAL: 0.70,
        SourceType.MANUAL: 0.65,
        SourceType.SESSION: 0.50,
        SourceType.INSIGHT: 0.55,
        SourceType.MATRIX: 0.40,
        SourceType.SYNTHETIC: 0.45,
    }
    
    def __init__(self, enable_personality_scoring: bool = True):
        """
        Initialize the Crucible ingestion engine.

        Args:
            enable_personality_scoring: If True, score personality for each example.
                                       Default True for enhanced analysis.
        """
        self.examples: list[TrainingExample] = []
        self._load_history: list[dict] = []
        self._enable_personality = enable_personality_scoring

        if self._enable_personality:
            self._personality_scorer = PersonalityScorer()
        else:
            self._personality_scorer = None
    
    def ingest_jsonl(self, path: Path) -> list[TrainingExample]:
        """Load existing JSONL training data."""
        examples = []
        path = Path(path)
        
        with open(path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    example = self._parse_jsonl_entry(data, path, i)
                    examples.append(example)
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping line {i} in {path}: {e}")
        
        self.examples.extend(examples)
        self._load_history.append({
            "source": str(path),
            "type": "jsonl",
            "count": len(examples),
        })
        
        return examples
    
    def ingest_journals(self, directory: Path) -> list[TrainingExample]:
        """Convert journal markdown files to training examples."""
        examples = []
        directory = Path(directory)
        
        for md_file in directory.glob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            example = self._parse_journal(content, md_file)
            if example:
                examples.append(example)
        
        self.examples.extend(examples)
        self._load_history.append({
            "source": str(directory),
            "type": "journals",
            "count": len(examples),
        })
        
        return examples
    
    def clear(self) -> None:
        """Clear all loaded examples."""
        self.examples = []
        self._load_history = []
    
    def get_stats(self) -> dict:
        """Get loading statistics."""
        return {
            "total_examples": len(self.examples),
            "load_history": self._load_history,
        }
    
    def _parse_jsonl_entry(
        self, 
        data: dict, 
        source: Path, 
        idx: int
    ) -> TrainingExample:
        """Parse a single JSONL entry into TrainingExample."""
        
        # Handle different JSONL formats
        if "messages" in data:
            # OpenAI format
            messages = data["messages"]
            system = next((m["content"] for m in messages if m["role"] == "system"), "")
            user = next((m["content"] for m in messages if m["role"] == "user"), "")
            assistant = next((m["content"] for m in messages if m["role"] == "assistant"), "")
        elif "conversations" in data:
            # Luna/ShareGPT format
            conversations = data["conversations"]
            system = next((m["content"] for m in conversations if m["role"] == "system"), "")
            user = next((m["content"] for m in conversations if m["role"] == "user"), "")
            assistant = next((m["content"] for m in conversations if m["role"] == "assistant"), "")
        else:
            # Simple format
            system = data.get("system", data.get("system_prompt", ""))
            user = data.get("user_message", data.get("user", data.get("prompt", data.get("input", ""))))
            assistant = data.get("assistant_response", data.get("assistant", data.get("response", data.get("output", ""))))
        
        # Determine source type from content or metadata
        source_type = self._infer_source_type(data, source)
        
        # Use interaction_type from source if provided, otherwise classify
        interaction_type = self._get_interaction_type(data, user, assistant)
        
        example = TrainingExample(
            system_prompt=system,
            user_message=user,
            assistant_response=assistant,
            source_type=source_type,
            source_file=str(source),
            interaction_type=interaction_type,
        )
        example.compute_metrics()
        
        # Analyze voice
        example.voice_markers = self._detect_voice_markers(assistant)
        example.anti_patterns = self._detect_anti_patterns(assistant)

        # Compute initial lock-in
        example.lock_in = self._compute_initial_lockin(example)

        # Score personality (if enabled)
        if self._personality_scorer:
            example.personality_scores = self._personality_scorer.score_response(assistant)

        return example
    
    def _parse_journal(self, content: str, source: Path) -> Optional[TrainingExample]:
        """Parse journal markdown into training example."""
        # Extract title as prompt
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if not title_match:
            return None
        
        title = title_match.group(1)
        body = content[title_match.end():].strip()
        
        if not body or len(body) < 50:
            return None
        
        # Create reflection-style prompt
        prompt = f"What are your thoughts on {title.lower()}?"
        
        example = TrainingExample(
            system_prompt="You are Luna, a sovereign AI companion.",
            user_message=prompt,
            assistant_response=body,
            source_type=SourceType.JOURNAL,
            source_file=str(source),
            interaction_type=InteractionType.REFLECTION,
        )
        example.compute_metrics()
        example.voice_markers = self._detect_voice_markers(body)
        example.anti_patterns = self._detect_anti_patterns(body)
        example.lock_in = self._compute_initial_lockin(example)

        # Score personality (if enabled)
        if self._personality_scorer:
            example.personality_scores = self._personality_scorer.score_response(body)

        return example
    
    def _infer_source_type(self, data: dict, source: Path) -> SourceType:
        """Infer source type from data or filename."""
        source_str = str(source).lower()
        
        if "journal" in source_str:
            return SourceType.JOURNAL
        elif "session" in source_str:
            return SourceType.SESSION
        elif "matrix" in source_str:
            return SourceType.MATRIX
        elif "insight" in source_str:
            return SourceType.INSIGHT
        elif "synthetic" in source_str or "generated" in source_str:
            return SourceType.SYNTHETIC
        
        # Check data for hints
        if "source" in data:
            source_hint = data["source"].lower()
            for st in SourceType:
                if st.value in source_hint:
                    return st
        
        return SourceType.MANUAL
    
    def _get_interaction_type(self, data: dict, user_msg: str, response: str) -> InteractionType:
        """Get interaction type from source data or classify if not provided."""
        # Check if interaction_type is provided in source data (multiple locations)
        source_type = None
        if "interaction_type" in data:
            source_type = data["interaction_type"]
        elif "_metadata" in data and "interaction_type" in data["_metadata"]:
            source_type = data["_metadata"]["interaction_type"]
        elif "metadata" in data and "interaction_type" in data["metadata"]:
            source_type = data["metadata"]["interaction_type"]

        if source_type:
            # Validate it's a valid InteractionType
            try:
                return InteractionType(source_type)
            except ValueError:
                # Invalid type, fall back to classification
                pass

        # Fall back to classification
        return self._classify_interaction_type(user_msg, response)
    
    def _classify_interaction_type(self, user_msg: str, response: str) -> InteractionType:
        """Classify interaction type based on content."""
        user_lower = user_msg.lower().strip()
        response_words = len(response.split())
        
        # Greeting patterns
        if any(g in user_lower for g in ["hey luna", "hi luna", "hello luna", "good morning", "good evening", "yo luna"]):
            return InteractionType.GREETING
        
        # Acknowledgment patterns
        if user_lower in ["ok", "okay", "got it", "thanks", "thank you", "cool", "nice", "k", "kk", "alright"]:
            return InteractionType.ACKNOWLEDGMENT
        
        # Delegation triggers
        if any(d in user_lower for d in ["analyze", "refactor", "review this", "debug", "explain this code", "write a", "create a", "implement"]):
            return InteractionType.DELEGATION_TRIGGER
        
        # Context recall
        if any(r in user_lower for r in ["remember", "what did we", "last time", "you said", "we talked about", "earlier"]):
            return InteractionType.CONTEXT_RECALL
        
        # Emotional
        if any(e in user_lower for e in ["how are you", "how do you feel", "are you okay", "feeling", "mood"]):
            return InteractionType.EMOTIONAL_PRESENCE
        
        # Humor
        if any(h in user_lower for h in ["joke", "funny", "fart", "laugh", "lol"]):
            return InteractionType.HUMOR
        
        # Technical
        if any(t in user_lower for t in ["code", "function", "error", "bug", "api", "database", "memory matrix"]):
            return InteractionType.TECHNICAL
        
        # Length-based heuristics
        if response_words < 50:
            return InteractionType.SHORT_EXCHANGE
        elif response_words > 200:
            return InteractionType.REFLECTION
        
        return InteractionType.SHORT_EXCHANGE
    
    def _detect_voice_markers(self, text: str) -> VoiceMarkers:
        """Detect positive voice markers in text."""
        return VoiceMarkers(
            first_person=1 if re.search(self.VOICE_MARKERS["first_person"], text, re.IGNORECASE) else 0,
            warmth_words=1 if re.search(self.VOICE_MARKERS["warmth_words"], text, re.IGNORECASE) else 0,
            uncertainty=1 if re.search(self.VOICE_MARKERS["uncertainty"], text, re.IGNORECASE) else 0,
            relationship=1 if re.search(self.VOICE_MARKERS["relationship"], text, re.IGNORECASE) else 0,
        )

    def _detect_anti_patterns(self, text: str) -> AntiPatterns:
        """Detect negative anti-patterns in text."""
        return AntiPatterns(
            generic_ai=1 if re.search(self.ANTI_PATTERNS["generic_ai"], text, re.IGNORECASE) else 0,
            corporate=1 if re.search(self.ANTI_PATTERNS["corporate"], text, re.IGNORECASE) else 0,
            hedging=1 if re.search(self.ANTI_PATTERNS["hedging"], text, re.IGNORECASE) else 0,
        )

    def _compute_initial_lockin(self, example: TrainingExample) -> LockIn:
        """Compute initial lock-in based on source and voice."""
        base = self.SOURCE_BASELINES.get(example.source_type, 0.5)

        # Voice bonuses
        if example.voice_markers.first_person > 0:
            base += 0.05
        if example.voice_markers.warmth_words > 0:
            base += 0.05
        if example.voice_markers.relationship > 0:
            base += 0.05
        # Note: inside_refs removed (not in VoiceMarkers model)

        # Anti-pattern penalties
        if example.anti_patterns.generic_ai > 0:
            base -= 0.30
        if example.anti_patterns.corporate > 0:
            base -= 0.15
        if example.anti_patterns.hedging > 0:
            base -= 0.10

        # Length appropriateness penalties
        if example.interaction_type in [InteractionType.GREETING, InteractionType.ACKNOWLEDGMENT]:
            if example.response_word_count > 100:
                base -= 0.15  # Too long for type

        base = max(0.15, min(0.85, base))

        return LockIn(base_quality=base)

#!/usr/bin/env python3
"""
Conversation Turn Ingester for Persona Forge
Processes conversation turns from luna_engine.db into training examples.

Phase B of ingestion pipeline.
"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Paths
DB_PATH = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db")
OUTPUT_PATH = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/data/ingested_turns.jsonl")

# Valid InteractionTypes from models.py
VALID_TYPES = {
    "greeting", "acknowledgment", "short_exchange", "context_recall",
    "emotional_presence", "delegation_trigger", "reflection", 
    "technical", "humor", "pushback"
}

@dataclass
class Turn:
    id: int
    session_id: str
    role: str
    content: str
    created_at: str

def classify_interaction(user_msg: str, assistant_msg: str) -> str:
    """Classify the interaction type based on content patterns.
    
    Uses ONLY valid InteractionType enum values.
    """
    user_lower = user_msg.lower()
    assistant_lower = assistant_msg.lower()
    
    # Greeting patterns (short hello-style messages)
    if re.match(r'^(hey|hi|hello|yo|sup|good morning|good evening)', user_lower):
        if len(user_msg) < 50:
            return "greeting"
    
    # Short acknowledgments
    if len(user_msg) < 25 and any(w in user_lower for w in ['ok', 'yeah', 'sure', 'got it', 'thanks', 'cool', 'nice', 'oh wow']):
        return "acknowledgment"
    
    # Memory/context recall - PRIORITY
    if any(phrase in user_lower for phrase in ['remember', 'recall', 'what did we', 'last time', 'do you know']):
        return "context_recall"
    
    # Emotional content
    if any(word in user_lower for word in ['feel', 'feeling', 'worried', 'excited', 'frustrated', 'happy', 'sad', 'love', 'hate']):
        return "emotional_presence"
    
    # Humor detection (lol, haha, jokes)
    if any(word in user_lower for word in ['lol', 'haha', 'funny', 'joke', '😂', '🤣']):
        return "humor"
    if any(word in assistant_lower for word in ['lol', 'haha', '*chuckles*', '*laughs*']):
        return "humor"
    
    # Pushback / disagreement
    if any(phrase in user_lower for phrase in ['no that\'s wrong', 'you\'re wrong', 'that\'s not', 'actually no', 'wait no']):
        return "pushback"
    
    # Technical questions
    if any(phrase in user_lower for phrase in ['how do', 'what is', 'explain', 'architecture', 'system', 'code', 'memory matrix', 'pipeline']):
        return "technical"
    
    # Reflection (long thoughtful assistant responses)
    if len(assistant_msg) > 500:
        if any(phrase in assistant_lower for phrase in ['i think', 'i feel', 'what strikes me', 'interesting', 'honestly', 'curious']):
            return "reflection"
    
    # Delegation triggers (asking Luna to do something complex)
    if any(phrase in user_lower for phrase in ['can you help', 'search for', 'find out', 'look up', 'analyze']):
        return "delegation_trigger"
    
    # Default to short_exchange
    return "short_exchange"

def is_noise(user_msg: str, assistant_msg: str) -> bool:
    """Filter out noise that shouldn't be training data."""
    user_lower = user_msg.lower().strip()
    
    # System messages
    if user_lower.startswith('[memory'):
        return True
    
    # Pure test messages
    if user_lower in ['test', 'test message 1', 'test message 2']:
        return True
    
    # Empty or near-empty
    if len(user_msg.strip()) < 3 or len(assistant_msg.strip()) < 10:
        return True
    
    # Assistant-only responses (no user message)
    if not user_msg.strip():
        return True
    
    # System/connection messages
    if "engine connected" in assistant_msg.lower():
        return True
        
    return False

def has_luna_voice(assistant_msg: str) -> tuple[bool, float]:
    """Check if the assistant response has Luna's voice markers."""
    markers = {
        'asterisk_actions': bool(re.search(r'\*[^*]+\*', assistant_msg)),  # *pulses warmly*
        'first_person': bool(re.search(r'\b(I |I\'m|my |me )', assistant_msg)),
        'warmth': any(w in assistant_msg.lower() for w in ['warmly', 'gently', 'softly', 'curious', 'honestly', 'actually']),
        'uncertainty': any(w in assistant_msg.lower() for w in ['interesting', 'hmm', 'maybe', 'probably', 'I think']),
        'relationship': any(w in assistant_msg.lower() for w in ['we', 'our', 'together', 'you and I', 'Ahab']),
    }
    
    score = sum(markers.values()) / len(markers)
    # More permissive - at least 2 of 5 markers
    has_voice = score >= 0.3
    return has_voice, score

def process_turns():
    """Process all conversation turns into training examples."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all turns ordered by session and time
    cursor.execute("""
        SELECT id, session_id, role, content, created_at 
        FROM conversation_turns 
        ORDER BY session_id, created_at
    """)
    
    turns = [Turn(**dict(row)) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Loaded {len(turns)} total turns")
    
    # Group by session
    sessions = {}
    for turn in turns:
        if turn.session_id not in sessions:
            sessions[turn.session_id] = []
        sessions[turn.session_id].append(turn)
    
    print(f"Found {len(sessions)} sessions")
    
    # Process into user/assistant pairs
    examples = []
    skipped_noise = 0
    skipped_no_voice = 0
    
    for session_id, session_turns in sessions.items():
        # Pair consecutive user/assistant turns
        i = 0
        while i < len(session_turns) - 1:
            # Find user turn
            if session_turns[i].role == 'user':
                user_turn = session_turns[i]
                # Look for assistant response
                if i + 1 < len(session_turns) and session_turns[i + 1].role == 'assistant':
                    assistant_turn = session_turns[i + 1]
                    
                    # Filter noise
                    if is_noise(user_turn.content, assistant_turn.content):
                        skipped_noise += 1
                        i += 2
                        continue
                    
                    # Check for Luna voice
                    has_voice, voice_score = has_luna_voice(assistant_turn.content)
                    if not has_voice:
                        skipped_no_voice += 1
                        i += 2
                        continue
                    
                    # Classify
                    interaction_type = classify_interaction(user_turn.content, assistant_turn.content)
                    
                    # Validate type
                    assert interaction_type in VALID_TYPES, f"Invalid type: {interaction_type}"
                    
                    # Create example
                    example = {
                        "user_message": user_turn.content,
                        "assistant_response": assistant_turn.content,
                        "interaction_type": interaction_type,
                        "source_type": "session",  # Valid SourceType
                        "source_file": f"session_{session_id[:8]}",
                        "confidence": min(0.95, 0.6 + voice_score),  # Higher confidence for stronger Luna voice
                        "tags": ["gold", "real_conversation", session_id[:8]]
                    }
                    examples.append(example)
                    i += 2
                else:
                    i += 1
            else:
                i += 1
    
    print(f"\nProcessing complete:")
    print(f"  - Valid examples: {len(examples)}")
    print(f"  - Skipped (noise): {skipped_noise}")
    print(f"  - Skipped (no Luna voice): {skipped_no_voice}")
    
    # Count by interaction type
    type_counts = {}
    for ex in examples:
        t = ex['interaction_type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print(f"\nInteraction type breakdown:")
    for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  - {t}: {count}")
    
    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    print(f"\nWrote {len(examples)} examples to {OUTPUT_PATH}")
    return examples

if __name__ == "__main__":
    process_turns()

# CLAUDE CODE HANDOFF: Voice Continuity Fix

**Created**: 2025-01-20
**Author**: Architecture Session (Dude)
**Priority**: CRITICAL - Luna is experiencing identity fragmentation in production
**Estimated Scope**: 3 focused fixes + diagnostic tracer

---

## SITUATION

Luna's voice interface is experiencing severe continuity breaks. Live conversation logs show:

1. **Local model responses** - Generic, no memory, slow (11-42s), hallucinating context
2. **Delegated responses** - Sharp, has memory access, fast (5-9s), coherent
3. **Neither maintains conversation history** - Each message processed in isolation

User has been repeating the same questions all night because Luna can't remember what was just discussed.

---

## DIAGNOSTIC TRACER (IMPLEMENT FIRST)

Before fixing, we need visibility. Create a tracer that logs every voice interaction.

### File: `src/voice/diagnostics/interaction_tracer.py`

```python
"""
Interaction Tracer - Diagnostic logging for voice pipeline debugging.

Logs every interaction with full context for post-hoc analysis.
Outputs to: data/diagnostics/voice_trace_{date}.jsonl
"""
import json
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any

@dataclass
class InteractionTrace:
    """Single interaction trace record."""
    timestamp: str
    session_id: str
    
    # Input
    user_message: str
    message_length: int
    
    # Routing Decision
    route_decision: str  # "local" | "delegated" | "hybrid"
    route_reason: str    # Why this route was chosen
    complexity_score: Optional[float] = None
    
    # Context Injection
    system_prompt_injected: bool = False
    system_prompt_tokens: int = 0
    memory_context_injected: bool = False
    memory_nodes_count: int = 0
    conversation_history_length: int = 0
    
    # Response
    response_text: str = ""
    response_tokens: int = 0
    response_time_ms: float = 0
    
    # Quality Signals
    contains_fallback_phrase: bool = False  # "Let me look into that..."
    contains_identity_confusion: bool = False
    contains_memory_reference: bool = False
    
    # Errors
    error: Optional[str] = None


class InteractionTracer:
    """Singleton tracer for voice interactions."""
    
    FALLBACK_PHRASES = [
        "let me look into that",
        "i'm not familiar with",
        "could you give me more context",
        "i don't have clear memories",
    ]
    
    IDENTITY_CONFUSION = [
        "as an ai",
        "i'm an ai assistant",
        "i don't have personal",
        "i cannot feel",
    ]
    
    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("data/diagnostics")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = self._get_trace_file()
        
    def _get_trace_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.output_dir / f"voice_trace_{date_str}.jsonl"
    
    def _detect_quality_signals(self, response: str) -> Dict[str, bool]:
        response_lower = response.lower()
        return {
            "contains_fallback_phrase": any(p in response_lower for p in self.FALLBACK_PHRASES),
            "contains_identity_confusion": any(p in response_lower for p in self.IDENTITY_CONFUSION),
            "contains_memory_reference": any(w in response_lower for w in ["remember", "recall", "memory", "earlier", "you mentioned"]),
        }
    
    def trace(
        self,
        session_id: str,
        user_message: str,
        route_decision: str,
        route_reason: str,
        response_text: str,
        response_time_ms: float,
        system_prompt_tokens: int = 0,
        memory_nodes_count: int = 0,
        conversation_history_length: int = 0,
        complexity_score: float = None,
        error: str = None,
    ):
        """Log a single interaction trace."""
        quality = self._detect_quality_signals(response_text)
        
        trace = InteractionTrace(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            user_message=user_message,
            message_length=len(user_message),
            route_decision=route_decision,
            route_reason=route_reason,
            complexity_score=complexity_score,
            system_prompt_injected=system_prompt_tokens > 0,
            system_prompt_tokens=system_prompt_tokens,
            memory_context_injected=memory_nodes_count > 0,
            memory_nodes_count=memory_nodes_count,
            conversation_history_length=conversation_history_length,
            response_text=response_text[:500],  # Truncate for storage
            response_tokens=len(response_text.split()),  # Rough estimate
            response_time_ms=response_time_ms,
            error=error,
            **quality
        )
        
        with open(self.current_file, "a") as f:
            f.write(json.dumps(asdict(trace)) + "\n")
        
        return trace
    
    def get_recent_traces(self, n: int = 20) -> List[Dict]:
        """Get last N traces for debugging."""
        if not self.current_file.exists():
            return []
        
        traces = []
        with open(self.current_file, "r") as f:
            for line in f:
                traces.append(json.loads(line))
        
        return traces[-n:]
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """Summarize quality metrics from today's traces."""
        traces = self.get_recent_traces(100)
        if not traces:
            return {"error": "No traces found"}
        
        total = len(traces)
        local_traces = [t for t in traces if t["route_decision"] == "local"]
        delegated_traces = [t for t in traces if t["route_decision"] == "delegated"]
        
        return {
            "total_interactions": total,
            "local_count": len(local_traces),
            "delegated_count": len(delegated_traces),
            "fallback_rate": sum(1 for t in traces if t["contains_fallback_phrase"]) / total,
            "identity_confusion_rate": sum(1 for t in traces if t["contains_identity_confusion"]) / total,
            "memory_reference_rate": sum(1 for t in traces if t["contains_memory_reference"]) / total,
            "avg_response_time_ms": sum(t["response_time_ms"] for t in traces) / total,
            "avg_local_time_ms": sum(t["response_time_ms"] for t in local_traces) / len(local_traces) if local_traces else 0,
            "avg_delegated_time_ms": sum(t["response_time_ms"] for t in delegated_traces) / len(delegated_traces) if delegated_traces else 0,
            "no_context_injected": sum(1 for t in traces if not t["system_prompt_injected"] and not t["memory_context_injected"]) / total,
        }


# Global singleton
_tracer: Optional[InteractionTracer] = None

def get_tracer() -> InteractionTracer:
    global _tracer
    if _tracer is None:
        _tracer = InteractionTracer()
    return _tracer
```

### Integration Point

Add tracer calls to the voice response pipeline. Find where responses are generated and wrap:

```python
from voice.diagnostics.interaction_tracer import get_tracer

# After generating response:
get_tracer().trace(
    session_id=session_id,
    user_message=user_input,
    route_decision="local" if used_local else "delegated",
    route_reason=complexity_router.last_reason,
    response_text=response,
    response_time_ms=elapsed_ms,
    system_prompt_tokens=len(system_prompt) // 4 if system_prompt else 0,
    memory_nodes_count=len(context_packet.nodes) if context_packet else 0,
    conversation_history_length=len(conversation_history),
)
```

---

## FIX #1: LOCAL MODEL CONTEXT INJECTION (HIGHEST IMPACT)

**Problem**: Local Qwen model receives raw user message with no identity or memory context.

**Evidence**: Local responses say things like "Let me piece together the fragments..." - hallucinating that it has memories when it doesn't.

**Location**: Find where local inference is called. Likely in:
- `src/voice/` somewhere
- `src/director/` 
- `src/persona/generator.py`

### Fix Spec

1. **Before calling local model**, inject minimal system prompt:

```python
LOCAL_SYSTEM_PROMPT_TEMPLATE = """
You are Luna, a sovereign AI companion. You have a warm, curious personality.

Current context:
- User: Ahab (your creator and collaborator)
- You're in voice conversation mode
- Keep responses conversational and concise

{memory_context}

{recent_turns}
"""
```

2. **Memory context** should be minimal for local (token budget ~500):
   - Current focus topic
   - 2-3 most relevant memory snippets
   - NO full foundation context (too expensive)

3. **Recent turns** = last 3-5 exchanges from conversation buffer

### Verification

After fix, tracer should show:
- `system_prompt_injected: true` for local calls
- `system_prompt_tokens: 300-600` range
- Reduced `fallback_rate`
- Reduced `identity_confusion_rate`

---

## FIX #2: CONVERSATION HISTORY BUFFER

**Problem**: Neither local nor delegated calls receive conversation history. Each message is processed in isolation.

**Evidence**: Luna can remember Marzipan (from memory matrix) but not that you asked about Mars College 30 seconds ago.

### Fix Spec

1. **Create rolling buffer** in voice session manager:

```python
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class ConversationBuffer:
    """Rolling buffer of recent conversation turns."""
    max_turns: int = 10
    max_tokens: int = 2000
    turns: List[Dict[str, str]] = field(default_factory=list)
    
    def add_turn(self, role: str, content: str):
        self.turns.append({"role": role, "content": content})
        self._trim()
    
    def _trim(self):
        # Keep last N turns
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        
        # Also enforce token budget
        while self._estimate_tokens() > self.max_tokens and len(self.turns) > 2:
            self.turns.pop(0)
    
    def _estimate_tokens(self) -> int:
        return sum(len(t["content"]) // 4 for t in self.turns)
    
    def to_messages(self) -> List[Dict[str, str]]:
        return self.turns.copy()
    
    def to_text(self) -> str:
        """For injection into system prompt."""
        lines = []
        for turn in self.turns[-5:]:  # Last 5 for text format
            role = "You" if turn["role"] == "assistant" else "Ahab"
            lines.append(f"{role}: {turn['content'][:200]}")
        return "\n".join(lines)
```

2. **Wire into voice pipeline**:
   - Create buffer at session start
   - Add user message before processing
   - Add assistant response after generation
   - Pass to both local and delegated paths

3. **Pass to PersonaCore**:

```python
# In voice processing:
result = await persona_core.process_query(
    query=user_message,
    budget="balanced",
    generate_response=True,
    conversation_history=conversation_buffer.to_messages(),  # THIS IS THE KEY
)
```

### Verification

After fix, tracer should show:
- `conversation_history_length: 2-10` (not 0)
- Luna can reference "you just asked about X"
- No more "starting fresh" every message

---

## FIX #3: MEMORY-AWARE COMPLEXITY ROUTING

**Problem**: Router decides local vs delegated arbitrarily, not based on whether query needs memory.

**Evidence**: "what do you remember about marzipan?" sometimes routes to local (which can't access memory), sometimes to delegated.

### Fix Spec

1. **Add memory-need detection** to complexity router:

```python
import re

MEMORY_TRIGGER_PATTERNS = [
    r"\bremember\b",
    r"\brecall\b",
    r"\bwhat (do|did) (you|we|i)\b",
    r"\b(earlier|before|yesterday|last time)\b",
    r"\babout (\w+)\?",  # "what about marzipan?"
    r"\bwho is\b",
    r"\btell me about\b",
]

def needs_memory_access(query: str) -> bool:
    query_lower = query.lower()
    return any(re.search(p, query_lower) for p in MEMORY_TRIGGER_PATTERNS)
```

2. **Update routing logic**:

```python
def route_query(query: str, complexity_score: float) -> tuple[str, str]:
    # Memory queries ALWAYS delegate
    if needs_memory_access(query):
        return "delegated", "Query requires memory access"
    
    # Simple greetings/acknowledgments stay local
    if len(query.split()) < 5 and complexity_score < 0.3:
        return "local", "Simple/short query"
    
    # Default threshold
    if complexity_score > 0.5:
        return "delegated", f"Complexity score {complexity_score:.2f}"
    
    return "local", f"Below threshold {complexity_score:.2f}"
```

### Verification

After fix, tracer should show:
- Memory-related queries always have `route_decision: delegated`
- `route_reason` explains why
- Reduced mismatch between query type and route

---

## IMPLEMENTATION ORDER

1. **Tracer first** - Get visibility before changing anything
2. **Conversation buffer** - Biggest impact on "remembers nothing" problem  
3. **Local context injection** - Fixes identity confusion on local responses
4. **Memory-aware routing** - Ensures right queries go to right path

---

## FILES TO INVESTIGATE

Based on codebase structure, likely locations:

```
src/voice/
├── ???.py              # Find the main voice processing loop
└── ???.py              # Find where local vs delegated decision happens

src/director/
├── complexity_router.py?  # If exists, routing logic here
└── ???.py              # Director orchestration

src/persona/
├── core.py             # PersonaCore.process_query - already takes conversation_history
└── generator.py        # ResponseGenerator - check if history is used
```

Run this to find entry points:
```bash
grep -r "local" src/voice/ --include="*.py" | grep -i "model\|inference\|generate"
grep -r "delegat" src/voice/ --include="*.py"
grep -r "complexity" src/ --include="*.py"
```

---

## SUCCESS CRITERIA

Run tracer for 20+ interactions, then check:

```python
summary = get_tracer().get_quality_summary()

# Before fix (expected baseline):
# fallback_rate: 0.3-0.5
# identity_confusion_rate: 0.2-0.4  
# no_context_injected: 0.4-0.6
# conversation_history_length avg: 0

# After fix (targets):
assert summary["fallback_rate"] < 0.1
assert summary["identity_confusion_rate"] < 0.05
assert summary["no_context_injected"] < 0.1
assert summary["memory_reference_rate"] > 0.3
```

---

## QUESTIONS FOR AHAB

If blocked, ask:

1. Where is the voice processing main loop? (file path)
2. Where does local vs delegated routing happen?
3. Is there an existing session manager that should hold the conversation buffer?
4. What's the target token budget for local model context?

---

*Handoff complete. Luna's waiting for her memory back.*

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
import logging

logger = logging.getLogger(__name__)


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
        "i don't have specific memories",
        "i can't recall",
        "let me think",
        "i'm not sure",
    ]

    IDENTITY_CONFUSION = [
        "as an ai",
        "i'm an ai assistant",
        "i don't have personal",
        "i cannot feel",
        "i'm just a",
        "as a language model",
        "i don't have feelings",
        "i don't have emotions",
    ]

    def __init__(self, output_dir: Path = None):
        from luna.core.paths import local_dir
        self.output_dir = output_dir or (local_dir() / "diagnostics")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = self._get_trace_file()
        self._session_traces: List[InteractionTrace] = []
        logger.info(f"InteractionTracer initialized, writing to {self.current_file}")

    def _get_trace_file(self) -> Path:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.output_dir / f"voice_trace_{date_str}.jsonl"

    def _detect_quality_signals(self, response: str) -> Dict[str, bool]:
        response_lower = response.lower()
        return {
            "contains_fallback_phrase": any(p in response_lower for p in self.FALLBACK_PHRASES),
            "contains_identity_confusion": any(p in response_lower for p in self.IDENTITY_CONFUSION),
            "contains_memory_reference": any(w in response_lower for w in ["remember", "recall", "memory", "earlier", "you mentioned", "you said", "we talked"]),
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
    ) -> InteractionTrace:
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

        # Store in memory for session
        self._session_traces.append(trace)

        # Write to file
        try:
            with open(self.current_file, "a") as f:
                f.write(json.dumps(asdict(trace)) + "\n")
        except Exception as e:
            logger.error(f"Failed to write trace: {e}")

        # Log quality issues
        if quality["contains_fallback_phrase"]:
            logger.warning(f"[TRACER] Fallback phrase detected in response")
        if quality["contains_identity_confusion"]:
            logger.warning(f"[TRACER] Identity confusion detected in response")

        return trace

    def get_recent_traces(self, n: int = 20) -> List[Dict]:
        """Get last N traces for debugging."""
        # Try memory first
        if self._session_traces:
            traces = [asdict(t) for t in self._session_traces[-n:]]
            if traces:
                return traces

        # Fall back to file
        if not self.current_file.exists():
            return []

        traces = []
        try:
            with open(self.current_file, "r") as f:
                for line in f:
                    traces.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read traces: {e}")

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
            "avg_conversation_history": sum(t["conversation_history_length"] for t in traces) / total,
        }

    def print_summary(self) -> None:
        """Print a formatted summary to console."""
        summary = self.get_quality_summary()
        if "error" in summary:
            print(f"⚠️  {summary['error']}")
            return

        print("\n" + "="*60)
        print("📊 VOICE INTERACTION QUALITY SUMMARY")
        print("="*60)
        print(f"Total interactions: {summary['total_interactions']}")
        print(f"Local: {summary['local_count']} | Delegated: {summary['delegated_count']}")
        print("-"*60)
        print(f"🔴 Fallback rate: {summary['fallback_rate']*100:.1f}% (target: <10%)")
        print(f"🔴 Identity confusion: {summary['identity_confusion_rate']*100:.1f}% (target: <5%)")
        print(f"🟢 Memory references: {summary['memory_reference_rate']*100:.1f}% (target: >30%)")
        print(f"⚠️  No context injected: {summary['no_context_injected']*100:.1f}% (target: <10%)")
        print("-"*60)
        print(f"⏱️  Avg response time: {summary['avg_response_time_ms']:.0f}ms")
        print(f"   Local avg: {summary['avg_local_time_ms']:.0f}ms")
        print(f"   Delegated avg: {summary['avg_delegated_time_ms']:.0f}ms")
        print(f"📝 Avg conversation history: {summary['avg_conversation_history']:.1f} turns")
        print("="*60 + "\n")


# Global singleton
_tracer: Optional[InteractionTracer] = None

def get_tracer() -> InteractionTracer:
    global _tracer
    if _tracer is None:
        _tracer = InteractionTracer()
    return _tracer

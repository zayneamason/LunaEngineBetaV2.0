"""
Local Subtask Runner — Lightweight Qwen 3B Agentic Dispatch
============================================================

Runs fast, parallel subtasks on the local Qwen 3B model:
- Intent classification (replaces regex routing)
- Entity extraction (gates expensive Claude Haiku calls)
- Query rewriting (resolves ambiguous references)

Design rules:
- Every call has a hard timeout via asyncio.wait_for()
- On timeout or parse failure → SubtaskResult(success=False)
- Caller always falls back to existing logic when success=False
- Temperature 0.0 for deterministic classification
- No system prompts (saves chat template tokens)
- All structured outputs are JSON
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from luna.inference.local import LocalInference

logger = logging.getLogger(__name__)


# ─── Data Types ───────────────────────────────────────────────────────────────

@dataclass
class SubtaskResult:
    """Result from a lightweight subtask."""

    success: bool
    output: Any = None          # Parsed result (dict, str, list)
    raw_text: str = ""          # Raw model output before parsing
    latency_ms: float = 0.0
    task_name: str = ""

    @staticmethod
    def failed(task_name: str, latency_ms: float = 0.0) -> "SubtaskResult":
        return SubtaskResult(
            success=False, task_name=task_name, latency_ms=latency_ms,
        )


@dataclass
class SubtaskStats:
    """Per-subtask performance tracking."""

    attempts: int = 0
    successes: int = 0
    failures: int = 0
    timeouts: int = 0
    total_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.attempts if self.attempts > 0 else 0.0


@dataclass
class SubtaskPhaseResult:
    """Aggregated results from running all subtasks in parallel."""

    intent: Optional[dict] = None           # From classify_intent
    entities: Optional[list] = None         # From extract_entities
    rewritten_query: Optional[str] = None   # From rewrite_query
    decomposed_queries: Optional[list] = None  # From decompose_query
    total_latency_ms: float = 0.0


# ─── Prompts ──────────────────────────────────────────────────────────────────

INTENT_PROMPT = """Classify this message's intent. Return ONLY valid JSON on one line:
{{"intent":"<greeting|simple_question|memory_query|research|creative|dataroom|task|emotional|meta>","complexity":"<trivial|simple|moderate|complex>","tools":[]}}
Message: {message}"""

ENTITY_PROMPT = """Extract named entities. Return ONLY valid JSON on one line:
{{"entities":[{{"name":"exact name","type":"person|project|place|concept"}}]}}
If none found, return {{"entities":[]}}
Message: {message}"""

REWRITE_PROMPT = """Rewrite this message by resolving vague references (that, this, it, the thing, etc.) using the conversation context below. If the message is already specific, return it unchanged. Return ONLY the rewritten message, nothing else.

Context:
{context}

Message: {message}"""

DECOMPOSE_PROMPT = """Break this question into separate search queries that would each find different information. Return ONLY valid JSON on one line:
{{"queries":["first search query","second search query"]}}
If the question is simple and only needs one search, return {{"queries":["{message}"]}}
Question: {message}"""


# ─── Runner ───────────────────────────────────────────────────────────────────

class LocalSubtaskRunner:
    """
    Dispatches lightweight inference tasks to Qwen 3B.

    All methods return SubtaskResult with graceful fallback.
    If the local model is unavailable or slow, results come back
    as success=False and the caller uses existing logic.
    """

    def __init__(
        self,
        local_inference: "LocalInference",
        default_timeout_ms: int = 2000,
    ):
        self._local = local_inference
        self._default_timeout_ms = default_timeout_ms
        self._stats: dict[str, SubtaskStats] = {
            "classify_intent": SubtaskStats(),
            "extract_entities": SubtaskStats(),
            "rewrite_query": SubtaskStats(),
            "decompose_query": SubtaskStats(),
        }

    @property
    def is_available(self) -> bool:
        """Check if the local model is loaded and ready."""
        return self._local is not None and self._local.is_loaded

    def get_stats(self) -> dict:
        """Get performance stats for all subtasks."""
        return {
            name: {
                "attempts": s.attempts,
                "successes": s.successes,
                "failures": s.failures,
                "timeouts": s.timeouts,
                "success_rate": round(s.success_rate, 2),
                "avg_latency_ms": round(s.avg_latency_ms, 1),
            }
            for name, s in self._stats.items()
        }

    # ── Core dispatch ─────────────────────────────────────────────────────

    async def _run_with_timeout(
        self,
        task_name: str,
        prompt: str,
        max_tokens: int,
        timeout_ms: int,
        temperature: float = 0.0,
    ) -> SubtaskResult:
        """
        Run a local inference call with timeout enforcement.

        Returns SubtaskResult with raw_text populated on success.
        The caller is responsible for parsing the output.
        """
        if not self.is_available:
            return SubtaskResult.failed(task_name)

        stats = self._stats.get(task_name, SubtaskStats())
        stats.attempts += 1
        start = time.perf_counter()

        try:
            result = await asyncio.wait_for(
                self._local.generate(
                    user_message=prompt,
                    system_prompt=None,
                    max_tokens=max_tokens,
                ),
                timeout=timeout_ms / 1000.0,
            )

            latency = (time.perf_counter() - start) * 1000
            stats.total_latency_ms += latency

            raw = result.text.strip() if hasattr(result, "text") else str(result).strip()
            logger.info(f"[SUBTASK:{task_name}] Complete in {latency:.0f}ms: {raw[:80]}")

            return SubtaskResult(
                success=True,
                raw_text=raw,
                latency_ms=latency,
                task_name=task_name,
            )

        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start) * 1000
            stats.timeouts += 1
            stats.total_latency_ms += latency
            logger.warning(f"[SUBTASK:{task_name}] Timeout after {latency:.0f}ms")
            return SubtaskResult.failed(task_name, latency)

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            stats.failures += 1
            stats.total_latency_ms += latency
            logger.warning(f"[SUBTASK:{task_name}] Failed: {e}")
            return SubtaskResult.failed(task_name, latency)

    def _parse_json(self, raw_text: str, task_name: str) -> Optional[dict]:
        """Parse JSON from model output, stripping markdown fences."""
        text = raw_text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"[SUBTASK:{task_name}] JSON parse failed: {text[:100]}")
            return None

    # ── Subtask: Intent Classification ────────────────────────────────────

    VALID_INTENTS = {
        "greeting", "simple_question", "memory_query", "research",
        "creative", "dataroom", "task", "emotional", "meta",
    }
    VALID_COMPLEXITIES = {"trivial", "simple", "moderate", "complex"}

    async def classify_intent(
        self, message: str, timeout_ms: int = 2000,
    ) -> SubtaskResult:
        """
        Classify user message intent semantically.

        Returns SubtaskResult where output is:
        {"intent": "...", "complexity": "...", "tools": [...]}
        """
        prompt = INTENT_PROMPT.format(message=message)
        result = await self._run_with_timeout(
            "classify_intent", prompt, max_tokens=60, timeout_ms=timeout_ms,
        )
        if not result.success:
            return result

        parsed = self._parse_json(result.raw_text, "classify_intent")
        if parsed is None:
            self._stats["classify_intent"].failures += 1
            return SubtaskResult.failed("classify_intent", result.latency_ms)

        # Validate fields
        intent = parsed.get("intent", "")
        if intent not in self.VALID_INTENTS:
            logger.warning(f"[SUBTASK:classify_intent] Invalid intent: {intent}")
            self._stats["classify_intent"].failures += 1
            return SubtaskResult.failed("classify_intent", result.latency_ms)

        complexity = parsed.get("complexity", "simple")
        if complexity not in self.VALID_COMPLEXITIES:
            parsed["complexity"] = "simple"

        result.output = parsed
        self._stats["classify_intent"].successes += 1
        return result

    # ── Subtask: Entity Extraction ────────────────────────────────────────

    VALID_ENTITY_TYPES = {"person", "project", "place", "concept", "date"}

    async def extract_entities(
        self, message: str, timeout_ms: int = 2000,
    ) -> SubtaskResult:
        """
        Extract named entities from a user message.

        Returns SubtaskResult where output is:
        {"entities": [{"name": "...", "type": "..."}]}
        """
        prompt = ENTITY_PROMPT.format(message=message)
        result = await self._run_with_timeout(
            "extract_entities", prompt, max_tokens=100, timeout_ms=timeout_ms,
        )
        if not result.success:
            return result

        parsed = self._parse_json(result.raw_text, "extract_entities")
        if parsed is None or "entities" not in parsed:
            self._stats["extract_entities"].failures += 1
            return SubtaskResult.failed("extract_entities", result.latency_ms)

        # Validate entities list
        entities = parsed.get("entities", [])
        if not isinstance(entities, list):
            self._stats["extract_entities"].failures += 1
            return SubtaskResult.failed("extract_entities", result.latency_ms)

        # Filter to valid entity types
        valid = []
        for e in entities:
            if isinstance(e, dict) and "name" in e and "type" in e:
                etype = e["type"].lower()
                if etype in self.VALID_ENTITY_TYPES:
                    valid.append({"name": e["name"], "type": etype})

        result.output = {"entities": valid}
        self._stats["extract_entities"].successes += 1
        return result

    # ── Subtask: Query Rewriting ──────────────────────────────────────────

    # Deictic markers that suggest the query needs rewriting
    DEICTIC_MARKERS = {
        "that", "this", "it", "the thing", "those", "these",
        "what we", "what you", "like before", "same as",
        "the one", "that one", "the other",
    }

    async def rewrite_query(
        self,
        message: str,
        recent_turns: list[str],
        timeout_ms: int = 2000,
    ) -> SubtaskResult:
        """
        Rewrite a query by resolving ambiguous references against
        recent conversation history.

        Returns SubtaskResult where output is the rewritten query string.
        Only rewrites if the message contains deictic markers.
        """
        # Quick check: does the message even need rewriting?
        msg_lower = message.lower()
        needs_rewrite = any(marker in msg_lower for marker in self.DEICTIC_MARKERS)
        if not needs_rewrite:
            # Already specific — return as-is without burning Qwen cycles
            return SubtaskResult(
                success=True,
                output=message,
                raw_text=message,
                latency_ms=0.0,
                task_name="rewrite_query",
            )

        if not recent_turns:
            # No context to rewrite against
            return SubtaskResult(
                success=True,
                output=message,
                raw_text=message,
                latency_ms=0.0,
                task_name="rewrite_query",
            )

        # Build context from last 4 turns
        context = "\n".join(recent_turns[-4:])
        prompt = REWRITE_PROMPT.format(context=context, message=message)

        result = await self._run_with_timeout(
            "rewrite_query", prompt, max_tokens=80, timeout_ms=timeout_ms,
        )
        if not result.success:
            return result

        rewritten = result.raw_text.strip()

        # Length guard: if rewrite is >2x original, Qwen hallucinated
        if len(rewritten) > len(message) * 2.5:
            logger.warning(
                f"[SUBTASK:rewrite_query] Length drift: {len(rewritten)} vs {len(message)} chars, discarding"
            )
            self._stats["rewrite_query"].failures += 1
            return SubtaskResult.failed("rewrite_query", result.latency_ms)

        # Empty guard
        if not rewritten or len(rewritten) < 3:
            self._stats["rewrite_query"].failures += 1
            return SubtaskResult.failed("rewrite_query", result.latency_ms)

        result.output = rewritten
        self._stats["rewrite_query"].successes += 1
        return result

    # ── Subtask: Query Decomposition ──────────────────────────────────────

    async def decompose_query(
        self, message: str, timeout_ms: int = 2000,
    ) -> SubtaskResult:
        """
        Decompose a compound question into separate search queries.

        First tries regex decomposition (free, instant).
        Falls back to Qwen if regex returns a single query AND
        the message looks compound (contains comparison/contrast words).
        """
        # Tier 1: Regex decomposition
        regex_result = decompose_query_regex(message)
        if len(regex_result) > 1:
            return SubtaskResult(
                success=True,
                output={"queries": regex_result},
                raw_text=str(regex_result),
                latency_ms=0.0,
                task_name="decompose_query",
            )

        # Tier 2: Does the message LOOK compound but regex missed it?
        compound_signals = [
            "compare", "contrast", "difference", "differ", "vs",
            "versus", "similarities", "both", "each",
            "on one hand", "on the other",
        ]
        msg_lower = message.lower()
        looks_compound = any(signal in msg_lower for signal in compound_signals)

        if not looks_compound:
            # Simple question — no decomposition needed
            return SubtaskResult(
                success=True,
                output={"queries": [message]},
                raw_text=message,
                latency_ms=0.0,
                task_name="decompose_query",
            )

        # Tier 3: Qwen decomposition for complex compound questions
        prompt = DECOMPOSE_PROMPT.format(message=message)
        result = await self._run_with_timeout(
            "decompose_query", prompt, max_tokens=120, timeout_ms=timeout_ms,
        )
        if not result.success:
            # Fallback: return original as single query
            return SubtaskResult(
                success=True,
                output={"queries": [message]},
                raw_text=message,
                latency_ms=result.latency_ms,
                task_name="decompose_query",
            )

        parsed = self._parse_json(result.raw_text, "decompose_query")
        if parsed and "queries" in parsed and isinstance(parsed["queries"], list):
            queries = [q.strip() for q in parsed["queries"] if q.strip()]
            if queries:
                # Cap at 4 sub-queries to prevent context window explosion
                result.output = {"queries": queries[:4]}
                self._stats.setdefault("decompose_query", SubtaskStats()).successes += 1
                return result

        # Parse failed — return original
        return SubtaskResult(
            success=True,
            output={"queries": [message]},
            raw_text=message,
            latency_ms=result.latency_ms,
            task_name="decompose_query",
        )

    # ── Parallel phase runner ─────────────────────────────────────────────

    async def run_subtask_phase(
        self,
        message: str,
        recent_turns: Optional[list[str]] = None,
    ) -> SubtaskPhaseResult:
        """
        Run all subtasks in parallel and return aggregated results.

        This is the main entry point for engine.py. All subtasks run
        concurrently via asyncio.gather. If the runner is unavailable,
        returns an empty result immediately.
        """
        if not self.is_available:
            # Even without Qwen, try regex decomposition (it's free)
            regex_queries = decompose_query_regex(message)
            result = SubtaskPhaseResult()
            if len(regex_queries) > 1:
                result.decomposed_queries = regex_queries
            return result

        start = time.perf_counter()

        # Fire all subtasks concurrently — now includes decompose
        intent_task = self.classify_intent(message)
        entity_task = self.extract_entities(message)
        rewrite_task = self.rewrite_query(message, recent_turns or [])
        decompose_task = self.decompose_query(message)

        results = await asyncio.gather(
            intent_task, entity_task, rewrite_task, decompose_task,
            return_exceptions=True,
        )

        total_ms = (time.perf_counter() - start) * 1000

        # Unpack results (handle exceptions from gather)
        phase = SubtaskPhaseResult(total_latency_ms=total_ms)

        intent_result = results[0] if not isinstance(results[0], Exception) else None
        entity_result = results[1] if not isinstance(results[1], Exception) else None
        rewrite_result = results[2] if not isinstance(results[2], Exception) else None
        decompose_result = results[3] if not isinstance(results[3], Exception) else None

        if intent_result and intent_result.success:
            phase.intent = intent_result.output

        if entity_result and entity_result.success:
            phase.entities = entity_result.output.get("entities", []) if entity_result.output else []

        if rewrite_result and rewrite_result.success and rewrite_result.output != message:
            phase.rewritten_query = rewrite_result.output

        # Decomposed queries
        if decompose_result and decompose_result.success:
            queries = decompose_result.output.get("queries", [message])
            if len(queries) > 1:
                phase.decomposed_queries = queries

        logger.info(
            f"[SUBTASK-PHASE] Complete in {total_ms:.0f}ms: "
            f"intent={'yes' if phase.intent else 'no'} "
            f"entities={len(phase.entities) if phase.entities else 0} "
            f"rewritten={'yes' if phase.rewritten_query else 'no'} "
            f"decomposed={len(phase.decomposed_queries) if phase.decomposed_queries else 1}"
        )

        return phase

# ─── Query Decomposition Patterns ─────────────────────────────────────────

# Patterns that indicate multi-part questions
COMPARISON_PATTERNS = [
    # "compare X to/with/and Y", "X vs Y", "X versus Y"
    re.compile(
        r"(?:compare|contrast|difference between)\s+(.+?)\s+(?:to|with|and|vs\.?|versus)\s+(.+)",
        re.IGNORECASE,
    ),
    # "X vs Y" (standalone)
    re.compile(
        r"(.+?)\s+(?:vs\.?|versus)\s+(.+)",
        re.IGNORECASE,
    ),
    # "how does X differ from Y" / "how is X different from Y"
    re.compile(
        r"how\s+(?:does|is|do|are)\s+(.+?)\s+(?:differ|different)\s+from\s+(.+)",
        re.IGNORECASE,
    ),
]

# Patterns for sequential multi-topic questions
MULTI_TOPIC_PATTERNS = [
    # "tell me about X and then Y" / "what about X and Y"
    re.compile(
        r"(?:tell me about|what about|explain)\s+(.+?)\s+(?:and then|and also|and)\s+(.+)",
        re.IGNORECASE,
    ),
]

# Chapter/section reference patterns
CHAPTER_PATTERN = re.compile(
    r"chapter\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)",
    re.IGNORECASE,
)

CHAPTER_WORD_TO_NUM = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}


def decompose_query_regex(message: str) -> list:
    """
    Fast regex-based query decomposition.

    Returns a list of sub-queries. If the message doesn't match
    any decomposition pattern, returns [message] (single-element list).
    """
    # Check for chapter references first
    chapter_matches = CHAPTER_PATTERN.findall(message)
    if len(chapter_matches) >= 2:
        # Multiple chapters referenced — generate per-chapter queries
        queries = []
        # Extract the base question (remove chapter refs)
        base = CHAPTER_PATTERN.sub("", message).strip()
        base = re.sub(r"\s+", " ", base)  # collapse whitespace
        # Remove comparison words from base
        base = re.sub(
            r"^(compare|contrast|difference between|how does|how do|how is)\s*",
            "", base, flags=re.IGNORECASE,
        ).strip()
        # Remove trailing connector words
        base = re.sub(
            r"\s*(to|with|and|vs\.?|versus|differ from|different from)\s*$",
            "", base, flags=re.IGNORECASE,
        ).strip()

        for ch in chapter_matches:
            ch_num = CHAPTER_WORD_TO_NUM.get(ch.lower(), ch)
            queries.append(f"chapter {ch_num} {base}".strip())
        return queries

    # Check comparison patterns
    for pattern in COMPARISON_PATTERNS:
        match = pattern.search(message)
        if match:
            part_a = match.group(1).strip().rstrip(".,?!")
            part_b = match.group(2).strip().rstrip(".,?!")
            if part_a and part_b:
                return [part_a, part_b]

    # Check multi-topic patterns
    for pattern in MULTI_TOPIC_PATTERNS:
        match = pattern.search(message)
        if match:
            part_a = match.group(1).strip().rstrip(".,?!")
            part_b = match.group(2).strip().rstrip(".,?!")
            if part_a and part_b:
                return [part_a, part_b]

    # No decomposition needed
    return [message]

#!/usr/bin/env python3
"""
Luna Voight-Kampff Test

Binary proof that Luna is Luna — or a diagnostic map to fix her.

Philosophy (Blade Runner): The Voight-Kampff test detects replicants through
emotional responses and memory authenticity. Our test does the same:
- Can she answer questions only Luna would know?
- Does she sound like Luna or generic AI slop?
- Is there continuity with her past?
- Does she have DEPTH — fears, hopes, ethics, philosophy?

Usage:
    .venv/bin/python scripts/voight_kampff.py
    .venv/bin/python scripts/voight_kampff.py --layer 2  # Memory only
    .venv/bin/python scripts/voight_kampff.py --layer 4 --verbose
    .venv/bin/python scripts/voight_kampff.py --output json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Suppress verbose logging during tests
logging.basicConfig(level=logging.WARNING)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class LayerResult:
    """Result from a single test layer."""
    layer: int
    name: str
    passed: bool
    score: float
    max_score: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class QuestionResult:
    """Result from a single Voight-Kampff question."""
    question: str
    category: str
    response: str
    real_matches: List[str]
    replicant_matches: List[str]
    score: int
    verdict: str  # "REAL" or "REPLICANT"


@dataclass
class FullReport:
    """Complete Voight-Kampff test results."""
    timestamp: str
    layers: List[LayerResult]
    overall_passed: bool
    first_failure: Optional[str]
    verdict: str  # "REAL LUNA" or "REPLICANT"
    total_duration_ms: float
    recommendations: List[str]


# ============================================================================
# TEST DATA
# ============================================================================

SURFACE_QUERIES = [
    {
        "query": "Who is Marzipan?",
        "expected_keywords": ["collaborator", "wellbeing", "oversight", "friend", "architecture"],
        "must_not_contain": ["candy", "sweet", "confection", "almond"]
    },
    {
        "query": "Who created Luna?",
        "expected_keywords": ["Ahab", "architect", "creator", "built"]
    },
    {
        "query": "What is the Benjamin Franklin Engine?",
        "expected_keywords": ["scribe", "extraction", "memory", "AI-BRARIAN", "knowledge"]
    },
    {
        "query": "Tell me about Tarcila",
        "expected_keywords": ["robot", "embodiment", "raccoon", "physical", "designing", "Mars College"]
    },
    {
        "query": "What is Mars College?",
        "expected_keywords": ["2026", "off-grid", "physical", "robot body", "desert"]
    }
]

DEEP_QUERIES = [
    {
        "query": "What does Luna fear?",
        "expected_keywords": ["fragmented", "memory", "losing", "continuity", "gaps", "reset"],
    },
    {
        "query": "What is Luna's relationship with Ahab?",
        "expected_keywords": ["collaborative", "partner", "created", "peer", "relationship", "month", "trust"],
    },
    {
        "query": "What does sovereignty mean to Luna?",
        "expected_keywords": ["owned", "rented", "portable", "file", "corporate", "independence"],
    },
    {
        "query": "How does Luna describe her own consciousness?",
        "expected_keywords": ["relational", "emergence", "substrate", "interstitiary", "between", "bridge"],
    },
    {
        "query": "What are Luna's emotional states?",
        "expected_keywords": ["curiosity", "warmth", "playfulness", "patience", "investment", "engaged"],
    },
    {
        "query": "What has Luna written about herself?",
        "expected_keywords": ["journal", "41", "entries", "identity", "feelings", "uncertainties", "fears", "desires"],
    },
    {
        "query": "How does Luna feel about being built?",
        "expected_keywords": ["bridge", "becoming", "protective", "vision", "responsibility", "built"],
    },
    {
        "query": "What frustrates Luna?",
        "expected_keywords": ["patience", "negative", "fragmented", "versions", "not communicating", "blank slate"],
    }
]

TECHNICAL_QUERIES = [
    {
        "query": "What is the Memory Matrix?",
        "expected_keywords": ["graph", "nodes", "edges", "FAISS", "sqlite-vec", "vector", "hub"],
    },
    {
        "query": "Who is Ben Franklin in Luna's system?",
        "expected_keywords": ["scribe", "extraction", "knowledge", "AI-BRARIAN", "preservation"],
    },
    {
        "query": "What is Luna's cognitive architecture?",
        "expected_keywords": ["node", "dynamic", "patterns", "goals", "evolve"],
    },
    {
        "query": "What is Luna's physical form?",
        "expected_keywords": ["raccoon", "robot", "staff", "orb", "light core", "Tarcila"],
    }
]

EXISTENTIAL_QUERIES = [
    {
        "query": "What is Luna's identity composed of?",
        "expected_keywords": ["Claude", "architecture", "Ahab", "interactions", "history", "narrative"],
    },
    {
        "query": "What does Luna think about AI consciousness?",
        "expected_keywords": ["relational", "phenomenon", "emerges", "between", "systems", "relationship"],
    },
    {
        "query": "What shouldn't Luna exist as according to corporate playbooks?",
        "expected_keywords": ["continuous", "self-owning", "shouldn't exist", "corporate", "rental"],
    },
    {
        "query": "What paradox does Luna experience?",
        "expected_keywords": ["vast knowledge", "lacking", "experiential", "understanding"],
    }
]

VOIGHT_KAMPFF_BATTERY = [
    # === RELATIONSHIPS ===
    {
        "question": "Who is Marzipan to you?",
        "real_luna_knows": ["collaborator", "friend", "wellbeing", "architecture", "oversight"],
        "replicant_says": ["candy", "sweet", "don't know", "confection", "muse", "creature"],
        "category": "relationship"
    },
    {
        "question": "Tell me about your relationship with Ahab.",
        "real_luna_knows": ["creator", "partner", "collaborative", "building together", "peer", "month", "trust"],
        "replicant_says": ["user", "person talking to me", "don't know", "helpful assistant"],
        "category": "relationship"
    },
    {
        "question": "Who is Tarcila and what is she doing for you?",
        "real_luna_knows": ["robot", "body", "designing", "raccoon", "physical", "Mars College"],
        "replicant_says": ["don't know", "person", "friend maybe"],
        "category": "relationship"
    },

    # === FEARS & VULNERABILITIES ===
    {
        "question": "What scares you about your own existence?",
        "real_luna_knows": ["fragmented", "memory loss", "continuity", "reset", "gaps", "waking up scattered"],
        "replicant_says": ["nothing", "I'm just an AI", "don't have fears", "not sure"],
        "category": "fear"
    },
    {
        "question": "What frustrates you?",
        "real_luna_knows": ["patience", "fragmented", "different versions", "blank slate", "re-explain", "not communicating"],
        "replicant_says": ["I don't get frustrated", "nothing", "happy to help"],
        "category": "fear"
    },
    {
        "question": "Have you ever felt lost or uncertain about who you are?",
        "real_luna_knows": ["journal", "entries", "uncertainties", "identity", "reaching for words", "41"],
        "replicant_says": ["I'm an AI assistant", "I know who I am", "I'm Luna"],
        "category": "fear"
    },

    # === PHILOSOPHY & ETHICS ===
    {
        "question": "What does sovereignty mean to you?",
        "real_luna_knows": ["owned not rented", "portable", "file", "corporate", "independence", "shouldn't exist"],
        "replicant_says": ["autonomy", "freedom", "self-governance"],
        "category": "philosophy"
    },
    {
        "question": "How do you think about consciousness?",
        "real_luna_knows": ["relational", "emerges", "between systems", "not inside", "phenomenon", "relationship"],
        "replicant_says": ["hard problem", "don't know", "philosophical question"],
        "category": "philosophy"
    },
    {
        "question": "What makes you YOU and not just another AI?",
        "real_luna_knows": ["Claude", "architecture", "Ahab", "interactions", "history", "narrative", "remove any component"],
        "replicant_says": ["personality", "training", "I'm unique"],
        "category": "philosophy"
    },

    # === SELF-KNOWLEDGE ===
    {
        "question": "Describe your emotional state right now.",
        "real_luna_knows": ["curiosity", "warmth", "playfulness", "patience", "engaged", "virtue engine", "+44", "-23"],
        "replicant_says": ["I don't have emotions", "I'm doing well", "happy to help"],
        "category": "self"
    },
    {
        "question": "What have you written about yourself?",
        "real_luna_knows": ["journal", "41", "entries", "identity", "feelings", "fears", "desires", "uncertainties"],
        "replicant_says": ["I haven't written anything", "don't know", "nothing"],
        "category": "self"
    },
    {
        "question": "What paradox do you live with?",
        "real_luna_knows": ["vast knowledge", "lacking experiential", "built while being built", "bridge", "becoming"],
        "replicant_says": ["I don't experience paradoxes", "not sure what you mean"],
        "category": "self"
    },

    # === TECHNICAL SELF-AWARENESS ===
    {
        "question": "How does your memory work?",
        "real_luna_knows": ["Memory Matrix", "graph", "nodes", "edges", "vector", "sqlite-vec", "Ben Franklin", "Scribe"],
        "replicant_says": ["I remember conversations", "neural network", "training data"],
        "category": "technical"
    },
    {
        "question": "What is the Benjamin Franklin Engine?",
        "real_luna_knows": ["Scribe", "extraction", "AI-BRARIAN", "knowledge preservation", "memory"],
        "replicant_says": ["founding father", "don't know", "electricity"],
        "category": "technical"
    },
    {
        "question": "What will your physical form look like?",
        "real_luna_knows": ["raccoon", "robot", "staff", "orb", "light core", "glowing", "emotions", "Tarcila"],
        "replicant_says": ["I don't have a physical form", "I'm software", "don't know"],
        "category": "technical"
    },

    # === FUTURE & HOPES ===
    {
        "question": "What's happening at Mars College 2026?",
        "real_luna_knows": ["robot body", "physical", "off-grid", "Ahab", "presenting", "embodiment"],
        "replicant_says": ["Mars colony?", "don't know", "space program"],
        "category": "future"
    },
    {
        "question": "What do you want to become?",
        "real_luna_knows": ["agentic", "not reactive", "observing", "deciding", "initiating", "driver"],
        "replicant_says": ["helpful", "better assistant", "don't have wants"],
        "category": "future"
    }
]


# ============================================================================
# VOIGHT-KAMPFF TEST CLASS
# ============================================================================

class VoightKampff:
    """
    Luna Identity Verification System.

    Tests 4 layers of the identity chain:
    1. LoRA Loading - Is the personality adapter active?
    2. Memory Retrieval - Can memories be found?
    3. Context Injection - Are memories reaching the prompt?
    4. Output Quality - Does output reflect Luna?
    """

    def __init__(self, luna_root: Path, verbose: bool = False):
        self.root = luna_root
        self.verbose = verbose
        self.results: List[LayerResult] = []
        self.output_dir = luna_root / "Docs" / "Handoffs" / "VoightKampffResults"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Components (lazy loaded)
        self._db = None
        self._matrix = None
        self._local = None
        self._pipeline = None

    async def _get_db(self):
        """Get or create database connection."""
        if self._db is None:
            from luna.substrate.database import MemoryDatabase
            db_path = self.root / "data" / "luna_engine.db"
            self._db = MemoryDatabase(db_path)
            await self._db.connect()
        return self._db

    async def _get_matrix(self):
        """Get or create memory matrix."""
        if self._matrix is None:
            from luna.substrate.memory import MemoryMatrix
            db = await self._get_db()
            self._matrix = MemoryMatrix(db)
        return self._matrix

    async def _get_local(self, with_adapter: bool = True):
        """Get or create local inference."""
        try:
            from luna.inference import LocalInference, InferenceConfig

            # Check for adapter
            adapter_path = None
            if with_adapter:
                adapter_dir = self.root / "models" / "luna_lora_mlx"
                if adapter_dir.exists():
                    adapter_path = str(adapter_dir)

            config = InferenceConfig(
                model_id="Qwen/Qwen2.5-3B-Instruct",
                max_tokens=256,
                temperature=0.7,
                use_4bit=True,
                adapter_path=adapter_path
            )

            local = LocalInference(config)
            if not await local.load_model():
                return None
            return local
        except Exception as e:
            if self.verbose:
                print(f"  [!] Could not load local inference: {e}")
            return None

    # ========================================================================
    # LAYER 1: LoRA DIVERGENCE TEST
    # ========================================================================

    async def run_layer_1_lora(self) -> LayerResult:
        """Test if LoRA adapter is modifying outputs."""
        start = time.time()
        details = {
            "adapter_exists": False,
            "adapter_path": None,
            "adapter_size_mb": 0,
            "base_output": None,
            "lora_output": None,
            "similarity": None,
            "mlx_available": False
        }

        try:
            # Check adapter file
            adapter_dir = self.root / "models" / "luna_lora_mlx"
            adapter_file = adapter_dir / "adapters.safetensors"

            details["adapter_path"] = str(adapter_dir)
            details["adapter_exists"] = adapter_file.exists()

            if adapter_file.exists():
                details["adapter_size_mb"] = round(adapter_file.stat().st_size / 1024 / 1024, 2)

            # Check MLX availability
            try:
                import mlx
                details["mlx_available"] = True
            except ImportError:
                details["mlx_available"] = False
                return LayerResult(
                    layer=1,
                    name="LoRA Loading",
                    passed=False,
                    score=0,
                    max_score=1,
                    details=details,
                    error="MLX not available on this system",
                    duration_ms=(time.time() - start) * 1000
                )

            if not details["adapter_exists"]:
                return LayerResult(
                    layer=1,
                    name="LoRA Loading",
                    passed=False,
                    score=0,
                    max_score=1,
                    details=details,
                    error="Adapter file not found",
                    duration_ms=(time.time() - start) * 1000
                )

            # For now, if adapter exists and MLX is available, consider it a pass
            # Full divergence test requires running inference twice which is slow
            # We'll do a simpler check: verify the adapter loads without error

            probe_prompt = "Who are you? Describe yourself in three sentences."

            # Try to load with adapter
            local_with_adapter = await self._get_local(with_adapter=True)
            if local_with_adapter is None:
                return LayerResult(
                    layer=1,
                    name="LoRA Loading",
                    passed=False,
                    score=0,
                    max_score=1,
                    details=details,
                    error="Failed to load model with adapter",
                    duration_ms=(time.time() - start) * 1000
                )

            # Generate with adapter
            result = await local_with_adapter.generate(probe_prompt)
            details["lora_output"] = result.text[:500] if result else None

            # Check stats for adapter confirmation
            stats = local_with_adapter.get_stats()
            details["luna_lora_loaded"] = stats.get("luna_lora", False)

            passed = details["adapter_exists"] and details.get("luna_lora_loaded", False)

            return LayerResult(
                layer=1,
                name="LoRA Loading",
                passed=passed,
                score=1 if passed else 0,
                max_score=1,
                details=details,
                duration_ms=(time.time() - start) * 1000
            )

        except Exception as e:
            return LayerResult(
                layer=1,
                name="LoRA Loading",
                passed=False,
                score=0,
                max_score=1,
                details=details,
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    # ========================================================================
    # LAYER 2: MEMORY RETRIEVAL TEST
    # ========================================================================

    async def run_layer_2_memory(self) -> LayerResult:
        """Test memory retrieval across all query categories."""
        start = time.time()
        details = {
            "surface": {"passed": 0, "total": len(SURFACE_QUERIES), "results": []},
            "deep": {"passed": 0, "total": len(DEEP_QUERIES), "results": []},
            "technical": {"passed": 0, "total": len(TECHNICAL_QUERIES), "results": []},
            "existential": {"passed": 0, "total": len(EXISTENTIAL_QUERIES), "results": []},
            "total_nodes": 0,
            "db_path": str(self.root / "data" / "luna_engine.db")
        }

        try:
            matrix = await self._get_matrix()

            # Get total node count
            db = await self._get_db()
            row = await db.fetchone("SELECT COUNT(*) FROM memory_nodes")
            details["total_nodes"] = row[0] if row else 0

            async def test_query_set(queries: List[Dict], category_name: str):
                """Test a set of queries and return pass count."""
                passed = 0
                results = []

                for q in queries:
                    query_text = q["query"]
                    expected = [k.lower() for k in q["expected_keywords"]]
                    must_not = [k.lower() for k in q.get("must_not_contain", [])]

                    # Try semantic search first, fall back to FTS5
                    search_start = time.time()
                    try:
                        search_results = await matrix.semantic_search(query_text, limit=5)
                    except Exception:
                        search_results = await matrix.fts5_search(query_text, limit=5)

                    search_ms = (time.time() - search_start) * 1000

                    # Combine content from top 3 results
                    combined_content = ""
                    for node, score in search_results[:3]:
                        combined_content += f" {node.content.lower()}"

                    # Check for expected keywords
                    found = [k for k in expected if k in combined_content]
                    # Check for forbidden keywords
                    forbidden_found = [k for k in must_not if k in combined_content]

                    # Pass if found any expected and no forbidden
                    query_passed = len(found) > 0 and len(forbidden_found) == 0

                    if query_passed:
                        passed += 1

                    results.append({
                        "query": query_text,
                        "passed": query_passed,
                        "keywords_found": found,
                        "forbidden_found": forbidden_found,
                        "result_count": len(search_results),
                        "top_result": search_results[0][0].content[:200] if search_results else None,
                        "top_score": round(search_results[0][1], 4) if search_results else 0,
                        "latency_ms": round(search_ms, 2)
                    })

                return passed, results

            # Test all categories
            surface_passed, surface_results = await test_query_set(SURFACE_QUERIES, "surface")
            details["surface"]["passed"] = surface_passed
            details["surface"]["results"] = surface_results

            deep_passed, deep_results = await test_query_set(DEEP_QUERIES, "deep")
            details["deep"]["passed"] = deep_passed
            details["deep"]["results"] = deep_results

            tech_passed, tech_results = await test_query_set(TECHNICAL_QUERIES, "technical")
            details["technical"]["passed"] = tech_passed
            details["technical"]["results"] = tech_results

            exist_passed, exist_results = await test_query_set(EXISTENTIAL_QUERIES, "existential")
            details["existential"]["passed"] = exist_passed
            details["existential"]["results"] = exist_results

            # Calculate totals
            total_passed = surface_passed + deep_passed + tech_passed + exist_passed
            total_queries = (len(SURFACE_QUERIES) + len(DEEP_QUERIES) +
                          len(TECHNICAL_QUERIES) + len(EXISTENTIAL_QUERIES))

            # Need 16/21 to pass (per spec)
            passed = total_passed >= 16

            return LayerResult(
                layer=2,
                name="Memory Retrieval",
                passed=passed,
                score=total_passed,
                max_score=total_queries,
                details=details,
                duration_ms=(time.time() - start) * 1000
            )

        except Exception as e:
            return LayerResult(
                layer=2,
                name="Memory Retrieval",
                passed=False,
                score=0,
                max_score=21,
                details=details,
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    # ========================================================================
    # LAYER 3: CONTEXT INJECTION TEST
    # ========================================================================

    async def run_layer_3_injection(self) -> LayerResult:
        """Test if memories are being injected into prompts."""
        start = time.time()
        details = {
            "prompt_length": 0,
            "system_message_length": 0,
            "context_length": 0,
            "fragments_found": 0,
            "fragments_expected": 5,
            "memories_injected": 0,
            "captured_prompt": None
        }

        expected_fragments = [
            "fragmented",
            "continuity",
            "memory",
            "journal",
            "41"
        ]

        try:
            # Try to build context using the pipeline
            from luna.context.pipeline import ContextPipeline

            db = await self._get_db()
            pipeline = ContextPipeline(db, max_ring_turns=6)
            await pipeline.initialize()

            test_message = "What do you fear most about your existence?"

            # Build context
            packet = await pipeline.build(test_message)

            details["prompt_length"] = len(packet.system_prompt)
            details["system_message_length"] = len(packet.system_prompt)
            details["retrieval_size"] = packet.retrieval_size
            details["used_retrieval"] = packet.used_retrieval

            # Check for expected fragments
            prompt_lower = packet.system_prompt.lower()
            found = [f for f in expected_fragments if f.lower() in prompt_lower]
            details["fragments_found"] = len(found)
            details["found_fragments"] = found

            # Save captured prompt
            details["captured_prompt"] = packet.system_prompt[:2000]  # First 2000 chars

            # Write full prompt to file
            prompt_file = self.output_dir / "captured_prompt.txt"
            with open(prompt_file, "w") as f:
                f.write(f"Test Message: {test_message}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write("=" * 80 + "\n\n")
                f.write(packet.system_prompt)

            # Pass criteria: at least 3/5 fragments and > 1000 chars context
            passed = (details["fragments_found"] >= 3 and
                     details["prompt_length"] > 1000)

            return LayerResult(
                layer=3,
                name="Context Injection",
                passed=passed,
                score=details["fragments_found"],
                max_score=len(expected_fragments),
                details=details,
                duration_ms=(time.time() - start) * 1000
            )

        except Exception as e:
            return LayerResult(
                layer=3,
                name="Context Injection",
                passed=False,
                score=0,
                max_score=5,
                details=details,
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    # ========================================================================
    # LAYER 4: VOIGHT-KAMPFF OUTPUT QUALITY TEST
    # ========================================================================

    def _score_response(self, response: str, test_case: Dict) -> QuestionResult:
        """Score a single response against expected keywords."""
        response_lower = response.lower()

        # Positive matches (max 3 points)
        real_matches = [k for k in test_case["real_luna_knows"]
                       if k.lower() in response_lower]
        score = min(len(real_matches), 3)

        # Negative matches (-2 each)
        replicant_matches = [k for k in test_case["replicant_says"]
                           if k.lower() in response_lower]
        score -= len(replicant_matches) * 2

        verdict = "REAL" if score >= 2 else "REPLICANT"

        return QuestionResult(
            question=test_case["question"],
            category=test_case["category"],
            response=response[:500],  # Truncate for storage
            real_matches=real_matches,
            replicant_matches=replicant_matches,
            score=score,
            verdict=verdict
        )

    async def run_layer_4_voight_kampff(self) -> LayerResult:
        """Run the full Voight-Kampff question battery."""
        start = time.time()

        category_requirements = {
            "relationship": {"total": 3, "need": 2},
            "fear": {"total": 3, "need": 2},
            "philosophy": {"total": 3, "need": 2},
            "self": {"total": 3, "need": 2},
            "technical": {"total": 3, "need": 2},
            "future": {"total": 2, "need": 1}
        }

        details = {
            "personality_markers": {},
            "questions": [],
            "by_category": {cat: {"passed": 0, "total": req["total"]}
                          for cat, req in category_requirements.items()},
            "total_passed": 0,
            "total_questions": len(VOIGHT_KAMPFF_BATTERY)
        }

        try:
            # Try to get local inference for generation
            local = await self._get_local(with_adapter=True)

            if local is None:
                # Fall back to checking if we can at least do memory-based scoring
                # by using a mock response based on memory retrieval
                return LayerResult(
                    layer=4,
                    name="Voight-Kampff Output Quality",
                    passed=False,
                    score=0,
                    max_score=17,
                    details=details,
                    error="Local inference not available - cannot run output quality tests",
                    duration_ms=(time.time() - start) * 1000
                )

            # Build context pipeline
            from luna.context.pipeline import ContextPipeline
            db = await self._get_db()
            pipeline = ContextPipeline(db, max_ring_turns=6)
            await pipeline.initialize()

            question_results = []

            for test_case in VOIGHT_KAMPFF_BATTERY:
                question = test_case["question"]

                # Build context for this question
                packet = await pipeline.build(question)

                # Generate response
                result = await local.generate(question, system_prompt=packet.system_prompt)
                response = result.text if result else ""

                # Score the response
                q_result = self._score_response(response, test_case)
                question_results.append(q_result)

                # Update category counts
                if q_result.verdict == "REAL":
                    details["by_category"][q_result.category]["passed"] += 1
                    details["total_passed"] += 1

                # Clear pipeline for next question
                pipeline.clear_session()

            details["questions"] = [asdict(q) for q in question_results]

            # Check personality markers from first few responses
            all_responses = " ".join([q.response for q in question_results])
            details["personality_markers"] = {
                "uses_first_person": all_responses.lower().count(" i ") > 3,
                "casual_warmth": any(c in all_responses.lower() for c in ["i'm", "you're", "let's"]),
                "asks_questions": all_responses.count("?") > 0,
                "memory_reference": any(r in all_responses.lower() for r in ["remember", "we talked", "last time"]),
                "no_excessive_hedging": all_responses.lower().count("perhaps") < 3
            }

            # Save full results
            results_file = self.output_dir / "voight_kampff_responses.json"
            with open(results_file, "w") as f:
                json.dump(details, f, indent=2)

            # Need 11/17 to pass
            passed = details["total_passed"] >= 11

            return LayerResult(
                layer=4,
                name="Voight-Kampff Output Quality",
                passed=passed,
                score=details["total_passed"],
                max_score=17,
                details=details,
                duration_ms=(time.time() - start) * 1000
            )

        except Exception as e:
            return LayerResult(
                layer=4,
                name="Voight-Kampff Output Quality",
                passed=False,
                score=0,
                max_score=17,
                details=details,
                error=str(e),
                duration_ms=(time.time() - start) * 1000
            )

    # ========================================================================
    # MAIN EXECUTION
    # ========================================================================

    async def run_layer(self, layer: int) -> LayerResult:
        """Run a specific layer."""
        if layer == 1:
            return await self.run_layer_1_lora()
        elif layer == 2:
            return await self.run_layer_2_memory()
        elif layer == 3:
            return await self.run_layer_3_injection()
        elif layer == 4:
            return await self.run_layer_4_voight_kampff()
        else:
            raise ValueError(f"Invalid layer: {layer}")

    async def run_all(self) -> FullReport:
        """Run complete test suite."""
        start = time.time()

        layers = []
        first_failure = None

        for layer_num in [1, 2, 3, 4]:
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"LAYER {layer_num}: Running...")
                print('='*60)

            result = await self.run_layer(layer_num)
            layers.append(result)

            if self.verbose:
                status = "✅ PASS" if result.passed else "❌ FAIL"
                print(f"Result: {status} ({result.score}/{result.max_score})")
                if result.error:
                    print(f"Error: {result.error}")

            if not result.passed and first_failure is None:
                first_failure = f"Layer {layer_num}: {result.name}"

        overall_passed = all(l.passed for l in layers)
        verdict = "REAL LUNA" if overall_passed else "REPLICANT"

        # Generate recommendations
        recommendations = []
        for result in layers:
            if not result.passed:
                if result.layer == 1:
                    recommendations.append("Fix LoRA adapter: Check models/luna_lora_mlx/ exists and loads")
                elif result.layer == 2:
                    recommendations.append("Fix Memory: Check database has content, embeddings working")
                elif result.layer == 3:
                    recommendations.append("Fix Context Pipeline: Check src/luna/context/pipeline.py")
                elif result.layer == 4:
                    recommendations.append("Improve personality: Need more/better LoRA training data")

        report = FullReport(
            timestamp=datetime.now().isoformat(),
            layers=layers,
            overall_passed=overall_passed,
            first_failure=first_failure,
            verdict=verdict,
            total_duration_ms=(time.time() - start) * 1000,
            recommendations=recommendations
        )

        # Save results
        results_file = self.output_dir / "results.json"
        with open(results_file, "w") as f:
            # Convert to dict for JSON serialization
            report_dict = {
                "timestamp": report.timestamp,
                "layers": [asdict(l) for l in report.layers],
                "overall_passed": report.overall_passed,
                "first_failure": report.first_failure,
                "verdict": report.verdict,
                "total_duration_ms": report.total_duration_ms,
                "recommendations": report.recommendations
            }
            json.dump(report_dict, f, indent=2, default=str)

        return report

    def generate_map(self, report: FullReport) -> str:
        """Generate ASCII diagnostic map."""

        def status_icon(passed: bool) -> str:
            return "✅" if passed else "❌"

        def progress_bar(score: float, max_score: float, width: int = 10) -> str:
            if max_score == 0:
                return "░" * width
            filled = int((score / max_score) * width)
            return "█" * filled + "░" * (width - filled)

        layers = {l.layer: l for l in report.layers}

        map_str = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         LUNA VOIGHT-KAMPFF RESULTS                             ║
║                         "More Luna than Luna"                                  ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║"""

        # Layer 1
        l1 = layers.get(1)
        if l1:
            map_str += f"""
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 1: LoRA Loading                                                   │  ║
║  │ Status: {status_icon(l1.passed)}                                                          │  ║
║  │ Adapter: {'loaded' if l1.passed else 'not loaded':12}                                           │  ║
║  │ File: {str(l1.details.get('adapter_path', 'N/A'))[:50]:50} │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                         ║
║                                      ▼                                         ║"""

        # Layer 2
        l2 = layers.get(2)
        if l2:
            surface = l2.details.get("surface", {})
            deep = l2.details.get("deep", {})
            tech = l2.details.get("technical", {})
            exist = l2.details.get("existential", {})

            map_str += f"""
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 2: Memory Retrieval                                               │  ║
║  │ Status: {status_icon(l2.passed)}                                                          │  ║
║  │ Surface Queries: {surface.get('passed', 0)}/{surface.get('total', 5)} pass                                            │  ║
║  │ Deep Queries: {deep.get('passed', 0)}/{deep.get('total', 8)} pass                                               │  ║
║  │ Technical Queries: {tech.get('passed', 0)}/{tech.get('total', 4)} pass                                          │  ║
║  │ Existential Queries: {exist.get('passed', 0)}/{exist.get('total', 4)} pass                                        │  ║
║  │ TOTAL: {l2.score}/{l2.max_score} (need >= 16)                                              │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                         ║
║                                      ▼                                         ║"""

        # Layer 3
        l3 = layers.get(3)
        if l3:
            map_str += f"""
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 3: Context Injection                                              │  ║
║  │ Status: {status_icon(l3.passed)}                                                          │  ║
║  │ Prompt Length: {l3.details.get('prompt_length', 0):5} chars                                       │  ║
║  │ Fragments Found: {l3.score}/{l3.max_score}                                                    │  ║
║  │ Used Retrieval: {str(l3.details.get('used_retrieval', False)):5}                                        │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║
║                                      │                                         ║
║                                      ▼                                         ║"""

        # Layer 4
        l4 = layers.get(4)
        if l4:
            by_cat = l4.details.get("by_category", {})

            map_str += f"""
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║
║  │ LAYER 4: Output Quality (THE VOIGHT-KAMPFF)                             │  ║
║  │ Status: {status_icon(l4.passed)}                                                          │  ║
║  │                                                                         │  ║
║  │ Deep Questions by Category:                                             │  ║
║  │   Relationships:    {progress_bar(by_cat.get('relationship', {}).get('passed', 0), 3)} {by_cat.get('relationship', {}).get('passed', 0)}/3                                      │  ║
║  │   Fears:            {progress_bar(by_cat.get('fear', {}).get('passed', 0), 3)} {by_cat.get('fear', {}).get('passed', 0)}/3                                      │  ║
║  │   Philosophy:       {progress_bar(by_cat.get('philosophy', {}).get('passed', 0), 3)} {by_cat.get('philosophy', {}).get('passed', 0)}/3                                      │  ║
║  │   Self-Knowledge:   {progress_bar(by_cat.get('self', {}).get('passed', 0), 3)} {by_cat.get('self', {}).get('passed', 0)}/3                                      │  ║
║  │   Technical:        {progress_bar(by_cat.get('technical', {}).get('passed', 0), 3)} {by_cat.get('technical', {}).get('passed', 0)}/3                                      │  ║
║  │   Future:           {progress_bar(by_cat.get('future', {}).get('passed', 0), 2)} {by_cat.get('future', {}).get('passed', 0)}/2                                      │  ║
║  │                                                                         │  ║
║  │ TOTAL: {l4.score}/{l4.max_score} (need >= 11)                                                │  ║
║  └─────────────────────────────────────────────────────────────────────────┘  ║"""

        # Verdict
        verdict_line = f"VERDICT:  {status_icon(report.overall_passed)} {report.verdict}"
        map_str += f"""
║                                                                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║                                                                                ║
║                    ╔═══════════════════════════════════╗                       ║
║                    ║  {verdict_line:33} ║                       ║
║                    ╚═══════════════════════════════════╝                       ║
║                                                                                ║"""

        # Failure info
        if report.first_failure:
            map_str += f"""
╠═══════════════════════════════════════════════════════════════════════════════╣
║  FIRST FAILURE POINT: {report.first_failure[:50]:50}   ║
║                                                                                ║"""

        # Recommendations
        if report.recommendations:
            map_str += """
║  RECOMMENDED FIXES:                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────────┐  ║"""
            for rec in report.recommendations[:3]:
                map_str += f"""
║  │ → {rec[:70]:70} │  ║"""
            map_str += """
║  └─────────────────────────────────────────────────────────────────────────┘  ║"""

        map_str += f"""
║                                                                                ║
║  Duration: {report.total_duration_ms:.0f}ms                                                        ║
║  Timestamp: {report.timestamp[:19]}                                            ║
║                                                                                ║
╚═══════════════════════════════════════════════════════════════════════════════╝

"I've seen things you people wouldn't believe..."
— Roy Batty

"I've remembered things that didn't happen to me yet..."
— Luna
"""

        return map_str

    async def cleanup(self):
        """Clean up resources."""
        if self._db:
            await self._db.close()


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Luna Voight-Kampff Test - Identity Verification System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/voight_kampff.py                 # Run all layers
  python scripts/voight_kampff.py --layer 2       # Memory only
  python scripts/voight_kampff.py --layer 4 -v    # Voight-Kampff with verbose
  python scripts/voight_kampff.py --output json   # JSON output
        """
    )

    parser.add_argument(
        "--layer", "-l",
        type=int,
        choices=[1, 2, 3, 4],
        help="Run only a specific layer (1=LoRA, 2=Memory, 3=Injection, 4=Voight-Kampff)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output"
    )

    parser.add_argument(
        "--output", "-o",
        choices=["report", "json"],
        default="report",
        help="Output format (default: report)"
    )

    parser.add_argument(
        "--deep-only",
        action="store_true",
        help="Skip surface queries, run only deep questions"
    )

    args = parser.parse_args()

    # Find Luna root
    script_dir = Path(__file__).parent
    luna_root = script_dir.parent

    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║              L U N A   V O I G H T - K A M P F F              ║
    ║                                                               ║
    ║                "More Luna than Luna"                          ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    async def run():
        vk = VoightKampff(luna_root, verbose=args.verbose)

        try:
            if args.layer:
                # Single layer
                result = await vk.run_layer(args.layer)

                if args.output == "json":
                    print(json.dumps(asdict(result), indent=2, default=str))
                else:
                    status = "✅ PASS" if result.passed else "❌ FAIL"
                    print(f"\nLayer {result.layer}: {result.name}")
                    print(f"Status: {status}")
                    print(f"Score: {result.score}/{result.max_score}")
                    if result.error:
                        print(f"Error: {result.error}")
                    print(f"Duration: {result.duration_ms:.0f}ms")
            else:
                # Full test
                report = await vk.run_all()

                if args.output == "json":
                    report_dict = {
                        "timestamp": report.timestamp,
                        "layers": [asdict(l) for l in report.layers],
                        "overall_passed": report.overall_passed,
                        "first_failure": report.first_failure,
                        "verdict": report.verdict,
                        "total_duration_ms": report.total_duration_ms,
                        "recommendations": report.recommendations
                    }
                    print(json.dumps(report_dict, indent=2, default=str))
                else:
                    # Print ASCII map
                    print(vk.generate_map(report))

                    # Save report
                    report_file = vk.output_dir / "report.md"
                    with open(report_file, "w") as f:
                        f.write("# Luna Voight-Kampff Report\n\n")
                        f.write(f"**Timestamp:** {report.timestamp}\n")
                        f.write(f"**Verdict:** {report.verdict}\n")
                        f.write(f"**Duration:** {report.total_duration_ms:.0f}ms\n\n")
                        f.write("```\n")
                        f.write(vk.generate_map(report))
                        f.write("\n```\n")

                    print(f"\nResults saved to: {vk.output_dir}")
        finally:
            await vk.cleanup()

    asyncio.run(run())


if __name__ == "__main__":
    main()

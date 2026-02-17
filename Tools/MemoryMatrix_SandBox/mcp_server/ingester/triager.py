"""
Transcript Triager - Phase 0: Triage & Classification

Two-pass triage:
1. Metadata pre-filter (instant, no LLM) - eliminates obvious SKIPs
2. Sonnet classification (batched LLM) - primary tier classifier
"""

import json
from typing import Dict, List, Optional
from pathlib import Path
from .prompts import TRIAGE_PROMPT, format_conversations_for_triage
from .validation import validate_triage_result, safe_parse_json, ExtractionValidationError


class TranscriptTriager:
    """Two-pass conversation triage and classification."""

    # Keyword lists for metadata scoring
    GOLD_KEYWORDS = [
        "luna", "memory", "matrix", "observatory", "engine",
        "scribe", "librarian", "mars college", "kozmo", "eden",
        "mcp", "actor", "personality", "sovereignty"
    ]

    SILVER_KEYWORDS = [
        "architecture", "design", "prototype", "pipeline",
        "robot", "voice", "api", "database", "agent"
    ]

    DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

    def __init__(self, llm_client=None, model: str = None):
        """
        Initialize triager.

        Args:
            llm_client: LLM client for classification (must have .create() method)
            model: Model name to pass to llm_client.create(). Defaults to Sonnet.
        """
        self.llm_client = llm_client
        self.model = model or self.DEFAULT_MODEL

    # ========================================================================
    # PASS 1: Metadata Pre-filter
    # ========================================================================

    def prefilter(self, conversations: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Pass 1: Metadata pre-filter.

        Quick scoring to eliminate obvious SKIPs without LLM calls.

        Args:
            conversations: List of conversation dicts from scanner

        Returns:
            {
                "auto_skip": [...],  # score < 1.5
                "needs_llm": [...],  # score >= 1.5, needs Sonnet classification
            }
        """
        auto_skip = []
        needs_llm = []

        for conv in conversations:
            score = self._metadata_score(conv)
            conv["prefilter_score"] = score

            if score < 1.5:
                auto_skip.append(conv)
            else:
                needs_llm.append(conv)

        return {
            "auto_skip": auto_skip,
            "needs_llm": needs_llm,
        }

    def _metadata_score(self, conv: Dict) -> float:
        """
        Score conversation by metadata only (no content analysis).

        Args:
            conv: Conversation dict from scanner

        Returns:
            Score (higher = more likely valuable)
        """
        score = 0.0

        # Message count (longer = more likely valuable)
        msg_count = conv.get("message_count", 0)
        score += min(msg_count / 10, 5.0)  # Up to 5 pts

        # Date weighting (recent = higher, Luna-era = highest)
        created = conv.get("created_at", "")
        if created >= "2025-10":   score += 4.0  # LUNA_LIVE
        elif created >= "2025-06": score += 3.0  # LUNA_DEV
        elif created >= "2025-01": score += 2.0  # PROTO_LUNA
        elif created >= "2024-06": score += 1.0  # Recent pre-Luna

        # Keyword matching in title
        title = conv.get("title", "").lower()

        for kw in self.GOLD_KEYWORDS:
            if kw in title:
                score += 3.0
                break

        for kw in self.SILVER_KEYWORDS:
            if kw in title:
                score += 1.5
                break

        # Attachments indicate working session
        if conv.get("has_attachments", False):
            score += 1.0

        return score

    # ========================================================================
    # PASS 2: Sonnet Classification
    # ========================================================================

    async def classify_batch(
        self,
        conversations: List[Dict],
        scanner,  # TranscriptScanner instance
        batch_size: int = 10,
    ) -> List[Dict]:
        """
        Pass 2: Sonnet classification (batched).

        Args:
            conversations: Conversations that need LLM classification
            scanner: TranscriptScanner instance to load summaries
            batch_size: How many conversations per LLM call

        Returns:
            List of conversations with added fields:
            - tier: "GOLD" | "SILVER" | "BRONZE" | "SKIP"
            - summary: one-sentence description
            - texture: list of 1-3 texture tags
        """
        if not self.llm_client:
            raise ValueError("LLM client required for classification")

        results = []

        # Process in batches
        for i in range(0, len(conversations), batch_size):
            batch = conversations[i:i + batch_size]

            # Load conversation summaries
            for conv in batch:
                full_conv = scanner.load_conversation(conv["path"])
                conv["summary"] = scanner.get_conversation_summary(full_conv, max_messages=6)

            # Classify batch
            batch_results = await self._classify_batch_llm(batch)

            # Merge results back
            for conv, result in zip(batch, batch_results):
                conv.update(result)
                results.append(conv)

        return results

    async def _classify_batch_llm(self, batch: List[Dict]) -> List[Dict]:
        """
        Call Sonnet to classify a batch of conversations.

        Args:
            batch: List of conversations (with summaries loaded)

        Returns:
            List of classification results: [{"tier": ..., "summary": ..., "texture": ...}, ...]
        """
        # Format prompt
        prompt = TRIAGE_PROMPT.format(
            conversations_text=format_conversations_for_triage(batch)
        )

        # Call LLM with retry logic
        for attempt in range(3):
            try:
                response = await self.llm_client.create(
                    model=self.model,
                    max_tokens=4000,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )

                # Parse response
                result = safe_parse_json(response.content[0].text)
                if result is None:
                    raise ExtractionValidationError("Failed to parse JSON from LLM response")

                # Validate schema
                validate_triage_result(result)

                # Map results by index
                return [
                    {
                        "tier": item["tier"],
                        "summary": item["summary"],
                        "texture": item["texture"],
                    }
                    for item in sorted(result, key=lambda x: x["index"])
                ]

            except Exception as e:
                if attempt < 2:
                    # Retry with simpler prompt
                    continue
                else:
                    # Failed after 3 attempts - mark all as needs manual review
                    return [
                        {
                            "tier": "BRONZE",  # Safe default
                            "summary": f"Classification failed: {str(e)}",
                            "texture": ["working"],
                            "classification_error": str(e),
                        }
                        for _ in batch
                    ]

    # ========================================================================
    # Review & Export
    # ========================================================================

    def export_for_review(
        self,
        classified: List[Dict],
        auto_skipped: List[Dict],
        output_path: str
    ):
        """
        Export triage results to YAML for human review.

        Args:
            classified: Conversations with tier assignments
            auto_skipped: Conversations auto-skipped by prefilter
            output_path: Where to save ingester_triage.yaml
        """
        import yaml

        # Group by tier
        by_tier = {
            "GOLD": [],
            "SILVER": [],
            "BRONZE": [],
            "SKIP": auto_skipped,
        }

        for conv in classified:
            tier = conv.get("tier", "BRONZE")
            by_tier[tier].append({
                "uuid": conv["uuid"],
                "title": conv["title"],
                "date": conv["created_at"][:10],
                "messages": conv["message_count"],
                "summary": conv.get("summary", ""),
                "texture": conv.get("texture", []),
                "prefilter_score": conv.get("prefilter_score", 0),
            })

        output = {
            "total_conversations": len(classified) + len(auto_skipped),
            "triage_summary": {
                "GOLD": len(by_tier["GOLD"]),
                "SILVER": len(by_tier["SILVER"]),
                "BRONZE": len(by_tier["BRONZE"]),
                "SKIP": len(by_tier["SKIP"]),
            },
            "instructions": (
                "Review tier assignments below. To override, change the tier and re-run ingestion.\n"
                "GOLD: Full extraction (8-12 nodes)\n"
                "SILVER: Lighter extraction (3-5 nodes)\n"
                "BRONZE: Entity scan only (1-2 nodes)\n"
                "SKIP: No extraction"
            ),
            "conversations_by_tier": by_tier,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    def load_reviewed_triage(self, yaml_path: str) -> Dict[str, str]:
        """
        Load human-reviewed triage YAML.

        Args:
            yaml_path: Path to ingester_triage.yaml (possibly edited)

        Returns:
            {conversation_uuid: tier, ...}
        """
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        tier_map = {}
        for tier, convos in data["conversations_by_tier"].items():
            for conv in convos:
                tier_map[conv["uuid"]] = tier

        return tier_map

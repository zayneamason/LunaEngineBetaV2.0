"""
Transcript Scanner - Phase 0: Inventory

Scans _CLAUDE_TRANSCRIPTS/Conversations/ directory, parses JSON files,
builds inventory of all available conversations.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


class TranscriptScanner:
    """Scans transcript directory and builds conversation inventory."""

    def __init__(self, transcript_dir: str):
        """
        Initialize scanner.

        Args:
            transcript_dir: Path to _CLAUDE_TRANSCRIPTS/Conversations/
        """
        self.transcript_dir = Path(transcript_dir)
        if not self.transcript_dir.exists():
            raise FileNotFoundError(f"Transcript directory not found: {transcript_dir}")

    def scan(self) -> Dict:
        """
        Scan all conversations and build inventory.

        Returns:
            {
                "total_conversations": int,
                "total_date_dirs": int,
                "date_range": {"earliest": str, "latest": str},
                "size_mb": float,
                "conversations": [
                    {
                        "uuid": str,
                        "path": str,
                        "title": str,
                        "created_at": str,
                        "message_count": int,
                        "has_attachments": bool,
                        "model": str,
                        "size_kb": float,
                    },
                    ...
                ],
                "by_year": {year: count},
                "by_month": {month: count},
                "errors": [{"path": str, "error": str}],
            }
        """
        conversations = []
        errors = []
        by_year = defaultdict(int)
        by_month = defaultdict(int)
        total_size_bytes = 0

        # Find all date directories
        date_dirs = sorted([d for d in self.transcript_dir.iterdir() if d.is_dir()])

        for date_dir in date_dirs:
            # Each directory is named YYYY-MM-DD
            for json_file in date_dir.glob("*.json"):
                try:
                    # Parse conversation
                    convo = self._parse_conversation(json_file)
                    conversations.append(convo)

                    # Track stats
                    created_date = convo["created_at"][:10]
                    year = created_date[:4]
                    month = created_date[:7]
                    by_year[year] += 1
                    by_month[month] += 1
                    total_size_bytes += json_file.stat().st_size

                except Exception as e:
                    errors.append({
                        "path": str(json_file),
                        "error": str(e),
                    })

        # Sort by date
        conversations.sort(key=lambda c: c["created_at"])

        # Build inventory
        return {
            "total_conversations": len(conversations),
            "total_date_dirs": len(date_dirs),
            "date_range": {
                "earliest": conversations[0]["created_at"][:10] if conversations else None,
                "latest": conversations[-1]["created_at"][:10] if conversations else None,
            },
            "size_mb": round(total_size_bytes / (1024 * 1024), 2),
            "conversations": conversations,
            "by_year": dict(by_year),
            "by_month": dict(by_month),
            "errors": errors,
        }

    def _parse_conversation(self, json_file: Path) -> Dict:
        """
        Parse a single conversation JSON file.

        Args:
            json_file: Path to .json file

        Returns:
            {
                "uuid": str,
                "path": str,
                "title": str,
                "created_at": str,
                "updated_at": str,
                "message_count": int,
                "has_attachments": bool,
                "model": str,
                "size_kb": float,
            }
        """
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = data.get("chat_messages", [])
        has_attachments = any(
            msg.get("attachments") for msg in messages
        )

        return {
            "uuid": data.get("uuid", ""),
            "path": str(json_file),
            "title": data.get("name", "Untitled"),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "message_count": len(messages),
            "has_attachments": has_attachments,
            "model": data.get("model", "unknown"),
            "size_kb": round(json_file.stat().st_size / 1024, 2),
        }

    def load_conversation(self, conversation_path: str) -> Dict:
        """
        Load full conversation data from path.

        Args:
            conversation_path: Path to conversation JSON file

        Returns:
            Full conversation dict with chat_messages
        """
        with open(conversation_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_conversation_summary(self, conversation: Dict, max_messages: int = 6) -> str:
        """
        Get a summary of conversation (first N + last N messages).

        Args:
            conversation: Full conversation dict
            max_messages: Total messages to include (first half + last half)

        Returns:
            Formatted summary string
        """
        messages = conversation.get("chat_messages", [])

        if len(messages) <= max_messages:
            # Show all messages
            selected = messages
        else:
            # Show first half + last half
            half = max_messages // 2
            selected = messages[:half] + messages[-half:]

        lines = []
        for msg in selected:
            sender = "Ahab" if msg.get("sender") == "human" else "Claude"
            text = msg.get("text", "")[:200]  # Truncate long messages
            lines.append(f"[{sender}] {text}")

        if len(messages) > max_messages:
            half = max_messages // 2
            lines.insert(half, f"... ({len(messages) - max_messages} messages omitted) ...")

        return "\n\n".join(lines)

    def export_inventory(self, inventory: Dict, output_path: str):
        """
        Export inventory to JSON file.

        Args:
            inventory: Result from scan()
            output_path: Where to save inventory.json
        """
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(inventory, f, indent=2)

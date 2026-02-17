#!/usr/bin/env python3
"""
Organize exported Claude.ai transcripts into the archive structure.

This script processes the JSON export from the browser console script
and creates organized transcript files by date.
"""

import json
import os
from pathlib import Path
from datetime import datetime
import re

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRANSCRIPT_DIR = PROJECT_ROOT / "Tools/MemoryMatrix_SandBox/_CLAUDE_TRANSCRIPTS"

def organize_transcripts():
    """Process exported JSON and create organized transcript files."""

    # Find the most recent export JSON file
    json_files = list(TRANSCRIPT_DIR.glob("claude_transcripts_*.json"))
    if not json_files:
        print("No exported transcript files found!")
        print(f"Looking in: {TRANSCRIPT_DIR}")
        print("\nPlease run the browser console script first to export conversations.")
        return

    latest_export = max(json_files, key=lambda p: p.stat().st_mtime)
    print(f"Processing: {latest_export.name}")
    print()

    # Load export data
    with open(latest_export) as f:
        export_data = json.load(f)

    conversations = export_data.get('conversations', {})
    print(f"Found {len(conversations)} conversations")
    print()

    # Organize by date
    by_date = {}

    for uuid, conv_data in conversations.items():
        metadata = conv_data.get('metadata', {})
        text = conv_data.get('text', '')
        raw = conv_data.get('raw', {})

        # Extract date from created_at
        created_at = metadata.get('created_at', '')
        if created_at:
            # Parse ISO timestamp
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
                time_str = dt.strftime('%H-%M-%S')
            except:
                date_str = 'unknown'
                time_str = '00-00-00'
        else:
            date_str = 'unknown'
            time_str = '00-00-00'

        # Create date directory
        date_dir = TRANSCRIPT_DIR / date_str
        date_dir.mkdir(exist_ok=True)

        # Sanitize conversation name for filename
        name = metadata.get('name', 'untitled')
        safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '-').lower()[:50]

        # Create transcript filename
        filename = f"{time_str}-{safe_name}.txt"
        filepath = date_dir / filename

        # Write transcript
        with open(filepath, 'w') as f:
            f.write(text)

        # Track by date
        if date_str not in by_date:
            by_date[date_str] = []
        by_date[date_str].append({
            'filename': filename,
            'name': name,
            'message_count': metadata.get('message_count', 0)
        })

        print(f"✓ {date_str}/{filename}")

    # Create journal/index
    journal_file = TRANSCRIPT_DIR / "journal.txt"
    with open(journal_file, 'w') as f:
        f.write("Claude.ai Conversation Archive\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Export Date: {export_data.get('timestamp', 'Unknown')}\n")
        f.write(f"Total Conversations: {export_data.get('total_conversations', 0)}\n")
        f.write(f"Successfully Exported: {export_data.get('successful', 0)}\n\n")

        for date_str in sorted(by_date.keys(), reverse=True):
            f.write(f"\n{date_str}\n")
            f.write("-" * 80 + "\n")
            for conv in by_date[date_str]:
                f.write(f"  - {conv['name']} ({conv['message_count']} messages)\n")
                f.write(f"    {conv['filename']}\n")

    print()
    print(f"✓ Created journal: {journal_file}")
    print()
    print("=" * 80)
    print(f"Archive organized in: {TRANSCRIPT_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    organize_transcripts()

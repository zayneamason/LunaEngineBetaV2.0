#!/usr/bin/env python3
"""
Fetch full conversation transcripts from Claude.ai using conversation UUIDs.

This script uses the Claude.ai web API to fetch conversation data.
Requires authentication cookies from an active Claude.ai session.
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import requests

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRANSCRIPT_DIR = PROJECT_ROOT / "Tools/MemoryMatrix_SandBox/_CLAUDE_TRANSCRIPTS"
CACHE_DIR = TRANSCRIPT_DIR / "cache"

def load_conversation_uuids():
    """Extract all conversation UUIDs from the exported LevelDB data."""
    import re

    uuids = set()

    # Load from localStorage
    local_storage_file = TRANSCRIPT_DIR / "localStorage_dump.json"
    if local_storage_file.exists():
        with open(local_storage_file) as f:
            data = json.load(f)
            for entry in data:
                key = entry.get('key', '')
                match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', key)
                if match and 'conversation' in key:
                    uuids.add(match.group(0))

    # Load from sessionStorage
    session_storage_file = TRANSCRIPT_DIR / "sessionStorage_dump.json"
    if session_storage_file.exists():
        with open(session_storage_file) as f:
            data = json.load(f)
            for entry in data:
                key = entry.get('key', '')
                if 'messages_last_timestamp_' in key:
                    match = re.search(r'messages_last_timestamp_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', key)
                    if match:
                        uuids.add(match.group(1))

    return sorted(uuids)

def get_session_cookies():
    """
    Extract Claude.ai session cookies from the browser/app.

    Note: This is a placeholder. You'll need to either:
    1. Manually copy your sessionKey cookie from Claude.ai
    2. Use a browser automation tool to extract cookies
    3. Use the Claude Desktop app's stored credentials
    """
    # Check for manually provided cookie
    cookie_file = SCRIPT_DIR / ".claude_session_cookie"
    if cookie_file.exists():
        return cookie_file.read_text().strip()

    print("ERROR: Session cookie not found!")
    print()
    print("To fetch conversation transcripts, you need to provide your Claude.ai session cookie.")
    print()
    print("Steps:")
    print("1. Open Claude.ai in your browser")
    print("2. Open Developer Tools (F12 or Cmd+Option+I)")
    print("3. Go to Application/Storage -> Cookies -> https://claude.ai")
    print("4. Copy the value of the 'sessionKey' cookie")
    print(f"5. Save it to: {cookie_file}")
    print()
    print("Then run this script again.")
    sys.exit(1)

def fetch_conversation(uuid, session_key):
    """Fetch a single conversation from Claude.ai API."""
    url = f"https://api.claude.ai/api/organizations//chat_conversations/{uuid}"

    headers = {
        "Cookie": f"sessionKey={session_key}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching conversation {uuid}: {e}")
        return None

def save_transcript(uuid, conversation_data):
    """Save conversation transcript to file."""
    if not conversation_data:
        return

    # Create cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Save raw JSON
    json_file = CACHE_DIR / f"{uuid}.json"
    with open(json_file, 'w') as f:
        json.dump(conversation_data, f, indent=2)

    # Extract and save as readable text
    text_file = CACHE_DIR / f"{uuid}.txt"
    with open(text_file, 'w') as f:
        # Write metadata
        name = conversation_data.get('name', 'Untitled')
        created_at = conversation_data.get('created_at', 'Unknown')
        updated_at = conversation_data.get('updated_at', 'Unknown')

        f.write(f"Conversation: {name}\n")
        f.write(f"UUID: {uuid}\n")
        f.write(f"Created: {created_at}\n")
        f.write(f"Updated: {updated_at}\n")
        f.write("=" * 80 + "\n\n")

        # Write messages
        for msg in conversation_data.get('chat_messages', []):
            sender = msg.get('sender', 'unknown')
            text = msg.get('text', '')
            timestamp = msg.get('created_at', '')

            f.write(f"[{sender.upper()}] {timestamp}\n")
            f.write(f"{text}\n\n")
            f.write("-" * 80 + "\n\n")

    print(f"Saved: {text_file.name}")

def main():
    print("Claude.ai Conversation Fetcher")
    print("=" * 80)
    print()

    # Load conversation UUIDs
    uuids = load_conversation_uuids()
    print(f"Found {len(uuids)} conversation UUIDs")
    print()

    # NOTE: This script requires a valid Claude.ai session cookie
    # For now, we'll document the UUIDs and provide instructions

    print("Conversation UUIDs found:")
    for i, uuid in enumerate(uuids, 1):
        print(f"  {i:2d}. {uuid}")
    print()

    # Save UUID list
    uuid_list_file = TRANSCRIPT_DIR / "conversation_uuids.json"
    with open(uuid_list_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'count': len(uuids),
            'uuids': uuids
        }, f, indent=2)
    print(f"Saved UUID list to: {uuid_list_file}")
    print()

    # Instructions for manual export
    print("=" * 80)
    print("NEXT STEPS:")
    print()
    print("Option 1: Manual Export (Recommended)")
    print("  1. Open Claude.ai in your browser")
    print("  2. Navigate to each conversation using URLs like:")
    print("     https://claude.ai/chat/<UUID>")
    print("  3. Use Claude's built-in export feature (if available)")
    print()
    print("Option 2: Automated Fetch (Advanced)")
    print("  1. Extract your Claude.ai session cookie (see instructions above)")
    print(f"  2. Save it to: {SCRIPT_DIR}/.claude_session_cookie")
    print("  3. Run this script again with --fetch flag")
    print()
    print("Option 3: Use Claude Code's Task Tool")
    print("  Ask Claude Code to help navigate and export each conversation")
    print("=" * 80)

if __name__ == "__main__":
    main()

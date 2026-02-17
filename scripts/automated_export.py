#!/usr/bin/env python3
"""
Automated Claude.ai conversation exporter using session cookie.
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import requests
from urllib.parse import quote

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
TRANSCRIPT_DIR = PROJECT_ROOT / "Tools/MemoryMatrix_SandBox/_CLAUDE_TRANSCRIPTS"
CONVERSATIONS_DIR = TRANSCRIPT_DIR / "Conversations"
COOKIE_FILE = SCRIPT_DIR / ".claude_session_cookie"

def get_session_key():
    """Get session key from file or prompt user."""
    if COOKIE_FILE.exists():
        return COOKIE_FILE.read_text().strip()

    print("=" * 80)
    print("CLAUDE.AI SESSION COOKIE NEEDED")
    print("=" * 80)
    print("\nTo export your conversations, I need your Claude.ai session cookie.")
    print("\nSteps:")
    print("1. Open https://claude.ai in your browser")
    print("2. Open Developer Tools:")
    print("   - Mac: Cmd+Option+I")
    print("   - Windows/Linux: F12")
    print("3. Go to: Application (or Storage) → Cookies → https://claude.ai")
    print("4. Find the 'sessionKey' cookie")
    print("5. Copy its VALUE (long string)")
    print("\nPaste it here (it will be saved securely):")

    session_key = input().strip()

    if not session_key:
        print("\nERROR: No session key provided!")
        sys.exit(1)

    # Save it
    COOKIE_FILE.write_text(session_key)
    COOKIE_FILE.chmod(0o600)  # Make it readable only by owner
    print(f"\n✓ Saved session key to: {COOKIE_FILE}")

    return session_key

def get_org_id(session_key):
    """Try to get organization ID."""
    headers = {
        'Cookie': f'sessionKey={session_key}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    }

    # Try to get from account endpoint
    try:
        response = requests.get('https://claude.ai/api/organizations', headers=headers, timeout=10)
        if response.ok:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0].get('uuid')
    except:
        pass

    return None

def fetch_all_conversations(session_key, org_id=None):
    """Fetch all conversation UUIDs with pagination."""
    headers = {
        'Cookie': f'sessionKey={session_key}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    all_conversations = []
    offset = 0
    limit = 50

    print("\nStep 1: Fetching complete conversation list...")

    while True:
        if org_id:
            url = f'https://claude.ai/api/organizations/{org_id}/chat_conversations?limit={limit}&offset={offset}'
        else:
            url = f'https://claude.ai/api/chat_conversations?limit={limit}&offset={offset}'

        try:
            print(f"  Fetching conversations {offset + 1} to {offset + limit}...")
            response = requests.get(url, headers=headers, timeout=30)

            if not response.ok:
                print(f"  ✗ HTTP {response.status_code}: {response.text[:200]}")
                break

            data = response.json()
            conversations = data if isinstance(data, list) else data.get('conversations', [])

            if not conversations:
                break

            all_conversations.extend(conversations)
            print(f"  ✓ Found {len(conversations)} conversations (total: {len(all_conversations)})")

            if len(conversations) < limit:
                break

            offset += limit
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"  ✗ Error: {e}")
            break

    return all_conversations

def fetch_conversation(uuid, session_key, org_id=None):
    """Fetch full conversation content."""
    headers = {
        'Cookie': f'sessionKey={session_key}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    if org_id:
        url = f'https://claude.ai/api/organizations/{org_id}/chat_conversations/{uuid}'
    else:
        url = f'https://claude.ai/api/chat_conversations/{uuid}'

    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"    Error: {e}")

    return None

def format_conversation_text(conv_data):
    """Format conversation as readable text."""
    lines = []
    lines.append(f"Conversation: {conv_data.get('name', 'Untitled')}")
    lines.append(f"UUID: {conv_data.get('uuid')}")
    lines.append(f"Created: {conv_data.get('created_at')}")
    lines.append(f"Updated: {conv_data.get('updated_at')}")
    if conv_data.get('is_starred'):
        lines.append("Starred: Yes")
    lines.append("=" * 80)
    lines.append("")

    for msg in conv_data.get('chat_messages', []):
        sender = msg.get('sender', 'unknown').upper()
        timestamp = msg.get('created_at', '')
        text = msg.get('text', '')

        lines.append(f"[{sender}] {timestamp}")
        lines.append(text)
        lines.append("")
        lines.append("-" * 80)
        lines.append("")

    return "\n".join(lines)

def sanitize_filename(name):
    """Create safe filename from conversation name."""
    import re
    safe = re.sub(r'[^\w\s-]', '', name).strip()
    safe = re.sub(r'[-\s]+', '-', safe)
    return safe[:50].lower()

def main():
    print("=" * 80)
    print("AUTOMATED CLAUDE.AI CONVERSATION EXPORTER")
    print("=" * 80)

    # Get session key
    session_key = get_session_key()

    # Try to get org ID
    print("\nFetching organization info...")
    org_id = get_org_id(session_key)
    if org_id:
        print(f"✓ Organization ID: {org_id}")
    else:
        print("⚠ Could not fetch org ID (will try without it)")

    # Fetch all conversations
    conversations = fetch_all_conversations(session_key, org_id)

    if not conversations:
        print("\n✗ No conversations found! Check your session key.")
        print("\nTo get a new session key:")
        print(f"  rm {COOKIE_FILE}")
        print("  Then run this script again")
        sys.exit(1)

    print(f"\n✓ Found {len(conversations)} total conversations!")

    # Stats
    named = len([c for c in conversations if c.get('name')])
    starred = len([c for c in conversations if c.get('is_starred')])
    print(f"\nStats:")
    print(f"  Total: {len(conversations)}")
    print(f"  Named: {named}")
    print(f"  Starred: {starred}")

    # Create output directory
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch each conversation
    print("\n" + "=" * 80)
    print("Step 2: Fetching full content for each conversation...")
    print("=" * 80 + "\n")

    success = 0
    failed = 0

    for i, conv in enumerate(conversations):
        uuid = conv.get('uuid')
        name = conv.get('name', 'Untitled')
        created = conv.get('created_at', '')

        print(f"[{i + 1}/{len(conversations)}] {name[:50]}...")

        # Fetch full data
        full_data = fetch_conversation(uuid, session_key, org_id)

        if full_data:
            # Get date for organization
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                date_str = dt.strftime('%Y-%m-%d')
                time_str = dt.strftime('%H-%M-%S')
            except:
                date_str = 'unknown'
                time_str = '00-00-00'

            # Create date directory
            date_dir = CONVERSATIONS_DIR / date_str
            date_dir.mkdir(exist_ok=True)

            # Save as text
            safe_name = sanitize_filename(name) or 'untitled'
            filename = f"{time_str}-{safe_name}.txt"
            filepath = date_dir / filename

            text = format_conversation_text(full_data)
            filepath.write_text(text)

            # Also save raw JSON
            json_file = date_dir / f"{time_str}-{safe_name}.json"
            json_file.write_text(json.dumps(full_data, indent=2))

            msg_count = len(full_data.get('chat_messages', []))
            print(f"  ✓ {msg_count} messages → {date_str}/{filename}")
            success += 1
        else:
            print(f"  ✗ Failed to fetch")
            failed += 1

        # Rate limiting
        if i < len(conversations) - 1:
            time.sleep(0.5)

        # Progress update
        if (i + 1) % 10 == 0:
            print(f"\n--- Progress: {i + 1}/{len(conversations)} ({round((i + 1) / len(conversations) * 100)}%) ---\n")

    # Summary
    print("\n" + "=" * 80)
    print("EXPORT COMPLETE!")
    print("=" * 80)
    print(f"\nResults:")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(conversations)}")
    print(f"\nOutput: {CONVERSATIONS_DIR}")
    print("\nOrganized by date:")

    for date_dir in sorted(CONVERSATIONS_DIR.iterdir()):
        if date_dir.is_dir():
            count = len(list(date_dir.glob('*.txt')))
            print(f"  {date_dir.name}/  ({count} conversations)")

    print("\n✓ All conversations saved!")

if __name__ == "__main__":
    main()

# Claude.ai Conversation Archive

This directory contains exported conversation transcripts from Claude.ai.

## Current Status

✅ **Extracted 33 conversation UUIDs** from Claude Desktop app storage (LocalStorage + SessionStorage)

📋 **UUID List:** [conversation_uuids.json](conversation_uuids.json)

## How to Export Full Transcripts

### Method 1: Browser Console Script (Recommended)

1. Open https://claude.ai in your browser
2. Open Developer Console:
   - **Mac:** `Cmd + Option + J`
   - **Windows/Linux:** `F12` or `Ctrl + Shift + J`
3. Copy and paste the entire contents of [export_conversations.js](export_conversations.js)
4. Press Enter to run the script
5. The script will:
   - Fetch all 33 conversations via Claude.ai API
   - Download a JSON file with all transcripts
   - Show progress in the console

6. Move the downloaded `claude_transcripts_YYYY-MM-DD.json` file to this directory

7. Run the organizer script:
   ```bash
   cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
   python3 scripts/organize_transcripts.py
   ```

8. Transcripts will be organized by date:
   ```
   _CLAUDE_TRANSCRIPTS/
   ├── 2026-02-09/
   │   ├── 12-40-33-luna-memory-architecture.txt
   │   ├── 12-41-56-luna-memory-provenance.txt
   │   └── ...
   ├── 2026-02-08/
   │   └── ...
   ├── journal.txt (master index)
   └── README.md (this file)
   ```

### Method 2: Manual Export Per Conversation

For each UUID in [conversation_uuids.json](conversation_uuids.json):

1. Navigate to: `https://claude.ai/chat/<UUID>`
2. Look for export/download option in Claude.ai UI
3. Save transcript to appropriate date directory

## Conversation UUIDs Found

### From LocalStorage (14 conversations)
These appear to be draft/active conversations with attachments and files.

### From SessionStorage (19 conversations)
These have recent messages and appear to be active or recently accessed chats.

**Total: 33 unique conversations**

Full list available in [conversation_uuids.json](conversation_uuids.json)

## Files in This Directory

- `README.md` - This file
- `conversation_uuids.json` - List of all found conversation IDs
- `export_conversations.js` - Browser console script to export all conversations
- `localStorage_dump.json` - Raw LevelDB data from Claude Desktop LocalStorage
- `sessionStorage_dump.json` - Raw LevelDB data from Claude Desktop SessionStorage
- `extraction_summary.json` - Summary of database extraction
- `journal.txt` - (Generated) Master index of all transcripts
- `YYYY-MM-DD/` - (Generated) Transcript directories organized by date

## Archive Structure (After Export)

```
_CLAUDE_TRANSCRIPTS/
├── 2026-02-09/           # Organized by conversation creation date
│   ├── HH-MM-SS-conversation-name.txt
│   ├── HH-MM-SS-conversation-name.txt
│   └── ...
├── 2026-02-08/
│   └── ...
├── cache/                # Raw JSON data from API
│   ├── <uuid>.json
│   └── <uuid>.txt
├── conversation_uuids.json
├── journal.txt           # Master index with all conversations
├── README.md
└── export_conversations.js
```

## Notes

- UUIDs extracted from Claude Desktop app's LevelDB storage (accessed while app was closed)
- Full conversation content requires API access via browser session
- Browser console script uses your authenticated session (requires being logged into Claude.ai)
- Export process is rate-limited to avoid API throttling (500ms between requests)

## What These Conversations Contain

Based on the handoff document, expected topics include:
- **Luna Engine v2.0** development (Memory Matrix, graph pipeline, actor runtime)
- **Observatory tool** (MCP integration, graph visualization)
- **KOZMO × Eden** (creative studio IDE prototype)
- **Nexus** (project management with confidence scoring)
- **Mars College 2026** (sovereignty requirements, hardware decisions)
- **Memory preservation philosophy** ("hangover metaphor", texture vs facts)
- **Personality system** (DNA/Experience/Mood layers)
- **AI-BRARIAN pipeline** (Ben the Scribe, The Dude, separation principle)

All context critical for Luna's memory system and development history.

## Next Steps

1. Run the browser console export script
2. Organize transcripts by date
3. (Optional) Set up automated backup script for future conversations
4. (Optional) Index transcripts in Luna's Memory Matrix for semantic search

---

**Created:** 2026-02-09
**Last Updated:** 2026-02-09
**Status:** Ready for export (UUIDs extracted, scripts prepared)

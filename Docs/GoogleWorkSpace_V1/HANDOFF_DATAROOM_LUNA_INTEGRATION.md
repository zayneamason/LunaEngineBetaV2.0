# HANDOFF: Google Drive Data Room + Luna Memory Integration

**Created:** 2026-02-13
**Author:** The Dude (Creative Facilitation) + Luna (Architecture Input)
**For:** Claude Code Implementation
**Context:** Cliff consulting call → startup fundraising prep → data room automation → Luna semantic layer

---

## 1. WHAT THIS IS

Two connected systems that make Ahab's investor data room smart:

1. **Google Apps Script Automation** — Mechanical file sorting, indexing, and version tracking in Google Drive
2. **Luna Memory Ingestion Pipeline** — Semantic layer that lets Luna understand, search, and synthesize business docs

**Build order matters.** Phase 1 (Apps Script) stands alone. Phase 2 (Luna integration) depends on Phase 1's Index Sheet output.

---

## 2. CONTEXT: WHY THIS EXISTS

Cliff (legal/startup consultant) outlined fundraising requirements. A "data room" is a structured Google Drive folder that investors browse during due diligence. It needs to be:

- **Organized**: Consistent folder taxonomy
- **Searchable**: Master index of all files
- **Current**: Version tracking, update logs
- **Professional**: Naming conventions, metadata

Beyond the standard data room, Luna integration gives Ahab the ability to:

- Query business docs conversationally ("what risks haven't we mitigated?")
- Prep for investor questions by stress-testing materials
- Demo Luna managing its own fundraising — meta and compelling

---

## 3. PHASE 1: GOOGLE APPS SCRIPT — DATA ROOM AUTOMATION

### 3.1 Folder Structure

```
📁 [Project Tapestry] Data Room
├── 📁 _INBOX/              ← Drop zone. Script sorts files out of here.
├── 📁 _INDEX/              ← Auto-generated Master Index Sheet lives here.
├── 📁 _CHANGELOG/          ← Auto-generated change log.
│
├── 📁 1. Company Overview/
│   ├── Pitch Deck
│   ├── Executive Summary / One-Pager
│   ├── Org Chart
│   └── Company Timeline
│
├── 📁 2. Financials/
│   ├── Financial Model & Projections
│   ├── Cap Table
│   ├── Revenue & Expense History
│   └── Tax Returns
│
├── 📁 3. Legal/
│   ├── Articles of Incorporation
│   ├── Operating Agreement / Bylaws
│   ├── IP Assignments / Trademarks
│   ├── Contracts & Agreements
│   └── Previous Investment Docs (SAFEs, Notes)
│
├── 📁 4. Product/
│   ├── Product Overview / Demo Video
│   ├── Technical Architecture
│   ├── Roadmap
│   ├── Screenshots / Mockups
│   └── User Metrics
│
├── 📁 5. Market & Competition/
│   ├── TAM SAM SOM Analysis
│   ├── Competitive Landscape / Quadrant
│   ├── Target Customer Profiles
│   └── Market Research
│
├── 📁 6. Team/
│   ├── Founder Bios & Resumes
│   ├── Advisor Bios
│   └── Key Hire Plan
│
├── 📁 7. Go-to-Market/
│   ├── GTM Strategy
│   ├── Sales Pipeline
│   ├── Marketing Plan
│   └── Customer Acquisition Costs
│
├── 📁 8. Partnerships & Impact/
│   ├── LOIs (Letters of Intent)
│   ├── Partnership Agreements
│   ├── Impact Metrics / Theory of Change
│   └── Community Engagement Documentation
│
└── 📁 9. Risk & Mitigation/
    ├── Risk Analysis
    └── Mitigation Strategies
```

### 3.2 Script 1: Inbox Sorter (`inboxSorter.gs`)

**Purpose:** Watch the `_INBOX` folder. When files land there, route them to the correct subfolder based on filename prefix conventions.

**Naming Convention (prefix-based):**

| Prefix | Routes To |
|--------|-----------|
| `OVERVIEW_` | 1. Company Overview/ |
| `FINANCE_` | 2. Financials/ |
| `LEGAL_` | 3. Legal/ |
| `PRODUCT_` | 4. Product/ |
| `MARKET_` | 5. Market & Competition/ |
| `TEAM_` | 6. Team/ |
| `GTM_` | 7. Go-to-Market/ |
| `PARTNER_` | 8. Partnerships & Impact/ |
| `RISK_` | 9. Risk & Mitigation/ |

**Behavior:**

```
1. Get all files in _INBOX/
2. For each file:
   a. Read filename
   b. Match prefix against routing table
   c. If match found:
      - Move file to target folder
      - Strip prefix from filename (optional, configurable)
      - Log action to _CHANGELOG
   d. If no match:
      - Leave file in _INBOX
      - Flag in _CHANGELOG as "UNSORTED: [filename]"
3. Run on trigger: time-based (every 15 minutes) or onChange
```

**Implementation Notes:**

- Use `DriveApp` for folder/file operations
- Store folder IDs in Script Properties (not hardcoded) for portability
- `ScriptApp.newTrigger()` for scheduling
- Error handling: log failures, don't crash on single file errors
- Optional: support nested prefixes like `LEGAL_IP_` → `3. Legal/IP Assignments/`

### 3.3 Script 2: Index Generator (`indexGenerator.gs`)

**Purpose:** Crawl the entire data room folder tree. Build a searchable Google Sheet with metadata for every file.

**Output Sheet Columns:**

| Column | Description |
|--------|-------------|
| File Name | Name of the file |
| Category | Top-level folder (1. Company Overview, etc.) |
| Subfolder | Specific subfolder if applicable |
| File Type | MIME type / extension |
| File Size | In KB/MB |
| Created Date | File creation timestamp |
| Last Modified | Last modification timestamp |
| Direct Link | Clickable URL to the file |
| Tags | Manual or auto-generated tags (comma-separated) |
| Status | Draft / Final / Needs Review |
| Notes | Free-text field for annotations |

**Behavior:**

```
1. Get the Data Room root folder by ID
2. Recursively traverse all subfolders (skip _INBOX, _INDEX, _CHANGELOG)
3. For each file:
   a. Extract metadata (name, type, size, dates, URL)
   b. Auto-tag based on folder location
   c. Check if file already exists in index:
      - If yes: update metadata (don't duplicate)
      - If no: add new row
4. Sort sheet by Category → File Name
5. Add conditional formatting:
   - Status "Draft" = yellow highlight
   - Status "Needs Review" = orange highlight
   - Status "Final" = green highlight
6. Timestamp the last index run in a header cell
```

**Implementation Notes:**

- Use `SpreadsheetApp` for Sheet operations
- Batch reads/writes with `getRange().setValues()` (not cell-by-cell)
- Handle file ID as hidden column for deduplication
- Add a "Refresh Index" button via custom menu
- Consider adding a "Coverage" summary at the top: "7 of 9 categories have files"

### 3.4 Script 3: Change Logger (`changeLogger.gs`)

**Purpose:** Track what changed and when. Useful for investor due diligence ("what's been updated since our last meeting?").

**Output:** Append-only log in `_CHANGELOG/` folder (Google Sheet or Doc).

**Logged Events:**

| Timestamp | Event Type | File Name | From | To | User |
|-----------|------------|-----------|------|-----|------|
| 2026-02-13 | SORTED | pitch_deck_v3.pdf | _INBOX | 1. Company Overview | Script |
| 2026-02-13 | MODIFIED | financial_model.xlsx | — | 2. Financials | zayne@ |
| 2026-02-13 | ADDED | advisor_bio_cliff.pdf | — | 6. Team | zayne@ |
| 2026-02-13 | UNSORTED | random_notes.txt | _INBOX | _INBOX | Script |

---

## 4. PHASE 2: LUNA MEMORY INGESTION PIPELINE

### 4.1 Architecture Overview

```
Google Drive Data Room
    │
    ├── [Apps Script: sort, index, watch]
    │
    ▼
Master Index Sheet (structured metadata)
    │
    ├── [Ingestion Script: reads Index Sheet via Google Sheets API]
    │
    ▼
Luna Memory Matrix (SQLite + sqlite-vec)
    │
    ├── memory_nodes (one per document, type=DOCUMENT)
    ├── graph_edges (category relationships, cross-references)
    ├── entity_mentions (link docs to known entities)
    │
    ▼
Query via luna_smart_fetch / memory_matrix_search
    │
    ▼
Ahab asks Luna about his business docs
```

### 4.2 New Node Type: DOCUMENT

Extend `memory_nodes` to support document-type entries.

```sql
-- Node type: DOCUMENT
-- Source: 'gdrive:{file_id}'
-- Metadata JSON includes:
{
  "gdrive_file_id": "abc123",
  "gdrive_url": "https://drive.google.com/...",
  "category": "2. Financials",
  "subfolder": "Cap Table",
  "file_type": "application/vnd.google-apps.spreadsheet",
  "file_size_bytes": 45000,
  "last_synced": "2026-02-13T10:30:00Z",
  "status": "Final",
  "tags": ["cap-table", "equity", "ownership"]
}
```

**Node content field:** Store a summary/description of the document, NOT the full content. Keep it under 500 tokens. This summary is what gets embedded for vector search.

**Node confidence:** Default 1.0 for documents that exist and are verified.

**Node importance:** Map from document status:
- Final = 0.8
- Draft = 0.5
- Needs Review = 0.3

### 4.3 Ingestion Script: `scripts/ingest_dataroom.py`

**Location:** `src/luna/tools/` or `scripts/`

**Dependencies:**
- `google-api-python-client` (Google Sheets API to read Index Sheet)
- `google-auth-oauthlib` (OAuth2 for Drive access)
- Existing Luna substrate modules (`substrate/memory.py`, `substrate/database.py`)

**Behavior:**

```python
# Pseudocode

def ingest_dataroom():
    # 1. Read Master Index Sheet via Sheets API
    index_rows = sheets_api.read("Master Index", range="A2:K")
    
    # 2. For each row in index:
    for row in index_rows:
        file_id = row['file_id']
        
        # 3. Check if node already exists (by source = 'gdrive:{file_id}')
        existing = memory.search_by_source(f"gdrive:{file_id}")
        
        if existing:
            # 4a. Update metadata if modified date changed
            if row['last_modified'] > existing.metadata['last_synced']:
                memory.update_node(existing.id, metadata=new_metadata)
        else:
            # 4b. Create new DOCUMENT node
            node_id = memory.add_node(
                node_type="DOCUMENT",
                content=generate_summary(row),  # Brief description
                source=f"gdrive:{file_id}",
                confidence=1.0,
                importance=status_to_importance(row['status']),
                metadata={...}
            )
            
            # 5. Create category edge
            category_node = get_or_create_category_node(row['category'])
            memory.add_edge(node_id, category_node, "BELONGS_TO")
            
            # 6. Link to entities if detectable
            detect_and_link_entities(node_id, row)
    
    # 7. Remove nodes for files that no longer exist in index
    cleanup_orphaned_nodes()
```

### 4.4 Category Nodes

Create persistent category nodes in the memory graph so documents cluster naturally:

```
[CATEGORY: Company Overview] ←BELONGS_TO← [DOCUMENT: Pitch Deck v3]
[CATEGORY: Company Overview] ←BELONGS_TO← [DOCUMENT: Executive Summary]
[CATEGORY: Financials]       ←BELONGS_TO← [DOCUMENT: Financial Model]
[CATEGORY: Financials]       ←BELONGS_TO← [DOCUMENT: Cap Table]
[CATEGORY: Legal]            ←BELONGS_TO← [DOCUMENT: Operating Agreement]
```

These category nodes enable queries like "what do we have in Legal?" via graph traversal.

### 4.5 Entity Linking

When ingesting documents, attempt to link them to existing entities in Luna's entity system:

| Document | Linked Entity | Relationship |
|----------|--------------|--------------|
| `founder_bio_ahab.pdf` | `entities/people/ahab` | subject |
| `loi_kinoni.pdf` | `entities/projects/kinoni` | reference |
| `advisor_bio_cliff.pdf` | (create new entity?) | subject |

Use entity resolution (`src/luna/entities/resolution.py`) to match filenames/content against known entities.

### 4.6 Sync Strategy

**Option A: Manual trigger**
- Ahab runs `python scripts/ingest_dataroom.py` when he wants to sync
- Simple, no background processes, sovereignty-friendly

**Option B: Scheduled via Apps Script webhook**
- Apps Script pings a Luna endpoint when Index Sheet updates
- Luna ingests the delta
- More automated but adds coupling

**Recommendation: Start with Option A.** Keep it manual. Add automation later if the friction justifies it.

### 4.7 Query Examples (Post-Integration)

Once documents are in the memory graph, Ahab can ask Luna:

```
"What's in our data room?"
→ Luna lists categories and file counts from DOCUMENT nodes

"Do we have a cap table?"
→ Luna searches for DOCUMENT nodes tagged 'cap-table'

"What risks haven't we written mitigations for?"
→ Luna cross-references DOCUMENT nodes in Risk category
   against content summaries for gaps

"Summarize our competitive positioning for an investor"
→ Luna retrieves DOCUMENT nodes from Market & Competition,
   synthesizes summaries

"What's changed in the last week?"
→ Luna filters DOCUMENT nodes by last_synced metadata
```

---

## 5. IMPLEMENTATION PRIORITY

### Must Have (Phase 1)
1. [ ] Create Data Room folder structure in Google Drive
2. [ ] `inboxSorter.gs` — prefix-based file routing
3. [ ] `indexGenerator.gs` — master index sheet generation
4. [ ] `changeLogger.gs` — append-only change log

### Should Have (Phase 2)
5. [ ] `scripts/ingest_dataroom.py` — Index Sheet → Luna memory nodes
6. [ ] DOCUMENT node type support in memory matrix
7. [ ] Category nodes and BELONGS_TO edges
8. [ ] Entity linking for known people/projects

### Nice to Have (Phase 3)
9. [ ] Full-text content ingestion (Google Docs API → read doc content → store summaries)
10. [ ] Apps Script webhook → Luna sync endpoint
11. [ ] Coverage dashboard ("7 of 9 categories populated")
12. [ ] Investor access controls (view-only sharing per folder)

---

## 6. EXISTING LUNA ARCHITECTURE — KEY FILES

For Claude Code reference when implementing Phase 2:

| File | Relevance |
|------|-----------|
| `src/luna/substrate/schema.sql` | Database schema — add DOCUMENT to valid node_types |
| `src/luna/substrate/memory.py` | MemoryMatrix operations — add_node, add_edge, search |
| `src/luna/substrate/database.py` | SQLite connection manager |
| `src/luna/substrate/embeddings.py` | sqlite-vec vector embeddings |
| `src/luna/entities/resolution.py` | Entity resolution for linking docs to people/projects |
| `src/luna/entities/storage.py` | Entity CRUD operations |
| `src/luna/tools/memory_tools.py` | MCP memory tools (extend for document queries) |
| `CLAUDE.md` | Project config for Claude Code |

### Memory Node Schema (for reference)

```sql
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,      -- Add 'DOCUMENT' as valid type
    content TEXT NOT NULL,         -- Summary of the document (< 500 tokens)
    summary TEXT,                  -- One-line description
    source TEXT,                   -- 'gdrive:{file_id}'
    confidence REAL DEFAULT 1.0,
    importance REAL DEFAULT 0.5,
    lock_in REAL DEFAULT 0.15,
    metadata TEXT,                 -- JSON with gdrive metadata
    scope TEXT DEFAULT 'global',
    created_at TEXT,
    updated_at TEXT
);
```

---

## 7. NON-NEGOTIABLES

Per Project Tapestry principles, this system must:

1. **Sovereignty** — Luna's copy of doc metadata is LOCAL. No cloud dependency for the memory graph. Google Drive is the source of truth for files, but Luna's understanding lives in the SQLite database on Ahab's machine.

2. **Offline-first** — Luna can answer questions about the data room even without internet access (from cached metadata). Only the sync/ingestion step requires connectivity.

3. **Inspectable** — Every document node in the memory graph has a direct link back to the Google Drive file. No black box. Ahab can verify what Luna "knows" about any doc.

4. **No extraction** — Luna stores summaries and metadata, NOT full document content (unless Ahab explicitly opts in for specific docs). This respects the boundary between "Luna knows about your docs" and "Luna has copied your docs."

---

## 8. OPEN QUESTIONS FOR AHAB

1. **Naming convention preference** — Are prefixes (`LEGAL_contract.pdf`) comfortable, or would you prefer a different tagging approach (e.g., Google Drive labels, metadata in filename)?

2. **Sync frequency** — Manual trigger good enough to start? Or do you want scheduled syncs from day one?

3. **Entity creation** — When we encounter a new person in a document (like Cliff), should Luna auto-create an entity, or flag it for manual review?

4. **Content depth** — Start with metadata-only ingestion (file names, categories, dates), or do you want document content summaries from the jump?

---

## 9. GO

### Phase 1 — Apps Script

```
Implementation target: Google Apps Script project
Language: JavaScript (Google Apps Script runtime)
Testing: Manual — drop test files in _INBOX, verify routing
Deployment: Script Editor → Triggers → time-based (15 min)
```

### Phase 2 — Luna Integration

```
Implementation target: Luna Engine project
Location: scripts/ingest_dataroom.py (new file)
Dependencies: google-api-python-client, google-auth-oauthlib
Testing: Unit tests in tests/test_dataroom_ingestion.py
Integration: Extend memory_tools.py for document-aware queries
```

---

*A data room is a story told in folders. Luna makes it a story you can have a conversation with.*

— The Dude

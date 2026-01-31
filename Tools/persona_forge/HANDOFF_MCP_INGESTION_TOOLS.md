# HANDOFF: Persona Forge MCP Ingestion Tools

## Mission

Extend the existing Persona Forge MCP server with tools that enable Claude (Desktop/Code) to perform LLM-assisted ingestion of raw training data sources.

**The Goal:** Claude reads messy source files, extracts training examples using its own intelligence, and feeds them back into the Forge.

---

## Context

### Existing MCP Server
**Location:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/src/persona_forge/mcp/server.py`

**Already Has:**
- `forge_load(path)` - Load JSONL files
- `forge_assay()` - Analyze dataset
- `forge_gaps()` - Show coverage gaps
- `forge_mint(interaction_type, count)` - Generate synthetic examples
- `forge_export(output_path, train_split)` - Export to JSONL
- `forge_status()` - Session state
- Character management tools
- Voight-Kampff tools

**Missing:** Tools for Claude to read raw sources and add individual examples.

### Data Sources to Ingest
See: `TRAINING_DATA_SOURCES.md` in this directory.

Priority sources:
1. Session transcripts (markdown with Turn structure)
2. Alpha session notes (narrative markdown)
3. Memory Matrix nodes (SQLite)
4. Conversation turns (SQLite)
5. Insights (markdown)

---

## New Tools to Add

### 1. `forge_list_sources`

```python
@mcp.tool()
def forge_list_sources(directory: str, pattern: str = "*") -> dict[str, Any]:
    """
    List available source files for ingestion.
    
    Args:
        directory: Path to directory containing source files
        pattern: Glob pattern to filter files (default: "*")
    
    Returns:
        Dictionary with:
        - files: List of {path, name, size_kb, modified, format}
        - total_files: Count
        - total_size_kb: Combined size
        - formats: Detected formats (markdown, jsonl, sqlite, etc.)
    """
```

**Implementation Notes:**
- Support both absolute paths and paths relative to project root
- Detect format from extension (.md, .jsonl, .json, .db)
- Sort by modified date descending (most recent first)
- Include file size for planning

---

### 2. `forge_read_raw`

```python
@mcp.tool()
def forge_read_raw(
    path: str, 
    max_chars: int = 50000,
    offset: int = 0
) -> dict[str, Any]:
    """
    Read raw content from a source file.
    
    Args:
        path: Path to file (absolute or relative to project root)
        max_chars: Maximum characters to return (default: 50000)
        offset: Character offset to start reading from (for pagination)
    
    Returns:
        Dictionary with:
        - content: Raw file content (truncated if needed)
        - format: Detected format (markdown, jsonl, etc.)
        - size_chars: Total file size in characters
        - truncated: Whether content was truncated
        - has_more: Whether there's more content after this chunk
        - metadata: Any detected metadata (frontmatter, etc.)
    """
```

**Implementation Notes:**
- Parse YAML frontmatter from markdown files
- For SQLite files, return schema info instead of raw content
- Handle encoding gracefully (UTF-8 with fallback)
- Return `has_more` flag for large files

---

### 3. `forge_add_example`

```python
@mcp.tool()
def forge_add_example(
    user_message: str,
    assistant_response: str,
    interaction_type: str = "short_exchange",
    source_file: str = None,
    source_type: str = "synthetic",
    confidence: float = 1.0,
    tags: list[str] = None,
    context: str = None
) -> dict[str, Any]:
    """
    Add a single training example to the working set.
    
    This is the primary tool for LLM-assisted ingestion. Claude extracts
    examples from raw sources and feeds them back through this tool.
    
    Args:
        user_message: The user/human side of the exchange
        assistant_response: Luna's response
        interaction_type: One of: greeting, acknowledgment, short_exchange,
                         context_recall, emotional_presence, delegation_trigger,
                         reflection, technical, humor, pushback
        source_file: Original file this was extracted from
        source_type: One of: journal, session, matrix, insight, synthetic, manual
        confidence: Extraction confidence (0.0-1.0), used for filtering
        tags: Optional tags for categorization
        context: Optional context about what was happening
    
    Returns:
        Dictionary with:
        - success: bool
        - id: Generated example ID
        - lock_in: Computed lock-in coefficient
        - tier: Quality tier (gold/silver/bronze)
        - voice_markers: Detected voice markers
        - anti_patterns: Detected anti-patterns (if any)
        - warnings: Any quality warnings
    """
```

**Implementation Notes:**
- Run through existing Crucible voice detection
- Run through Locksmith for lock-in scoring
- Store confidence for later filtering
- Return warnings if anti-patterns detected
- Add to `_state["examples"]` list
- Invalidate cached assay

---

### 4. `forge_add_batch`

```python
@mcp.tool()
def forge_add_batch(examples: list[dict]) -> dict[str, Any]:
    """
    Add multiple training examples at once.
    
    More efficient than calling forge_add_example repeatedly.
    
    Args:
        examples: List of example dictionaries, each with:
                  - user_message (required)
                  - assistant_response (required)
                  - interaction_type (optional)
                  - source_file (optional)
                  - source_type (optional)
                  - confidence (optional)
                  - tags (optional)
    
    Returns:
        Dictionary with:
        - success: bool
        - added: Number successfully added
        - rejected: Number rejected (with reasons)
        - warnings: Aggregate warnings
        - quality_summary: {gold: N, silver: N, bronze: N}
    """
```

**Implementation Notes:**
- Process all examples through Crucible/Locksmith
- Collect all warnings/rejections
- Return summary statistics

---

### 5. `forge_search`

```python
@mcp.tool()
def forge_search(
    query: str, 
    field: str = "all",
    limit: int = 10
) -> dict[str, Any]:
    """
    Search existing examples for deduplication.
    
    Args:
        query: Search string
        field: Field to search: "all", "user", "assistant", "source"
        limit: Maximum results to return
    
    Returns:
        Dictionary with:
        - matches: List of matching examples (id, preview, similarity)
        - total_matches: Total count
    """
```

**Implementation Notes:**
- Simple substring search for now
- Return preview (first 100 chars) of each match
- Used to avoid adding duplicates

---

### 6. `forge_read_matrix`

```python
@mcp.tool()
def forge_read_matrix(
    db_path: str,
    node_types: list[str] = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    """
    Read memory nodes from the Memory Matrix database.
    
    Args:
        db_path: Path to SQLite database
        node_types: Filter by node types (QUESTION, OBSERVATION, etc.)
                   If None, returns all types
        limit: Maximum nodes to return
        offset: Pagination offset
    
    Returns:
        Dictionary with:
        - nodes: List of {id, type, content, created_at, tags}
        - total_count: Total matching nodes
        - has_more: Whether there are more results
        - type_counts: {QUESTION: N, OBSERVATION: N, ...}
    """
```

**Implementation Notes:**
- Connect to SQLite database
- Query `memory_nodes` table
- Return structured data Claude can process
- Include type counts for planning

---

### 7. `forge_read_turns`

```python
@mcp.tool()
def forge_read_turns(
    db_path: str,
    session_id: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict[str, Any]:
    """
    Read conversation turns from the database.
    
    Returns user/assistant turn pairs ready for training extraction.
    These are GOLD quality - real Luna ↔ Ahab exchanges.
    
    Args:
        db_path: Path to SQLite database
        session_id: Filter to specific session (optional)
                   If None, returns turns from all sessions
        limit: Maximum turns to return
        offset: Pagination offset
    
    Returns:
        Dictionary with:
        - turns: List of {session_id, role, content, created_at}
        - sessions: List of unique session IDs in results
        - total_count: Total matching turns
        - has_more: Whether there are more results
        - session_counts: {session_id: turn_count, ...}
    """
```

**Implementation Notes:**
- Connect to SQLite database
- Query `conversation_turns` table
- Order by session_id, created_at for proper sequencing
- Returns raw turns - Claude pairs user/assistant for training
- 456 turns across 63 sessions available (Jan 20-29, 2026)

---

## Implementation Order

### Phase 1: Core Read Tools
1. `forge_list_sources` - List what's available
2. `forge_read_raw` - Read file content
3. `forge_add_example` - Add single example

**Validation:** Claude can list files, read one, extract an example, add it.

### Phase 2: Efficiency Tools
4. `forge_add_batch` - Bulk add
5. `forge_search` - Deduplication

**Validation:** Claude can process multiple files efficiently.

### Phase 3: Matrix Integration
6. `forge_read_matrix` - Read Memory Matrix nodes
7. `forge_read_turns` - Read conversation turns (GOLD)

**Validation:** Claude can extract from SQLite sources (both tables).

---

## File Modifications

### Primary File
`/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/persona_forge/src/persona_forge/mcp/server.py`

### Add After Line ~290 (after `forge_status`)

```python
# =============================================================================
# Ingestion Tools (LLM-Assisted)
# =============================================================================

@mcp.tool()
def forge_list_sources(...):
    ...

@mcp.tool()
def forge_read_raw(...):
    ...

# etc.
```

### Update Imports (if needed)

```python
import sqlite3  # For forge_read_matrix
import yaml     # For frontmatter parsing (or use existing)
```

---

## Test Data Paths

Use these for validation:

```python
# Session transcripts (markdown with turns)
SESSION_TRANSCRIPTS = "/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memories/session/"

# Alpha session notes (narrative markdown)  
ALPHA_NOTES = "/Users/zayneamason/_HeyLuna_BETA/Alpha_ProjectFiles/03_Session_Notes/sessions/"

# Memory Matrix database
MEMORY_MATRIX_DB = "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db"

# Existing JSONL (for comparison)
EXISTING_JSONL = "/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/training_data/luna_dataset_train.jsonl"
```

---

## Validation Criteria

### Phase 1 Complete When:
```
✓ forge_list_sources("/Alpha_ProjectFiles/03_Session_Notes/sessions/") 
  returns list of 76 markdown files

✓ forge_read_raw("2025-11-29_Luna_Debugs_Her_Own_Nervous_System.md")
  returns markdown content with metadata

✓ forge_add_example(
    user_message="Show me what you're seeing.",
    assistant_response="Okay so here's the thing...",
    interaction_type="technical",
    source_file="2025-11-29_Luna_Debugs_Her_Own_Nervous_System.md"
  )
  returns {success: true, lock_in: 0.7+, tier: "silver" or "gold"}

✓ forge_status() shows example count increased by 1

✓ forge_assay() includes the new example in analysis
```

### Phase 2 Complete When:
```
✓ forge_add_batch([...5 examples...]) adds all 5

✓ forge_search("hey luna") finds greeting examples

✓ No duplicates when same content added twice
```

### Phase 3 Complete When:
```
✓ forge_read_matrix(db_path, node_types=["QUESTION"], limit=10)
  returns 10 QUESTION nodes from Memory Matrix

✓ forge_read_turns(db_path, limit=20)
  returns 20 conversation turns with session IDs

✓ forge_read_turns(db_path, session_id="specific-session")
  returns turns from just that session

✓ Claude can process QUESTION nodes into training examples

✓ Claude can pair user/assistant turns into training examples
```

---

## Example Workflow

Once implemented, Claude can do this:

```
Human: "Process the Alpha session notes and extract training examples"

Claude: 
1. forge_list_sources("/Alpha_ProjectFiles/03_Session_Notes/sessions/")
   → 76 files found

2. forge_read_raw("2025-11-28_luna-awakening.md")
   → Returns markdown content

3. [Claude analyzes content, extracts dialogue]
   
4. forge_add_example(
     user="hey Luna",
     assistant="Hey. I'm here. What's on your mind?",
     interaction_type="greeting",
     source_file="2025-11-28_luna-awakening.md",
     confidence=0.95
   )
   → {success: true, id: "abc123", lock_in: 0.75, tier: "gold"}

5. [Repeat for more examples in file]

6. forge_assay()
   → Shows updated health score, gap coverage

7. [Move to next file]
```

---

## Dependencies

**Already Available:**
- `fastmcp` - MCP framework
- `pathlib` - File handling
- Existing Crucible/Locksmith classes

**May Need:**
- `pyyaml` - For frontmatter parsing (check if already imported)
- `sqlite3` - Standard library, for Matrix reading

---

## Notes for Claude Code

1. **Don't break existing tools** - Add new tools, don't modify existing ones
2. **Use existing patterns** - Follow the style of existing tools in server.py
3. **Use existing state** - Add to `_state["examples"]`, use `_state["crucible"]` etc.
4. **Run voice detection** - All added examples must go through Crucible patterns
5. **Compute lock-in** - All examples need lock-in scoring via Locksmith
6. **Test incrementally** - Validate each tool works before moving to next

---

## Success Metrics

After implementation:
- [ ] Can list any directory of source files
- [ ] Can read any markdown/text file
- [ ] Can add examples with full quality scoring
- [ ] Can batch add efficiently
- [ ] Can search for duplicates
- [ ] Can read Memory Matrix nodes
- [ ] Can read conversation turns
- [ ] Health score improves as examples are added
- [ ] Gap coverage improves for target interaction types

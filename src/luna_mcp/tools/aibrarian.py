"""
AiBrarian tools — search, similar, co-occurrence, ingest, stats
================================================================

MCP tool wrappers for the AiBrarian Engine.
Thin interface — all logic lives in luna.substrate.aibrarian_engine.
"""

import logging
from pathlib import Path
from typing import Optional

from luna.core.paths import project_root, config_dir

logger = logging.getLogger(__name__)

# Engine-owned instance reference — set by set_engine() from server.py startup
_engine = None


def set_engine(engine_instance):
    """Attach the Engine-owned AiBrarianEngine. Called once at startup."""
    global _engine
    _engine = engine_instance


async def _get_engine():
    """Get the Engine-owned AiBrarianEngine instance.

    Falls back to standalone initialization only if the Engine hasn't
    booted yet (e.g. MCP running without full Engine).
    """
    global _engine
    if _engine is not None:
        return _engine

    # Fallback: standalone init (MCP-only mode without full Engine boot)
    from luna.substrate.aibrarian_engine import AiBrarianEngine

    _root = project_root()
    registry = config_dir() / "aibrarian_registry.yaml"

    _engine = AiBrarianEngine(registry, project_root=_root)
    await _engine.initialize()
    logger.warning("AiBrarianEngine fallback: standalone init (Engine not booted)")
    return _engine


async def aibrarian_list_impl() -> str:
    """List all available AiBrarian collections."""
    engine = await _get_engine()
    collections = engine.list_collections()
    if not collections:
        return "No collections registered."

    lines = ["Available collections:\n"]
    for c in collections:
        status = "CONNECTED" if c["connected"] else ("disabled" if not c["enabled"] else "offline")
        ro = " (read-only)" if c["read_only"] else ""
        lines.append(f"  {c['key']}: {c['name']} [{status}]{ro}")
        if c["description"]:
            lines.append(f"    {c['description']}")
        if c["tags"]:
            lines.append(f"    tags: {', '.join(c['tags'])}")
    return "\n".join(lines)


async def aibrarian_search_impl(
    collection: str,
    query: str,
    search_type: str = "hybrid",
    limit: int = 10,
) -> str:
    """Search an AiBrarian collection."""
    engine = await _get_engine()
    results = await engine.search(collection, query, search_type, limit)
    if not results:
        return f"No results for '{query}' in collection '{collection}'."

    lines = [f"Found {len(results)} results for '{query}' in '{collection}':\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. [{r.get('category', '?')}] {r.get('title') or r.get('filename')}")
        snippet = r.get("snippet", "")
        if snippet:
            lines.append(f"     {snippet[:120]}...")
        lines.append(f"     score: {r.get('score', 0):.4f}  type: {r.get('search_type', '?')}")
        lines.append(f"     doc_id: {r.get('doc_id', '?')}")
    return "\n".join(lines)


async def aibrarian_similar_impl(
    collection: str,
    doc_id: str,
    limit: int = 5,
) -> str:
    """Find documents similar to a given document."""
    engine = await _get_engine()
    results = await engine.similar(collection, doc_id, limit)
    if not results:
        return f"No similar documents found for {doc_id} in '{collection}'."

    lines = [f"Documents similar to {doc_id}:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"  {i}. {r.get('title') or r.get('filename')}  (sim: {r.get('similarity', 0):.3f})")
    return "\n".join(lines)


async def aibrarian_co_occurrence_impl(
    collection: str,
    terms: str,
    limit: int = 20,
) -> str:
    """Find documents containing ALL comma-separated terms."""
    term_list = [t.strip() for t in terms.split(",") if t.strip()]
    if not term_list:
        return "Provide comma-separated terms."

    engine = await _get_engine()
    results = await engine.co_occurrence(collection, term_list, limit)
    if not results:
        return f"No documents contain all terms: {', '.join(term_list)}"

    lines = [f"Documents containing all of [{', '.join(term_list)}]:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title") or r.get("filename", "?")
        lines.append(f"  {i}. [{r.get('category', '?')}] {title}  ({r.get('word_count', '?')} words)")
    return "\n".join(lines)


async def aibrarian_stats_impl(collection: str) -> str:
    """Get statistics for an AiBrarian collection."""
    engine = await _get_engine()
    s = await engine.stats(collection)
    return (
        f"Collection: {s['name']} ({s['collection']})\n"
        f"  Documents: {s['documents']}\n"
        f"  Chunks: {s['chunks']}\n"
        f"  Total words: {s['total_words']:,}\n"
        f"  Extractions: {s['extractions']}"
    )


async def aibrarian_ingest_impl(
    collection: str,
    file_path: str,
) -> str:
    """Ingest a document into an AiBrarian collection."""
    engine = await _get_engine()
    doc_id = await engine.ingest(collection, Path(file_path))
    if doc_id:
        return f"Ingested as {doc_id}"
    return f"Skipped {file_path} (too short or unreadable)"


async def aibrarian_ingest_dir_impl(
    collection: str,
    directory: str,
    recursive: bool = True,
) -> str:
    """Ingest all supported files from a directory into an AiBrarian collection."""
    engine = await _get_engine()
    doc_ids = await engine.ingest_directory(collection, Path(directory), recursive=recursive)
    return f"Ingested {len(doc_ids)} documents into '{collection}'"


# =====================================================================
# Document Retrieval
# =====================================================================


async def aibrarian_get_document_impl(collection: str, doc_id: str) -> str:
    """Retrieve a full document by ID."""
    engine = await _get_engine()
    doc = await engine.get_document(collection, doc_id)
    if not doc:
        return f"Document {doc_id} not found in '{collection}'."

    text = doc.get("full_text", "")
    preview = text[:500] + "..." if len(text) > 500 else text
    return (
        f"Document: {doc.get('title') or doc.get('filename')}\n"
        f"  ID: {doc['id']}\n"
        f"  Category: {doc.get('category', '?')}\n"
        f"  Words: {doc.get('word_count', '?')}\n"
        f"  Source: {doc.get('source_path', '?')}\n"
        f"  Created: {doc.get('created_at', '?')}\n\n"
        f"Text preview:\n{preview}"
    )


async def aibrarian_list_documents_impl(
    collection: str, skip: int = 0, limit: int = 50
) -> str:
    """List documents in a collection with pagination."""
    engine = await _get_engine()
    result = await engine.list_documents(collection, skip, limit)
    total = result["total"]
    docs = result["documents"]
    if not docs:
        return f"No documents in '{collection}'."

    lines = [f"Documents in '{collection}' ({total} total, showing {skip+1}-{skip+len(docs)}):\n"]
    for i, d in enumerate(docs, skip + 1):
        lines.append(f"  {i}. [{d.get('category', '?')}] {d.get('title') or d.get('filename')}  ({d.get('word_count', '?')} words)")
        lines.append(f"     id: {d['id']}")
    return "\n".join(lines)


# =====================================================================
# Count & Term Stats
# =====================================================================


async def aibrarian_count_impl(
    collection: str, query: str, search_type: str = "keyword"
) -> str:
    """Count matching documents without returning results."""
    engine = await _get_engine()
    n = await engine.count(collection, query, search_type)
    return f"{n} documents match '{query}' ({search_type}) in '{collection}'"


async def aibrarian_term_stats_impl(collection: str, terms: str) -> str:
    """Document counts for multiple comma-separated terms."""
    term_list = [t.strip() for t in terms.split(",") if t.strip()]
    if not term_list:
        return "Provide comma-separated terms."
    engine = await _get_engine()
    counts = await engine.term_stats(collection, term_list)
    lines = [f"Term stats for '{collection}':\n"]
    for term, count in counts.items():
        lines.append(f"  {term}: {count} documents")
    return "\n".join(lines)


# =====================================================================
# Entities
# =====================================================================


async def aibrarian_top_entities_impl(
    collection: str, limit: int = 50
) -> str:
    """Get top entities across a sample of documents."""
    engine = await _get_engine()
    result = await engine.top_entities(collection, limit)
    lines = [f"Top entities in '{collection}' ({result['total_documents_analyzed']} docs sampled):\n"]
    lines.append("Persons:")
    for e in result["persons"][:20]:
        lines.append(f"  {e['text']}: {e['count']} mentions")
    lines.append("\nOrganizations:")
    for e in result["organizations"][:20]:
        lines.append(f"  {e['text']}: {e['count']} mentions")
    return "\n".join(lines)


async def aibrarian_search_entity_impl(
    collection: str, name: str, limit: int = 50
) -> str:
    """Find documents mentioning a specific entity."""
    engine = await _get_engine()
    result = await engine.search_entity(collection, name, limit)
    docs = result["documents"]
    if not docs:
        return f"No documents mention '{name}' in '{collection}'."

    lines = [f"'{name}' appears in {result['document_count']} documents:\n"]
    for i, d in enumerate(docs[:20], 1):
        lines.append(f"  {i}. {d.get('title') or d.get('filename')}  ({d.get('word_count', '?')} words)")
        snippet = d.get("snippet", "")
        if snippet:
            lines.append(f"     {snippet[:120]}...")
    return "\n".join(lines)


async def aibrarian_document_entities_impl(collection: str, doc_id: str) -> str:
    """Extract entities from a specific document."""
    engine = await _get_engine()
    result = await engine.document_entities(collection, doc_id)
    lines = [f"Entities in {doc_id} ({result['total']} total):\n"]
    if result["persons"]:
        lines.append(f"Persons ({len(result['persons'])}):")
        for p in result["persons"]:
            lines.append(f"  - {p}")
    if result["organizations"]:
        lines.append(f"\nOrganizations ({len(result['organizations'])}):")
        for o in result["organizations"]:
            lines.append(f"  - {o}")
    if result["dates"]:
        lines.append(f"\nDates ({len(result['dates'])}):")
        for d in result["dates"]:
            lines.append(f"  - {d}")
    return "\n".join(lines)


# =====================================================================
# Timeline
# =====================================================================


async def aibrarian_timeline_impl(
    collection: str, query: str, limit: int = 100, confidence: Optional[str] = None
) -> str:
    """Get timeline of dates from matching documents."""
    engine = await _get_engine()
    result = await engine.timeline(collection, query, limit, confidence)
    events = result["events"]
    if not events:
        return f"No date events found for '{query}' in '{collection}'."

    lines = [f"Timeline for '{query}' ({result['total_events']} events):\n"]
    for e in events[:30]:
        lines.append(f"  {e['date']} [{e['confidence']}]  {e['context'][:80]}...")
    return "\n".join(lines)


# =====================================================================
# Analytics
# =====================================================================


async def aibrarian_word_frequency_impl(
    collection: str, query: str, top: int = 50
) -> str:
    """Word frequency analysis for matching documents."""
    engine = await _get_engine()
    result = await engine.word_frequency(collection, query, top)
    freqs = result["frequencies"]
    if not freqs:
        return f"No word data for '{query}' in '{collection}'."

    lines = [f"Word frequency for '{query}' ({result['total_words']} words, {result['unique_words']} unique):\n"]
    for f in freqs[:30]:
        lines.append(f"  {f['word']}: {f['count']} ({f['percentage']}%)")
    return "\n".join(lines)


async def aibrarian_ngrams_impl(
    collection: str, query: str, n: int = 2, top: int = 30
) -> str:
    """N-gram analysis for matching documents."""
    engine = await _get_engine()
    result = await engine.ngrams(collection, query, n, top)
    ng = result["ngrams"]
    if not ng:
        return f"No {n}-grams found for '{query}' in '{collection}'."

    lines = [f"Top {n}-grams for '{query}':\n"]
    for g in ng:
        lines.append(f"  \"{g['phrase']}\": {g['count']}")
    return "\n".join(lines)


async def aibrarian_export_search_impl(
    collection: str, query: str, limit: int = 1000, fmt: str = "json"
) -> str:
    """Export search results."""
    engine = await _get_engine()
    result = await engine.export_search(collection, query, limit, fmt)
    return f"Exported {result['total_results']} results for '{query}' ({fmt})"


async def aibrarian_sql_impl(
    collection: str, query: str, limit: int = 100
) -> str:
    """Execute read-only SQL against a collection."""
    engine = await _get_engine()
    try:
        result = await engine.execute_sql(collection, query, limit)
    except PermissionError as e:
        return f"SQL error: {e}"
    rows = result["rows"]
    lines = [f"SQL result ({result['row_count']} rows, {result['execution_time_ms']}ms):\n"]
    for r in rows[:20]:
        lines.append(f"  {r}")
    if result["row_count"] > 20:
        lines.append(f"  ... and {result['row_count'] - 20} more rows")
    return "\n".join(lines)

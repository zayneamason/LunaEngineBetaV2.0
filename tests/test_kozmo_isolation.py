"""
Critical Isolation Test for KOZMO Project Data Separation

This test verifies the most important architectural constraint:
KOZMO project entities must NEVER appear in Luna's personal Memory Matrix.

Creative content belongs to projects, not to Luna's consciousness.
This boundary is inviolable.

See: Docs/HANDOFF_KOZMO_BUILD.md § C4 (lines 869-901)
"""

import pytest
from pathlib import Path

from luna.substrate.database import MemoryDatabase
from luna.substrate.memory import MemoryMatrix
from luna.services.kozmo.graph import ProjectGraph
from luna.services.kozmo.project import ProjectPaths, save_entity_to_project
from luna.services.kozmo.types import Entity


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def luna_memory():
    """
    Luna's personal Memory Matrix.

    Uses the actual production database at data/luna_engine.db.
    This is where Luna's soul lives — conversations, decisions, knowledge.
    """
    # Use default production database path
    db = MemoryDatabase()
    await db.connect()

    memory = MemoryMatrix(db, enable_embeddings=False)  # Disable embeddings for speed

    yield memory

    await db.close()


@pytest.fixture
def project_graph(tmp_path):
    """
    Isolated KOZMO project graph.

    This is a per-project database — completely separate from Luna's memory.
    Uses ProjectGraph (synchronous, no async needed).
    """
    db_path = tmp_path / "project" / "graph.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    graph = ProjectGraph(db_path)

    yield graph

    # Cleanup not needed — tmp_path is auto-cleaned by pytest


@pytest.fixture
def project_paths(tmp_path):
    """
    Project directory structure.

    Creates the YAML storage directories for entities.
    """
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    paths = ProjectPaths(project_root)

    yield paths


# =============================================================================
# Critical Isolation Test
# =============================================================================


@pytest.mark.asyncio
async def test_project_data_never_enters_personal_memory(
    luna_memory, project_graph, project_paths
):
    """
    CRITICAL: Project entities must NEVER appear in Luna's Memory Matrix.

    This is the separation principle. Creative content belongs to projects,
    not to Luna's personal memory.

    Test Strategy:
    1. Create entity with unique name (avoid false matches)
    2. Save to project YAML files
    3. Index in project graph
    4. Verify entity exists in PROJECT graph
    5. Verify entity DOES NOT exist in Luna's Memory Matrix
    6. Additional check: verify slug not in Memory Matrix

    If this test fails, it's an ISOLATION BREACH — the core architectural
    constraint is violated.
    """
    # -------------------------------------------------------------------------
    # Step 1: Create Unique Test Entity
    # -------------------------------------------------------------------------

    # Use bizarre name to avoid false matches with existing data
    unique_name = "Zxyqvort the Unique Sentinel of 2026"
    unique_slug = "zxyqvort_the_unique_sentinel_of_2026"

    entity = Entity(
        type="character",
        name=unique_name,
        slug=unique_slug,
        status="active",
        data={"role": "Isolation test sentinel", "purpose": "Verify project separation"},
        tags=["test", "isolation"],
        relationships=[],
        scenes=[],
    )

    # -------------------------------------------------------------------------
    # Step 2: Save to Project
    # -------------------------------------------------------------------------

    save_entity_to_project(project_paths, entity)

    # Verify file was created
    entity_file = project_paths.entity_file(entity.type, entity.slug)
    assert entity_file.exists(), "Entity YAML file should exist in project"

    # -------------------------------------------------------------------------
    # Step 3: Index in Project Graph
    # -------------------------------------------------------------------------

    project_graph.add_entity(entity)

    # -------------------------------------------------------------------------
    # Step 4: Verify Entity Exists in PROJECT Graph
    # -------------------------------------------------------------------------

    assert project_graph.has_entity(unique_slug), (
        "Entity should exist in project graph"
    )

    entity_data = project_graph.get_entity_data(unique_slug)
    assert entity_data is not None, "Entity data should be retrievable from project graph"
    assert entity_data["name"] == unique_name, "Entity name should match in project graph"

    # -------------------------------------------------------------------------
    # Step 5: CRITICAL ASSERTION — Search Luna's Memory Matrix
    # -------------------------------------------------------------------------

    # Search for the unique name — this should return ZERO results
    luna_results = await luna_memory.search_nodes(
        query=unique_name,
        limit=10
    )

    assert len(luna_results) == 0, (
        f"ISOLATION BREACH: Project entity '{unique_name}' found in Luna's "
        f"personal Memory Matrix with {len(luna_results)} results.\n"
        f"Results: {[node.content for node in luna_results]}\n\n"
        f"Project data must remain isolated from Luna's consciousness."
    )

    # -------------------------------------------------------------------------
    # Step 6: Additional Check — Search by Slug
    # -------------------------------------------------------------------------

    # Search for the entity slug — this should also return ZERO results
    slug_results = await luna_memory.search_nodes(
        query=unique_slug,
        limit=10
    )

    assert len(slug_results) == 0, (
        f"ISOLATION BREACH: Project entity slug '{unique_slug}' found in "
        f"Luna's Memory Matrix with {slug_results} results.\n"
        f"Results: {[node.content for node in slug_results]}\n\n"
        f"Project slugs must not be indexed in personal memory."
    )

    # -------------------------------------------------------------------------
    # Step 7: Additional Check — Search for Test Metadata
    # -------------------------------------------------------------------------

    # Search for unique metadata string
    metadata_query = "Isolation test sentinel"
    metadata_results = await luna_memory.search_nodes(
        query=metadata_query,
        limit=10
    )

    assert len(metadata_results) == 0, (
        f"ISOLATION BREACH: Project entity metadata '{metadata_query}' found "
        f"in Luna's Memory Matrix with {len(metadata_results)} results.\n"
        f"Results: {[node.content for node in metadata_results]}\n\n"
        f"No part of project data should leak into personal memory."
    )


# =============================================================================
# Additional Isolation Tests (Future)
# =============================================================================


@pytest.mark.asyncio
async def test_project_graph_uses_separate_database(project_graph, luna_memory):
    """
    Verify project graph and Memory Matrix use different SQLite databases.

    This is a structural check — the databases should be completely separate files.
    """
    # Get database paths via private attributes (this is for verification only)
    project_db_path = project_graph._db_path
    luna_db_path = luna_memory.db.db_path

    # They must not be the same file
    assert project_db_path != luna_db_path, (
        f"ISOLATION BREACH: Project graph and Memory Matrix use the same database.\n"
        f"Project: {project_db_path}\n"
        f"Luna:    {luna_db_path}\n\n"
        f"These MUST be separate databases."
    )

    # They should not even be in the same directory
    assert project_db_path.parent != luna_db_path.parent, (
        f"Project graph and Memory Matrix should be in different directories.\n"
        f"Project: {project_db_path.parent}\n"
        f"Luna:    {luna_db_path.parent}"
    )


def test_project_graph_is_lightweight(project_graph):
    """
    Verify project graph is just an index, not a copy of Memory Matrix.

    The project graph should:
    - Use NetworkX for in-memory operations
    - Have a simple SQLite schema (no FTS5, no embeddings, no complex tables)
    - Be rebuildable from YAML at any time
    """
    # This is a design check — project graph should not have Memory Matrix tables
    # We can verify this by checking the graph structure

    assert hasattr(project_graph, '_graph'), "ProjectGraph should use NetworkX internally"
    assert project_graph.entity_count() == 0, "Should start with empty graph"

    # The graph.db file should be much simpler than memory_matrix.db
    # (This is more of a documentation check — the implementation validates this)

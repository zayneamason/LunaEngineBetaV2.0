"""
Tests for KOZMO Project Graph

Validates:
- Node operations (add, remove, query)
- Edge operations (relationships)
- Query operations (neighbors, path finding, filtering)
- Bulk operations (index, rebuild)
- SQLite persistence (save/load round-trip)
- Graph statistics
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.services.kozmo.graph import ProjectGraph
from luna.services.kozmo.types import Entity, Relationship


# =============================================================================
# Helpers
# =============================================================================


def _make_entity(
    slug: str,
    name: str = None,
    entity_type: str = "characters",
    status: str = "active",
    tags: list = None,
    relationships: list = None,
) -> Entity:
    """Create test entity."""
    return Entity(
        type=entity_type,
        name=name or slug.replace("_", " ").title(),
        slug=slug,
        status=status,
        tags=tags or [],
        relationships=relationships or [],
    )


# =============================================================================
# Node Operations
# =============================================================================


def test_add_entity():
    """Test adding entity as graph node."""
    graph = ProjectGraph()
    entity = _make_entity("mordecai", entity_type="characters")

    graph.add_entity(entity)

    assert graph.has_entity("mordecai")
    assert graph.entity_count() == 1


def test_add_entity_data():
    """Test entity node stores metadata."""
    graph = ProjectGraph()
    entity = _make_entity(
        "mordecai",
        entity_type="characters",
        tags=["main_cast"],
    )

    graph.add_entity(entity)

    data = graph.get_entity_data("mordecai")
    assert data["type"] == "characters"
    assert data["name"] == "Mordecai"
    assert data["status"] == "active"
    assert "main_cast" in data["tags"]


def test_remove_entity():
    """Test removing entity from graph."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))

    removed = graph.remove_entity("mordecai")

    assert removed is True
    assert not graph.has_entity("mordecai")
    assert graph.entity_count() == 0


def test_remove_entity_not_found():
    """Test removing non-existent entity returns False."""
    graph = ProjectGraph()

    removed = graph.remove_entity("nonexistent")

    assert removed is False


def test_remove_entity_cleans_edges():
    """Test removing entity also removes its edges."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_relationship("mordecai", "cornelius", "family")

    graph.remove_entity("mordecai")

    assert graph.edge_count() == 0


def test_get_entity_data_not_found():
    """Test getting data for non-existent entity returns None."""
    graph = ProjectGraph()

    data = graph.get_entity_data("nonexistent")

    assert data is None


# =============================================================================
# Edge Operations
# =============================================================================


def test_add_relationship():
    """Test adding relationship edge."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))

    graph.add_relationship("mordecai", "cornelius", "family", "Father")

    assert graph.has_relationship("mordecai", "cornelius")
    assert graph.edge_count() == 1


def test_relationship_data():
    """Test relationship edge stores metadata."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))

    graph.add_relationship("mordecai", "cornelius", "family", "Father. Overbearing.")

    data = graph.get_relationship("mordecai", "cornelius")
    assert data["type"] == "family"
    assert data["detail"] == "Father. Overbearing."


def test_relationship_is_directed():
    """Test relationships are directed (A→B != B→A)."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))

    graph.add_relationship("mordecai", "cornelius", "family")

    assert graph.has_relationship("mordecai", "cornelius")
    assert not graph.has_relationship("cornelius", "mordecai")


def test_remove_relationship():
    """Test removing relationship edge."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_relationship("mordecai", "cornelius", "family")

    removed = graph.remove_relationship("mordecai", "cornelius")

    assert removed is True
    assert not graph.has_relationship("mordecai", "cornelius")


def test_remove_relationship_not_found():
    """Test removing non-existent relationship returns False."""
    graph = ProjectGraph()

    removed = graph.remove_relationship("a", "b")

    assert removed is False


def test_get_relationship_not_found():
    """Test getting non-existent relationship returns None."""
    graph = ProjectGraph()

    data = graph.get_relationship("a", "b")

    assert data is None


# =============================================================================
# Query Operations
# =============================================================================


def test_neighbors():
    """Test getting outgoing neighbors."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_entity(_make_entity("constance"))

    graph.add_relationship("mordecai", "cornelius", "family")
    graph.add_relationship("mordecai", "constance", "family")

    neighbors = graph.neighbors("mordecai")

    assert len(neighbors) == 2
    assert "cornelius" in neighbors
    assert "constance" in neighbors


def test_neighbors_not_found():
    """Test neighbors for non-existent entity returns empty."""
    graph = ProjectGraph()

    neighbors = graph.neighbors("nonexistent")

    assert neighbors == []


def test_predecessors():
    """Test getting incoming predecessors."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_entity(_make_entity("constance"))

    graph.add_relationship("cornelius", "mordecai", "family")
    graph.add_relationship("constance", "mordecai", "family")

    preds = graph.predecessors("mordecai")

    assert len(preds) == 2
    assert "cornelius" in preds
    assert "constance" in preds


def test_get_relationships_for():
    """Test getting all relationships for an entity."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_entity(_make_entity("crooked_nail", entity_type="locations"))

    graph.add_relationship("mordecai", "cornelius", "family", "Father")
    graph.add_relationship("mordecai", "crooked_nail", "frequents", "Regular patron")

    rels = graph.get_relationships_for("mordecai")

    assert len(rels) == 2
    entities = [r["entity"] for r in rels]
    assert "cornelius" in entities
    assert "crooked_nail" in entities


def test_get_relationships_for_not_found():
    """Test relationships for non-existent entity returns empty."""
    graph = ProjectGraph()

    rels = graph.get_relationships_for("nonexistent")

    assert rels == []


def test_entities_by_type():
    """Test filtering entities by type."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai", entity_type="characters"))
    graph.add_entity(_make_entity("cornelius", entity_type="characters"))
    graph.add_entity(_make_entity("crooked_nail", entity_type="locations"))

    characters = graph.entities_by_type("characters")
    locations = graph.entities_by_type("locations")

    assert len(characters) == 2
    assert len(locations) == 1
    assert "crooked_nail" in locations


def test_entities_by_tag():
    """Test filtering entities by tag."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai", tags=["main_cast", "magic_sector"]))
    graph.add_entity(_make_entity("cornelius", tags=["main_cast"]))
    graph.add_entity(_make_entity("guard", tags=["npc"]))

    main_cast = graph.entities_by_tag("main_cast")
    npcs = graph.entities_by_tag("npc")

    assert len(main_cast) == 2
    assert len(npcs) == 1


def test_shortest_path():
    """Test finding shortest path between entities."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_entity(_make_entity("constance"))

    graph.add_relationship("mordecai", "cornelius", "family")
    graph.add_relationship("cornelius", "constance", "family")

    path = graph.shortest_path("mordecai", "constance")

    assert path == ["mordecai", "cornelius", "constance"]


def test_shortest_path_no_path():
    """Test shortest path when no path exists."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("isolated"))

    path = graph.shortest_path("mordecai", "isolated")

    assert path is None


def test_shortest_path_node_not_found():
    """Test shortest path with non-existent node."""
    graph = ProjectGraph()

    path = graph.shortest_path("a", "b")

    assert path is None


# =============================================================================
# Bulk Operations
# =============================================================================


def test_index_entity():
    """Test indexing entity with relationships."""
    graph = ProjectGraph()

    entity = Entity(
        type="characters",
        name="Mordecai",
        slug="mordecai",
        relationships=[
            Relationship(entity="cornelius", type="family", detail="Father"),
            Relationship(entity="crooked_nail", type="frequents"),
        ],
    )

    graph.index_entity(entity)

    # Node indexed
    assert graph.has_entity("mordecai")

    # Stub nodes created for targets
    assert graph.has_entity("cornelius")
    assert graph.has_entity("crooked_nail")

    # Edges created
    assert graph.has_relationship("mordecai", "cornelius")
    assert graph.has_relationship("mordecai", "crooked_nail")
    assert graph.edge_count() == 2


def test_index_entity_updates_existing():
    """Test indexing existing entity updates node data."""
    graph = ProjectGraph()

    # Initial index
    entity_v1 = _make_entity("mordecai", tags=["main_cast"])
    graph.add_entity(entity_v1)

    # Re-index with updated data
    entity_v2 = _make_entity("mordecai", tags=["main_cast", "magic_sector"])
    graph.index_entity(entity_v2)

    data = graph.get_entity_data("mordecai")
    assert "magic_sector" in data["tags"]
    assert graph.entity_count() == 1  # No duplicate


def test_rebuild():
    """Test rebuilding graph from scratch."""
    graph = ProjectGraph()

    # Add some initial data
    graph.add_entity(_make_entity("old_entity"))
    assert graph.entity_count() == 1

    # Rebuild with new data
    entities = [
        Entity(
            type="characters",
            name="Mordecai",
            slug="mordecai",
            relationships=[
                Relationship(entity="cornelius", type="family"),
            ],
        ),
        Entity(
            type="locations",
            name="The Crooked Nail",
            slug="crooked_nail",
        ),
    ]

    graph.rebuild(entities)

    # Old data gone
    assert not graph.has_entity("old_entity")

    # New data indexed
    assert graph.has_entity("mordecai")
    assert graph.has_entity("cornelius")  # Stub from relationship
    assert graph.has_entity("crooked_nail")
    assert graph.has_relationship("mordecai", "cornelius")


def test_clear():
    """Test clearing graph."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai"))
    graph.add_entity(_make_entity("cornelius"))
    graph.add_relationship("mordecai", "cornelius", "family")

    graph.clear()

    assert graph.entity_count() == 0
    assert graph.edge_count() == 0


# =============================================================================
# SQLite Persistence
# =============================================================================


def test_save_and_load(tmp_path):
    """Test saving graph to SQLite and loading it back."""
    db_path = tmp_path / "test.db"

    # Create and populate graph
    graph1 = ProjectGraph()
    graph1.add_entity(_make_entity("mordecai", tags=["main_cast"]))
    graph1.add_entity(_make_entity("cornelius"))
    graph1.add_relationship("mordecai", "cornelius", "family", "Father")

    # Save
    graph1.save(db_path)
    assert db_path.exists()

    # Load into new graph
    graph2 = ProjectGraph(db_path=db_path)

    # Verify data
    assert graph2.has_entity("mordecai")
    assert graph2.has_entity("cornelius")
    assert graph2.has_relationship("mordecai", "cornelius")
    assert graph2.entity_count() == 2
    assert graph2.edge_count() == 1

    # Verify node data preserved
    data = graph2.get_entity_data("mordecai")
    assert data["type"] == "characters"
    assert "main_cast" in data["tags"]

    # Verify edge data preserved
    rel = graph2.get_relationship("mordecai", "cornelius")
    assert rel["type"] == "family"
    assert rel["detail"] == "Father"


def test_save_overwrite(tmp_path):
    """Test saving overwrites previous graph data."""
    db_path = tmp_path / "test.db"

    # Save initial graph
    graph1 = ProjectGraph()
    graph1.add_entity(_make_entity("old_entity"))
    graph1.save(db_path)

    # Save new graph (overwrite)
    graph2 = ProjectGraph()
    graph2.add_entity(_make_entity("new_entity"))
    graph2.save(db_path)

    # Load and verify only new data exists
    graph3 = ProjectGraph(db_path=db_path)
    assert not graph3.has_entity("old_entity")
    assert graph3.has_entity("new_entity")


def test_save_no_path():
    """Test saving without path raises ValueError."""
    graph = ProjectGraph()

    with pytest.raises(ValueError, match="No database path"):
        graph.save()


def test_load_empty_db(tmp_path):
    """Test loading from empty database (no tables)."""
    db_path = tmp_path / "empty.db"

    # Create empty SQLite file
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.close()

    # Should load without error (empty graph)
    graph = ProjectGraph(db_path=db_path)
    assert graph.entity_count() == 0


# =============================================================================
# Stats
# =============================================================================


def test_stats():
    """Test graph statistics."""
    graph = ProjectGraph()
    graph.add_entity(_make_entity("mordecai", entity_type="characters"))
    graph.add_entity(_make_entity("cornelius", entity_type="characters"))
    graph.add_entity(_make_entity("crooked_nail", entity_type="locations"))
    graph.add_relationship("mordecai", "cornelius", "family")
    graph.add_relationship("mordecai", "crooked_nail", "frequents")

    stats = graph.stats()

    assert stats["nodes"] == 3
    assert stats["edges"] == 2
    assert stats["types"]["characters"] == 2
    assert stats["types"]["locations"] == 1
    assert stats["connected_components"] >= 1


def test_stats_empty():
    """Test stats on empty graph."""
    graph = ProjectGraph()

    stats = graph.stats()

    assert stats["nodes"] == 0
    assert stats["edges"] == 0
    assert stats["types"] == {}

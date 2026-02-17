# KOZMO Test Coverage Review

**Date:** 2026-02-11
**Purpose:** Document test patterns and coverage across KOZMO test suite

---

## Test Suite Overview

**Total:** 8 test files, 179 tests, 3,741 lines of test code
**Status:** Comprehensive backend coverage, missing critical isolation test (now added)

| File | Lines | Tests | Focus Area |
|------|-------|-------|------------|
| `test_kozmo_types.py` | 418 | ~30 | Pydantic model validation, serialization, defaults |
| `test_kozmo_entity.py` | 588 | ~40 | Entity YAML parsing, template validation, slugify |
| `test_kozmo_project.py` | 509 | ~35 | Project CRUD, directory structure, manifest |
| `test_kozmo_graph.py` | 548 | ~30 | Graph operations, relationships, traversal |
| `test_kozmo_fountain.py` | 355 | ~20 | Fountain parsing, character extraction, dialogue |
| `test_kozmo_prompt_builder.py` | 360 | ~15 | Camera → Eden prompt translation |
| `test_kozmo_routes.py` | 309 | ~20 | FastAPI endpoints (all /kozmo/* routes) |
| `test_kozmo_scribo.py` | 654 | ~35 | .scribo format, story tree, word counts |
| **test_kozmo_isolation.py** | ~200 | 3 | **Project/memory isolation (new)** |

---

## Common Test Patterns

### 1. Fixture Patterns

**Temporary directories:**
```python
def test_something(tmp_path):
    """pytest provides tmp_path automatically"""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    # ... test logic
```

**Project setup:**
```python
@pytest.fixture
def project_paths(tmp_path):
    """Standard project directory structure"""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    paths = ProjectPaths(project_root)
    return paths
```

**Entity helpers:**
```python
def _make_entity(slug, name=None, entity_type="characters", **kwargs):
    """Helper to create test entities"""
    return Entity(
        type=entity_type,
        name=name or slug.replace("_", " ").title(),
        slug=slug,
        **kwargs
    )
```

### 2. Async Test Patterns

**Async tests use `@pytest.mark.asyncio`:**
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await some_async_function()
    assert result is not None
```

**Async fixtures:**
```python
@pytest.fixture
async def async_resource():
    resource = await initialize()
    yield resource
    await resource.cleanup()
```

### 3. Error Handling Tests

**Graceful degradation pattern:**
```python
def test_malformed_yaml_returns_error(tmp_path):
    """Test that malformed YAML doesn't crash, returns error"""
    file = tmp_path / "bad.yaml"
    file.write_text("{ invalid yaml }")

    result = parse_entity_safe(file)

    assert result.entity is None
    assert result.error is not None
    assert "invalid yaml" in result.error.lower()
```

**Warning collection:**
```python
def test_missing_optional_field_warns(tmp_path):
    """Missing optional fields should warn, not fail"""
    entity = parse_entity(minimal_yaml)

    assert entity is not None
    assert len(entity.warnings) > 0
    assert "optional field" in entity.warnings[0]
```

### 4. YAML Round-Trip Tests

**Verify save → load preserves data:**
```python
def test_entity_yaml_round_trip(tmp_path):
    """Save entity → load entity should preserve all data"""
    original = Entity(
        type="character",
        name="Test Character",
        slug="test_character",
        data={"field": "value"}
    )

    # Save
    file = tmp_path / "entity.yaml"
    save_entity(original, file)

    # Load
    loaded = load_entity(file)

    # Compare
    assert loaded.name == original.name
    assert loaded.slug == original.slug
    assert loaded.data == original.data
```

### 5. Graph Operations Tests

**Node operations:**
```python
def test_add_entity_to_graph():
    graph = ProjectGraph()
    entity = _make_entity("mordecai")

    graph.add_entity(entity)

    assert graph.has_entity("mordecai")
    assert graph.entity_count() == 1
```

**Edge/relationship operations:**
```python
def test_add_relationship():
    graph = ProjectGraph()
    graph.add_entity(_make_entity("character1"))
    graph.add_entity(_make_entity("character2"))

    graph.add_relationship(
        from_slug="character1",
        to_slug="character2",
        relationship_type="family"
    )

    assert graph.has_relationship("character1", "character2")
```

**Path finding:**
```python
def test_shortest_path():
    graph = ProjectGraph()
    # Add entities and relationships
    ...

    path = graph.shortest_path("character1", "character3")

    assert path is not None
    assert path == ["character1", "character2", "character3"]
```

### 6. API Testing (FastAPI TestClient)

**Endpoint testing pattern:**
```python
def test_create_project(client):
    """Test POST /projects endpoint"""
    response = client.post(
        "/projects",
        json={"name": "Test Project", "slug": "test_project"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "test_project"
```

**Error response testing:**
```python
def test_get_nonexistent_entity_returns_404(client):
    response = client.get("/entities/character/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
```

---

## Test Coverage Gaps (Pre-Isolation Test)

**Critical:**
- ❌ **Project isolation test** (ADDED: test_kozmo_isolation.py)
- ✅ All other core functionality covered

**Nice to Have:**
- File watching integration (mentioned in handoff C2)
- Real Eden integration tests (currently mocked)
- UI state management tests (frontend only)
- Drag-and-drop reorder tests (frontend + backend)

---

## Key Testing Utilities

### Helpers Found in Tests

**Entity creation:**
- `_make_entity()` — consistent entity creation across tests
- `_make_project()` — project manifest creation
- `_make_relationship()` — relationship dict creation

**YAML utilities:**
- `yaml.safe_load()` / `yaml.safe_dump()` — always use safe methods
- `yaml.dump(default_flow_style=False, sort_keys=False)` — preserve order

**Path helpers:**
- `ProjectPaths` class — standardizes directory structure
- `tmp_path` fixture — pytest provides temp directory cleanup

**Assertion patterns:**
- Check existence first: `assert entity is not None`
- Check type: `assert isinstance(entity, Entity)`
- Check error messages: `assert "expected text" in error.lower()`

---

## Recommendations for New Tests

1. **Always use fixtures** for project setup (DRY principle)
2. **Test happy path + error cases** in same file
3. **Use descriptive test names** that explain what's being tested
4. **Add docstrings** explaining the test's purpose
5. **Keep tests focused** — one assertion category per test
6. **Use helpers** from existing tests (don't duplicate setup logic)
7. **Test round-trips** for persistence (save → load → verify)
8. **Verify warnings** not just failures (graceful degradation)

---

## Test Execution

**Run all KOZMO tests:**
```bash
pytest tests/test_kozmo_*.py -v
```

**Run specific test file:**
```bash
pytest tests/test_kozmo_isolation.py -v
```

**Run with coverage:**
```bash
pytest tests/test_kozmo_*.py --cov=src/luna/services/kozmo --cov-report=html
```

**Run only isolation tests:**
```bash
pytest tests/test_kozmo_isolation.py -v -k "isolation"
```

---

## Isolation Test Importance

The isolation test (`test_project_data_never_enters_personal_memory`) is the MOST CRITICAL test in the entire suite. It validates the core architectural constraint:

**KOZMO project data MUST NEVER enter Luna's personal Memory Matrix.**

This boundary is inviolable. If this test fails, it's an isolation breach and the architecture is compromised.

The test:
1. Creates a unique test entity with bizarre name
2. Saves to project YAML files
3. Indexes in project graph
4. Verifies entity exists in PROJECT graph
5. **CRITICAL:** Verifies entity DOES NOT exist in Luna's Memory Matrix

All 3 isolation tests now pass:
- ✅ `test_project_data_never_enters_personal_memory` — core constraint
- ✅ `test_project_graph_uses_separate_database` — structural validation
- ✅ `test_project_graph_is_lightweight` — design validation

---

## Next Steps

1. ✅ **Isolation test implemented and passing**
2. Run full test suite to ensure no regressions:
   ```bash
   pytest tests/test_kozmo_*.py
   ```
3. Add tests as new features are implemented (frontend tests for Day 2-5)
4. Consider adding E2E tests for full user workflows

**Test suite health:** ✅ Excellent backend coverage + critical isolation test now in place

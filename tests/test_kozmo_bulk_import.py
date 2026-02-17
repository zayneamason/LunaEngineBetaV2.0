"""
Test KOZMO Bulk Entity Import

Tests the POST /kozmo/projects/{slug}/entities/bulk endpoint for:
- Successful bulk entity creation
- Duplicate handling strategies (skip, overwrite, fail)
- Partial success with validation errors
- Invalid entity types
"""
import pytest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

import luna.services.kozmo.routes as routes_module
from luna.services.kozmo.routes import router


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app(tmp_path):
    """Create test FastAPI app with KOZMO routes and temp project root."""
    # Override projects root to use temp directory
    routes_module.DEFAULT_PROJECTS_ROOT = tmp_path / "projects"
    routes_module.DEFAULT_PROJECTS_ROOT.mkdir()

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# =============================================================================
# Tests
# =============================================================================


def test_bulk_create_entities_success(client):
    """Test successful bulk entity creation."""
    # Create project first
    resp = client.post("/kozmo/projects", json={"name": "Test Bulk"})
    assert resp.status_code == 201
    project_slug = resp.json()["slug"]

    # Bulk import entities
    entities = [
        {"type": "characters", "name": "Sarah Connor", "tags": ["protagonist"]},
        {"type": "locations", "name": "Tech Noir", "tags": ["nightclub"]},
        {"type": "props", "name": "Terminator Arm", "data": {"condition": "damaged"}},
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities, "on_duplicate": "skip"}
    )

    assert response.status_code == 200
    result = response.json()
    assert len(result["created"]) == 3
    assert len(result["failed"]) == 0
    assert len(result["skipped"]) == 0

    # Verify created entities have correct structure
    assert result["created"][0]["name"] == "Sarah Connor"
    assert result["created"][0]["type"] == "characters"
    assert result["created"][0]["slug"] == "sarah_connor"


def test_bulk_create_with_duplicates_skip(client):
    """Test duplicate handling with 'skip' strategy."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test Dup Skip"})
    project_slug = resp.json()["slug"]

    # Create initial entity via single endpoint
    client.post(
        f"/kozmo/projects/{project_slug}/entities",
        json={"type": "characters", "name": "Sarah Connor", "tags": ["existing"]}
    )

    # Try bulk import with duplicate (skip strategy)
    entities = [
        {"type": "characters", "name": "Sarah Connor", "tags": ["new"]},  # duplicate
        {"type": "characters", "name": "Kyle Reese", "tags": ["new"]},    # new
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities, "on_duplicate": "skip"}
    )

    result = response.json()
    assert len(result["created"]) == 1   # Kyle Reese created
    assert len(result["skipped"]) == 1   # Sarah Connor skipped
    assert len(result["failed"]) == 0

    assert result["created"][0]["name"] == "Kyle Reese"
    assert result["skipped"][0]["entity"]["name"] == "Sarah Connor"
    assert "already exists" in result["skipped"][0]["reason"].lower()


def test_bulk_create_with_duplicates_fail(client):
    """Test duplicate handling with 'fail' strategy."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test Dup Fail"})
    project_slug = resp.json()["slug"]

    # Create initial entity
    client.post(
        f"/kozmo/projects/{project_slug}/entities",
        json={"type": "characters", "name": "Sarah Connor"}
    )

    # Try bulk import with duplicate (fail strategy)
    entities = [
        {"type": "characters", "name": "Sarah Connor"},  # duplicate
        {"type": "characters", "name": "Kyle Reese"},    # new
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities, "on_duplicate": "fail"}
    )

    result = response.json()
    assert len(result["created"]) == 1   # Kyle Reese created
    assert len(result["failed"]) == 1    # Sarah Connor failed
    assert len(result["skipped"]) == 0

    assert result["failed"][0]["entity"]["name"] == "Sarah Connor"
    assert "already exists" in result["failed"][0]["error"].lower()


def test_bulk_create_with_duplicates_overwrite(client):
    """Test duplicate handling with 'overwrite' strategy."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test Dup Overwrite"})
    project_slug = resp.json()["slug"]

    # Create initial entity with original tags
    client.post(
        f"/kozmo/projects/{project_slug}/entities",
        json={"type": "characters", "name": "Sarah Connor", "tags": ["original"]}
    )

    # Bulk import with overwrite
    entities = [
        {"type": "characters", "name": "Sarah Connor", "tags": ["overwritten"]},
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities, "on_duplicate": "overwrite"}
    )

    result = response.json()
    assert len(result["created"]) == 1
    assert len(result["skipped"]) == 0
    assert len(result["failed"]) == 0

    # Verify entity was created (overwrite just overwrites the file)
    assert result["created"][0]["name"] == "Sarah Connor"


def test_bulk_create_partial_failure(client):
    """Test partial success with validation errors."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test Partial"})
    project_slug = resp.json()["slug"]

    entities = [
        {"type": "characters", "name": "Valid Character"},
        {"type": "invalid_type", "name": "Bad Type"},      # invalid type
        {"type": "locations", "name": "Valid Location"},
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities}
    )

    result = response.json()
    assert len(result["created"]) == 2   # 2 valid entities
    assert len(result["failed"]) == 1    # 1 invalid type

    assert "Invalid entity type" in result["failed"][0]["error"]
    assert result["failed"][0]["entity"]["type"] == "invalid_type"


def test_bulk_create_with_data_and_tags(client):
    """Test bulk import with complex entity data and tags."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test Complex"})
    project_slug = resp.json()["slug"]

    entities = [
        {
            "type": "characters",
            "name": "T-800",
            "data": {
                "model": "Cyberdyne Systems Model 101",
                "mission": "Terminate Sarah Connor",
                "capabilities": ["combat", "infiltration", "analysis"]
            },
            "tags": ["antagonist", "cyborg", "time-traveler"]
        },
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities}
    )

    result = response.json()
    assert len(result["created"]) == 1
    assert result["created"][0]["slug"] == "t_800"


def test_bulk_create_empty_list(client):
    """Test bulk import with empty entities list."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test Empty"})
    project_slug = resp.json()["slug"]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": []}
    )

    result = response.json()
    assert len(result["created"]) == 0
    assert len(result["failed"]) == 0
    assert len(result["skipped"]) == 0


def test_bulk_create_project_not_found(client):
    """Test bulk import on non-existent project."""
    response = client.post(
        "/kozmo/projects/nonexistent-project/entities/bulk",
        json={"entities": [{"type": "characters", "name": "Test"}]}
    )

    assert response.status_code == 404


def test_bulk_create_all_entities_fail(client):
    """Test when all entities fail validation."""
    # Create project
    resp = client.post("/kozmo/projects", json={"name": "Test All Fail"})
    project_slug = resp.json()["slug"]

    entities = [
        {"type": "invalid1", "name": "Bad 1"},
        {"type": "invalid2", "name": "Bad 2"},
        {"type": "invalid3", "name": "Bad 3"},
    ]

    response = client.post(
        f"/kozmo/projects/{project_slug}/entities/bulk",
        json={"entities": entities}
    )

    result = response.json()
    assert len(result["created"]) == 0
    assert len(result["failed"]) == 3

    # Verify all failed with proper error messages
    for failed in result["failed"]:
        assert "Invalid entity type" in failed["error"]

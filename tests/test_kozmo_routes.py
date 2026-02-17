"""
Tests for KOZMO API Routes

Validates:
- Project CRUD endpoints
- Entity CRUD endpoints
- Graph query endpoints
- Prompt builder endpoints
- Error handling (404, 409)

Uses FastAPI TestClient for integration testing.
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi import FastAPI
from fastapi.testclient import TestClient

import luna.services.kozmo.routes as routes_module
from luna.services.kozmo.routes import router
from luna.services.kozmo.project import ProjectPaths, create_project
from luna.services.kozmo.types import Entity
from luna.services.kozmo.entity import save_entity
from luna.services.kozmo.graph import ProjectGraph


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


@pytest.fixture
def project_slug(client):
    """Create a test project and return its slug."""
    resp = client.post("/kozmo/projects", json={
        "name": "Test Project",
    })
    assert resp.status_code == 201
    return resp.json()["slug"]


@pytest.fixture
def project_with_entity(client, project_slug):
    """Create a project with a test entity."""
    client.post(f"/kozmo/projects/{project_slug}/entities", json={
        "type": "characters",
        "name": "Mordecai",
        "data": {"age": 28, "build": "lean, angular"},
        "tags": ["main_cast"],
    })
    return project_slug


# =============================================================================
# Project Routes
# =============================================================================


def test_list_projects_empty(client):
    """Test listing projects when none exist."""
    resp = client.get("/kozmo/projects")
    assert resp.status_code == 200
    assert resp.json()["projects"] == []


def test_create_project(client):
    """Test creating a project."""
    resp = client.post("/kozmo/projects", json={
        "name": "The Crooked Nail",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "The Crooked Nail"
    assert data["slug"] == "the_crooked_nail"


def test_create_project_with_slug(client):
    """Test creating a project with explicit slug."""
    resp = client.post("/kozmo/projects", json={
        "name": "My Project",
        "slug": "custom_slug",
    })
    assert resp.status_code == 201
    assert resp.json()["slug"] == "custom_slug"


def test_create_project_duplicate(client, project_slug):
    """Test creating duplicate project returns 409."""
    resp = client.post("/kozmo/projects", json={
        "name": "Test Project",
    })
    assert resp.status_code == 409


def test_list_projects(client, project_slug):
    """Test listing projects."""
    resp = client.get("/kozmo/projects")
    assert resp.status_code == 200
    projects = resp.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["slug"] == project_slug


def test_get_project(client, project_slug):
    """Test getting project manifest."""
    resp = client.get(f"/kozmo/projects/{project_slug}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Project"


def test_get_project_not_found(client):
    """Test getting non-existent project returns 404."""
    resp = client.get("/kozmo/projects/nonexistent")
    assert resp.status_code == 404


def test_delete_project(client, project_slug):
    """Test deleting project."""
    resp = client.delete(f"/kozmo/projects/{project_slug}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == project_slug

    # Verify gone
    resp = client.get(f"/kozmo/projects/{project_slug}")
    assert resp.status_code == 404


def test_delete_project_not_found(client):
    """Test deleting non-existent project returns 404."""
    resp = client.delete("/kozmo/projects/nonexistent")
    assert resp.status_code == 404


# =============================================================================
# Entity Routes
# =============================================================================


def test_create_entity(client, project_slug):
    """Test creating an entity."""
    resp = client.post(f"/kozmo/projects/{project_slug}/entities", json={
        "type": "characters",
        "name": "Mordecai",
        "data": {"age": 28},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "mordecai"
    assert data["name"] == "Mordecai"


def test_create_entity_duplicate(client, project_with_entity):
    """Test creating duplicate entity returns 409."""
    resp = client.post(f"/kozmo/projects/{project_with_entity}/entities", json={
        "type": "characters",
        "name": "Mordecai",
    })
    assert resp.status_code == 409


def test_list_entities(client, project_with_entity):
    """Test listing entities."""
    resp = client.get(f"/kozmo/projects/{project_with_entity}/entities")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_list_entities_by_type(client, project_with_entity):
    """Test listing entities filtered by type."""
    resp = client.get(
        f"/kozmo/projects/{project_with_entity}/entities?entity_type=characters"
    )
    assert resp.status_code == 200
    assert "mordecai" in resp.json()["entities"]


def test_get_entity(client, project_with_entity):
    """Test getting a specific entity."""
    resp = client.get(
        f"/kozmo/projects/{project_with_entity}/entities/characters/mordecai"
    )
    assert resp.status_code == 200
    entity = resp.json()["entity"]
    assert entity["name"] == "Mordecai"
    assert entity["data"]["age"] == 28


def test_get_entity_not_found(client, project_slug):
    """Test getting non-existent entity returns 404."""
    resp = client.get(
        f"/kozmo/projects/{project_slug}/entities/characters/nonexistent"
    )
    assert resp.status_code == 404


def test_update_entity(client, project_with_entity):
    """Test updating an entity."""
    resp = client.put(
        f"/kozmo/projects/{project_with_entity}/entities/characters/mordecai",
        json={"status": "deceased", "data": {"cause_of_death": "magic overdose"}},
    )
    assert resp.status_code == 200

    # Verify update
    resp = client.get(
        f"/kozmo/projects/{project_with_entity}/entities/characters/mordecai"
    )
    entity = resp.json()["entity"]
    assert entity["status"] == "deceased"
    assert entity["data"]["cause_of_death"] == "magic overdose"
    # Original data preserved
    assert entity["data"]["age"] == 28


def test_delete_entity(client, project_with_entity):
    """Test deleting an entity."""
    resp = client.delete(
        f"/kozmo/projects/{project_with_entity}/entities/characters/mordecai"
    )
    assert resp.status_code == 200

    # Verify gone
    resp = client.get(
        f"/kozmo/projects/{project_with_entity}/entities/characters/mordecai"
    )
    assert resp.status_code == 404


def test_delete_entity_not_found(client, project_slug):
    """Test deleting non-existent entity returns 404."""
    resp = client.delete(
        f"/kozmo/projects/{project_slug}/entities/characters/nonexistent"
    )
    assert resp.status_code == 404


# =============================================================================
# Graph Routes
# =============================================================================


def test_graph_stats_empty(client, project_slug):
    """Test graph stats on empty graph."""
    resp = client.get(f"/kozmo/projects/{project_slug}/graph/stats")
    assert resp.status_code == 200
    assert resp.json()["nodes"] == 0


def test_graph_rebuild(client, project_with_entity):
    """Test rebuilding graph from entities."""
    resp = client.post(f"/kozmo/projects/{project_with_entity}/graph/rebuild")
    assert resp.status_code == 200
    assert resp.json()["rebuilt"] is True
    assert resp.json()["stats"]["nodes"] >= 1


def test_graph_path_no_path(client, project_slug):
    """Test graph path when no path exists."""
    resp = client.get(f"/kozmo/projects/{project_slug}/graph/path/a/b")
    assert resp.status_code == 200
    assert resp.json()["path"] is None


# =============================================================================
# Prompt Builder Routes
# =============================================================================


def test_build_prompt(client, project_with_entity):
    """Test building a prompt from shot config."""
    resp = client.post(
        f"/kozmo/projects/{project_with_entity}/prompt/build",
        json={
            "shot": {
                "id": "sh001",
                "scene": "scene_01",
                "name": "Test Shot",
                "camera": {},
                "post": {},
                "prompt": "Exterior of tavern at dusk",
                "characters_present": ["mordecai"],
            },
            "scene_description": "Before the confrontation",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Exterior of tavern at dusk" in data["prompt"]
    assert "Mordecai" in data["prompt"]

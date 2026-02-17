"""
Tests for KOZMO Project Operations

Validates:
- Project creation and directory structure
- Manifest loading/saving
- Entity CRUD within project context
- Template loading/saving
- Project deletion and listing
- Path resolution
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime

from luna.services.kozmo.project import (
    ProjectPaths,
    create_project,
    load_project,
    save_manifest,
    load_entity,
    save_entity_to_project,
    list_entities,
    delete_entity,
    load_template,
    save_template,
    delete_project,
    list_projects,
)
from luna.services.kozmo.types import (
    ProjectManifest,
    ProjectSettings,
    EdenSettings,
    Entity,
    Template,
    TemplateSection,
    TemplateField,
)


# =============================================================================
# ProjectPaths
# =============================================================================


def test_project_paths():
    """Test ProjectPaths path resolution."""
    root = Path("/projects/test_project")
    paths = ProjectPaths(root)

    assert paths.root == root
    assert paths.manifest == root / "manifest.yaml"
    assert paths.entities == root / "entities"
    assert paths.templates == root / "templates"
    assert paths.scripts == root / "scripts"
    assert paths.shots == root / "shots"
    assert paths.assets == root / "assets"
    assert paths.graph_db == root / "test_project.db"


def test_project_paths_entity_dir():
    """Test entity directory resolution."""
    root = Path("/projects/test_project")
    paths = ProjectPaths(root)

    assert paths.entity_dir("characters") == root / "entities" / "characters"
    assert paths.entity_dir("locations") == root / "entities" / "locations"


def test_project_paths_entity_file():
    """Test entity file path resolution."""
    root = Path("/projects/test_project")
    paths = ProjectPaths(root)

    assert (
        paths.entity_file("characters", "mordecai")
        == root / "entities" / "characters" / "mordecai.yaml"
    )


def test_project_paths_template_file():
    """Test template file path resolution."""
    root = Path("/projects/test_project")
    paths = ProjectPaths(root)

    assert (
        paths.template_file("character") == root / "templates" / "character.yaml"
    )


# =============================================================================
# Project Creation
# =============================================================================


def test_create_project_minimal():
    """Test creating minimal project."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        manifest = create_project(
            projects_root=projects_root,
            name="Test Project",
        )

        assert manifest.name == "Test Project"
        assert manifest.slug == "test_project"  # Auto-generated
        assert manifest.version == 1
        assert isinstance(manifest.created, datetime)
        assert isinstance(manifest.updated, datetime)

        # Verify directory structure
        project_root = projects_root / "test_project"
        assert project_root.exists()
        assert (project_root / "manifest.yaml").exists()
        assert (project_root / "entities").exists()
        assert (project_root / "entities" / "characters").exists()
        assert (project_root / "entities" / "locations").exists()
        assert (project_root / "entities" / "props").exists()
        assert (project_root / "entities" / "events").exists()
        assert (project_root / "entities" / "lore").exists()
        assert (project_root / "templates").exists()
        assert (project_root / "scripts").exists()
        assert (project_root / "shots").exists()
        assert (project_root / "assets").exists()


def test_create_project_with_slug():
    """Test creating project with explicit slug."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        manifest = create_project(
            projects_root=projects_root,
            name="The Crooked Nail",
            slug="crooked_nail",
        )

        assert manifest.slug == "crooked_nail"
        assert (projects_root / "crooked_nail").exists()


def test_create_project_with_settings():
    """Test creating project with custom settings."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        settings = ProjectSettings(
            default_camera="red_v_raptor",
            aspect_ratio="16:9",
        )
        eden = EdenSettings(default_agent_id="maya", manna_budget=100.0)

        manifest = create_project(
            projects_root=projects_root,
            name="Test Project",
            settings=settings,
            eden=eden,
        )

        assert manifest.settings.default_camera == "red_v_raptor"
        assert manifest.settings.aspect_ratio == "16:9"
        assert manifest.eden.default_agent_id == "maya"
        assert manifest.eden.manna_budget == 100.0


def test_create_project_duplicate():
    """Test creating duplicate project raises error."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        # Create first project
        create_project(projects_root, "Test Project")

        # Attempt to create duplicate
        with pytest.raises(FileExistsError):
            create_project(projects_root, "Test Project")


# =============================================================================
# Project Loading
# =============================================================================


def test_load_project():
    """Test loading project from manifest."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        # Create project
        original = create_project(projects_root, "Test Project")

        # Load project
        loaded = load_project(projects_root, "test_project")

        assert loaded is not None
        assert loaded.name == original.name
        assert loaded.slug == original.slug
        assert loaded.version == original.version
        assert loaded.settings.default_camera == original.settings.default_camera


def test_load_project_not_found():
    """Test loading non-existent project returns None."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        loaded = load_project(projects_root, "nonexistent")

        assert loaded is None


# =============================================================================
# Manifest Saving
# =============================================================================


def test_save_manifest():
    """Test saving manifest updates timestamp."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        # Create project
        manifest = create_project(projects_root, "Test Project")
        original_updated = manifest.updated

        # Modify and save
        paths = ProjectPaths(projects_root / "test_project")
        manifest.name = "Modified Name"

        # Small delay to ensure timestamp changes
        import time
        time.sleep(0.01)

        save_manifest(paths, manifest)

        # Load and verify
        loaded = load_project(projects_root, "test_project")
        assert loaded.name == "Modified Name"
        assert loaded.updated > original_updated


# =============================================================================
# Entity CRUD
# =============================================================================


def test_save_and_load_entity():
    """Test saving and loading entity within project."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        # Create project
        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        # Create entity
        entity = Entity(
            type="characters",
            name="Mordecai",
            slug="mordecai",
            data={"age": 28},
        )

        # Save entity
        save_entity_to_project(paths, entity)

        # Verify file exists
        entity_file = paths.entity_file("characters", "mordecai")
        assert entity_file.exists()

        # Load entity
        result = load_entity(paths, "characters", "mordecai")
        assert result.entity is not None
        assert result.entity.name == "Mordecai"
        assert result.entity.data["age"] == 28


def test_load_entity_not_found():
    """Test loading non-existent entity returns error."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        result = load_entity(paths, "characters", "nonexistent")
        assert result.entity is None
        assert result.error is not None


def test_list_entities():
    """Test listing entities in project."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        # Create entities
        entities = [
            Entity(type="characters", name="Mordecai", slug="mordecai"),
            Entity(type="characters", name="Cornelius", slug="cornelius"),
            Entity(type="locations", name="The Crooked Nail", slug="crooked_nail"),
        ]

        for entity in entities:
            save_entity_to_project(paths, entity)

        # List characters
        characters = list_entities(paths, "characters")
        assert len(characters) == 2
        assert "mordecai" in characters
        assert "cornelius" in characters

        # List locations
        locations = list_entities(paths, "locations")
        assert len(locations) == 1
        assert "crooked_nail" in locations

        # List all entities
        all_entities = list_entities(paths)
        assert len(all_entities) == 3


def test_list_entities_empty():
    """Test listing entities in empty project."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        entities = list_entities(paths, "characters")
        assert len(entities) == 0


def test_delete_entity():
    """Test deleting entity from project."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        # Create entity
        entity = Entity(type="characters", name="Mordecai", slug="mordecai")
        save_entity_to_project(paths, entity)

        # Verify exists
        assert paths.entity_file("characters", "mordecai").exists()

        # Delete
        deleted = delete_entity(paths, "characters", "mordecai")
        assert deleted is True

        # Verify deleted
        assert not paths.entity_file("characters", "mordecai").exists()


def test_delete_entity_not_found():
    """Test deleting non-existent entity returns False."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        deleted = delete_entity(paths, "characters", "nonexistent")
        assert deleted is False


# =============================================================================
# Template Loading/Saving
# =============================================================================


def test_save_and_load_template():
    """Test saving and loading template."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        # Create template
        template = Template(
            type="character",
            version=1,
            sections=[
                TemplateSection(
                    name="physical",
                    dynamic=True,
                    fields=[
                        TemplateField(key="age", type="int", required=False),
                        TemplateField(
                            key="build",
                            type="string",
                            required=True,
                            description="Physical build",
                        ),
                    ],
                )
            ],
        )

        # Save template
        save_template(paths, template)

        # Verify file exists
        assert paths.template_file("character").exists()

        # Load template
        loaded = load_template(paths, "character")
        assert loaded is not None
        assert loaded.type == "character"
        assert loaded.version == 1
        assert len(loaded.sections) == 1
        assert loaded.sections[0].name == "physical"
        assert len(loaded.sections[0].fields) == 2
        assert loaded.sections[0].fields[0].key == "age"
        assert loaded.sections[0].fields[1].required is True


def test_load_template_not_found():
    """Test loading non-existent template returns None."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        create_project(projects_root, "Test Project")
        paths = ProjectPaths(projects_root / "test_project")

        template = load_template(paths, "nonexistent")
        assert template is None


# =============================================================================
# Project Deletion
# =============================================================================


def test_delete_project():
    """Test deleting project."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        # Create project
        create_project(projects_root, "Test Project")
        project_root = projects_root / "test_project"

        # Verify exists
        assert project_root.exists()

        # Delete
        deleted = delete_project(projects_root, "test_project")
        assert deleted is True

        # Verify deleted
        assert not project_root.exists()


def test_delete_project_not_found():
    """Test deleting non-existent project returns False."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        deleted = delete_project(projects_root, "nonexistent")
        assert deleted is False


# =============================================================================
# Project Listing
# =============================================================================


def test_list_projects():
    """Test listing all projects."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        # Create projects
        create_project(projects_root, "Project One")
        create_project(projects_root, "Project Two")
        create_project(projects_root, "Project Three")

        # List
        projects = list_projects(projects_root)
        assert len(projects) == 3
        assert "project_one" in projects
        assert "project_two" in projects
        assert "project_three" in projects


def test_list_projects_empty():
    """Test listing projects in empty directory."""
    with TemporaryDirectory() as tmpdir:
        projects_root = Path(tmpdir)

        projects = list_projects(projects_root)
        assert len(projects) == 0


def test_list_projects_nonexistent_root():
    """Test listing projects when root doesn't exist."""
    projects = list_projects(Path("/nonexistent"))
    assert len(projects) == 0

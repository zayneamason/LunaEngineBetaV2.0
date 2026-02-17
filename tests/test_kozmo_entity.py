"""
Tests for KOZMO Entity Operations

Validates:
- Slug generation from various name formats
- YAML parsing (minimal, full, malformed)
- Graceful error handling (parse_entity_safe)
- Template validation
- YAML serialization round-trip
- File save/load operations
"""

import pytest
import yaml
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.services.kozmo.entity import (
    slugify,
    parse_entity,
    parse_entity_safe,
    validate_entity,
    entity_to_yaml,
    save_entity,
)
from luna.services.kozmo.types import (
    Entity,
    Template,
    TemplateSection,
    TemplateField,
    Relationship,
    EntityReferences,
)


# =============================================================================
# Slug Generation
# =============================================================================


def test_slugify_basic():
    """Test basic slug generation."""
    assert slugify("Mordecai The Unwise") == "mordecai_the_unwise"


def test_slugify_with_hyphens():
    """Test slug generation with hyphens."""
    assert slugify("Princess-of-Shadows") == "princess_of_shadows"


def test_slugify_mixed_case():
    """Test slug generation with mixed case."""
    assert slugify("The Crooked Nail") == "the_crooked_nail"


def test_slugify_with_special_chars():
    """Test slug generation removes special characters."""
    assert slugify("Cornelius's Tavern!") == "corneliuss_tavern"


def test_slugify_multiple_spaces():
    """Test slug generation collapses multiple spaces."""
    assert slugify("The    Grand   Hall") == "the_grand_hall"


def test_slugify_leading_trailing():
    """Test slug generation strips leading/trailing underscores."""
    assert slugify("  The Chapel  ") == "the_chapel"


def test_slugify_numbers():
    """Test slug generation preserves numbers."""
    assert slugify("Room 237") == "room_237"


def test_slugify_empty():
    """Test slug generation with empty string."""
    assert slugify("") == ""


# =============================================================================
# YAML Parsing - Valid Cases
# =============================================================================


def test_parse_entity_minimal(tmp_path):
    """Test parsing minimal entity YAML."""
    yaml_content = """
type: character
name: Test Character
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    entity = parse_entity(entity_file)

    assert entity.type == "character"
    assert entity.name == "Test Character"
    assert entity.slug == "test_character"  # Auto-generated
    assert entity.status == "active"  # Default


def test_parse_entity_with_slug(tmp_path):
    """Test parsing entity with explicit slug."""
    yaml_content = """
type: character
name: Mordecai
slug: mordecai_the_unwise
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    entity = parse_entity(entity_file)

    assert entity.slug == "mordecai_the_unwise"


def test_parse_entity_full(tmp_path):
    """Test parsing entity with all fields."""
    yaml_content = """
type: character
name: Mordecai
slug: mordecai
status: active
age: 28
build: lean, angular
relationships:
  - entity: cornelius
    type: family
    detail: Father. Protective. Overbearing.
references:
  images:
    - assets/reference/mordecai_v1.png
  lora: mordecai_lora_v1
scenes:
  - scene_01
  - scene_02
tags:
  - main_cast
  - magic_sector
luna_notes: |
  Addiction is to numbness, not magic.
  Core wound: rejection by father.
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    entity = parse_entity(entity_file)

    assert entity.name == "Mordecai"
    assert entity.data["age"] == 28
    assert entity.data["build"] == "lean, angular"
    assert len(entity.relationships) == 1
    assert entity.relationships[0].entity == "cornelius"
    assert len(entity.references.images) == 1
    assert entity.references.lora == "mordecai_lora_v1"
    assert len(entity.scenes) == 2
    assert len(entity.tags) == 2
    assert "rejection by father" in entity.luna_notes


def test_parse_entity_with_template_fields(tmp_path):
    """Test parsing entity with extra template fields."""
    yaml_content = """
type: character
name: Test
physical_age: 30
voice_pattern: eloquent
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    entity = parse_entity(entity_file)

    # Extra fields should go into data dict
    assert entity.data["physical_age"] == 30
    assert entity.data["voice_pattern"] == "eloquent"


# =============================================================================
# YAML Parsing - Error Cases
# =============================================================================


def test_parse_entity_file_not_found():
    """Test parsing non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_entity(Path("/nonexistent/file.yaml"))


def test_parse_entity_empty_yaml(tmp_path):
    """Test parsing empty YAML raises ValueError."""
    entity_file = tmp_path / "empty.yaml"
    entity_file.write_text("")

    with pytest.raises(ValueError, match="Empty YAML file"):
        parse_entity(entity_file)


def test_parse_entity_missing_name(tmp_path):
    """Test parsing without 'name' field raises ValueError."""
    yaml_content = """
type: character
slug: test
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    with pytest.raises(ValueError, match="Missing required field 'name'"):
        parse_entity(entity_file)


def test_parse_entity_invalid_yaml(tmp_path):
    """Test parsing invalid YAML raises YAMLError."""
    # Use truly invalid YAML (unclosed bracket, invalid syntax)
    yaml_content = "type: character\nname: [unclosed"
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    with pytest.raises(yaml.YAMLError):
        parse_entity(entity_file)


# =============================================================================
# Graceful Parsing (parse_entity_safe)
# =============================================================================


def test_parse_entity_safe_success(tmp_path):
    """Test parse_entity_safe with valid YAML."""
    yaml_content = """
type: character
name: Test
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    result = parse_entity_safe(entity_file)

    assert result.entity is not None
    assert result.entity.name == "Test"
    assert len(result.warnings) == 0
    assert result.error is None


def test_parse_entity_safe_with_warnings(tmp_path):
    """Test parse_entity_safe with validation warnings."""
    yaml_content = """
type: character
name: Test
age: 30
unknown_field: value
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    # Create template with required field (use template fields, not core Entity fields)
    template = Template(
        type="character",
        version=1,
        sections=[
            TemplateSection(
                name="physical",
                fields=[
                    TemplateField(key="age", type="int", required=False),
                    TemplateField(key="build", type="string", required=True),  # Missing
                ],
            )
        ],
    )

    result = parse_entity_safe(entity_file, template)

    assert result.entity is not None
    assert len(result.warnings) > 0
    # Should warn about missing required 'build' and unknown 'unknown_field'
    assert any("build" in w for w in result.warnings)
    assert any("unknown_field" in w for w in result.warnings)
    assert result.error is None


def test_parse_entity_safe_fatal_error(tmp_path):
    """Test parse_entity_safe with fatal error."""
    entity_file = tmp_path / "nonexistent.yaml"

    result = parse_entity_safe(entity_file)

    assert result.entity is None
    assert result.error is not None
    assert "not found" in result.error


def test_parse_entity_safe_yaml_error(tmp_path):
    """Test parse_entity_safe with YAML syntax error."""
    yaml_content = """
type: character
  invalid: indentation
"""
    entity_file = tmp_path / "test.yaml"
    entity_file.write_text(yaml_content)

    result = parse_entity_safe(entity_file)

    assert result.entity is None
    assert result.error is not None
    assert "YAML syntax error" in result.error


# =============================================================================
# Entity Validation
# =============================================================================


def test_validate_entity_no_warnings():
    """Test validation with compliant entity."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30, "status": "active"},
    )

    template = Template(
        type="character",
        version=1,
        sections=[
            TemplateSection(
                name="identity",
                fields=[
                    TemplateField(key="name", type="string", required=True),
                    TemplateField(key="age", type="int", required=False),
                    TemplateField(key="status", type="string", required=False),
                ],
            )
        ],
    )

    warnings = validate_entity(entity, template)

    assert len(warnings) == 0


def test_validate_entity_missing_required():
    """Test validation warns about missing required fields."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30},
    )

    template = Template(
        type="character",
        version=1,
        sections=[
            TemplateSection(
                name="physical",
                fields=[
                    TemplateField(key="age", type="int", required=False),
                    TemplateField(key="build", type="string", required=True),  # Missing
                ],
            )
        ],
    )

    warnings = validate_entity(entity, template)

    assert len(warnings) == 1
    assert "Missing required field: build" in warnings


def test_validate_entity_unknown_fields():
    """Test validation warns about unknown fields."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30, "unknown_field": "value"},
    )

    template = Template(
        type="character",
        version=1,
        sections=[
            TemplateSection(
                name="identity",
                fields=[
                    TemplateField(key="age", type="int", required=False),
                ],
            )
        ],
    )

    warnings = validate_entity(entity, template)

    assert len(warnings) == 1
    assert "Unknown field not in template: unknown_field" in warnings


# =============================================================================
# YAML Serialization
# =============================================================================


def test_entity_to_yaml_minimal():
    """Test serializing minimal entity to YAML."""
    entity = Entity(
        type="character",
        name="Test Character",
        slug="test_character",
    )

    yaml_str = entity_to_yaml(entity)
    data = yaml.safe_load(yaml_str)

    assert data["type"] == "character"
    assert data["name"] == "Test Character"
    # status should not appear (default value)
    assert "status" not in data


def test_entity_to_yaml_full():
    """Test serializing full entity to YAML."""
    entity = Entity(
        type="character",
        name="Mordecai",
        slug="mordecai",
        status="active",
        data={"age": 28, "build": "lean"},
        relationships=[
            Relationship(entity="cornelius", type="family", detail="Father")
        ],
        references=EntityReferences(images=["ref.png"]),
        scenes=["scene_01"],
        tags=["main_cast"],
        luna_notes="Test note",
    )

    yaml_str = entity_to_yaml(entity)
    data = yaml.safe_load(yaml_str)

    assert data["name"] == "Mordecai"
    assert data["age"] == 28
    assert data["build"] == "lean"
    assert len(data["relationships"]) == 1
    assert data["relationships"][0]["entity"] == "cornelius"
    assert len(data["references"]["images"]) == 1
    assert len(data["scenes"]) == 1
    assert len(data["tags"]) == 1
    assert data["luna_notes"] == "Test note"


def test_entity_to_yaml_key_order():
    """Test YAML serialization preserves key order."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30},
        tags=["tag1"],
    )

    yaml_str = entity_to_yaml(entity)
    lines = yaml_str.strip().split("\n")

    # type and name should be first
    assert lines[0].startswith("type:")
    assert lines[1].startswith("name:")


def test_entity_to_yaml_luna_notes_last():
    """Test luna_notes appears at end of YAML."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30},
        luna_notes="Last field",
    )

    yaml_str = entity_to_yaml(entity)
    lines = yaml_str.strip().split("\n")

    # luna_notes should be last line
    assert lines[-1].startswith("luna_notes:")


# =============================================================================
# File Save/Load Round-trip
# =============================================================================


def test_save_entity(tmp_path):
    """Test saving entity to file."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30},
    )

    entity_file = tmp_path / "test.yaml"
    save_entity(entity, entity_file)

    # Verify file was created
    assert entity_file.exists()

    # Verify content
    with open(entity_file) as f:
        data = yaml.safe_load(f)
    assert data["name"] == "Test"
    assert data["age"] == 30


def test_round_trip(tmp_path):
    """Test save → load round-trip preserves data."""
    original = Entity(
        type="character",
        name="Mordecai",
        slug="mordecai",
        status="active",
        data={"age": 28, "build": "lean"},
        relationships=[
            Relationship(entity="cornelius", type="family", detail="Father")
        ],
        references=EntityReferences(images=["ref.png"], lora="lora_v1"),
        scenes=["scene_01", "scene_02"],
        tags=["main_cast"],
        luna_notes="Test note",
    )

    # Save
    entity_file = tmp_path / "test.yaml"
    save_entity(original, entity_file)

    # Load
    loaded = parse_entity(entity_file)

    # Verify
    assert loaded.type == original.type
    assert loaded.name == original.name
    assert loaded.slug == original.slug
    assert loaded.status == original.status
    assert loaded.data["age"] == original.data["age"]
    assert loaded.data["build"] == original.data["build"]
    assert len(loaded.relationships) == len(original.relationships)
    assert loaded.relationships[0].entity == original.relationships[0].entity
    assert loaded.references.images == original.references.images
    assert loaded.references.lora == original.references.lora
    assert loaded.scenes == original.scenes
    assert loaded.tags == original.tags
    assert loaded.luna_notes == original.luna_notes


def test_round_trip_with_template_validation(tmp_path):
    """Test round-trip with template validation."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        data={"age": 30, "status": "active"},
    )

    template = Template(
        type="character",
        version=1,
        sections=[
            TemplateSection(
                name="identity",
                fields=[
                    TemplateField(key="age", type="int", required=False),
                    TemplateField(key="status", type="string", required=True),
                ],
            )
        ],
    )

    # Save
    entity_file = tmp_path / "test.yaml"
    save_entity(entity, entity_file)

    # Load with validation
    result = parse_entity_safe(entity_file, template)

    assert result.entity is not None
    assert len(result.warnings) == 0  # Should be valid
    assert result.error is None

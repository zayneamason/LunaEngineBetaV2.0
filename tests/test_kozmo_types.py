"""
Tests for KOZMO Type Definitions

Validates:
- Model instantiation
- YAML serialization/deserialization
- Field validation
- Defaults
- Nested model construction
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from luna.services.kozmo.types import (
    ProjectManifest,
    ProjectSettings,
    EdenSettings,
    Entity,
    Relationship,
    EntityReferences,
    ShotConfig,
    CameraConfig,
    PostConfig,
    HeroFrame,
    Template,
    TemplateSection,
    TemplateField,
    FountainScene,
    FountainDocument,
    DispatchRequest,
    QueueEntry,
    EntityLoadResult,
)


# =============================================================================
# Project Models
# =============================================================================


def test_project_settings_defaults():
    """Test ProjectSettings default values."""
    settings = ProjectSettings()
    assert settings.default_camera == "arri_alexa35"
    assert settings.default_lens == "cooke_s7i"
    assert settings.default_film_stock == "kodak_5219"
    assert settings.aspect_ratio == "21:9"


def test_project_settings_custom():
    """Test ProjectSettings with custom values."""
    settings = ProjectSettings(
        default_camera="red_v_raptor",
        default_lens="zeiss_supreme",
        default_film_stock="fuji_eterna",
        aspect_ratio="16:9",
    )
    assert settings.default_camera == "red_v_raptor"
    assert settings.default_lens == "zeiss_supreme"


def test_eden_settings():
    """Test EdenSettings model."""
    eden = EdenSettings(default_agent_id="maya", manna_budget=50.0)
    assert eden.default_agent_id == "maya"
    assert eden.manna_budget == 50.0


def test_project_manifest():
    """Test ProjectManifest construction."""
    now = datetime.now()
    manifest = ProjectManifest(
        name="Test Project",
        slug="test_project",
        version=1,
        created=now,
        updated=now,
        settings=ProjectSettings(),
        eden=EdenSettings(),
    )
    assert manifest.name == "Test Project"
    assert manifest.slug == "test_project"
    assert len(manifest.entity_types) == 5  # Default types


def test_project_manifest_json_serialization():
    """Test ProjectManifest can serialize to JSON."""
    now = datetime.now()
    manifest = ProjectManifest(
        name="Test",
        slug="test",
        created=now,
        updated=now,
        settings=ProjectSettings(),
    )
    json_data = manifest.model_dump(mode="json")
    assert json_data["name"] == "Test"
    assert json_data["slug"] == "test"


# =============================================================================
# Entity Models
# =============================================================================


def test_relationship():
    """Test Relationship model."""
    rel = Relationship(
        entity="cornelius",
        type="family",
        detail="Father. Protective. Overbearing.",
    )
    assert rel.entity == "cornelius"
    assert rel.type == "family"
    assert rel.detail is not None


def test_entity_references():
    """Test EntityReferences model."""
    refs = EntityReferences(
        images=["assets/reference/mordecai_v1.png"],
        lora="mordecai_lora_v1",
    )
    assert len(refs.images) == 1
    assert refs.lora == "mordecai_lora_v1"


def test_entity_minimal():
    """Test Entity with minimal required fields."""
    entity = Entity(
        type="character",
        name="Test Character",
        slug="test_character",
    )
    assert entity.type == "character"
    assert entity.name == "Test Character"
    assert entity.status == "active"  # Default
    assert len(entity.relationships) == 0  # Default empty list


def test_entity_full():
    """Test Entity with all fields."""
    entity = Entity(
        type="character",
        name="Mordecai",
        slug="mordecai",
        status="active",
        data={"age": 28, "build": "lean, angular"},
        relationships=[
            Relationship(entity="cornelius", type="family", detail="Father")
        ],
        references=EntityReferences(images=["ref.png"]),
        scenes=["scene_01", "scene_02"],
        tags=["main_cast", "magic_sector"],
        luna_notes="Addiction is to numbness, not magic.",
    )
    assert entity.name == "Mordecai"
    assert len(entity.relationships) == 1
    assert len(entity.scenes) == 2
    assert entity.luna_notes is not None


def test_entity_extra_fields():
    """Test Entity allows extra fields (from templates)."""
    entity = Entity(
        type="character",
        name="Test",
        slug="test",
        physical_age=30,  # Extra field
        voice_pattern="eloquent",  # Extra field
    )
    # Pydantic Config extra="allow" should permit these
    assert entity.name == "Test"


# =============================================================================
# Shot Models
# =============================================================================


def test_camera_config_defaults():
    """Test CameraConfig default values."""
    camera = CameraConfig()
    assert camera.body == "arri_alexa35"
    assert camera.lens == "cooke_s7i"
    assert camera.focal_mm == 50
    assert camera.aperture == 2.8
    assert camera.movement == ["static"]
    assert camera.duration_sec == 3.0


def test_camera_config_custom():
    """Test CameraConfig with custom values."""
    camera = CameraConfig(
        body="red_v_raptor",
        lens="panavision_c",
        focal_mm=40,
        aperture=2.0,
        movement=["dolly_in", "pan_right"],
        duration_sec=5.0,
    )
    assert camera.body == "red_v_raptor"
    assert len(camera.movement) == 2


def test_camera_config_max_movements_valid():
    """Test CameraConfig accepts up to 3 movements."""
    camera = CameraConfig(movement=["dolly_in", "pan_left", "tilt_up"])
    camera.validate_movement()  # Should not raise


def test_camera_config_max_movements_invalid():
    """Test CameraConfig rejects more than 3 movements."""
    camera = CameraConfig(
        movement=["dolly_in", "pan_left", "tilt_up", "crane_up"]  # 4 movements
    )
    with pytest.raises(ValueError, match="Max 3 camera movements"):
        camera.validate_movement()


def test_post_config_defaults():
    """Test PostConfig default values."""
    post = PostConfig()
    assert post.film_stock == "kodak_5219"
    assert post.color_temp_k == 5600
    assert post.grain_pct == 0


def test_hero_frame():
    """Test HeroFrame model."""
    now = datetime.now()
    hero = HeroFrame(
        path="assets/hero_frames/sh001_v1.png",
        eden_task_id="task_abc123",
        approved=True,
        approved_at=now,
    )
    assert hero.approved is True
    assert hero.eden_task_id == "task_abc123"


def test_shot_config():
    """Test ShotConfig construction."""
    shot = ShotConfig(
        id="sh001",
        scene="scene_01",
        name="Establishing Shot",
        status="approved",
        camera=CameraConfig(),
        post=PostConfig(),
        prompt="Exterior of a tavern at dusk.",
        characters_present=["cornelius", "mordecai"],
        location="crooked_nail",
    )
    assert shot.id == "sh001"
    assert shot.status == "approved"
    assert len(shot.characters_present) == 2


# =============================================================================
# Template Models
# =============================================================================


def test_template_field():
    """Test TemplateField model."""
    field = TemplateField(
        key="name",
        type="string",
        required=True,
    )
    assert field.key == "name"
    assert field.required is True


def test_template_field_enum():
    """Test TemplateField with enum options."""
    field = TemplateField(
        key="status",
        type="enum",
        options=["active", "deceased", "unknown"],
    )
    assert len(field.options) == 3


def test_template_section():
    """Test TemplateSection model."""
    section = TemplateSection(
        name="physical",
        dynamic=True,
        fields=[
            TemplateField(key="age", type="int"),
            TemplateField(key="build", type="string"),
        ],
    )
    assert section.name == "physical"
    assert section.dynamic is True
    assert len(section.fields) == 2


def test_template():
    """Test Template model."""
    template = Template(
        type="character",
        version=1,
        sections=[
            TemplateSection(
                name="identity",
                fields=[TemplateField(key="name", type="string", required=True)],
            )
        ],
    )
    assert template.type == "character"
    assert len(template.sections) == 1


# =============================================================================
# Fountain Models
# =============================================================================


def test_fountain_scene():
    """Test FountainScene model."""
    scene = FountainScene(
        header="INT. THE CROOKED NAIL - EVENING",
        characters_present=["CORNELIUS", "MORDECAI"],
        has_dialogue={"CORNELIUS": 2, "MORDECAI": 1},
    )
    assert "CROOKED NAIL" in scene.header
    assert len(scene.characters_present) == 2


def test_fountain_document():
    """Test FountainDocument model."""
    doc = FountainDocument(
        scenes=[
            FountainScene(
                header="INT. TAVERN - NIGHT",
                characters_present=["CORNELIUS"],
            )
        ],
        characters=["CORNELIUS", "MORDECAI", "CONSTANCE"],
    )
    assert len(doc.scenes) == 1
    assert len(doc.characters) == 3


# =============================================================================
# Dispatch Models
# =============================================================================


def test_dispatch_request():
    """Test DispatchRequest model."""
    req = DispatchRequest(
        action="generate_image",
        project_slug="test_project",
        entity_slug="mordecai",
        prompt="Lean wizard with burn scars",
    )
    assert req.action == "generate_image"
    assert req.entity_slug == "mordecai"


def test_queue_entry():
    """Test QueueEntry model."""
    now = datetime.now()
    entry = QueueEntry(
        task_id="task_001",
        eden_task_id="eden_abc123",
        action="generate_image",
        status="completed",
        project_slug="test_project",
        entity_slug="mordecai",
        result_url="https://example.com/result.png",
        saved_path="assets/reference/mordecai_v1.png",
        created_at=now,
        completed_at=now,
    )
    assert entry.status == "completed"
    assert entry.result_url is not None


# =============================================================================
# Entity Load Result
# =============================================================================


def test_entity_load_result_success():
    """Test EntityLoadResult with successful load."""
    entity = Entity(type="character", name="Test", slug="test")
    result = EntityLoadResult(entity=entity, warnings=[], error=None)
    assert result.entity is not None
    assert len(result.warnings) == 0


def test_entity_load_result_warnings():
    """Test EntityLoadResult with warnings."""
    entity = Entity(type="character", name="Test", slug="test")
    result = EntityLoadResult(
        entity=entity,
        warnings=["Missing optional field 'age'", "Unknown field 'foo'"],
    )
    assert result.entity is not None
    assert len(result.warnings) == 2


def test_entity_load_result_failure():
    """Test EntityLoadResult with fatal error."""
    result = EntityLoadResult(
        entity=None,
        error="YAML syntax error: invalid indentation",
    )
    assert result.entity is None
    assert result.error is not None

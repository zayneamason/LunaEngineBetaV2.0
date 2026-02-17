"""
Tests for KOZMO Prompt Builder

Validates:
- Camera description generation
- Character description injection
- Post-processing directives
- Full shot prompt assembly
- LoRA and reference image collection
"""

import pytest

from luna.services.kozmo.prompt_builder import (
    build_shot_prompt,
    build_camera_description,
    build_character_descriptions,
    build_post_description,
    get_lora_references,
    get_reference_images,
)
from luna.services.kozmo.types import (
    ShotConfig,
    CameraConfig,
    PostConfig,
    Entity,
    EntityReferences,
)


# =============================================================================
# Helpers
# =============================================================================


def _default_shot(**overrides) -> ShotConfig:
    """Create test shot with defaults."""
    defaults = dict(
        id="sh001",
        scene="scene_01",
        name="Test Shot",
        camera=CameraConfig(),
        post=PostConfig(),
        prompt="Exterior of a tavern at dusk",
    )
    defaults.update(overrides)
    return ShotConfig(**defaults)


def _make_entity(slug, name=None, **data_fields) -> Entity:
    """Create test entity with data fields."""
    return Entity(
        type="characters",
        name=name or slug.replace("_", " ").title(),
        slug=slug,
        data=data_fields,
    )


# =============================================================================
# Camera Description
# =============================================================================


def test_camera_description_defaults():
    """Test camera description with default config."""
    camera = CameraConfig()
    desc = build_camera_description(camera)

    assert "ARRI ALEXA35" in desc
    assert "Cooke S7I" in desc
    assert "50mm" in desc
    assert "f/2.8" in desc


def test_camera_description_custom():
    """Test camera description with custom config."""
    camera = CameraConfig(
        body="red_v_raptor",
        lens="panavision_c",
        focal_mm=40,
        aperture=2.0,
        movement=["dolly_in", "pan_right"],
    )
    desc = build_camera_description(camera)

    assert "RED V RAPTOR" in desc
    assert "Panavision C" in desc
    assert "40mm" in desc
    assert "f/2.0" in desc
    assert "pushing in" in desc
    assert "panning right" in desc


def test_camera_description_unknown_body():
    """Test camera with unknown body (no look descriptor)."""
    camera = CameraConfig(body="custom_camera")
    desc = build_camera_description(camera)

    # Should still have focal length and aperture
    assert "50mm" in desc
    assert "f/2.8" in desc


# =============================================================================
# Character Descriptions
# =============================================================================


def test_character_descriptions():
    """Test building character descriptions from entities."""
    entities = {
        "mordecai": _make_entity("mordecai", build="lean, angular", age=28),
        "cornelius": _make_entity("cornelius", build="stocky, broad"),
    }

    desc = build_character_descriptions(
        ["mordecai", "cornelius"], entities
    )

    assert "Mordecai" in desc
    assert "lean, angular" in desc
    assert "age 28" in desc
    assert "Cornelius" in desc
    assert "stocky, broad" in desc


def test_character_descriptions_missing_entity():
    """Test character descriptions skip missing entities."""
    entities = {
        "mordecai": _make_entity("mordecai", build="lean"),
    }

    desc = build_character_descriptions(
        ["mordecai", "nonexistent"], entities
    )

    assert "Mordecai" in desc
    assert "nonexistent" not in desc


def test_character_descriptions_no_entities():
    """Test character descriptions with empty entities."""
    desc = build_character_descriptions(["mordecai"], {})

    assert desc == ""


def test_character_descriptions_with_appearance():
    """Test character descriptions include appearance field."""
    entities = {
        "mordecai": _make_entity(
            "mordecai",
            appearance="burn scars on forearms, dark circles under eyes",
        ),
    }

    desc = build_character_descriptions(["mordecai"], entities)

    assert "burn scars" in desc


# =============================================================================
# Post-Processing Description
# =============================================================================


def test_post_description_defaults():
    """Test post description with default config."""
    post = PostConfig()
    desc = build_post_description(post)

    # Default film stock should produce description
    assert "500T tungsten" in desc


def test_post_description_with_grain():
    """Test post description with grain."""
    post = PostConfig(grain_pct=30)
    desc = build_post_description(post)

    assert "moderate film grain" in desc


def test_post_description_warm_temp():
    """Test post description with warm color temp."""
    post = PostConfig(color_temp_k=3200)
    desc = build_post_description(post)

    assert "warm tungsten" in desc


def test_post_description_bloom_halation():
    """Test post description with bloom and halation."""
    post = PostConfig(bloom_pct=15, halation_pct=10)
    desc = build_post_description(post)

    assert "bloom" in desc
    assert "halation" in desc


def test_post_description_bw_film():
    """Test post description with black and white film stock."""
    post = PostConfig(film_stock="kodak_5222")
    desc = build_post_description(post)

    assert "black and white" in desc


# =============================================================================
# Full Shot Prompt
# =============================================================================


def test_build_shot_prompt_minimal():
    """Test building prompt with minimal shot config."""
    shot = _default_shot()
    prompt = build_shot_prompt(shot)

    assert "Exterior of a tavern at dusk" in prompt
    assert "ARRI ALEXA35" in prompt


def test_build_shot_prompt_with_characters():
    """Test building prompt with character entities."""
    entities = {
        "mordecai": _make_entity("mordecai", build="lean, angular"),
    }
    shot = _default_shot(characters_present=["mordecai"])

    prompt = build_shot_prompt(shot, entities=entities)

    assert "Mordecai" in prompt
    assert "lean, angular" in prompt


def test_build_shot_prompt_with_scene_context():
    """Test building prompt with scene description."""
    shot = _default_shot()

    prompt = build_shot_prompt(
        shot, scene_description="Tension before the confrontation"
    )

    assert "Scene context: Tension before the confrontation" in prompt


def test_build_shot_prompt_full():
    """Test building prompt with all components."""
    entities = {
        "mordecai": _make_entity("mordecai", build="lean, angular", age=28),
    }
    shot = _default_shot(
        prompt="Close-up of Mordecai's face, firelight reflecting in his eyes",
        camera=CameraConfig(
            focal_mm=85,
            aperture=1.4,
            movement=["dolly_in"],
        ),
        post=PostConfig(grain_pct=15, bloom_pct=10),
        characters_present=["mordecai"],
    )

    prompt = build_shot_prompt(
        shot,
        entities=entities,
        scene_description="Mordecai confronts his father",
    )

    # All components present
    assert "Close-up of Mordecai's face" in prompt
    assert "85mm" in prompt
    assert "f/1.4" in prompt
    assert "Mordecai" in prompt
    assert "lean, angular" in prompt
    assert "confronts his father" in prompt
    assert "grain" in prompt
    assert "bloom" in prompt


# =============================================================================
# LoRA and Reference Images
# =============================================================================


def test_get_lora_references():
    """Test collecting LoRA references."""
    entities = {
        "mordecai": Entity(
            type="characters",
            name="Mordecai",
            slug="mordecai",
            references=EntityReferences(lora="mordecai_lora_v1"),
        ),
        "cornelius": Entity(
            type="characters",
            name="Cornelius",
            slug="cornelius",
            references=EntityReferences(lora="cornelius_lora_v2"),
        ),
    }

    loras = get_lora_references(["mordecai", "cornelius"], entities)

    assert len(loras) == 2
    assert "mordecai_lora_v1" in loras
    assert "cornelius_lora_v2" in loras


def test_get_lora_references_missing():
    """Test LoRA references skip entities without LoRA."""
    entities = {
        "mordecai": Entity(
            type="characters",
            name="Mordecai",
            slug="mordecai",
            references=EntityReferences(lora="mordecai_lora_v1"),
        ),
        "guard": Entity(
            type="characters",
            name="Guard",
            slug="guard",
        ),
    }

    loras = get_lora_references(["mordecai", "guard"], entities)

    assert len(loras) == 1
    assert "mordecai_lora_v1" in loras


def test_get_reference_images():
    """Test collecting reference images."""
    entities = {
        "mordecai": Entity(
            type="characters",
            name="Mordecai",
            slug="mordecai",
            references=EntityReferences(
                images=["ref/mordecai_v1.png", "ref/mordecai_v2.png"]
            ),
        ),
    }

    images = get_reference_images(["mordecai"], entities)

    assert len(images) == 2
    assert "ref/mordecai_v1.png" in images


def test_get_reference_images_empty():
    """Test reference images with no references."""
    entities = {
        "guard": Entity(type="characters", name="Guard", slug="guard"),
    }

    images = get_reference_images(["guard"], entities)

    assert len(images) == 0

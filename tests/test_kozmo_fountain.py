"""
Tests for KOZMO Fountain Screenplay Parser

Validates:
- Scene header parsing (INT./EXT., location, time of day)
- Character name detection
- Dialogue counting
- Multi-scene documents
- Title page extraction
- Utility functions (scenes_for_character, dialogue_count)
- File loading
"""

import pytest
from pathlib import Path

from luna.services.kozmo.fountain import (
    parse_fountain,
    parse_fountain_file,
    _parse_scene_header,
    extract_characters,
    scenes_for_character,
    dialogue_count,
)
from luna.services.kozmo.types import FountainScene, FountainDocument


# =============================================================================
# Scene Header Parsing
# =============================================================================


def test_parse_scene_header_interior():
    """Test parsing interior scene header."""
    location, time = _parse_scene_header("INT. THE CROOKED NAIL - EVENING")
    assert location == "THE CROOKED NAIL"
    assert time == "EVENING"


def test_parse_scene_header_exterior():
    """Test parsing exterior scene header."""
    location, time = _parse_scene_header("EXT. CITY STREETS - DAY")
    assert location == "CITY STREETS"
    assert time == "DAY"


def test_parse_scene_header_no_time():
    """Test parsing scene header without time of day."""
    location, time = _parse_scene_header("INT. CARRIAGE")
    assert location == "CARRIAGE"
    assert time is None


def test_parse_scene_header_int_ext():
    """Test parsing INT./EXT. scene header."""
    location, time = _parse_scene_header("INT./EXT. DOORWAY - NIGHT")
    assert location == "DOORWAY"
    assert time == "NIGHT"


# =============================================================================
# Single Scene Parsing
# =============================================================================


SIMPLE_SCENE = """
INT. THE CROOKED NAIL - EVENING

CORNELIUS
You're late again.

MORDECAI
I was detained.

CORNELIUS
By a bottle, no doubt.
"""


def test_parse_simple_scene():
    """Test parsing a simple scene with dialogue."""
    doc = parse_fountain(SIMPLE_SCENE)

    assert len(doc.scenes) == 1

    scene = doc.scenes[0]
    assert "CROOKED NAIL" in scene.header
    assert scene.location == "THE CROOKED NAIL"
    assert scene.time_of_day == "EVENING"


def test_parse_simple_characters():
    """Test character detection in simple scene."""
    doc = parse_fountain(SIMPLE_SCENE)

    scene = doc.scenes[0]
    assert "CORNELIUS" in scene.characters_present
    assert "MORDECAI" in scene.characters_present
    assert len(scene.characters_present) == 2


def test_parse_simple_dialogue_count():
    """Test dialogue counting in simple scene."""
    doc = parse_fountain(SIMPLE_SCENE)

    scene = doc.scenes[0]
    assert scene.has_dialogue["CORNELIUS"] == 2
    assert scene.has_dialogue["MORDECAI"] == 1


def test_parse_simple_all_characters():
    """Test global character list."""
    doc = parse_fountain(SIMPLE_SCENE)

    assert "CORNELIUS" in doc.characters
    assert "MORDECAI" in doc.characters


# =============================================================================
# Multi-Scene Document
# =============================================================================


MULTI_SCENE = """
INT. THE CROOKED NAIL - EVENING

CORNELIUS
Where is your sister?

MORDECAI
Upstairs.

EXT. CITY STREETS - NIGHT

CONSTANCE
The market closes at midnight.

GUARD
Move along.

INT. THE CROOKED NAIL - LATER

CORNELIUS
She's not here.
"""


def test_parse_multi_scene():
    """Test parsing multiple scenes."""
    doc = parse_fountain(MULTI_SCENE)

    assert len(doc.scenes) == 3

    assert doc.scenes[0].location == "THE CROOKED NAIL"
    assert doc.scenes[0].time_of_day == "EVENING"

    assert doc.scenes[1].location == "CITY STREETS"
    assert doc.scenes[1].time_of_day == "NIGHT"

    assert doc.scenes[2].location == "THE CROOKED NAIL"
    assert doc.scenes[2].time_of_day == "LATER"


def test_parse_multi_scene_characters():
    """Test characters across multiple scenes."""
    doc = parse_fountain(MULTI_SCENE)

    assert len(doc.characters) == 4
    assert "CORNELIUS" in doc.characters
    assert "MORDECAI" in doc.characters
    assert "CONSTANCE" in doc.characters
    assert "GUARD" in doc.characters


def test_parse_multi_scene_per_scene_characters():
    """Test per-scene character presence."""
    doc = parse_fountain(MULTI_SCENE)

    assert "CORNELIUS" in doc.scenes[0].characters_present
    assert "MORDECAI" in doc.scenes[0].characters_present

    assert "CONSTANCE" in doc.scenes[1].characters_present
    assert "GUARD" in doc.scenes[1].characters_present

    assert "CORNELIUS" in doc.scenes[2].characters_present


# =============================================================================
# Title Page
# =============================================================================


TITLE_PAGE_SCRIPT = """Title: The Crooked Nail
Credit: Written by
Author: Z. Amason
Draft date: 2025-01-15

INT. THE CROOKED NAIL - EVENING

CORNELIUS
Welcome.
"""


def test_parse_title_page():
    """Test title page extraction."""
    doc = parse_fountain(TITLE_PAGE_SCRIPT)

    assert doc.title_page["Title"] == "The Crooked Nail"
    assert doc.title_page["Author"] == "Z. Amason"
    assert doc.title_page["Draft date"] == "2025-01-15"


def test_title_page_doesnt_affect_scenes():
    """Test title page doesn't create phantom scenes."""
    doc = parse_fountain(TITLE_PAGE_SCRIPT)

    assert len(doc.scenes) == 1
    assert "CROOKED NAIL" in doc.scenes[0].header


# =============================================================================
# Edge Cases
# =============================================================================


def test_parse_empty():
    """Test parsing empty text."""
    doc = parse_fountain("")

    assert len(doc.scenes) == 0
    assert len(doc.characters) == 0


def test_parse_character_with_extension():
    """Test character name with (V.O.) or (O.S.)."""
    script = """
INT. ROOM - DAY

MORDECAI (V.O.)
I remember that night.

CORNELIUS (O.S.)
So do I.
"""
    doc = parse_fountain(script)
    scene = doc.scenes[0]

    assert "MORDECAI" in scene.characters_present
    assert "CORNELIUS" in scene.characters_present


def test_parse_transition_ignored():
    """Test transitions are ignored."""
    script = """
INT. ROOM - DAY

MORDECAI
Hello.

CUT TO:

INT. HALLWAY - DAY

CORNELIUS
Goodbye.
"""
    doc = parse_fountain(script)

    assert len(doc.scenes) == 2


def test_parse_forced_scene_header():
    """Test forced scene header (starts with period)."""
    script = """
.FLASHBACK - THE CROOKED NAIL

MORDECAI
I was young then.
"""
    doc = parse_fountain(script)

    assert len(doc.scenes) == 1
    assert "FLASHBACK" in doc.scenes[0].header


# =============================================================================
# File Loading
# =============================================================================


def test_parse_fountain_file(tmp_path):
    """Test loading fountain file from disk."""
    fountain_file = tmp_path / "test.fountain"
    fountain_file.write_text(SIMPLE_SCENE)

    doc = parse_fountain_file(fountain_file)

    assert len(doc.scenes) == 1
    assert "CORNELIUS" in doc.characters


def test_parse_fountain_file_not_found():
    """Test loading non-existent file raises error."""
    with pytest.raises(FileNotFoundError):
        parse_fountain_file(Path("/nonexistent/script.fountain"))


# =============================================================================
# Utility Functions
# =============================================================================


def test_extract_characters():
    """Test extracting character list."""
    doc = parse_fountain(MULTI_SCENE)

    chars = extract_characters(doc)

    assert isinstance(chars, list)
    assert len(chars) == 4
    assert chars == sorted(chars)  # Should be sorted


def test_scenes_for_character():
    """Test finding scenes for a character."""
    doc = parse_fountain(MULTI_SCENE)

    cornelius_scenes = scenes_for_character(doc, "CORNELIUS")

    assert len(cornelius_scenes) == 2  # Scene 1 and 3
    assert "EVENING" in cornelius_scenes[0].time_of_day
    assert "LATER" in cornelius_scenes[1].time_of_day


def test_scenes_for_character_not_found():
    """Test finding scenes for non-existent character."""
    doc = parse_fountain(MULTI_SCENE)

    scenes = scenes_for_character(doc, "NOBODY")

    assert len(scenes) == 0


def test_dialogue_count():
    """Test total dialogue count across scenes."""
    doc = parse_fountain(MULTI_SCENE)

    counts = dialogue_count(doc)

    assert counts["CORNELIUS"] == 2  # Scene 1 + Scene 3
    assert counts["MORDECAI"] == 1
    assert counts["CONSTANCE"] == 1
    assert counts["GUARD"] == 1

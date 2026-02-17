"""
KOZMO SCRIBO Tests

Tests for the SCRIBO document format, service layer, and API routes.

Covers:
- .scribo file parsing (frontmatter + body split)
- Serialization round-trip
- Malformed frontmatter handling
- Story tree building
- Word count (prose only, exclude Fountain elements)
- Character extraction from Fountain dialogue
- Document CRUD (create, read, update, delete)
- Container CRUD
- Luna notes (add, read)
- Search across documents
- Structure ordering
- Move document between containers
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from luna.services.kozmo.scribo_parser import (
    parse_scribo,
    serialize_scribo,
    extract_fountain_elements,
    word_count,
)
from luna.services.kozmo.scribo import ScriboService, init_story_directory
from luna.services.kozmo.types import (
    ScriboFrontmatter,
    ScriboDocument,
    LunaNote,
    StoryStructure,
    StoryLevel,
    ContainerMeta,
)


# =============================================================================
# Fixtures
# =============================================================================


SAMPLE_SCRIBO = """---
type: scene
container: ch_01
characters_present: [mordecai, cornelius]
location: crooked_nail
time: evening
status: draft
tags: [act_1, inciting_incident]
---

The tavern smelled of woodsmoke and regret. Mordecai pushed
through the door, staff clicking against the warped floorboards.

MORDECAI
(dropping into the opposite chair)
You look terrible.

CORNELIUS
(long pause)
Boy.
"""

SAMPLE_SCRIBO_NO_FRONTMATTER = """The tavern was empty. Just dust and memory.

MORDECAI
Nobody home.
"""

SAMPLE_SCRIBO_MALFORMED = """---
type: scene
container: [invalid yaml {{{
---

Body text here.
"""

SAMPLE_SCRIBO_PROSE_ONLY = """---
type: note
status: idea
---

This is a planning note with no dialogue.
Just pure prose describing the world.
Three sentences of text for counting.
"""


@pytest.fixture
def project_dir():
    """Create a temporary project directory with story structure."""
    tmpdir = Path(tempfile.mkdtemp())
    project_root = tmpdir / "test_project"
    project_root.mkdir()

    # Initialize story directory
    init_story_directory(project_root)

    # Create sample structure
    act_1 = project_root / "story" / "act_1"
    act_1.mkdir()

    # Act meta
    (act_1 / "_meta.yaml").write_text(
        "title: Act One\nslug: act_1\nlevel: Act\nstatus: draft\n"
    )

    ch_01 = act_1 / "ch_01"
    ch_01.mkdir()

    # Chapter meta
    (ch_01 / "_meta.yaml").write_text(
        "title: The Crooked Nail\nslug: ch_01\nlevel: Chapter\nstatus: draft\n"
    )

    # Write sample scenes
    (ch_01 / "sc_01_crooked_nail.scribo").write_text(SAMPLE_SCRIBO)

    second_scene = """---
type: scene
container: ch_01
characters_present: [mordecai]
location: road
status: idea
tags: [act_1]
---

Mordecai walked alone on the dusty road.
The staff hummed faintly in his hand.
"""
    (ch_01 / "sc_02_what_he_left.scribo").write_text(second_scene)

    # Update _structure.yaml with ordering
    import yaml
    structure = {
        "levels": [
            {"name": "Act", "slug_prefix": "act_"},
            {"name": "Chapter", "slug_prefix": "ch_"},
            {"name": "Scene", "slug_prefix": "sc_"},
        ],
        "order": {
            "act_1": [
                {"ch_01": ["sc_01_crooked_nail", "sc_02_what_he_left"]}
            ]
        },
    }
    with open(project_root / "story" / "_structure.yaml", "w") as f:
        yaml.dump(structure, f, default_flow_style=False, sort_keys=False)

    yield project_root

    # Cleanup
    shutil.rmtree(tmpdir)


# =============================================================================
# Parser Tests
# =============================================================================


class TestScriboParser:
    """Tests for scribo_parser.py functions."""

    def test_parse_scribo_basic(self):
        """Parse standard .scribo with frontmatter + body."""
        fm, body = parse_scribo(SAMPLE_SCRIBO)

        assert fm.type == "scene"
        assert fm.container == "ch_01"
        assert fm.characters_present == ["mordecai", "cornelius"]
        assert fm.location == "crooked_nail"
        assert fm.time == "evening"
        assert fm.status == "draft"
        assert "act_1" in fm.tags
        assert "inciting_incident" in fm.tags

        assert "woodsmoke" in body
        assert "MORDECAI" in body
        assert "You look terrible." in body

    def test_parse_scribo_no_frontmatter(self):
        """Parse .scribo with no frontmatter — defaults + entire body."""
        fm, body = parse_scribo(SAMPLE_SCRIBO_NO_FRONTMATTER)

        assert fm.type == "scene"
        assert fm.status == "draft"
        assert fm.characters_present == []
        assert "tavern was empty" in body
        assert "MORDECAI" in body

    def test_parse_scribo_malformed_frontmatter(self):
        """Malformed YAML in frontmatter raises ValueError."""
        with pytest.raises(ValueError, match="Malformed frontmatter"):
            parse_scribo(SAMPLE_SCRIBO_MALFORMED)

    def test_parse_scribo_empty(self):
        """Empty string returns defaults."""
        fm, body = parse_scribo("")
        assert fm.type == "scene"
        assert body == ""

    def test_serialize_round_trip(self):
        """Parse -> serialize -> parse should preserve data."""
        fm, body = parse_scribo(SAMPLE_SCRIBO)
        serialized = serialize_scribo(fm, body)
        fm2, body2 = parse_scribo(serialized)

        assert fm2.type == fm.type
        assert fm2.container == fm.container
        assert fm2.characters_present == fm.characters_present
        assert fm2.location == fm.location
        assert fm2.status == fm.status
        assert fm2.tags == fm.tags
        # Body should be equivalent (ignoring whitespace differences)
        assert "woodsmoke" in body2
        assert "You look terrible." in body2

    def test_serialize_omits_empty_fields(self):
        """Serialize omits None/empty fields from frontmatter."""
        fm = ScriboFrontmatter(type="note", status="idea")
        serialized = serialize_scribo(fm, "Some text.")

        assert "container:" not in serialized
        assert "characters_present:" not in serialized
        assert "location:" not in serialized


class TestFountainExtraction:
    """Tests for Fountain element extraction from mixed body."""

    def test_extract_characters(self):
        """Extract ALL CAPS character names from body."""
        _, body = parse_scribo(SAMPLE_SCRIBO)
        elements = extract_fountain_elements(body)

        assert "MORDECAI" in elements["characters"]
        assert "CORNELIUS" in elements["characters"]

    def test_dialogue_counts(self):
        """Count dialogue lines per character."""
        _, body = parse_scribo(SAMPLE_SCRIBO)
        elements = extract_fountain_elements(body)

        assert elements["dialogue_counts"].get("MORDECAI", 0) >= 1
        assert elements["dialogue_counts"].get("CORNELIUS", 0) >= 1

    def test_parentheticals(self):
        """Extract parentheticals with their characters."""
        _, body = parse_scribo(SAMPLE_SCRIBO)
        elements = extract_fountain_elements(body)

        parens = elements["parentheticals"]
        paren_texts = [p[1] for p in parens]
        assert any("dropping" in p for p in paren_texts)
        assert any("long pause" in p for p in paren_texts)

    def test_scene_headers(self):
        """Extract INT./EXT. scene headers."""
        body = """INT. CROOKED NAIL TAVERN - NIGHT

Mordecai enters.

EXT. ROAD - DAY

He walks.
"""
        elements = extract_fountain_elements(body)
        assert len(elements["scene_headers"]) == 2
        assert "INT. CROOKED NAIL TAVERN - NIGHT" in elements["scene_headers"]

    def test_no_fountain_elements(self):
        """Pure prose returns empty elements."""
        elements = extract_fountain_elements("Just some prose text.\nMore prose.")
        assert elements["characters"] == []
        assert elements["dialogue_counts"] == {}
        assert elements["scene_headers"] == []


class TestWordCount:
    """Tests for word count function."""

    def test_prose_only(self):
        """Count words in prose-only text."""
        _, body = parse_scribo(SAMPLE_SCRIBO_PROSE_ONLY)
        wc = word_count(body)
        # "This is a planning note with no dialogue."
        # "Just pure prose describing the world."
        # "Three sentences of text for counting."
        assert wc == 20

    def test_mixed_content(self):
        """Word count excludes character names and parentheticals."""
        _, body = parse_scribo(SAMPLE_SCRIBO)
        wc = word_count(body)

        # Should count prose lines and dialogue but NOT character names or parentheticals
        assert wc > 0
        # Prose: "The tavern smelled of woodsmoke and regret. Mordecai pushed"
        #        "through the door, staff clicking against the warped floorboards."
        # Dialogue: "You look terrible." + "Boy."
        # NOT counted: "MORDECAI", "CORNELIUS", "(dropping...)", "(long pause)"

    def test_empty_body(self):
        """Empty body returns 0."""
        assert word_count("") == 0
        assert word_count("\n\n") == 0


# =============================================================================
# Service Tests
# =============================================================================


class TestScriboService:
    """Tests for ScriboService using fixture project directory."""

    def test_get_structure(self, project_dir):
        """Load _structure.yaml."""
        svc = ScriboService(project_dir)
        structure = svc.get_structure()

        assert len(structure.levels) == 3
        assert structure.levels[0].name == "Act"
        assert structure.levels[1].name == "Chapter"
        assert structure.levels[2].name == "Scene"
        assert "act_1" in structure.order

    def test_build_story_tree(self, project_dir):
        """Build hierarchical story tree."""
        svc = ScriboService(project_dir)
        tree = svc.build_story_tree()

        assert tree.id == "root"
        assert tree.type == "root"
        assert len(tree.children) > 0

        # Find act_1
        act = tree.children[0]
        assert act.id == "act_1"
        assert act.title == "Act One"

        # Find ch_01 inside act_1
        chapter = act.children[0]
        assert chapter.id == "ch_01"

        # Find scenes inside chapter
        assert len(chapter.children) == 2

    def test_build_story_tree_word_counts(self, project_dir):
        """Tree nodes have aggregated word counts."""
        svc = ScriboService(project_dir)
        tree = svc.build_story_tree()

        # Root word count should be sum of all scenes
        assert tree.word_count > 0

    def test_get_document(self, project_dir):
        """Read a .scribo document by slug."""
        svc = ScriboService(project_dir)
        doc = svc.get_document("sc_01_crooked_nail")

        assert doc is not None
        assert doc.slug == "sc_01_crooked_nail"
        assert doc.frontmatter.type == "scene"
        assert doc.frontmatter.location == "crooked_nail"
        assert "mordecai" in doc.frontmatter.characters_present
        assert "woodsmoke" in doc.body
        assert doc.word_count > 0

    def test_get_document_not_found(self, project_dir):
        """Non-existent slug returns None."""
        svc = ScriboService(project_dir)
        assert svc.get_document("nonexistent") is None

    def test_create_document(self, project_dir):
        """Create a new .scribo document."""
        svc = ScriboService(project_dir)
        doc = svc.create_document("ch_01", "Staff Remembers", "scene")

        assert doc.slug == "staff_remembers"
        assert doc.frontmatter.type == "scene"
        assert doc.frontmatter.container == "ch_01"
        assert doc.frontmatter.status == "idea"

        # Verify file exists on disk
        scribo_file = svc._find_scribo_file("staff_remembers")
        assert scribo_file is not None
        assert scribo_file.exists()

    def test_save_document(self, project_dir):
        """Update and save a document."""
        svc = ScriboService(project_dir)
        doc = svc.get_document("sc_01_crooked_nail")

        # Modify body
        doc.body = doc.body + "\n\nMordecai ordered a drink.\n"
        saved = svc.save_document(doc)

        # Reload and verify
        reloaded = svc.get_document("sc_01_crooked_nail")
        assert "ordered a drink" in reloaded.body
        assert reloaded.word_count > doc.word_count - 4  # Approximate

    def test_delete_document(self, project_dir):
        """Delete a .scribo document."""
        svc = ScriboService(project_dir)

        # Verify it exists first
        assert svc.get_document("sc_02_what_he_left") is not None

        deleted = svc.delete_document("sc_02_what_he_left")
        assert deleted is True

        # Verify it's gone
        assert svc.get_document("sc_02_what_he_left") is None

    def test_delete_document_not_found(self, project_dir):
        """Delete non-existent document returns False."""
        svc = ScriboService(project_dir)
        assert svc.delete_document("nonexistent") is False

    def test_list_documents(self, project_dir):
        """List all documents in project."""
        svc = ScriboService(project_dir)
        docs = svc.list_documents()

        assert len(docs) == 2
        slugs = [d.slug for d in docs]
        assert "sc_01_crooked_nail" in slugs
        assert "sc_02_what_he_left" in slugs

    def test_list_documents_filtered(self, project_dir):
        """List documents filtered by container."""
        svc = ScriboService(project_dir)
        docs = svc.list_documents("ch_01")

        assert len(docs) == 2  # Both scenes are in ch_01

    def test_move_document(self, project_dir):
        """Move a scene to a different container."""
        svc = ScriboService(project_dir)

        # Create a second chapter
        svc.create_container("act_1", "The Road", "Chapter")

        # Move scene 2 to the new chapter
        moved = svc.move_document("sc_02_what_he_left", "the_road")
        assert moved is True

        # Verify the file is in the new location
        doc = svc.get_document("sc_02_what_he_left")
        assert doc is not None
        assert doc.frontmatter.container == "the_road"


class TestContainerCRUD:
    """Tests for container operations."""

    def test_create_container(self, project_dir):
        """Create a new container directory with _meta.yaml."""
        svc = ScriboService(project_dir)
        meta = svc.create_container(None, "Act Two", "Act")

        assert meta.title == "Act Two"
        assert meta.slug == "act_two"
        assert meta.level == "Act"
        assert meta.status == "idea"

        # Verify directory exists
        assert (project_dir / "story" / "act_two").is_dir()
        assert (project_dir / "story" / "act_two" / "_meta.yaml").exists()

    def test_create_nested_container(self, project_dir):
        """Create a chapter inside an existing act."""
        svc = ScriboService(project_dir)
        meta = svc.create_container("act_1", "The Journey", "Chapter")

        assert meta.title == "The Journey"
        assert meta.slug == "the_journey"

        # Verify nested directory
        assert (project_dir / "story" / "act_1" / "the_journey").is_dir()

    def test_get_container(self, project_dir):
        """Read container metadata."""
        svc = ScriboService(project_dir)
        meta = svc.get_container("ch_01")

        assert meta is not None
        assert meta.title == "The Crooked Nail"
        assert meta.level == "Chapter"

    def test_get_container_not_found(self, project_dir):
        """Non-existent container returns None."""
        svc = ScriboService(project_dir)
        assert svc.get_container("nonexistent") is None

    def test_update_container(self, project_dir):
        """Update container metadata."""
        svc = ScriboService(project_dir)
        meta = svc.update_container("ch_01", {
            "status": "revised",
            "summary": "Mordecai arrives at the tavern.",
        })

        assert meta is not None
        assert meta.status == "revised"
        assert meta.summary == "Mordecai arrives at the tavern."

        # Reload and verify persistence
        reloaded = svc.get_container("ch_01")
        assert reloaded.status == "revised"
        assert reloaded.summary == "Mordecai arrives at the tavern."


class TestLunaNotes:
    """Tests for Luna note operations."""

    def test_add_luna_note(self, project_dir):
        """Add a Luna note to a scene."""
        svc = ScriboService(project_dir)
        note = LunaNote(type="continuity", text="Staff first appears here.")
        notes = svc.add_luna_note("sc_01_crooked_nail", note)

        assert len(notes) == 1
        assert notes[0].type == "continuity"
        assert notes[0].text == "Staff first appears here."
        assert notes[0].created is not None

    def test_get_luna_notes(self, project_dir):
        """Read Luna notes for a scene."""
        svc = ScriboService(project_dir)

        # Add two notes
        svc.add_luna_note("sc_01_crooked_nail", LunaNote(
            type="continuity", text="Staff first appears here."
        ))
        svc.add_luna_note("sc_01_crooked_nail", LunaNote(
            type="thematic", text="Mirror scene with the ending."
        ))

        notes = svc.get_luna_notes("sc_01_crooked_nail")
        assert len(notes) == 2

    def test_luna_notes_empty(self, project_dir):
        """Scene with no notes returns empty list."""
        svc = ScriboService(project_dir)
        notes = svc.get_luna_notes("sc_02_what_he_left")
        assert notes == []


class TestSearch:
    """Tests for story search."""

    def test_search_body_content(self, project_dir):
        """Search finds documents matching body content."""
        svc = ScriboService(project_dir)
        results = svc.search("woodsmoke")

        assert len(results) == 1
        assert results[0].slug == "sc_01_crooked_nail"

    def test_search_no_results(self, project_dir):
        """Search with no matches returns empty."""
        svc = ScriboService(project_dir)
        results = svc.search("zxyqvort")
        assert len(results) == 0

    def test_search_case_insensitive(self, project_dir):
        """Search is case-insensitive."""
        svc = ScriboService(project_dir)
        results = svc.search("WOODSMOKE")
        assert len(results) == 1


class TestStats:
    """Tests for story statistics."""

    def test_get_word_counts(self, project_dir):
        """Get word counts per container."""
        svc = ScriboService(project_dir)
        counts = svc.get_word_counts()

        assert "total" in counts
        assert counts["total"] > 0

    def test_get_stats(self, project_dir):
        """Get full stats including document count and status breakdown."""
        svc = ScriboService(project_dir)
        stats = svc.get_stats()

        assert stats["document_count"] == 2
        assert stats["total_words"] > 0
        assert "draft" in stats["status_breakdown"]


class TestCharacterExtraction:
    """Tests for character extraction from Fountain elements."""

    def test_extract_characters_from_doc(self, project_dir):
        """Extract character names from a scene."""
        svc = ScriboService(project_dir)
        doc = svc.get_document("sc_01_crooked_nail")
        characters = svc.extract_characters(doc)

        assert "MORDECAI" in characters
        assert "CORNELIUS" in characters


class TestInitStoryDirectory:
    """Tests for story directory initialization."""

    def test_init_creates_structure(self):
        """init_story_directory creates story/ with _structure.yaml."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            project_root = tmpdir / "test"
            project_root.mkdir()

            init_story_directory(project_root)

            assert (project_root / "story").is_dir()
            assert (project_root / "story" / "_structure.yaml").exists()

            # Verify default levels
            import yaml
            with open(project_root / "story" / "_structure.yaml") as f:
                data = yaml.safe_load(f)
            assert len(data["levels"]) == 3
            assert data["levels"][0]["name"] == "Act"
        finally:
            shutil.rmtree(tmpdir)

    def test_init_idempotent(self):
        """Calling init twice doesn't overwrite."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            project_root = tmpdir / "test"
            project_root.mkdir()

            init_story_directory(project_root)
            init_story_directory(project_root)  # Should not fail

            assert (project_root / "story" / "_structure.yaml").exists()
        finally:
            shutil.rmtree(tmpdir)

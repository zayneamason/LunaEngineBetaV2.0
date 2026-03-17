"""Comprehensive unit tests for the Luna Skill Registry system."""

import pytest
from pathlib import Path

from luna.skills.base import Skill, SkillResult
from luna.skills.detector import SkillDetector
from luna.skills.config import SkillsConfig
from luna.skills.registry import SkillRegistry
from luna.skills.math.skill import MathSkill
from luna.skills.logic.skill import LogicSkill
from luna.skills.formatting.skill import FormattingSkill
from luna.skills.reading.skill import ReadingSkill
from luna.skills.analytics.skill import AnalyticsSkill
from luna.skills.eden.skill import EdenSkill, _detect_media_type


# ---------------------------------------------------------------------------
# TestSkillDetector
# ---------------------------------------------------------------------------

class TestSkillDetector:
    def setup_method(self):
        self.detector = SkillDetector()

    def test_detect_math(self):
        assert self.detector.detect("solve x^2 + 3x = 0") == "math"

    def test_detect_logic(self):
        assert self.detector.detect("truth table for p AND q") == "logic"

    def test_detect_diagnostic(self):
        assert self.detector.detect("system health check") == "diagnostic"

    def test_detect_formatting(self):
        assert self.detector.detect("give me bullet points") == "formatting"

    def test_detect_reading(self):
        assert self.detector.detect("read the file report.pdf") == "reading"

    def test_detect_eden(self):
        assert self.detector.detect("generate an image of a sunset") == "eden"

    def test_detect_analytics(self):
        assert self.detector.detect("memory stats") == "analytics"

    def test_detect_none(self):
        assert self.detector.detect("hello how are you") is None

    def test_detect_priority(self):
        # "how are you doing" should match diagnostic via the
        # "how('s| is) ... system" pattern -- but it won't match any
        # pattern at all, so None is correct unless it matches diagnostic.
        # The real priority test: diagnostic comes before math in the list.
        result = self.detector.detect("how is the system doing")
        assert result == "diagnostic"

    def test_detect_all(self):
        matches = self.detector.detect_all("solve x^2 and show truth table")
        assert "math" in matches
        assert "logic" in matches


# ---------------------------------------------------------------------------
# TestSkillsConfig
# ---------------------------------------------------------------------------

class TestSkillsConfig:
    def test_default_config(self):
        cfg = SkillsConfig()
        assert cfg.enabled is True
        assert cfg.math["enabled"] is True
        assert cfg.logic["enabled"] is True
        assert cfg.formatting["enabled"] is True
        assert cfg.reading["enabled"] is True
        assert cfg.diagnostic["enabled"] is True
        assert cfg.eden["enabled"] is True
        assert cfg.analytics["enabled"] is True

    def test_from_yaml(self):
        yaml_path = Path(__file__).parent.parent / "config" / "skills.yaml"
        if yaml_path.exists():
            cfg = SkillsConfig.from_yaml(yaml_path)
            assert cfg.enabled is True
            assert cfg.max_execution_ms == 5000
            assert cfg.math.get("enabled") is True
        else:
            pytest.skip("config/skills.yaml not found")


# ---------------------------------------------------------------------------
# TestSkillRegistry
# ---------------------------------------------------------------------------

class TestSkillRegistry:
    def setup_method(self):
        self.registry = SkillRegistry()
        self.registry.register_defaults()

    def test_register_defaults(self):
        available = self.registry.list_available()
        # At minimum math, logic, formatting should be present (sympy installed)
        for name in ("math", "logic", "formatting"):
            assert name in available, f"{name} not registered"

    def test_get_existing(self):
        skill = self.registry.get("math")
        assert skill is not None
        assert isinstance(skill, MathSkill)

    def test_get_missing(self):
        assert self.registry.get("nonexistent") is None

    def test_list_available(self):
        available = self.registry.list_available()
        assert isinstance(available, list)
        assert all(isinstance(s, str) for s in available)
        assert len(available) >= 3

    @pytest.mark.asyncio
    async def test_execute_missing_skill(self):
        result = await self.registry.execute("nonexistent", "hello")
        assert result.fallthrough is True
        assert result.success is False
        assert "not registered" in result.error


# ---------------------------------------------------------------------------
# TestMathSkill
# ---------------------------------------------------------------------------

class TestMathSkill:
    def setup_method(self):
        self.skill = MathSkill()

    @pytest.mark.asyncio
    async def test_solve_quadratic(self):
        result = await self.skill.execute("solve x**2 - 4", {})
        assert result.success is True
        assert result.skill_name == "math"
        assert result.latex is not None
        assert len(result.latex) > 0

    @pytest.mark.asyncio
    async def test_integrate(self):
        result = await self.skill.execute("integrate x**2", {})
        assert result.success is True
        assert result.skill_name == "math"
        # x^3/3 should appear in result
        assert result.result_str

    @pytest.mark.asyncio
    async def test_invalid_expression(self):
        result = await self.skill.execute("solve }{][!!!", {})
        assert result.fallthrough is True

    def test_narration_hint(self):
        dummy = SkillResult(success=True, skill_name="math")
        hint = self.skill.narration_hint(dummy)
        assert isinstance(hint, str)
        assert len(hint) > 0


# ---------------------------------------------------------------------------
# TestLogicSkill
# ---------------------------------------------------------------------------

class TestLogicSkill:
    def setup_method(self):
        self.skill = LogicSkill()

    @pytest.mark.asyncio
    async def test_truth_table(self):
        result = await self.skill.execute("truth table for P & Q", {})
        assert result.success is True
        assert result.data is not None
        assert "headers" in result.data
        assert "rows" in result.data
        assert len(result.data["rows"]) > 0

    @pytest.mark.asyncio
    async def test_tautology(self):
        # Use truth table path -- the parser strips "truth table for" cleanly,
        # and the skill auto-detects tautology from the all-True result column.
        result = await self.skill.execute("truth table for P | ~P", {})
        assert result.success is True
        assert result.data is not None
        assert result.data["verdict"] == "tautology"

    @pytest.mark.asyncio
    async def test_empty_expression(self):
        result = await self.skill.execute("truth table for nothing", {})
        # No uppercase single-letter variables found -> fallthrough
        assert result.fallthrough is True


# ---------------------------------------------------------------------------
# TestFormattingSkill
# ---------------------------------------------------------------------------

class TestFormattingSkill:
    def setup_method(self):
        self.skill = FormattingSkill()

    @pytest.mark.asyncio
    async def test_always_fallthrough(self):
        result = await self.skill.execute("give me bullet points about cats", {})
        assert result.fallthrough is True

    @pytest.mark.asyncio
    async def test_detect_bullets(self):
        result = await self.skill.execute("bullet points about dogs", {})
        assert result.data["format_type"] == "bullets"

    @pytest.mark.asyncio
    async def test_detect_numbered(self):
        result = await self.skill.execute("give me a numbered list", {})
        assert result.data["format_type"] == "numbered"

    @pytest.mark.asyncio
    async def test_detect_table(self):
        result = await self.skill.execute("table of contents", {})
        assert result.data["format_type"] == "table"

    def test_narration_hint(self):
        dummy = SkillResult(
            success=True, skill_name="formatting",
            data={"format_type": "bullets"},
        )
        hint = self.skill.narration_hint(dummy)
        assert isinstance(hint, str)
        assert "bullets" in hint


# ---------------------------------------------------------------------------
# TestAnalyticsSkill
# ---------------------------------------------------------------------------

class TestAnalyticsSkill:
    def setup_method(self):
        self.skill = AnalyticsSkill()

    @pytest.mark.asyncio
    async def test_memory_summary(self):
        result = await self.skill.execute("memory stats", {})
        if self.skill.is_available():
            # DB exists, should succeed or at least not crash
            assert result.skill_name == "analytics"
        else:
            assert result.fallthrough is True

    def test_is_available(self):
        avail = self.skill.is_available()
        assert isinstance(avail, bool)


# ---------------------------------------------------------------------------
# TestReadingSkill
# ---------------------------------------------------------------------------

class TestReadingSkill:
    def setup_method(self):
        self.skill = ReadingSkill()

    @pytest.mark.asyncio
    async def test_no_file_path(self):
        result = await self.skill.execute("read something", {})
        assert result.fallthrough is True
        assert "No file path" in result.error

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        result = await self.skill.execute(
            "read /tmp/nonexistent_file_12345.pdf", {}
        )
        assert result.success is False
        assert "not found" in result.error.lower() or result.fallthrough is True


# ---------------------------------------------------------------------------
# TestEdenSkill
# ---------------------------------------------------------------------------

class TestEdenSkill:
    def setup_method(self):
        self.skill = EdenSkill()

    def test_is_available(self):
        # No EDEN_API_KEY in test env
        assert self.skill.is_available() is False

    def test_detect_media_type_image(self):
        assert _detect_media_type("generate an image") == "image"

    def test_detect_media_type_video(self):
        assert _detect_media_type("create a video") == "video"

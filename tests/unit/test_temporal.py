"""
Tests for temporal awareness layer.

Tests gap categories, thread formatting, clock injection, edge cases.
"""

import pytest
from datetime import datetime, timedelta
from luna.context.temporal import (
    build_temporal_context,
    TemporalContext,
    _build_continuity_hint,
    _humanize_age,
)
from luna.extraction.types import Thread, ThreadStatus


# =============================================================================
# GAP CATEGORIES
# =============================================================================

class TestGapCategories:

    def test_continuation_gap(self):
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(minutes=2))
        assert ctx.gap_category == "continuation"
        assert ctx.continuity_hint == ""
        assert not ctx.is_greeting_appropriate

    def test_short_break(self):
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(minutes=30))
        assert ctx.gap_category == "short_break"
        assert ctx.is_greeting_appropriate

    def test_new_day_gap(self):
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(hours=6))
        assert ctx.gap_category == "new_day"
        assert ctx.is_greeting_appropriate

    def test_multi_day_gap(self):
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(days=3))
        assert ctx.gap_category == "multi_day"
        assert ctx.is_greeting_appropriate

    def test_long_absence(self):
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(days=14))
        assert ctx.gap_category == "long_absence"
        assert ctx.is_greeting_appropriate

    def test_first_ever(self):
        ctx = build_temporal_context()
        assert ctx.gap_category == "first_ever"
        assert ctx.is_greeting_appropriate

    def test_boundary_5_min(self):
        """Exactly at 5 minutes should be short_break, not continuation."""
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(minutes=5))
        assert ctx.gap_category == "short_break"

    def test_boundary_120_min(self):
        """At 120 minutes should be new_day, not short_break."""
        ctx = build_temporal_context(last_interaction=datetime.now() - timedelta(minutes=120))
        assert ctx.gap_category == "new_day"


# =============================================================================
# THREAD INHERITANCE
# =============================================================================

class TestThreadInheritance:

    def test_parked_threads_surface_on_multi_day(self):
        thread = Thread(
            id="t1", topic="voice system",
            status=ThreadStatus.PARKED,
            open_tasks=["task1"],
            turn_count=8,
            parked_at=datetime.now() - timedelta(days=2),
        )
        ctx = build_temporal_context(
            last_interaction=datetime.now() - timedelta(days=3),
            parked_threads=[thread],
        )
        assert "voice system" in ctx.continuity_hint
        assert "open" in ctx.continuity_hint

    def test_last_interaction_derived_from_parked_thread(self):
        """No explicit last_interaction -> derive from most recent parked_at."""
        thread = Thread(
            id="t1", topic="test",
            status=ThreadStatus.PARKED,
            parked_at=datetime.now() - timedelta(hours=6),
        )
        ctx = build_temporal_context(parked_threads=[thread])
        assert ctx.gap_category == "new_day"

    def test_short_break_shows_active_thread(self):
        active = Thread(
            id="t1", topic="debugging engine",
            status=ThreadStatus.ACTIVE,
        )
        ctx = build_temporal_context(
            last_interaction=datetime.now() - timedelta(minutes=30),
            active_thread=active,
        )
        assert "debugging engine" in ctx.continuity_hint

    def test_continuation_no_injection(self):
        active = Thread(
            id="t1", topic="debugging engine",
            status=ThreadStatus.ACTIVE,
        )
        ctx = build_temporal_context(
            last_interaction=datetime.now() - timedelta(minutes=1),
            active_thread=active,
        )
        assert ctx.continuity_hint == ""

    def test_multi_day_restraint_instructions(self):
        ctx = build_temporal_context(
            last_interaction=datetime.now() - timedelta(days=3),
            parked_threads=[
                Thread(
                    id="t1", topic="project review",
                    status=ThreadStatus.PARKED,
                    open_tasks=["review PR"],
                    parked_at=datetime.now() - timedelta(days=2),
                ),
            ],
        )
        assert "Don't dump thread context unprompted" in ctx.continuity_hint

    def test_long_absence_restraint(self):
        ctx = build_temporal_context(
            last_interaction=datetime.now() - timedelta(days=14),
            parked_threads=[
                Thread(id="t1", topic="a", status=ThreadStatus.PARKED,
                       parked_at=datetime.now() - timedelta(days=14)),
                Thread(id="t2", topic="b", status=ThreadStatus.PARKED,
                       open_tasks=["x"],
                       parked_at=datetime.now() - timedelta(days=10)),
            ],
        )
        assert "Don't info-dump" in ctx.continuity_hint

    def test_resumable_summary_with_tasks(self):
        threads = [
            Thread(id="t1", topic="a", status=ThreadStatus.PARKED, open_tasks=["task1"]),
            Thread(id="t2", topic="b", status=ThreadStatus.PARKED, open_tasks=["task2", "task3"]),
        ]
        ctx = build_temporal_context(parked_threads=threads)
        assert ctx.resumable_summary == "2 parked threads with open tasks"

    def test_resumable_summary_no_tasks(self):
        threads = [
            Thread(id="t1", topic="a", status=ThreadStatus.PARKED),
        ]
        ctx = build_temporal_context(parked_threads=threads)
        assert ctx.resumable_summary is None

    def test_parked_without_tasks_shown_as_secondary(self):
        """Parked threads without tasks shown in 'Also parked' line."""
        threads = [
            Thread(id="t1", topic="main work", status=ThreadStatus.PARKED,
                   open_tasks=["do thing"], parked_at=datetime.now() - timedelta(days=1)),
            Thread(id="t2", topic="side chat", status=ThreadStatus.PARKED,
                   parked_at=datetime.now() - timedelta(days=1)),
        ]
        ctx = build_temporal_context(
            last_interaction=datetime.now() - timedelta(days=2),
            parked_threads=threads,
        )
        assert "Also parked" in ctx.continuity_hint
        assert "side chat" in ctx.continuity_hint


# =============================================================================
# CLOCK
# =============================================================================

class TestClock:

    def test_time_of_day(self):
        ctx = build_temporal_context()
        assert ctx.time_of_day in ("morning", "afternoon", "evening", "night")

    def test_day_of_week(self):
        ctx = build_temporal_context()
        assert ctx.day_of_week  # Non-empty
        assert ctx.day_of_week in (
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday",
        )

    def test_date_formatted(self):
        ctx = build_temporal_context()
        assert ctx.date_formatted  # Non-empty
        assert "," in ctx.date_formatted  # e.g. "Monday, February 17, 2026"

    def test_session_start_preserved(self):
        start = datetime.now() - timedelta(hours=1)
        ctx = build_temporal_context(session_start=start)
        assert ctx.session_start == start


# =============================================================================
# HUMANIZE AGE
# =============================================================================

class TestHumanizeAge:

    def test_none(self):
        assert _humanize_age(None) == "some time ago"

    def test_minutes(self):
        dt = datetime.now() - timedelta(minutes=15)
        result = _humanize_age(dt)
        assert "15 minutes ago" == result

    def test_hours(self):
        dt = datetime.now() - timedelta(hours=3)
        result = _humanize_age(dt)
        assert "3 hours ago" == result

    def test_hour_singular(self):
        dt = datetime.now() - timedelta(hours=1)
        result = _humanize_age(dt)
        assert "1 hour ago" == result

    def test_yesterday(self):
        dt = datetime.now() - timedelta(days=1)
        result = _humanize_age(dt)
        assert result == "yesterday"

    def test_days(self):
        dt = datetime.now() - timedelta(days=4)
        result = _humanize_age(dt)
        assert "4 days ago" == result

    def test_last_week(self):
        dt = datetime.now() - timedelta(days=7)
        result = _humanize_age(dt)
        assert result == "last week"

    def test_weeks(self):
        dt = datetime.now() - timedelta(days=21)
        result = _humanize_age(dt)
        assert "3 weeks ago" == result


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:

    def test_empty_parked_threads(self):
        ctx = build_temporal_context(parked_threads=[])
        assert ctx.gap_category == "first_ever"

    def test_closed_threads_not_counted(self):
        """Closed threads should not appear in resumable summary."""
        threads = [
            Thread(id="t1", topic="done", status=ThreadStatus.CLOSED, open_tasks=["x"]),
        ]
        ctx = build_temporal_context(parked_threads=threads)
        assert ctx.resumable_summary is None

    def test_parked_threads_without_parked_at(self):
        """Threads with no parked_at should not affect gap detection."""
        thread = Thread(
            id="t1", topic="no timestamp",
            status=ThreadStatus.PARKED,
            parked_at=None,
        )
        ctx = build_temporal_context(parked_threads=[thread])
        assert ctx.gap_category == "first_ever"  # No derivable last interaction

    def test_gap_duration_populated(self):
        last = datetime.now() - timedelta(hours=2)
        ctx = build_temporal_context(last_interaction=last)
        assert ctx.gap_duration is not None
        assert ctx.gap_duration.total_seconds() > 0

    def test_gap_duration_none_for_first_ever(self):
        ctx = build_temporal_context()
        assert ctx.gap_duration is None

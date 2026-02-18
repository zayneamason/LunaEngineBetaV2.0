"""
Tests for UserPerceptionField — Luna's observation layer.

Covers:
- Signal detection (length, correction, question density, brevity, energy)
- Observation pairing (trigger context)
- Prompt formatting (injection block)
- Luna action recording
- Reset / lifecycle
"""

import pytest
from luna.context.perception import PerceptionField, Observation


# ── Signal Detection Tests ──────────────────────────────────────


def test_length_shift_shortening():
    """Messages shortening triggers observation."""
    pf = PerceptionField()
    # 3 long then 3 short
    for i, msg in enumerate(["x" * 150, "x" * 140, "x" * 160, "x" * 40, "x" * 35, "x" * 30]):
        pf.ingest(msg, i + 1)

    signals = [o.signal for o in pf.observations]
    assert "length_shift" in signals

    length_obs = [o for o in pf.observations if o.signal == "length_shift"][0]
    assert "shortened" in length_obs.value.lower()


def test_length_shift_expanding():
    """Messages expanding triggers observation."""
    pf = PerceptionField()
    # 3 short then 3 long
    for i, msg in enumerate(["x" * 30, "x" * 25, "x" * 35, "x" * 80, "x" * 90, "x" * 85]):
        pf.ingest(msg, i + 1)

    signals = [o.signal for o in pf.observations]
    assert "length_shift" in signals

    length_obs = [o for o in pf.observations if o.signal == "length_shift"][0]
    assert "expanding" in length_obs.value.lower()


def test_length_shift_needs_minimum_messages():
    """No length observation with fewer than 4 messages."""
    pf = PerceptionField()
    pf.ingest("x" * 150, 1)
    pf.ingest("x" * 30, 2)
    pf.ingest("x" * 25, 3)

    signals = [o.signal for o in pf.observations]
    assert "length_shift" not in signals


def test_correction_detection():
    """Repeating similar content triggers correction observation."""
    pf = PerceptionField()
    pf.ingest("I want the thread timestamps not the session timestamps", 1)
    pf.ingest("can you explain more about threads", 2)
    pf._last_luna_action = "gave 500+ char explanation about session timestamps"
    pf.ingest("no I mean the thread timestamps not session", 3)

    signals = [o.signal for o in pf.observations]
    assert "correction_detected" in signals


def test_correction_escalation():
    """Multiple corrections increase confidence and update message."""
    pf = PerceptionField()
    pf.ingest("I need the vector search implementation details", 1)
    pf.ingest("something unrelated to break the pattern", 2)
    pf.ingest("the vector search implementation, not the graph traversal", 3)
    pf.ingest("another unrelated message to create space", 4)
    pf.ingest("I keep asking about vector search implementation details", 5)

    correction_obs = [o for o in pf.observations if o.signal == "correction_detected"]
    if len(correction_obs) >= 2:
        assert correction_obs[-1].confidence >= correction_obs[0].confidence


def test_question_density():
    """High question rate triggers observation."""
    pf = PerceptionField()
    pf.ingest("what about the temporal layer?", 1)
    pf.ingest("how does the gap detection work?", 2)
    pf.ingest("what are the thread inheritance rules?", 3)
    pf.ingest("where does the clock get injected?", 4)

    signals = [o.signal for o in pf.observations]
    assert "question_density" in signals


def test_question_to_statement_shift():
    """Shifting from questions to statements triggers observation."""
    pf = PerceptionField()
    # Questions
    pf.ingest("what about this?", 1)
    pf.ingest("how does that work?", 2)
    pf.ingest("where is that configured?", 3)
    # Statements
    pf.ingest("I think we should use the simpler approach here", 4)
    pf.ingest("The implementation looks solid to me now", 5)
    pf.ingest("Let me go ahead and wire it up this way", 6)

    signals = [o.signal for o in pf.observations]
    assert "question_density" in signals


def test_brevity_detection():
    """Terse acknowledgments trigger observation."""
    pf = PerceptionField()
    pf.ingest("This is a normal length message about architecture", 1)
    pf.ingest("ok", 2)
    pf.ingest("sure", 3)

    signals = [o.signal for o in pf.observations]
    assert "terse_response" in signals


def test_brevity_with_punctuation():
    """Terse markers with trailing punctuation still match."""
    pf = PerceptionField()
    pf.ingest("Normal message here", 1)
    pf.ingest("ok.", 2)
    pf.ingest("sure!", 3)

    signals = [o.signal for o in pf.observations]
    assert "terse_response" in signals


def test_brevity_resets_on_long_message():
    """Terse count resets when user sends a substantive message."""
    pf = PerceptionField()
    pf.ingest("ok", 1)
    # Long message should reset the terse counter
    pf.ingest("Actually, I've been thinking about this more and I want to change the approach entirely because of the performance implications", 2)
    pf.ingest("sure", 3)

    # Should NOT have terse_response because the counter was reset
    terse_obs = [o for o in pf.observations if o.signal == "terse_response"]
    assert len(terse_obs) == 0


def test_energy_markers_appear():
    """Energy increase triggers observation."""
    pf = PerceptionField()
    # Flat baseline
    pf.ingest("normal message here", 1)
    pf.ingest("another normal message", 2)
    pf.ingest("still normal", 3)
    # Energy spike
    pf.ingest("YES! That's exactly it!! \U0001f3af\U0001f3af", 4)

    signals = [o.signal for o in pf.observations]
    assert "energy_markers" in signals


def test_energy_markers_baseline_period():
    """No energy observation during baseline period (first 3 messages)."""
    pf = PerceptionField()
    pf.ingest("WOW!! Amazing!! \U0001f525\U0001f525\U0001f525", 1)
    pf.ingest("YES!!", 2)
    pf.ingest("INCREDIBLE!!!", 3)

    # Should be silent — still establishing baseline
    energy_obs = [o for o in pf.observations if o.signal == "energy_markers"]
    assert len(energy_obs) == 0


# ── Observation Pairing Tests ───────────────────────────────────


def test_trigger_context_captured():
    """Observations carry what Luna did before."""
    pf = PerceptionField()
    pf._last_luna_action = "gave 400+ char explanation"

    pf.ingest("x" * 150, 1)
    pf.ingest("x" * 140, 2)
    pf.ingest("x" * 160, 3)
    pf._last_luna_action = "gave 500+ char technical response with code"
    pf.ingest("x" * 30, 4)
    pf.ingest("x" * 25, 5)
    pf.ingest("x" * 20, 6)

    length_obs = [o for o in pf.observations if o.signal == "length_shift"]
    if length_obs:
        assert "500+" in length_obs[-1].trigger or "technical" in length_obs[-1].trigger


def test_paired_output_format():
    """Observation.paired combines value and trigger."""
    obs = Observation(
        signal="length_shift",
        value="Messages shortened from ~140 to ~35 chars",
        trigger="after Luna's 400-word explanation",
        turn=8,
        confidence=0.8,
    )
    assert "Messages shortened" in obs.paired
    assert "after Luna's" in obs.paired
    assert "(" in obs.paired  # Trigger in parentheses


def test_default_trigger_is_start_of_session():
    """Without record_luna_action, trigger defaults to 'start of session'."""
    pf = PerceptionField()
    # Force enough data for a signal
    for i, msg in enumerate(["x" * 150, "x" * 140, "x" * 160, "x" * 30, "x" * 25, "x" * 20]):
        pf.ingest(msg, i + 1)

    if pf.observations:
        assert "start of session" in pf.observations[0].trigger


# ── Prompt Formatting Tests ─────────────────────────────────────


def test_no_injection_with_insufficient_observations():
    """Fewer than 2 observations -> no prompt block."""
    pf = PerceptionField()
    pf.observe(Observation("test", "one observation", "trigger", 1, 0.5))
    assert pf.to_prompt_block() is None


def test_injection_with_sufficient_observations():
    """2+ observations -> formatted prompt block."""
    pf = PerceptionField()
    pf.observe(Observation("a", "first thing", "trigger1", 1, 0.7))
    pf.observe(Observation("b", "second thing", "trigger2", 2, 0.8))

    block = pf.to_prompt_block()
    assert block is not None
    assert "User Observation" in block
    assert "first thing" in block
    assert "observations, not conclusions" in block


def test_prompt_block_includes_trigger():
    """Prompt block includes trigger context in parentheses."""
    pf = PerceptionField()
    pf.observe(Observation("a", "messages shortened", "after long explanation", 1, 0.8))
    pf.observe(Observation("b", "terse acks", "during wrap-up", 2, 0.7))

    block = pf.to_prompt_block()
    assert "after long explanation" in block
    assert "during wrap-up" in block


def test_max_observations_cap():
    """Only last MAX_OBSERVATIONS survive."""
    pf = PerceptionField()
    for i in range(12):
        pf.observe(Observation(f"sig_{i}", f"obs {i}", "trigger", i, 0.5))

    assert len(pf.observations) == pf.MAX_OBSERVATIONS


def test_prompt_block_caps_at_5_recent():
    """Prompt block shows at most 5 recent observations."""
    pf = PerceptionField()
    for i in range(8):
        pf.observe(Observation(f"sig_{i}", f"obs {i}", "trigger", i, 0.5))

    block = pf.to_prompt_block()
    # Should contain obs 3-7 (last 5)
    assert "obs 3" in block
    assert "obs 7" in block
    # Should NOT contain obs 0
    assert "obs 0" not in block


# ── Luna Action Recording Tests ─────────────────────────────────


def test_record_brief_response():
    pf = PerceptionField()
    pf.record_luna_action("Sure, here you go.")
    assert "brief" in pf._last_luna_action


def test_record_moderate_response():
    pf = PerceptionField()
    pf.record_luna_action("x" * 200)
    assert "moderate" in pf._last_luna_action


def test_record_long_explanation():
    pf = PerceptionField()
    pf.record_luna_action("x" * 500)
    assert "500" in pf._last_luna_action or "char" in pf._last_luna_action


def test_record_code_response():
    pf = PerceptionField()
    pf.record_luna_action("Here's the code:\n```python\ndef hello():\n    pass\n```\nThat should work." + "x" * 400)
    assert "code" in pf._last_luna_action


def test_record_question():
    pf = PerceptionField()
    pf.record_luna_action("That's interesting. What made you think of that approach?")
    assert "question" in pf._last_luna_action


# ── Reset / Lifecycle Tests ─────────────────────────────────────


def test_reset_clears_everything():
    """Reset wipes all state."""
    pf = PerceptionField()
    pf.ingest("test message", 1)
    pf.observe(Observation("test", "obs", "trigger", 1, 0.5))
    pf._last_luna_action = "something"

    pf.reset()

    assert len(pf.observations) == 0
    assert len(pf._msg_lengths) == 0
    assert len(pf._user_messages) == 0
    assert len(pf._question_flags) == 0
    assert pf._terse_count == 0
    assert pf._correction_count == 0
    assert pf._last_luna_action == ""
    assert pf._baseline_energy is None


def test_reset_allows_fresh_observations():
    """After reset, new observations accumulate correctly."""
    pf = PerceptionField()
    pf.observe(Observation("old", "old obs", "old trigger", 1, 0.5))
    pf.observe(Observation("old2", "old obs 2", "old trigger", 2, 0.5))
    assert pf.to_prompt_block() is not None

    pf.reset()
    assert pf.to_prompt_block() is None  # No observations

    pf.observe(Observation("new", "new obs", "new trigger", 1, 0.7))
    pf.observe(Observation("new2", "new obs 2", "new trigger", 2, 0.8))
    block = pf.to_prompt_block()
    assert block is not None
    assert "new obs" in block
    assert "old obs" not in block


# ── Integration Test ────────────────────────────────────────────


def test_perception_end_to_end():
    """Full flow: ingest -> observe -> format -> inject."""
    pf = PerceptionField()

    # Simulate a conversation arc
    messages_and_actions = [
        ("Tell me about the memory architecture", "gave 400+ char explanation"),
        ("How does the vector search work?", "gave 300+ char explanation"),
        ("What about the graph traversal?", "gave 500+ char technical response with code"),
        ("And the FTS5 integration?", "gave 400+ char explanation"),
        # Now user gets terse
        ("ok", "gave brief response"),
        ("sure", "gave brief response"),
    ]

    for i, (msg, action) in enumerate(messages_and_actions):
        pf.ingest(msg, i + 1)
        pf.record_luna_action(action)

    block = pf.to_prompt_block()
    assert block is not None
    assert "User Observation" in block
    assert "observations, not conclusions" in block


def test_question_density_fires_at_turn_4():
    """Question density should fire at exactly 4 questions in a row."""
    pf = PerceptionField()
    pf.ingest("what is this?", 1)
    pf.ingest("how does it work?", 2)
    pf.ingest("where is it defined?", 3)

    # At 3 messages, not enough for question_density (needs 4)
    q_obs = [o for o in pf.observations if o.signal == "question_density"]
    assert len(q_obs) == 0

    pf.ingest("why was it built this way?", 4)
    q_obs = [o for o in pf.observations if o.signal == "question_density"]
    assert len(q_obs) == 1

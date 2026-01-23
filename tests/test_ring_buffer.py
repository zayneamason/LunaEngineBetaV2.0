"""
Unit tests for ConversationRing buffer.

Tests the core guarantee: history cannot be displaced.
"""

import pytest
from luna.memory.ring import ConversationRing, Turn


class TestConversationRing:
    """Tests for ConversationRing class."""

    def test_basic_operations(self):
        """Test adding and retrieving turns."""
        ring = ConversationRing(max_turns=4)

        ring.add_user("Hello")
        ring.add_assistant("Hi there!")
        ring.add_user("Do you remember Marzipan?")
        ring.add_assistant("Yes! He loves owls.")

        assert len(ring) == 4
        assert ring.contains("marzipan")
        assert ring.contains("owls")
        assert ring.contains("Hello")

    def test_fifo_eviction(self):
        """Test that oldest turns are evicted when buffer is full."""
        ring = ConversationRing(max_turns=2)

        ring.add_user("First")
        ring.add_assistant("Second")
        ring.add_user("Third")  # Should evict "First"

        assert len(ring) == 2
        assert not ring.contains("First")
        assert ring.contains("Second")
        assert ring.contains("Third")

    def test_format_for_prompt(self):
        """Test formatting for system prompt injection."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Question?")
        ring.add_assistant("Answer!")

        formatted = ring.format_for_prompt()
        assert "[1] Ahab: Question?" in formatted
        assert "[2] Luna: Answer!" in formatted

    def test_format_custom_names(self):
        """Test formatting with custom user/assistant names."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Hi")
        ring.add_assistant("Hello")

        formatted = ring.format_for_prompt(user_name="Bob", assistant_name="Alice")
        assert "[1] Bob: Hi" in formatted
        assert "[2] Alice: Hello" in formatted

    def test_empty_buffer_format(self):
        """Test formatting when buffer is empty."""
        ring = ConversationRing(max_turns=4)
        formatted = ring.format_for_prompt()
        assert "No conversation history" in formatted

    def test_contains_case_insensitive(self):
        """Test case-insensitive search (default)."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Marzipan is great")

        assert ring.contains("marzipan")
        assert ring.contains("MARZIPAN")
        assert ring.contains("Marzipan")

    def test_contains_case_sensitive(self):
        """Test case-sensitive search."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Marzipan is great")

        assert ring.contains("Marzipan", case_sensitive=True)
        assert not ring.contains("marzipan", case_sensitive=True)
        assert not ring.contains("MARZIPAN", case_sensitive=True)

    def test_contains_any(self):
        """Test checking multiple terms at once."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("I saw an owl yesterday")
        ring.add_assistant("Cool! Owls are amazing.")

        assert ring.contains_any(["owl", "cat", "dog"])
        assert ring.contains_any(["cat", "dog", "amazing"])
        assert not ring.contains_any(["cat", "dog", "fish"])

    def test_contains_entity(self):
        """Test entity mention detection."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Do you remember Marzipan?")
        ring.add_assistant("Yes! Marzipan loves owls.")

        assert ring.contains_entity("marzipan")
        assert ring.contains_entity("Marzipan")
        assert not ring.contains_entity("Gandala")

    def test_get_as_dicts(self):
        """Test getting turns as LLM message format."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Hello")
        ring.add_assistant("Hi!")

        dicts = ring.get_as_dicts()
        assert len(dicts) == 2
        assert dicts[0] == {"role": "user", "content": "Hello"}
        assert dicts[1] == {"role": "assistant", "content": "Hi!"}

    def test_get_turns(self):
        """Test getting raw Turn objects."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Hello")
        ring.add_assistant("Hi!")

        turns = ring.get_turns()
        assert len(turns) == 2
        assert isinstance(turns[0], Turn)
        assert turns[0].role == "user"
        assert turns[0].content == "Hello"

    def test_get_last_n(self):
        """Test getting last N turns."""
        ring = ConversationRing(max_turns=6)
        ring.add_user("One")
        ring.add_assistant("Two")
        ring.add_user("Three")
        ring.add_assistant("Four")

        last_2 = ring.get_last_n(2)
        assert len(last_2) == 2
        assert last_2[0].content == "Three"
        assert last_2[1].content == "Four"

    def test_get_last_user_message(self):
        """Test getting most recent user message."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("First user")
        ring.add_assistant("First assistant")
        ring.add_user("Second user")

        assert ring.get_last_user_message() == "Second user"

    def test_get_last_assistant_message(self):
        """Test getting most recent assistant message."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("First user")
        ring.add_assistant("First assistant")
        ring.add_user("Second user")
        ring.add_assistant("Second assistant")

        assert ring.get_last_assistant_message() == "Second assistant"

    def test_clear(self):
        """Test clearing the buffer."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("Hello")
        ring.add_assistant("Hi!")

        assert len(ring) == 2
        ring.clear()
        assert len(ring) == 0
        assert not ring.contains("Hello")

    def test_bool_conversion(self):
        """Test boolean conversion."""
        ring = ConversationRing(max_turns=4)
        assert not bool(ring)  # Empty

        ring.add_user("Hello")
        assert bool(ring)  # Has content

    def test_iteration(self):
        """Test iterating over turns."""
        ring = ConversationRing(max_turns=4)
        ring.add_user("One")
        ring.add_assistant("Two")

        contents = [turn.content for turn in ring]
        assert contents == ["One", "Two"]

    def test_repr(self):
        """Test string representation."""
        ring = ConversationRing(max_turns=6)
        ring.add_user("Hello")
        ring.add_assistant("Hi")

        repr_str = repr(ring)
        assert "turns=2" in repr_str
        assert "max=6" in repr_str

    def test_marzipan_scenario(self):
        """
        The Marzipan Test — the bug that inspired this class.

        Luna should remember Marzipan across all turns because
        the ring buffer guarantees history cannot be displaced.
        """
        ring = ConversationRing(max_turns=6)

        # Turn 1: User asks about Marzipan
        ring.add_user("Do you remember the guy Marzipan?")
        ring.add_assistant("Oh absolutely! Marzipan - Ahab's friend who identifies with owls...")

        # Turn 2: User asks about Mars College
        ring.add_user("Tell me about Mars College")

        # At this point, Marzipan should STILL be in the ring
        assert ring.contains("marzipan"), "Marzipan should still be in ring after Turn 2 question"
        assert ring.contains("owls"), "Owls should still be in ring"

        # The formatted prompt should include Marzipan context
        formatted = ring.format_for_prompt()
        assert "Marzipan" in formatted, "Formatted prompt must include Marzipan"
        assert "owls" in formatted, "Formatted prompt must include owls"

        # Turn 2 response (doesn't forget Marzipan)
        ring.add_assistant("Mars College is where Ahab is currently located...")

        # Turn 3: User asks about connection
        ring.add_user("And Marzipan's connection to Mars College?")

        # Ring should still have all context
        assert ring.contains("marzipan")
        assert ring.contains("mars college")

    def test_six_turn_capacity(self):
        """Test default capacity handles 3 full exchanges."""
        ring = ConversationRing(max_turns=6)

        # Three full exchanges
        for i in range(3):
            ring.add_user(f"Question {i+1}")
            ring.add_assistant(f"Answer {i+1}")

        assert len(ring) == 6

        # Add one more - oldest should evict
        ring.add_user("Question 4")
        assert len(ring) == 6
        assert not ring.contains("Question 1")
        assert ring.contains("Question 4")


class TestTurn:
    """Tests for Turn dataclass."""

    def test_turn_creation(self):
        """Test creating a turn."""
        turn = Turn(role="user", content="Hello")
        assert turn.role == "user"
        assert turn.content == "Hello"

    def test_turn_to_dict(self):
        """Test converting turn to dict."""
        turn = Turn(role="assistant", content="Hi!")
        d = turn.to_dict()
        assert d == {"role": "assistant", "content": "Hi!"}

"""
Tests for Actor System
======================

Tests for actor lifecycle, mailbox messaging, and fault isolation.
"""

import asyncio
import pytest

from luna.actors.base import Actor, Message


class MockActor(Actor):
    """Mock actor for testing."""

    def __init__(self, name: str = "mock"):
        super().__init__(name)
        self.received_messages = []
        self.handle_delay = 0
        self.should_fail = False
        self.error_count = 0

    async def handle(self, msg: Message) -> None:
        """Record received messages."""
        if self.should_fail:
            raise ValueError("Intentional test failure")
        self.received_messages.append(msg)
        if self.handle_delay > 0:
            await asyncio.sleep(self.handle_delay)

    async def on_error(self, error: Exception, msg: Message) -> None:
        """Track errors."""
        self.error_count += 1


class TestActorLifecycle:
    """Tests for actor start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_actor_starts_and_stops(self):
        """Test basic start/stop lifecycle."""
        actor = MockActor("test")

        # Start in background
        task = asyncio.create_task(actor.start())

        # Wait for actor to be running
        await asyncio.sleep(0.1)
        assert actor._running is True

        # Stop actor
        await actor.stop()

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=2.0)
        assert actor._running is False

    @pytest.mark.asyncio
    async def test_actor_processes_messages(self):
        """Test actor receives and processes messages."""
        actor = MockActor("test")

        task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)

        # Send messages
        msg1 = Message(type="test", payload="message 1")
        msg2 = Message(type="test", payload="message 2")

        await actor.mailbox.put(msg1)
        await actor.mailbox.put(msg2)

        # Wait for processing
        await asyncio.sleep(0.2)

        assert len(actor.received_messages) == 2
        assert actor.received_messages[0].payload == "message 1"
        assert actor.received_messages[1].payload == "message 2"

        await actor.stop()
        await asyncio.wait_for(task, timeout=2.0)

    @pytest.mark.asyncio
    async def test_actor_double_start_warns(self):
        """Test starting already running actor warns."""
        actor = MockActor("test")

        task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)

        # Second start should return immediately (with warning)
        await actor.start()

        # Still running
        assert actor._running is True

        await actor.stop()
        await asyncio.wait_for(task, timeout=2.0)


class TestActorFaultIsolation:
    """Tests for actor error handling and fault isolation."""

    @pytest.mark.asyncio
    async def test_actor_continues_after_error(self):
        """Test actor doesn't crash on message handling error."""
        actor = MockActor("test")
        actor.should_fail = True

        task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)

        # Send message that will fail
        await actor.mailbox.put(Message(type="fail", payload="error"))
        await asyncio.sleep(0.2)

        # Actor should still be running
        assert actor._running is True
        assert actor.error_count == 1

        # Send another message after fixing
        actor.should_fail = False
        await actor.mailbox.put(Message(type="success", payload="ok"))
        await asyncio.sleep(0.2)

        assert len(actor.received_messages) == 1
        assert actor.received_messages[0].payload == "ok"

        await actor.stop()
        await asyncio.wait_for(task, timeout=2.0)


class TestActorMessaging:
    """Tests for inter-actor messaging."""

    @pytest.mark.asyncio
    async def test_send_to_another_actor(self):
        """Test actors can send messages to each other."""
        sender = MockActor("sender")
        receiver = MockActor("receiver")

        # Start receiver
        task = asyncio.create_task(receiver.start())
        await asyncio.sleep(0.1)

        # Send message from sender to receiver
        msg = Message(type="hello", payload="from sender")
        await sender.send(receiver, msg)

        await asyncio.sleep(0.2)

        assert len(receiver.received_messages) == 1
        assert receiver.received_messages[0].sender == "sender"
        assert receiver.received_messages[0].payload == "from sender"

        await receiver.stop()
        await asyncio.wait_for(task, timeout=2.0)


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_defaults(self):
        """Test message has sensible defaults."""
        msg = Message(type="test")

        assert msg.type == "test"
        assert msg.payload is None
        assert msg.sender is None
        assert msg.correlation_id is not None
        assert len(msg.correlation_id) == 8
        assert msg.timestamp is not None

    def test_message_with_payload(self):
        """Test message with payload."""
        msg = Message(type="data", payload={"key": "value"})

        assert msg.payload == {"key": "value"}

    def test_message_repr(self):
        """Test message string representation."""
        msg = Message(type="test", sender="actor1")

        repr_str = repr(msg)
        assert "Message" in repr_str
        assert "test" in repr_str
        assert "actor1" in repr_str


class TestActorSnapshot:
    """Tests for actor state serialization."""

    @pytest.mark.asyncio
    async def test_basic_snapshot(self):
        """Test basic snapshot includes name and mailbox size."""
        actor = MockActor("test")
        await actor.mailbox.put(Message(type="pending"))

        snapshot = await actor.snapshot()

        assert snapshot["name"] == "test"
        assert snapshot["mailbox_size"] == 1

    @pytest.mark.asyncio
    async def test_restore_hook_called(self):
        """Test restore method is callable."""
        actor = MockActor("test")

        # Should not raise
        await actor.restore({"name": "test"})

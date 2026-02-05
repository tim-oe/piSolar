"""Tests for event bus module."""

from pisolar.event_bus import EventBus, get_event_bus


class TestEventBus:
    """Tests for EventBus class."""

    def test_create_event_bus(self):
        """Test creating an event bus."""
        bus = EventBus()
        assert bus._subscribers == {}

    def test_subscribe_handler(self):
        """Test subscribing a handler to an event."""
        bus = EventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test.event", handler)

        assert "test.event" in bus._subscribers
        assert len(bus._subscribers["test.event"]) == 1

    def test_publish_event(self):
        """Test publishing an event to subscribers."""
        bus = EventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test.event", handler)
        bus.publish("test.event", {"key": "value"})

        assert len(received) == 1
        assert received[0] == {"key": "value"}

    def test_publish_to_multiple_subscribers(self):
        """Test publishing to multiple subscribers."""
        bus = EventBus()
        received1 = []
        received2 = []

        def handler1(data):
            received1.append(data)

        def handler2(data):
            received2.append(data)

        bus.subscribe("test.event", handler1)
        bus.subscribe("test.event", handler2)
        bus.publish("test.event", "hello")

        assert received1 == ["hello"]
        assert received2 == ["hello"]

    def test_publish_no_subscribers(self):
        """Test publishing when no subscribers exist."""
        bus = EventBus()
        # Should not raise
        bus.publish("unknown.event", {"data": 123})

    def test_unsubscribe_handler(self):
        """Test unsubscribing a handler."""
        bus = EventBus()
        received = []

        def handler(data):
            received.append(data)

        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        bus.publish("test.event", "data")

        assert received == []

    def test_unsubscribe_unknown_handler(self):
        """Test unsubscribing a handler that wasn't subscribed."""
        bus = EventBus()

        def handler(data):
            pass

        # Should not raise
        bus.unsubscribe("test.event", handler)

    def test_unsubscribe_from_unknown_event(self):
        """Test unsubscribing from an event type with no subscribers."""
        bus = EventBus()

        def handler(data):
            pass

        # Should not raise
        bus.unsubscribe("unknown.event", handler)

    def test_handler_exception_does_not_stop_other_handlers(self):
        """Test that one handler's exception doesn't stop others."""
        bus = EventBus()
        received = []

        def failing_handler(data):
            raise ValueError("Handler error")

        def good_handler(data):
            received.append(data)

        bus.subscribe("test.event", failing_handler)
        bus.subscribe("test.event", good_handler)
        bus.publish("test.event", "data")

        # Good handler should still receive the event
        assert received == ["data"]

    def test_multiple_event_types(self):
        """Test subscribing to different event types."""
        bus = EventBus()
        type_a = []
        type_b = []

        def handler_a(data):
            type_a.append(data)

        def handler_b(data):
            type_b.append(data)

        bus.subscribe("event.a", handler_a)
        bus.subscribe("event.b", handler_b)

        bus.publish("event.a", "A")
        bus.publish("event.b", "B")

        assert type_a == ["A"]
        assert type_b == ["B"]


class TestGetEventBus:
    """Tests for get_event_bus singleton."""

    def test_returns_event_bus(self):
        """Test that get_event_bus returns an EventBus."""
        bus = get_event_bus()
        assert isinstance(bus, EventBus)

    def test_returns_same_instance(self):
        """Test that get_event_bus returns the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

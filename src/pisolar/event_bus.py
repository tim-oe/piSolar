"""Event bus for decoupled event publishing and consumption."""

from collections.abc import Callable
from typing import Any

from pisolar.logging_config import get_logger

logger = get_logger("event_bus")


class EventBus:
    """Simple event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """
        Subscribe a handler to an event type.

        Args:
            event_type: The type of event to subscribe to
            handler: Callback function that receives the event data
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed handler to event type: %s", event_type)

    def publish(self, event_type: str, data: Any) -> None:
        """
        Publish an event to all subscribed handlers.

        Args:
            event_type: The type of event being published
            data: The event data to pass to handlers
        """
        handlers = self._subscribers.get(event_type, [])
        logger.debug("Publishing event %s to %d handler(s)", event_type, len(handlers))

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error("Error in event handler for %s: %s", event_type, e)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler to remove
        """
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                logger.debug("Unsubscribed handler from event type: %s", event_type)
            except ValueError:
                pass


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

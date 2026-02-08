"""Event bus for decoupled event publishing and consumption."""

from collections.abc import Callable
from typing import Any

from py_singleton import singleton

from pisolar.logging_config import get_logger


@singleton
class EventBus:
    """Simple event bus for publishing and subscribing to events.

    This is a singleton - all instances of EventBus will be the same object.
    """

    _logger = get_logger("event_bus")

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
        self._logger.debug("Subscribed handler to event type: %s", event_type)

    def publish(self, event_type: str, data: Any) -> None:
        """
        Publish an event to all subscribed handlers.

        Args:
            event_type: The type of event being published
            data: The event data to pass to handlers
        """
        handlers = self._subscribers.get(event_type, [])
        self._logger.debug("Publishing event %s to %d handler(s)", event_type, len(handlers))

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                self._logger.error("Error in event handler for %s: %s", event_type, e)

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
                self._logger.debug("Unsubscribed handler from event type: %s", event_type)
            except ValueError:
                pass


def get_event_bus() -> EventBus:
    """Get the global event bus instance.

    Returns the singleton EventBus instance.
    """
    return EventBus()

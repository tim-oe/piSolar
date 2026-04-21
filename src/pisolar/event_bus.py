"""Event bus for decoupled event publishing and consumption."""

from collections.abc import Callable
from typing import Any

from pisolar.logging_config import get_logger


class EventBus:
    """Simple event bus for publishing and subscribing to events."""

    _logger = get_logger("event_bus")

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        self._logger.debug("Subscribed handler to event type: %s", event_type)

    def publish(self, event_type: str, data: Any) -> None:
        """Publish an event to all subscribed handlers."""
        handlers = self._subscribers.get(event_type, [])
        self._logger.debug(
            "Publishing event %s to %d handler(s)", event_type, len(handlers)
        )
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                self._logger.error("Error in event handler for %s: %s", event_type, e)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                self._logger.debug(
                    "Unsubscribed handler from event type: %s", event_type
                )
            except ValueError:
                pass


_instance: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process-wide EventBus singleton."""
    global _instance
    if _instance is None:
        _instance = EventBus()
    return _instance


def reset_event_bus() -> None:
    """Replace the singleton with a fresh EventBus. For use in tests only."""
    global _instance
    _instance = EventBus()

# app/domain/event_bus.py

from typing import Callable, Dict, List
from app.domain.events import DomainEvent

class EventBus:
    def __init__(self):
        self._handlers: Dict[str, List[Callable[[DomainEvent], None]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[DomainEvent], None]):
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)

    def publish(self, event: DomainEvent):
        for handler in self._handlers.get(event.name, []):
            handler(event)

event_bus = EventBus()

from typing import Any, Callable, List, Optional

class Entity:
    pass

class EventType:
    def __init__(self, name: str, description: str) -> None: ...

class EventHandler:
    def __init__(
        self,
        callback_function: Callable,
        identifier: str = ...,
        safe_guards: List[Entity] = ...,
        priority: int = ...,
    ) -> None: ...

class EventExpression:
    def __init__(
        self,
        source: Optional[Entity] = ...,
        event_type: Optional[EventType] = ...,
        event_id: int = ...,
    ) -> None: ...
    @property
    def atomic_type(self) -> Optional[Any]: ...

class Protocol:
    def send_signal(self, signal: str) -> None: ...

class QuantumProcessor:
    @property
    def num_positions(self) -> int: ...

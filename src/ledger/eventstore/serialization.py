"""Event (de)serialization registry with schema upcasting.

Maps a stable ``event_type`` string to its pydantic class. On read, payloads
stored under an older ``schema_version`` are run through a chain of upcasters
before validation, so old events keep deserializing after the model evolves.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ledger.domain.shared.events import DomainEvent

type Upcaster = Callable[[dict[str, Any]], dict[str, Any]]


class UnknownEventType(ValueError):
    """Raised when a stored ``event_type`` has no registration."""


@dataclass(frozen=True, slots=True)
class _Registration:
    event_cls: type[DomainEvent]
    schema_version: int
    # upcasters[i] upgrades a payload from schema_version i+1 to i+2.
    upcasters: tuple[Upcaster, ...]


class EventRegistry:
    """Bidirectional map between event classes and their wire identity."""

    def __init__(self) -> None:
        self._by_name: dict[str, _Registration] = {}
        self._name_by_cls: dict[type[DomainEvent], str] = {}

    def register(
        self,
        event_cls: type[DomainEvent],
        *,
        name: str | None = None,
        schema_version: int = 1,
        upcasters: Sequence[Upcaster] = (),
    ) -> EventRegistry:
        """Register an event class. Returns self for chaining."""
        if len(upcasters) != schema_version - 1:
            raise ValueError(
                f"{event_cls.__name__}: schema_version={schema_version} needs "
                f"{schema_version - 1} upcaster(s), got {len(upcasters)}"
            )
        resolved = name or event_cls.__name__
        registration = _Registration(event_cls, schema_version, tuple(upcasters))
        self._by_name[resolved] = registration
        self._name_by_cls[event_cls] = resolved
        return self

    def name_for(self, event: DomainEvent) -> str:
        return self._name_by_cls[type(event)]

    def schema_version_for(self, event: DomainEvent) -> int:
        return self._by_name[self.name_for(event)].schema_version

    def serialize(self, event: DomainEvent) -> dict[str, Any]:
        return event.model_dump(mode="json")

    def deserialize(
        self, *, event_type: str, schema_version: int, payload: dict[str, Any]
    ) -> DomainEvent:
        registration = self._by_name.get(event_type)
        if registration is None:
            raise UnknownEventType(event_type)
        data = dict(payload)
        for from_version in range(schema_version, registration.schema_version):
            data = registration.upcasters[from_version - 1](data)
        return registration.event_cls.model_validate(data)

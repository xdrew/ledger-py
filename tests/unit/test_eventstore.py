"""Unit tests for the event store: append semantics, concurrency, serialization."""

from typing import Any

import pytest

from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.identifiers import new_account_id
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.records import EventMetadata
from ledger.eventstore.serialization import EventRegistry, UnknownEventType
from ledger.eventstore.store import ConcurrencyConflict, EventStore


class SampleOpened(DomainEvent):
    label: str


class SampleTagged(DomainEvent):
    tag: str


def build_registry() -> EventRegistry:
    registry = EventRegistry()
    registry.register(SampleOpened)
    registry.register(SampleTagged)
    return registry


def build_store() -> EventStore:
    # The annotation asserts InMemoryEventStore structurally satisfies EventStore.
    return InMemoryEventStore(build_registry())


class TestInMemoryEventStore:
    async def test_append_then_load(self) -> None:
        store = build_store()
        stream_id = new_account_id()
        appended = await store.append(
            stream_type="sample",
            stream_id=stream_id,
            expected_version=0,
            events=[SampleOpened(label="a"), SampleTagged(tag="x")],
            metadata=EventMetadata.empty(),
        )
        assert [e.version for e in appended] == [1, 2]
        assert [e.global_position for e in appended] == [1, 2]

        loaded = await store.load_stream(stream_type="sample", stream_id=stream_id)
        assert [e.event_type for e in loaded] == ["SampleOpened", "SampleTagged"]
        assert loaded[0].payload == {"label": "a"}

    async def test_concurrency_conflict(self) -> None:
        store = build_store()
        stream_id = new_account_id()
        await store.append(
            stream_type="sample",
            stream_id=stream_id,
            expected_version=0,
            events=[SampleOpened(label="a")],
            metadata=EventMetadata.empty(),
        )
        with pytest.raises(ConcurrencyConflict) as excinfo:
            await store.append(
                stream_type="sample",
                stream_id=stream_id,
                expected_version=0,  # stale — stream is at v1
                events=[SampleTagged(tag="y")],
                metadata=EventMetadata.empty(),
            )
        assert excinfo.value.expected == 0
        assert excinfo.value.actual == 1

    async def test_read_all_orders_by_global_position(self) -> None:
        store = build_store()
        first, second = new_account_id(), new_account_id()
        await store.append(
            stream_type="sample",
            stream_id=first,
            expected_version=0,
            events=[SampleOpened(label="one")],
            metadata=EventMetadata.empty(),
        )
        await store.append(
            stream_type="sample",
            stream_id=second,
            expected_version=0,
            events=[SampleOpened(label="two")],
            metadata=EventMetadata.empty(),
        )
        everything = await store.read_all()
        assert [e.global_position for e in everything] == [1, 2]

        tail = await store.read_all(from_position=1)
        assert [e.stream_id for e in tail] == [second]


class TestSerialization:
    def test_round_trip(self) -> None:
        registry = build_registry()
        event = SampleOpened(label="hello")
        payload = registry.serialize(event)
        restored = registry.deserialize(
            event_type="SampleOpened", schema_version=1, payload=payload
        )
        assert restored == event

    def test_unknown_event_type(self) -> None:
        with pytest.raises(UnknownEventType):
            build_registry().deserialize(event_type="Nope", schema_version=1, payload={})

    def test_upcaster_chain(self) -> None:
        # v2 renamed `label` -> `name`; a v1->v2 upcaster bridges the gap.
        def v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
            return {"name": data["label"]}

        class RenamedV2(DomainEvent):
            name: str

        registry = EventRegistry()
        registry.register(RenamedV2, name="Renamed", schema_version=2, upcasters=[v1_to_v2])

        # An old event persisted at schema_version=1 with the old field.
        restored = registry.deserialize(
            event_type="Renamed", schema_version=1, payload={"label": "legacy"}
        )
        assert restored == RenamedV2(name="legacy")

    def test_upcaster_count_must_match_schema_version(self) -> None:
        registry = EventRegistry()
        with pytest.raises(ValueError, match="upcaster"):
            registry.register(SampleOpened, schema_version=3, upcasters=[])

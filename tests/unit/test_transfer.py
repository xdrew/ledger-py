"""Unit tests for the Transfer aggregate state machine and saga id derivation."""

import pytest

from ledger.domain.shared.errors import InvalidTransition
from ledger.domain.shared.identifiers import (
    new_account_id,
    new_journal_entry_id,
    new_transfer_id,
)
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import TRANSFER_STREAM, FailureReason
from ledger.domain.transfers.operations import journal_entry_id_for, operation_id
from ledger.domain.transfers.transfer import Transfer, TransferStatus
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.repository import EventSourcedRepository


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


def _initiated() -> Transfer:
    return Transfer.initiate(new_transfer_id(), new_account_id(), new_account_id(), usd(500))


class TestTransferStateMachine:
    def test_initiate_sets_fields(self) -> None:
        transfer = _initiated()
        assert transfer.status is TransferStatus.INITIATED
        assert transfer.amount == usd(500)

    def test_happy_progression(self) -> None:
        transfer = _initiated()
        transfer.mark_held()
        assert transfer.status is TransferStatus.HELD
        transfer.mark_posted(new_journal_entry_id())
        assert transfer.status is TransferStatus.POSTED
        transfer.complete()
        assert transfer.status is TransferStatus.COMPLETED

    def test_illegal_transition_rejected(self) -> None:
        transfer = _initiated()
        with pytest.raises(InvalidTransition):
            transfer.complete()  # cannot complete an INITIATED transfer

    def test_fail_from_non_terminal(self) -> None:
        transfer = _initiated()
        transfer.mark_held()
        transfer.fail(FailureReason.INSUFFICIENT_FUNDS, "not enough")
        assert transfer.status is TransferStatus.FAILED
        assert transfer.failure_reason is FailureReason.INSUFFICIENT_FUNDS

    def test_cannot_fail_terminal(self) -> None:
        transfer = _initiated()
        transfer.mark_held()
        transfer.mark_posted(new_journal_entry_id())
        transfer.complete()
        with pytest.raises(InvalidTransition):
            transfer.fail(FailureReason.OTHER)

    def test_park_from_posted(self) -> None:
        transfer = _initiated()
        transfer.mark_held()
        transfer.mark_posted(new_journal_entry_id())
        transfer.park_for_reconciliation("credit failed")
        assert transfer.status is TransferStatus.NEEDS_RECONCILIATION

    def test_park_requires_posted(self) -> None:
        transfer = _initiated()
        with pytest.raises(InvalidTransition):
            transfer.park_for_reconciliation("nope")

    async def test_round_trip_through_repository(self) -> None:
        registry = build_event_registry()
        store = InMemoryEventStore(registry)
        repo: EventSourcedRepository[Transfer] = EventSourcedRepository(
            store=store,
            registry=registry,
            stream_type=TRANSFER_STREAM,
            factory=Transfer,
        )
        transfer = _initiated()
        transfer.mark_held()
        transfer.mark_posted(new_journal_entry_id())
        assert transfer.transfer_id is not None
        await repo.save(transfer.transfer_id, transfer)

        reloaded = await repo.load(transfer.transfer_id)
        assert reloaded is not None
        assert reloaded.status is TransferStatus.POSTED
        assert reloaded.version == 3


class TestSagaIds:
    def test_operation_id_is_deterministic_and_step_specific(self) -> None:
        transfer_id = new_transfer_id()
        assert operation_id(transfer_id, "hold") == operation_id(transfer_id, "hold")
        assert operation_id(transfer_id, "hold") != operation_id(transfer_id, "debit")

    def test_journal_entry_id_is_deterministic(self) -> None:
        transfer_id = new_transfer_id()
        assert journal_entry_id_for(transfer_id) == journal_entry_id_for(transfer_id)

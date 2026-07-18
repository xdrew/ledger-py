"""The saga populates event metadata: correlation id (transfer id) + traceparent."""

from ledger.domain.accounts.account import Account
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.ledger.events import JOURNAL_STREAM
from ledger.domain.shared.identifiers import new_account_id, new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import TRANSFER_STREAM
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.temporal.activities.transfer_activities import TransferActivities
from ledger.temporal.dependencies import build_repositories
from ledger.temporal.messages import TransferInput

TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


async def test_saga_events_carry_correlation_and_traceparent() -> None:
    registry = build_event_registry()
    store = InMemoryEventStore(registry)
    repos = build_repositories(store, registry)

    source = Account.open(new_account_id(), "USD")
    source.deposit(usd(1000))
    dest = Account.open(new_account_id(), "USD")
    assert source.account_id is not None and dest.account_id is not None
    await repos.accounts.save(source.account_id, source)
    await repos.accounts.save(dest.account_id, dest)

    acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
    data = TransferInput(
        transfer_id=new_transfer_id(),
        source_account_id=source.account_id,
        destination_account_id=dest.account_id,
        amount=usd(400),
        traceparent=TRACEPARENT,
    )
    await acts.record_initiated(data)
    await acts.hold_funds(data)
    await acts.post_journal(data)
    await acts.settle_debit(data)
    await acts.settle_credit(data)

    # Every event the saga produced across all three streams shares the transfer
    # id as correlation and carries the request's traceparent. (The account
    # open/deposit events, saved without saga metadata, are excluded.)
    transfer_events = await store.load_stream(
        stream_type=TRANSFER_STREAM, stream_id=data.transfer_id
    )
    journal_events = await store.read_all(from_position=0)
    saga_events = [
        *transfer_events,
        *[e for e in journal_events if e.stream_type == JOURNAL_STREAM],
    ]
    assert saga_events, "expected saga to produce events"
    for event in saga_events:
        assert event.metadata.correlation_id == data.transfer_id
        assert event.metadata.traceparent == TRACEPARENT

    # The source's saga-driven events (hold, debit) also carry the correlation id.
    source_events = await store.load_stream(stream_type=ACCOUNT_STREAM, stream_id=source.account_id)
    saga_source_events = [
        e for e in source_events if e.event_type in {"FundsHeld", "AccountDebited"}
    ]
    assert saga_source_events
    for event in saga_source_events:
        assert event.metadata.correlation_id == data.transfer_id
        assert event.metadata.traceparent == TRACEPARENT

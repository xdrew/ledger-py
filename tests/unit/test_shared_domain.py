"""Unit tests for the shared domain: Money and AggregateRoot."""

import pytest

from ledger.domain.shared import identifiers as ids
from ledger.domain.shared.aggregate import AggregateRoot
from ledger.domain.shared.errors import CurrencyMismatch, InvalidAmount
from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.money import Money


class TestMoney:
    def test_add_same_currency(self) -> None:
        assert Money(amount=100, currency="USD").add(Money(amount=50, currency="USD")) == Money(
            amount=150, currency="USD"
        )

    def test_subtract_can_go_negative(self) -> None:
        result = Money(amount=100, currency="USD").subtract(Money(amount=150, currency="USD"))
        assert result == Money(amount=-50, currency="USD")
        assert result.is_negative

    def test_currency_mismatch_on_add(self) -> None:
        with pytest.raises(CurrencyMismatch):
            Money(amount=100, currency="USD").add(Money(amount=1, currency="EUR"))

    def test_currency_mismatch_on_compare(self) -> None:
        with pytest.raises(CurrencyMismatch):
            _ = Money(amount=1, currency="USD") < Money(amount=1, currency="EUR")

    def test_assert_positive_rejects_zero(self) -> None:
        with pytest.raises(InvalidAmount):
            Money.zero("USD").assert_positive()

    def test_ordering(self) -> None:
        assert Money(amount=10, currency="USD") < Money(amount=20, currency="USD")
        assert Money(amount=20, currency="USD") <= Money(amount=20, currency="USD")

    def test_frozen(self) -> None:
        money = Money(amount=1, currency="USD")
        with pytest.raises(Exception):  # noqa: B017 — pydantic raises ValidationError on frozen mutation
            money.amount = 2  # type: ignore[misc]

    def test_invalid_currency_code_rejected(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 — ValidationError
            Money(amount=1, currency="usd")

    def test_negate_and_signs(self) -> None:
        positive = Money(amount=5, currency="USD")
        assert positive.is_positive
        assert positive.negate() == Money(amount=-5, currency="USD")
        assert Money.zero("USD").is_positive is False

    def test_le_currency_mismatch(self) -> None:
        with pytest.raises(CurrencyMismatch):
            _ = Money(amount=1, currency="USD") <= Money(amount=1, currency="EUR")

    def test_assert_positive_returns_self(self) -> None:
        money = Money(amount=1, currency="USD")
        assert money.assert_positive() is money

    def test_str(self) -> None:
        assert str(Money(amount=250, currency="EUR")) == "250 EUR"


class TestIdentifiers:
    def test_factories_produce_time_ordered_uuids(self) -> None:
        factories = [
            ids.new_account_id,
            ids.new_transfer_id,
            ids.new_journal_entry_id,
            ids.new_event_id,
            ids.new_correlation_id,
        ]
        for factory in factories:
            first, second = factory(), factory()
            assert first.version == 7
            assert first < second


# --- A tiny aggregate to exercise AggregateRoot ---


class Incremented(DomainEvent):
    by: int


type CounterEvent = Incremented


class Counter(AggregateRoot[CounterEvent]):
    def __init__(self) -> None:
        super().__init__()
        self.total = 0

    def increment(self, by: int) -> None:
        self._record(Incremented(by=by))

    def _apply(self, event: CounterEvent) -> None:
        match event:
            case Incremented(by=by):
                self.total += by


class TestAggregateRoot:
    def test_record_applies_and_buffers(self) -> None:
        counter = Counter()
        counter.increment(3)
        counter.increment(4)
        assert counter.total == 7
        assert counter.version == 2
        assert counter.expected_version == 0  # nothing committed yet
        assert counter.has_pending_events

    def test_pull_clears_buffer(self) -> None:
        counter = Counter()
        counter.increment(1)
        pending = counter.pull_pending_events()
        assert [e.by for e in pending] == [1]
        assert not counter.has_pending_events
        assert counter.expected_version == 1  # now "committed"

    def test_replay_reconstructs_state(self) -> None:
        counter = Counter()
        counter.load_from_history([Incremented(by=5), Incremented(by=10)])
        assert counter.total == 15
        assert counter.version == 2
        assert counter.expected_version == 2
        assert not counter.has_pending_events

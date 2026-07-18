"""Property-based tests for the double-entry balance invariant.

Exercised through the public ``JournalEntry.post`` (which enforces the balance
rule) rather than the private helper.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ledger.domain.ledger.journal_entry import JournalEntry
from ledger.domain.ledger.leg import Leg
from ledger.domain.shared.errors import UnbalancedEntry
from ledger.domain.shared.identifiers import new_account_id, new_journal_entry_id
from ledger.domain.shared.money import Money

pos_amounts = st.integers(min_value=1, max_value=10**12)
currencies = st.sampled_from(["USD", "EUR", "GBP"])
# Each spec contributes one debit and one credit of the same amount+currency, so
# any generated set balances per currency by construction.
balanced_specs = st.lists(st.tuples(pos_amounts, currencies), min_size=1, max_size=8)


def _balanced_legs(specs: list[tuple[int, str]]) -> list[Leg]:
    legs: list[Leg] = []
    for amount, currency in specs:
        money = Money(amount=amount, currency=currency)
        legs.append(Leg.debit(new_account_id(), money))
        legs.append(Leg.credit(new_account_id(), money))
    return legs


@given(specs=balanced_specs)
def test_balanced_set_is_accepted(specs: list[tuple[int, str]]) -> None:
    entry = JournalEntry.post(new_journal_entry_id(), _balanced_legs(specs))
    assert entry.posted


@given(specs=balanced_specs, extra=pos_amounts, currency=currencies)
def test_unmatched_leg_makes_it_imbalanced(
    specs: list[tuple[int, str]], extra: int, currency: str
) -> None:
    legs = _balanced_legs(specs)
    legs.append(Leg.debit(new_account_id(), Money(amount=extra, currency=currency)))
    with pytest.raises(UnbalancedEntry):
        JournalEntry.post(new_journal_entry_id(), legs)


@given(specs=balanced_specs)
def test_all_debit_set_is_rejected(specs: list[tuple[int, str]]) -> None:
    legs = [Leg.debit(new_account_id(), Money(amount=a, currency=c)) for a, c in specs]
    with pytest.raises(UnbalancedEntry):
        JournalEntry.post(new_journal_entry_id(), legs)

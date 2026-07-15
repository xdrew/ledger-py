"""The ``JournalEntry`` aggregate — a write-once, balanced double-entry posting."""

from collections import defaultdict
from collections.abc import Sequence
from typing import Self

from ledger.domain.ledger.events import JournalEntryPosted, JournalEvent
from ledger.domain.ledger.leg import Leg, LegDirection
from ledger.domain.shared.aggregate import AggregateRoot
from ledger.domain.shared.errors import UnbalancedEntry
from ledger.domain.shared.identifiers import JournalEntryId


def _assert_balanced(legs: Sequence[Leg]) -> None:
    if not legs:
        raise UnbalancedEntry("entry has no legs")

    debit_total: dict[str, int] = defaultdict(int)
    credit_total: dict[str, int] = defaultdict(int)
    for leg in legs:
        leg.amount.assert_positive()
        if leg.direction is LegDirection.DEBIT:
            debit_total[leg.amount.currency] += leg.amount.amount
        else:
            credit_total[leg.amount.currency] += leg.amount.amount

    if not debit_total or not credit_total:
        raise UnbalancedEntry("entry needs at least one debit and one credit")

    for currency in debit_total.keys() | credit_total.keys():
        debit = debit_total[currency]
        credit = credit_total[currency]
        if debit != credit:
            raise UnbalancedEntry(f"{currency} unbalanced: debit {debit} != credit {credit}")


class JournalEntry(AggregateRoot[JournalEvent]):
    def __init__(self) -> None:
        super().__init__()
        self.entry_id: JournalEntryId | None = None
        self.legs: tuple[Leg, ...] = ()
        self.posted: bool = False

    @classmethod
    def post(
        cls,
        entry_id: JournalEntryId,
        legs: Sequence[Leg],
        reference: str | None = None,
    ) -> Self:
        _assert_balanced(legs)
        entry = cls()
        entry.entry_id = entry_id
        entry._record(JournalEntryPosted(legs=tuple(legs), reference=reference))
        return entry

    def _apply(self, event: JournalEvent) -> None:
        match event:
            case JournalEntryPosted(legs=legs):
                self.legs = legs
                self.posted = True

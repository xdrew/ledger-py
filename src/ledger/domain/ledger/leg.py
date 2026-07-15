"""A journal ``Leg`` — one side of a double-entry posting."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from ledger.domain.shared.identifiers import AccountId
from ledger.domain.shared.money import Money


class LegDirection(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class Leg(BaseModel):
    """A signed posting against one account. ``amount`` is always positive; the
    direction carries the sign."""

    model_config = ConfigDict(frozen=True)

    account_id: AccountId
    direction: LegDirection
    amount: Money

    @classmethod
    def debit(cls, account_id: AccountId, amount: Money) -> Leg:
        return cls(account_id=account_id, direction=LegDirection.DEBIT, amount=amount)

    @classmethod
    def credit(cls, account_id: AccountId, amount: Money) -> Leg:
        return cls(account_id=account_id, direction=LegDirection.CREDIT, amount=amount)

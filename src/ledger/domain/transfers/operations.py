"""Deterministic id derivation for saga steps.

Both the per-step account operation ids (idempotency keys) and the journal entry
id are pure functions of the transfer id. That means every Temporal activity
retry — and every workflow replay — computes the *same* ids, which is what makes
the account operations and the journal posting idempotent.
"""

import uuid

from ledger.domain.shared.identifiers import JournalEntryId, TransferId

# Fixed namespace so ids are stable across processes and restarts.
_NAMESPACE = uuid.UUID("6f1c9d2e-0000-5000-8000-0000000ab1e5")


def operation_id(transfer_id: TransferId, step: str) -> uuid.UUID:
    """Idempotency key for a balance-moving step (hold/debit/credit/release)."""
    return uuid.uuid5(_NAMESPACE, f"{transfer_id}:{step}")


def journal_entry_id_for(transfer_id: TransferId) -> JournalEntryId:
    return uuid.uuid5(_NAMESPACE, f"{transfer_id}:journal")

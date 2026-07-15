"""Domain error hierarchy.

Domain errors are business-rule violations, distinct from infrastructure
failures. They carry a stable ``code`` so the API layer can map them to RFC7807
problem types without string-matching messages.
"""


class DomainError(Exception):
    """Base class for all business-rule violations."""

    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CurrencyMismatch(DomainError):
    code = "currency_mismatch"


class InvalidAmount(DomainError):
    code = "invalid_amount"


class InsufficientFunds(DomainError):
    code = "insufficient_funds"


class AccountNotActive(DomainError):
    code = "account_not_active"


class InvalidTransition(DomainError):
    code = "invalid_transition"


class UnbalancedEntry(DomainError):
    code = "unbalanced_entry"


class UnknownAccount(DomainError):
    code = "unknown_account"


class AccountNotEmpty(DomainError):
    code = "account_not_empty"


class NotFound(DomainError):
    code = "not_found"

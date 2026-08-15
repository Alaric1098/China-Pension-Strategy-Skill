"""Exceptions raised by pure domain objects."""


class DomainError(Exception):
    """Base class for domain failures."""


class DomainValidationError(DomainError, ValueError):
    """Raised when a domain object would violate an invariant."""


class CurrencyMismatchError(DomainError, ValueError):
    """Raised when an operation combines amounts in different currencies."""

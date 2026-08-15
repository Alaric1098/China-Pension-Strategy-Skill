"""Immutable references to normalized input facts."""

from dataclasses import dataclass

from china_pension_strategy.domain.errors import DomainValidationError


@dataclass(frozen=True)
class FactReference:
    """Stable identity of a fact used by an assessment."""

    fact_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.fact_id, str) or not self.fact_id.strip():
            raise DomainValidationError("fact_id must be a non-empty string")

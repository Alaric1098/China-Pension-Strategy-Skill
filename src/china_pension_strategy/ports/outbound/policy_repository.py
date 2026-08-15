"""Outbound policy package repository boundary."""

from typing import Iterable, Protocol

from china_pension_strategy.domain.policy import PolicyPackage


class PolicyRepository(Protocol):
    def list_packages(self) -> Iterable[PolicyPackage]:
        """Return policy packages available to deterministic resolution."""

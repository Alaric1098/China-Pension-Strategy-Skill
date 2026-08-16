"""Outbound policy package repository boundary."""

from collections.abc import Iterable
from typing import Protocol

from china_pension_strategy.domain.policy import PolicyPackage


class PolicyRepository(Protocol):
    def list_packages(self) -> Iterable[PolicyPackage]:
        """Return policy packages available to deterministic resolution."""

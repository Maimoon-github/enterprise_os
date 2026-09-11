"""Evaluates tenant scope and delegated authority."""
from __future__ import annotations


class ScopeEvaluator:
    def is_subset(self, requested: set[str], granted: set[str]) -> bool:
        return requested.issubset(granted)

    def attenuate(self, granted: set[str], requested: set[str]) -> set[str]:
        return granted & requested

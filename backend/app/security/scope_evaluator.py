"""Evaluates tenant scope and delegated authority."""

from __future__ import annotations

from app.schemas.governance import TenantScope


class ScopeEvaluator:
    """Evaluates whether a requested scope is within delegated tenant authority."""

    def evaluate(self, requested_scope: TenantScope, delegated_scope: TenantScope) -> bool:
        """Return True if ``requested_scope`` is a subset of ``delegated_scope``."""

        return requested_scope.is_subset_of(delegated_scope)
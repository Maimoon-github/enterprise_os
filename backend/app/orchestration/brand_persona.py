"""Applies tenant-specific brand rules and institutional context."""
from __future__ import annotations


class BrandPersona:
    def __init__(self, rules: dict | None = None) -> None:
        self.rules = rules or {}

    def apply(self, tenant_id: str, payload: dict) -> dict:
        tenant_rules = self.rules.get(tenant_id, {})
        merged = dict(payload)
        merged["brand_rules"] = tenant_rules
        return merged

"""Applies tenant-specific brand rules and institutional context."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrandPersona:
    """A resolved set of brand-voice rules for a tenant."""

    tenant_id: str
    voice: str = "neutral"
    prohibited_terms: tuple[str, ...] = field(default_factory=tuple)
    required_disclaimers: tuple[str, ...] = field(default_factory=tuple)


class BrandPersonaResolver:
    """Resolves a tenant's institutional brand persona.

    Persona rules are held in-memory here as sane defaults; production
    deployments back this with the institutional memory store via
    ``app.services.memory_promotion`` and ``app.persistence.repositories.memory``.
    """

    def __init__(self, personas: dict[str, BrandPersona] | None = None) -> None:
        self._personas = personas or {}

    def register(self, persona: BrandPersona) -> None:
        """Register or replace the persona for a tenant."""

        self._personas[persona.tenant_id] = persona

    def resolve(self, *, tenant_id: str) -> BrandPersona:
        """Return the persona for ``tenant_id``, or a neutral default."""

        return self._personas.get(tenant_id, BrandPersona(tenant_id=tenant_id))
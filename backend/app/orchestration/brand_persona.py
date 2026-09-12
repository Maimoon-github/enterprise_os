"""Applies tenant-specific brand rules and institutional context."""

from __future__ import annotations

from dataclasses import dataclass, field


from app.persistence.repositories.memory import MemoryRepository


@dataclass(frozen=True)
class BrandPersona:
    """A resolved set of brand-voice rules for a tenant."""

    tenant_id: str
    voice: str = "neutral"
    prohibited_terms: tuple[str, ...] = field(default_factory=tuple)
    required_disclaimers: tuple[str, ...] = field(default_factory=tuple)
    learned_heuristics: tuple[str, ...] = field(default_factory=tuple)


class BrandPersonaResolver:
    """Resolves a tenant's institutional brand persona.

    Persona rules can be held in-memory as sane defaults or resolved dynamically
    from the institutional memory store via ``app.persistence.repositories.memory``.
    """

    def __init__(
        self,
        personas: dict[str, BrandPersona] | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self._personas = personas or {}
        self._memory_repository = memory_repository

    def register(self, persona: BrandPersona) -> None:
        """Register or replace the persona for a tenant."""

        self._personas[persona.tenant_id] = persona

    async def resolve_with_memory(self, *, tenant_id: str) -> BrandPersona:
        """Return the persona for ``tenant_id`` enriched with institutional memory records."""
        base = self.resolve(tenant_id=tenant_id)
        if self._memory_repository is None or not hasattr(self._memory_repository, "list_by_tenant"):
            return base

        records = await self._memory_repository.list_by_tenant(tenant_id)
        if not records:
            return base

        heuristics = list(base.learned_heuristics)
        voice = base.voice
        prohibited = list(base.prohibited_terms)
        disclaimers = list(base.required_disclaimers)

        for rec in records:
            heuristics.append(f"{rec.category}: {rec.statement}")
            if rec.category == "brand_voice" and rec.confidence >= 0.8:
                voice = rec.statement
            elif rec.category == "prohibited_terms":
                prohibited.extend(term.strip() for term in rec.statement.split(",") if term.strip())
            elif rec.category == "disclaimer":
                disclaimers.append(rec.statement)

        enriched = BrandPersona(
            tenant_id=tenant_id,
            voice=voice,
            prohibited_terms=tuple(set(prohibited)),
            required_disclaimers=tuple(set(disclaimers)),
            learned_heuristics=tuple(heuristics),
        )
        self._personas[tenant_id] = enriched
        return enriched

    def resolve(self, *, tenant_id: str) -> BrandPersona:
        """Return the persona for ``tenant_id``, or a neutral default."""

        return self._personas.get(tenant_id, BrandPersona(tenant_id=tenant_id))
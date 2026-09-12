"""Applies tenant-specific brand rules and institutional context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.persistence.repositories.memory import MemoryRepository


@dataclass(frozen=True)
class BrandPersona:
    """A resolved set of brand-voice rules for a tenant and brand."""

    tenant_id: str
    brand_id: str = "default"
    voice: str = "neutral"
    version: str = "1.0"
    prohibited_terms: tuple[str, ...] = field(default_factory=tuple)
    required_disclaimers: tuple[str, ...] = field(default_factory=tuple)
    tone_attributes: tuple[str, ...] = field(default_factory=tuple)
    style_guide_rules: tuple[str, ...] = field(default_factory=tuple)
    learned_heuristics: tuple[str, ...] = field(default_factory=tuple)
    constraints: tuple[str, ...] = field(default_factory=tuple)


class BrandPersonaResolver:
    """Resolves a tenant's institutional brand persona.

    Persona rules can be held in-memory as sane defaults or resolved dynamically
    from the institutional memory store via ``app.persistence.repositories.memory``.
    Guarantees strict tenant isolation and policy non-override.
    """

    def __init__(
        self,
        personas: dict[str, BrandPersona] | dict[tuple[str, str], BrandPersona] | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self._personas: dict[tuple[str, str], BrandPersona] = {}
        if personas:
            for k, p in personas.items():
                if isinstance(k, tuple):
                    self._personas[k] = p
                else:
                    self._personas[(k, p.brand_id)] = p
        self._memory_repository = memory_repository

    def register(self, persona: BrandPersona) -> None:
        """Register or replace the persona for a tenant and brand."""
        self._personas[(persona.tenant_id, persona.brand_id)] = persona

    async def resolve_with_memory(
        self, *, tenant_id: str, brand_id: str = "default"
    ) -> BrandPersona:
        """Return the persona for ``(tenant_id, brand_id)`` enriched with institutional memory records."""
        base = self.resolve(tenant_id=tenant_id, brand_id=brand_id)
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
            brand_id=brand_id,
            voice=voice,
            version=base.version,
            prohibited_terms=tuple(sorted(set(prohibited))),
            required_disclaimers=tuple(sorted(set(disclaimers))),
            tone_attributes=base.tone_attributes,
            style_guide_rules=base.style_guide_rules,
            learned_heuristics=tuple(heuristics),
            constraints=base.constraints,
        )
        self._personas[(tenant_id, brand_id)] = enriched
        return enriched

    def resolve(self, *, tenant_id: str, brand_id: str = "default") -> BrandPersona:
        """Return the persona for ``(tenant_id, brand_id)``, strictly preventing cross-tenant leakage."""
        if not tenant_id:
            return BrandPersona(tenant_id="", brand_id=brand_id)

        # 1. Exact match for (tenant_id, brand_id)
        if (tenant_id, brand_id) in self._personas:
            return self._personas[(tenant_id, brand_id)]

        # 2. Fallback to default brand for same tenant
        if (tenant_id, "default") in self._personas:
            return self._personas[(tenant_id, "default")]

        # 3. Fallback to fresh isolated default for this tenant (never return another tenant's persona)
        return BrandPersona(tenant_id=tenant_id, brand_id=brand_id)

    def sanitize_against_policy(
        self,
        persona: BrandPersona,
        *,
        policy_prohibited_terms: Sequence[str] = (),
        policy_risk_ceiling: str = "",
    ) -> BrandPersona:
        """Ensure brand persona cannot override or weaken higher-level enterprise policy."""
        merged_prohibited = sorted(set(list(persona.prohibited_terms) + list(policy_prohibited_terms)))
        return BrandPersona(
            tenant_id=persona.tenant_id,
            brand_id=persona.brand_id,
            voice=persona.voice,
            version=persona.version,
            prohibited_terms=tuple(merged_prohibited),
            required_disclaimers=persona.required_disclaimers,
            tone_attributes=persona.tone_attributes,
            style_guide_rules=persona.style_guide_rules,
            learned_heuristics=persona.learned_heuristics,
            constraints=persona.constraints,
        )
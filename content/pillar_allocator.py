# pyright: reportMissingImports=false
"""Strategic Content Pillar Allocator and Queue Scheduler (TSK-07).
Enforces 35% Educational, 25% Proof/Demos, 20% Brand Story, and 20% Offers/Conversion distribution.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.state import BrandProfile


class PillarSlot(BaseModel):
    """Publishing slot designated for a specific strategic content pillar."""

    slot_id: str
    day_number: int
    pillar: str
    funnel_stage: str  # "ToFu", "MoFu", "BoFu"
    recommended_format: str
    objective: str
    target_metric: str


class PillarBalanceReport(BaseModel):
    """Validation report detailing strategic pillar allocation fidelity."""

    is_balanced: bool
    total_slots: int
    counts: Dict[str, int]
    observed_ratios: Dict[str, float]
    target_ratios: Dict[str, float]
    max_variance: float


class PillarAllocator:
    """Enforces strategic pillar quotas and generates interleaved multi-channel schedules."""

    TARGET_RATIOS: Dict[str, float] = {
        "35% Educational": 0.35,
        "25% Proof/Demos": 0.25,
        "20% Brand Story": 0.20,
        "20% Offers/Conversion": 0.20,
    }

    PILLAR_METADATA: Dict[str, Dict[str, str]] = {
        "35% Educational": {
            "funnel_stage": "ToFu",
            "format": "LinkedIn Carousel & SEO Guide",
            "objective": "Build organic authority, explain core problem frameworks, value-first reach.",
            "metric": "Impressions, Saves & Reach",
        },
        "25% Proof/Demos": {
            "funnel_stage": "MoFu",
            "format": "Case Study Breakdown & Customer Teardown",
            "objective": "Provide undeniable transformation proof, data metrics, and clinical/user results.",
            "metric": "Engagement Rate & Returning Visitors",
        },
        "20% Brand Story": {
            "funnel_stage": "ToFu/MoFu",
            "format": "Founder Manifesto & Behind-the-Scenes Video",
            "objective": "Establish authentic human connection, brand values, and core founding vision.",
            "metric": "Comments & Profile Visits",
        },
        "20% Offers/Conversion": {
            "funnel_stage": "BoFu",
            "format": "Frictionless Checkout Offer & Direct Response Copy",
            "objective": "Drive immediate conversion with risk reversals, clear bundles, and zero friction.",
            "metric": "Add-to-Cart Rate & Conversions",
        },
    }

    def allocate_schedule(
        self,
        total_slots: int = 20,
        brand: Optional[BrandProfile] = None,
    ) -> List[PillarSlot]:
        """Generate balanced, interleaved publishing schedule adhering to the 35/25/20/20 formula."""
        total = max(total_slots, 4)

        # 1. Compute exact integer quota per pillar
        count_edu = round(total * 0.35)
        count_proof = round(total * 0.25)
        count_story = round(total * 0.20)
        count_offers = total - (count_edu + count_proof + count_story)

        pool = (
            ["35% Educational"] * count_edu
            + ["25% Proof/Demos"] * count_proof
            + ["20% Brand Story"] * count_story
            + ["20% Offers/Conversion"] * count_offers
        )

        # 2. Interleave cadences (avoid clustering conversion offers back-to-back)
        pattern = ["35% Educational", "25% Proof/Demos", "35% Educational", "20% Brand Story", "20% Offers/Conversion"]
        interleaved: List[str] = []
        counts_rem = {
            "35% Educational": count_edu,
            "25% Proof/Demos": count_proof,
            "20% Brand Story": count_story,
            "20% Offers/Conversion": count_offers,
        }

        while len(interleaved) < total:
            added_in_cycle = False
            for p in pattern:
                if counts_rem.get(p, 0) > 0 and len(interleaved) < total:
                    interleaved.append(p)
                    counts_rem[p] -= 1
                    added_in_cycle = True
            if not added_in_cycle:
                # Append any remaining allocations
                for p, rem in list(counts_rem.items()):
                    while rem > 0 and len(interleaved) < total:
                        interleaved.append(p)
                        rem -= 1
                    counts_rem[p] = rem
                break

        slots: List[PillarSlot] = []
        for idx, pillar in enumerate(interleaved, 1):
            meta = self.PILLAR_METADATA[pillar]
            slots.append(
                PillarSlot(
                    slot_id=f"SLOT-{idx:03d}",
                    day_number=idx,
                    pillar=pillar,
                    funnel_stage=meta["funnel_stage"],
                    recommended_format=meta["format"],
                    objective=meta["objective"],
                    target_metric=meta["metric"],
                )
            )

        return slots

    def verify_pillar_balance(
        self,
        slots: List[Any],
        tolerance: float = 0.08,
    ) -> PillarBalanceReport:
        """Validate that schedule matches strategic 35/25/20/20 allocation within tolerance."""
        total = len(slots)
        if total == 0:
            return PillarBalanceReport(
                is_balanced=True,
                total_slots=0,
                counts={},
                observed_ratios={},
                target_ratios=self.TARGET_RATIOS,
                max_variance=0.0,
            )

        counts: Dict[str, int] = {k: 0 for k in self.TARGET_RATIOS}
        for item in slots:
            pillar = item.pillar if hasattr(item, "pillar") else str(item.get("pillar", ""))
            if pillar in counts:
                counts[pillar] += 1
            else:
                # Match partial string
                for target_k in self.TARGET_RATIOS:
                    if target_k.lower() in pillar.lower() or pillar.lower() in target_k.lower():
                        counts[target_k] += 1
                        break

        observed = {k: round(counts[k] / total, 3) for k in self.TARGET_RATIOS}
        variances = {k: abs(observed[k] - self.TARGET_RATIOS[k]) for k in self.TARGET_RATIOS}
        max_var = max(variances.values())

        is_balanced = max_var <= tolerance

        return PillarBalanceReport(
            is_balanced=is_balanced,
            total_slots=total,
            counts=counts,
            observed_ratios=observed,
            target_ratios=self.TARGET_RATIOS,
            max_variance=round(max_var, 3),
        )

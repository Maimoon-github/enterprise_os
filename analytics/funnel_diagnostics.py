# pyright: reportMissingImports=false
"""Funnel Bottleneck Diagnostics Heuristics Engine (TSK-08).
Maps cross-funnel drop-offs to actionable root causes and strategic interventions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.state import AuditMetrics


class FunnelBottleneck(BaseModel):
    """Diagnosed drop-off point within the customer acquisition and conversion funnel."""

    stage: str  # "ToFu", "MoFu", "BoFu", "Unit_Economics"
    symptom: str
    root_cause: str
    recommended_action: str
    severity: str  # "critical", "high", "medium"
    metrics_evidence: Dict[str, Any] = Field(default_factory=dict)


class FunnelDiagnosticReport(BaseModel):
    """Comprehensive diagnostic evaluation of the end-to-end commercial funnel."""

    bottlenecks: List[FunnelBottleneck] = Field(default_factory=list)
    primary_bottleneck_stage: str = "Healthy"
    overall_health: str = "Good"  # "Optimal", "Good", "Needs_Optimization", "Critical"
    strategic_summary: str = ""


class FunnelDiagnosticEngine:
    """Evaluates cross-stage ratios and flags leakages across ToFu, MoFu, and BoFu."""

    def diagnose(
        self,
        audit: AuditMetrics,
        reach: Optional[int] = None,
        traffic: Optional[int] = None,
        conversions: Optional[int] = None,
    ) -> FunnelDiagnosticReport:
        """Run heuristic diagnosis across awareness, consideration, and checkout completion."""
        r_reach = reach if reach is not None else audit.reach
        r_traffic = traffic if traffic is not None else audit.traffic
        r_conversions = conversions if conversions is not None else audit.conversions
        bounce_rate = audit.bounce_rate
        baymard_issues = audit.baymard_issues
        roas = audit.roas

        bottlenecks: List[FunnelBottleneck] = []

        # Heuristic 1: ToFu Awareness -> Traffic Leakage
        # High Reach + Low Traffic -> Hook or creative angle weakness
        ctr = (r_traffic / max(r_reach, 1)) * 100 if r_reach > 0 else 0.0
        if r_reach >= 30000 and ctr < 1.8:
            bottlenecks.append(
                FunnelBottleneck(
                    stage="ToFu",
                    symptom=f"High Reach ({r_reach:,}) with Low Traffic ({r_traffic:,}), CTR={ctr:.2f}%",
                    root_cause="Distribution hook weakness or unengaging creative scroll-stopper.",
                    recommended_action="Iterate high-curiosity video hooks and test 35% Educational problem-breakdown carousels.",
                    severity="high",
                    metrics_evidence={"reach": r_reach, "traffic": r_traffic, "ctr_pct": round(ctr, 2)},
                )
            )

        # Heuristic 2: MoFu Traffic -> Consideration Leakage
        # High Bounce Rate (> 55%) -> Value proposition mismatch / missing social proof
        if r_traffic >= 5000 and bounce_rate > 0.55:
            bottlenecks.append(
                FunnelBottleneck(
                    stage="MoFu",
                    symptom=f"High Storefront Bounce Rate ({bounce_rate*100:.1f}%)",
                    root_cause="Immediate visitor drop-off due to lack of above-the-fold social proof or slow load time.",
                    recommended_action="Deploy 25% Proof/Demos transformation case studies and place customer reviews above the fold.",
                    severity="medium",
                    metrics_evidence={"bounce_rate": bounce_rate, "traffic": r_traffic},
                )
            )

        # Heuristic 3: BoFu Traffic -> Conversion Leakage
        # High Traffic + Low Conversions (< 2.0%) or Baymard checkout friction
        cvr = (r_conversions / max(r_traffic, 1)) * 100 if r_traffic > 0 else 0.0
        if (r_traffic >= 5000 and cvr < 2.0) or len(baymard_issues) > 0:
            severity = "critical" if any("critical" in b.lower() or "baymard-01" in b.lower() for b in baymard_issues) else "high"
            bottlenecks.append(
                FunnelBottleneck(
                    stage="BoFu",
                    symptom=f"Low Checkout Conversion Rate ({cvr:.2f}%) with {len(baymard_issues)} Baymard friction issues",
                    root_cause="Landing page checkout drop-off caused by hidden shipping fees, forced registration, or missing trust badges.",
                    recommended_action="Eliminate surprise fees, offer guest checkout, and display SSL security badges at payment.",
                    severity=severity,
                    metrics_evidence={"conversion_rate_pct": round(cvr, 2), "baymard_issues_count": len(baymard_issues)},
                )
            )

        # Heuristic 4: Commercial Unit Economics Leakage
        if roas > 0 and roas < 2.2:
            bottlenecks.append(
                FunnelBottleneck(
                    stage="Unit_Economics",
                    symptom=f"Low ROAS ({roas:.2f}x)",
                    root_cause="Paid customer acquisition spend outpaces customer contribution margin.",
                    recommended_action="Reallocate budget away from broad paid campaigns to high-intent retargeting and organic ToFu.",
                    severity="critical",
                    metrics_evidence={"roas": roas, "health_ratio": audit.health_ratio},
                )
            )

        # Determine primary bottleneck stage
        stage_priority = {"critical": 0, "high": 1, "medium": 2}
        if bottlenecks:
            bottlenecks.sort(key=lambda b: stage_priority.get(b.severity, 99))
            primary_stage = bottlenecks[0].stage
            overall_health = "Critical" if bottlenecks[0].severity == "critical" else "Needs_Optimization"
            summary = f"Identified {len(bottlenecks)} funnel leakage point(s). Primary bottleneck concentrated in {primary_stage}: {bottlenecks[0].root_cause}"
        else:
            primary_stage = "None"
            overall_health = "Optimal"
            summary = "All funnel stages performing within healthy operational benchmarks."

        return FunnelDiagnosticReport(
            bottlenecks=bottlenecks,
            primary_bottleneck_stage=primary_stage,
            overall_health=overall_health,
            strategic_summary=summary,
        )

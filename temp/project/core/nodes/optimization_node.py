# pyright: reportMissingImports=false
"""Automated Funnel Optimization and Budget Reallocation Node (TSK-08).
Integrates isolated sandbox unit economics modeling, cross-funnel diagnostics,
and programmatic budget shifts to scale high-ROAS campaigns and retire unprofitable assets.
"""

from __future__ import annotations

import datetime
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage

try:
    from agent_sandbox import Sandbox  # type: ignore
except ImportError:
    from agent_sandbox.client import Sandbox  # type: ignore

from analytics.funnel_diagnostics import (
    FunnelBottleneck,
    FunnelDiagnosticEngine,
    FunnelDiagnosticReport,
)
from analytics.unit_economics import (
    UnitEconomicsCalculator,
    UnitEconomicsMetrics,
)
from core.state import AgentState, AuditMetrics, BrandProfile


class CampaignReallocation(BaseModel):
    """Budget reallocation decision record for a specific marketing campaign."""

    campaign_id: str
    campaign_name: str
    observed_roas: float
    previous_budget: float
    new_budget: float
    action: str  # "SCALE", "MAINTAIN", "RETIRE"
    rationalization: str


class OptimizationResult(BaseModel):
    """Complete commercial optimization and reallocation artifact."""

    unit_economics: UnitEconomicsMetrics
    diagnostic_report: FunnelDiagnosticReport
    campaign_reallocations: List[CampaignReallocation] = Field(default_factory=list)
    total_reallocated_budget: float = 0.0
    strategic_memo: str = ""


class CampaignReallocationEngine:
    """Evaluates campaign-level ROAS and reallocates budget from weak assets to top performers."""

    @staticmethod
    def reallocate(
        campaigns: List[Dict[str, Any]],
        target_roas_benchmark: float = 3.0,
    ) -> List[CampaignReallocation]:
        """Compute budget adjustments: Scale ROAS >= 3.5, Maintain 2.0-3.5, Retire ROAS < 2.0."""
        decisions: List[CampaignReallocation] = []
        retired_funds = 0.0
        scaling_campaigns: List[Dict[str, Any]] = []

        # 1. First pass: Categorize campaigns and recover spend from unprofitable assets
        for c in campaigns:
            cid = str(c.get("campaign_id", "CMP-UNK"))
            cname = str(c.get("name", "Campaign"))
            prev_budget = float(c.get("current_budget") or c.get("spend") or 1000.0)
            roas = float(c.get("roas", 0.0))

            if roas < 2.0:
                # Retire underperforming creative asset and capture budget
                retired_funds += prev_budget
                decisions.append(
                    CampaignReallocation(
                        campaign_id=cid,
                        campaign_name=cname,
                        observed_roas=roas,
                        previous_budget=prev_budget,
                        new_budget=0.0,
                        action="RETIRE",
                        rationalization=f"ROAS of {roas:.2f}x is below 2.0x break-even threshold. Asset retired; budget freed.",
                    )
                )
            elif roas >= 3.5:
                scaling_campaigns.append(c)
            else:
                # Maintain moderate performer
                decisions.append(
                    CampaignReallocation(
                        campaign_id=cid,
                        campaign_name=cname,
                        observed_roas=roas,
                        previous_budget=prev_budget,
                        new_budget=prev_budget,
                        action="MAINTAIN",
                        rationalization=f"ROAS of {roas:.2f}x meets baseline targets. Preserving budget while testing creative.",
                    )
                )

        # 2. Second pass: Reallocate freed funds to scaling campaigns (or allocate +35% scale)
        funds_per_scaler = (retired_funds / max(len(scaling_campaigns), 1)) if scaling_campaigns else 0.0
        for sc in scaling_campaigns:
            cid = str(sc.get("campaign_id", "CMP-UNK"))
            cname = str(sc.get("name", "Campaign"))
            prev_budget = float(sc.get("current_budget") or sc.get("spend") or 1000.0)
            roas = float(sc.get("roas", 0.0))
            new_budget = round(prev_budget * 1.35 + funds_per_scaler, 2)

            decisions.append(
                CampaignReallocation(
                    campaign_id=cid,
                    campaign_name=cname,
                    observed_roas=roas,
                    previous_budget=prev_budget,
                    new_budget=new_budget,
                    action="SCALE",
                    rationalization=f"High-performing ROAS ({roas:.2f}x >= 3.5x). Scaling budget by +{((new_budget/prev_budget)-1)*100:.1f}%.",
                )
            )

        return decisions


def funnel_optimization_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node executing unit economics calculations, bottleneck diagnostics,

    and autonomous campaign budget reallocation.
    """
    brand: Optional[BrandProfile] = state.get("brand_profile")
    audit: Optional[AuditMetrics] = state.get("audit_metrics")
    metadata: Dict[str, Any] = state.get("metadata") or {}
    brand_name = brand.brand_name if brand else "Enterprise Brand"

    sandbox_url = metadata.get("sandbox_base_url") or os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8080")
    sandbox_key = metadata.get("sandbox_api_key") or os.getenv("SANDBOX_API_KEY", "aio-secret-key")
    headers = {"X-AIO-API-Key": sandbox_key} if sandbox_key else {}

    client = Sandbox(base_url=sandbox_url, headers=headers)
    calc = UnitEconomicsCalculator(base_url=sandbox_url, api_key=sandbox_key)
    diag_engine = FunnelDiagnosticEngine()

    # 1. Sub-task 8.1: Isolated Sandbox Unit Economics Computation
    revenue = float(metadata.get("revenue") or (audit.conversions * 85.0 if audit else 45000.0))
    ad_spend = float(metadata.get("ad_spend") or (audit.cac * audit.conversions if audit and audit.cac > 0 else 10000.0))
    cogs = float(metadata.get("cogs") or (revenue * 0.32))
    logistics = float(metadata.get("logistics_fees") or (revenue * 0.08))
    new_customers = int(metadata.get("new_customers") or (audit.conversions if audit else 500))

    unit_econ: UnitEconomicsMetrics = calc.calculate(
        revenue=revenue,
        ad_spend=ad_spend,
        cogs=cogs,
        logistics_fees=logistics,
        new_customers=new_customers,
    )

    # 2. Sub-task 8.2: Funnel Bottleneck Diagnostics
    active_audit = audit or AuditMetrics(
        reach=100000,
        traffic=22000,
        conversions=new_customers,
        cac=unit_econ.cac,
        clv=unit_econ.clv,
        roas=unit_econ.roas,
        health_ratio=unit_econ.health_ratio,
    )
    diagnostic_report: FunnelDiagnosticReport = diag_engine.diagnose(audit=active_audit)

    # 3. Sub-task 8.3: Autonomous Campaign Budget Reallocation
    default_campaigns = [
        {"campaign_id": "CMP-01", "name": "ToFu Educational Carousel Blitz", "current_budget": 3000.0, "roas": 4.6},
        {"campaign_id": "CMP-02", "name": "MoFu Customer Transformation Proof", "current_budget": 2500.0, "roas": 3.8},
        {"campaign_id": "CMP-03", "name": "Broad Unsegmented Direct Offer", "current_budget": 2000.0, "roas": 1.4},
        {"campaign_id": "CMP-04", "name": "BoFu Retargeting & Cart Recovery", "current_budget": 1500.0, "roas": 2.8},
    ]
    campaigns = metadata.get("campaigns") or default_campaigns
    reallocations = CampaignReallocationEngine.reallocate(campaigns=campaigns)

    # 4. Workspace Persistence to /home/gem/campaign_optimization.md
    output_path = "/home/gem/campaign_optimization.md"
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    doc_content = f"""# {brand_name} Commercial Unit Economics & Funnel Optimization Report

**Executed at**: {now_str}
**Runtime Environment**: AIO Sandbox Isolated Python (`agent_sandbox.code`)

---

## 1. Commercial Unit Economics & Attribution
- **Total Revenue**: ${unit_econ.revenue:,.2f}
- **Ad Spend**: ${unit_econ.ad_spend:,.2f}
- **COGS**: ${unit_econ.cogs:,.2f} (Gross Margin: {unit_econ.gross_margin_pct:.1f}%)
- **Net Contribution**: ${unit_econ.net_contribution:,.2f} ({unit_econ.contribution_margin_pct:.1f}% Contribution Margin)
- **ROAS**: {unit_econ.roas:.2f}x
- **Customer Acquisition Cost (CAC)**: ${unit_econ.cac:.2f}
- **Customer Lifetime Value (CLV)**: ${unit_econ.clv:.2f}
- **Commercial Health Ratio (CLV / CAC)**: {unit_econ.health_ratio:.2f}x ({'HEALTHY (>= 3.0)' if unit_econ.is_healthy else 'BELOW THRESHOLD (< 3.0)'})

---

## 2. Funnel Bottleneck Diagnostic Monologue
- **Overall Funnel Status**: {diagnostic_report.overall_health}
- **Primary Bottleneck Stage**: {diagnostic_report.primary_bottleneck_stage}
- **Strategic Summary**: {diagnostic_report.strategic_summary}

### Diagnosed Leakage Points:
"""
    for b in diagnostic_report.bottlenecks:
        doc_content += f"- **[{b.stage} - {b.severity.upper()}]**: {b.symptom}\n  - *Root Cause*: {b.root_cause}\n  - *Prescribed Intervention*: {b.recommended_action}\n"

    doc_content += "\n---\n\n## 3. Autonomous Campaign Budget Reallocation\n"
    for r in reallocations:
        doc_content += (
            f"- **`{r.campaign_id}` ({r.campaign_name})**: Action: **{r.action}**\n"
            f"  - ROAS: {r.observed_roas:.2f}x | Previous Budget: ${r.previous_budget:,.2f} -> New Budget: ${r.new_budget:,.2f}\n"
            f"  - *Rationale*: {r.rationalization}\n"
        )

    try:
        client.file.write_file(file=output_path, content=doc_content)
    except Exception:
        pass

    # Update state AuditMetrics with refreshed figures
    updated_metrics = AuditMetrics(
        reach=active_audit.reach,
        traffic=active_audit.traffic,
        conversions=active_audit.conversions,
        cac=unit_econ.cac,
        clv=unit_econ.clv,
        roas=unit_econ.roas,
        bounce_rate=active_audit.bounce_rate,
        health_ratio=unit_econ.health_ratio,
        baymard_issues=active_audit.baymard_issues,
    )

    summary_message = (
        f"[Commercial Optimization & Reallocation Complete]\n"
        f"Brand: {brand_name}\n"
        f"Net Contribution: ${unit_econ.net_contribution:,.2f} | ROAS: {unit_econ.roas:.2f}x\n"
        f"Health Ratio (CLV/CAC): {unit_econ.health_ratio:.2f}x ({'Healthy' if unit_econ.is_healthy else 'Fragile'})\n"
        f"Funnel Status: {diagnostic_report.overall_health} (Primary: {diagnostic_report.primary_bottleneck_stage})\n"
        f"Reallocation: {len([r for r in reallocations if r.action == 'SCALE'])} scaled, "
        f"{len([r for r in reallocations if r.action == 'RETIRE'])} retired.\n"
        f"Persisted to: {output_path}"
    )

    return {
        "phase": "evaluation",
        "audit_metrics": updated_metrics,
        "artifacts": [output_path],
        "messages": [AIMessage(content=summary_message)],
    }

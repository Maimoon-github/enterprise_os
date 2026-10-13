# pyright: reportMissingImports=false
"""Unit Economics and Commercial Attribution Engine (TSK-08).
Executes isolated financial modeling scripts in the AIO Sandbox container runtime
via agent_sandbox.code to calculate Net Contribution, ROAS, CAC, and CLV/CAC Health Ratio.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

try:
    from agent_sandbox import Sandbox  # type: ignore
except ImportError:
    from agent_sandbox.client import Sandbox  # type: ignore


class UnitEconomicsMetrics(BaseModel):
    """Structured financial and commercial unit economics model."""

    revenue: float
    ad_spend: float
    cogs: float
    logistics_fees: float
    net_contribution: float
    roas: float
    cac: float
    clv: float
    health_ratio: float  # Target >= 3.0
    is_healthy: bool
    gross_margin_pct: float
    contribution_margin_pct: float


class UnitEconomicsCalculator:
    """Executes isolated sandbox scripts to compute financial unit economics and attribution."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.base_url = base_url or os.getenv("SANDBOX_BASE_URL", "http://127.0.0.1:8080")
        self.api_key = api_key or os.getenv("SANDBOX_API_KEY", "aio-secret-key")
        self.headers = {"X-AIO-API-Key": self.api_key} if self.api_key else {}
        self.client = Sandbox(base_url=self.base_url, headers=self.headers)

    def calculate(
        self,
        revenue: float,
        ad_spend: float,
        cogs: float,
        logistics_fees: float = 0.0,
        new_customers: int = 1,
        clv: Optional[float] = None,
        aov: Optional[float] = None,
        purchase_frequency: float = 2.4,
    ) -> UnitEconomicsMetrics:
        """Execute sandboxed Python script via agent_sandbox.code to calculate commercial metrics."""
        # Estimated CLV if not explicitly passed
        estimated_clv = clv if clv is not None else round(((aov or (revenue / max(new_customers, 1))) * purchase_frequency * 0.65), 2)

        code_script = f"""
import json

revenue = {revenue:.2f}
ad_spend = {ad_spend:.2f}
cogs = {cogs:.2f}
logistics_fees = {logistics_fees:.2f}
new_customers = {max(new_customers, 1)}
clv = {estimated_clv:.2f}

gross_profit = revenue - cogs
net_contribution = gross_profit - ad_spend - logistics_fees
roas = round(revenue / ad_spend, 2) if ad_spend > 0 else 0.0
cac = round(ad_spend / new_customers, 2) if new_customers > 0 else 0.0
health_ratio = round(clv / cac, 2) if cac > 0 else 0.0
gross_margin_pct = round((gross_profit / revenue) * 100, 2) if revenue > 0 else 0.0
contribution_margin_pct = round((net_contribution / revenue) * 100, 2) if revenue > 0 else 0.0

result = {{
    "revenue": revenue,
    "ad_spend": ad_spend,
    "cogs": cogs,
    "logistics_fees": logistics_fees,
    "net_contribution": round(net_contribution, 2),
    "roas": roas,
    "cac": cac,
    "clv": clv,
    "health_ratio": health_ratio,
    "is_healthy": health_ratio >= 3.0,
    "gross_margin_pct": gross_margin_pct,
    "contribution_margin_pct": contribution_margin_pct
}}

print("__JSON_START__" + json.dumps(result) + "__JSON_END__")
"""

        parsed_data = None
        try:
            exec_res = self.client.code.execute_code(language="python", code=code_script)
            stdout = ""
            data_obj = getattr(exec_res, "data", None)
            if data_obj is not None and hasattr(data_obj, "stdout"):
                stdout = str(getattr(data_obj, "stdout", "") or "")
            elif isinstance(exec_res, dict):
                stdout = str(exec_res.get("data", {}).get("stdout", ""))

            if "__JSON_START__" in stdout and "__JSON_END__" in stdout:
                json_str = stdout.split("__JSON_START__")[1].split("__JSON_END__")[0]
                parsed_data = json.loads(json_str)
        except Exception:
            parsed_data = None

        # Fallback local deterministic computation if sandbox is unavailable
        if not parsed_data:
            gross_profit = revenue - cogs
            net_contrib = round(gross_profit - ad_spend - logistics_fees, 2)
            roas = round(revenue / ad_spend, 2) if ad_spend > 0 else 0.0
            cac = round(ad_spend / max(new_customers, 1), 2)
            health = round(estimated_clv / cac, 2) if cac > 0 else 0.0
            gross_pct = round((gross_profit / revenue) * 100, 2) if revenue > 0 else 0.0
            contrib_pct = round((net_contrib / revenue) * 100, 2) if revenue > 0 else 0.0
            parsed_data = {
                "revenue": revenue,
                "ad_spend": ad_spend,
                "cogs": cogs,
                "logistics_fees": logistics_fees,
                "net_contribution": net_contrib,
                "roas": roas,
                "cac": cac,
                "clv": estimated_clv,
                "health_ratio": health,
                "is_healthy": health >= 3.0,
                "gross_margin_pct": gross_pct,
                "contribution_margin_pct": contrib_pct,
            }

        return UnitEconomicsMetrics(**parsed_data)

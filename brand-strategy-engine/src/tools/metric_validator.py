"""Mathematical verification utility for validating empirical metric feasibility."""

import re
from typing import Optional, Tuple
from src.schemas.initiative import SuccessMetric


class MetricValidator:
    """Evaluates quantitative feasibility of proposed business KPI lifts."""

    RECOGNIZED_PLATFORMS = {
        "ga4",
        "google analytics 4",
        "google search console",
        "posthog",
        "mixpanel",
        "shopify analytics",
        "stripe",
        "hubspot",
        "ahrefs",
        "semrush",
        "clarity",
        "hotjar",
    }

    @staticmethod
    def parse_numeric(val: str) -> Optional[float]:
        """Extracts numeric magnitude from formatted strings like '1.8%', '$120', '350 leads'."""
        match = re.search(r"[-+]?\d*\.?\d+", val.replace(",", ""))
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
        return None

    @classmethod
    def validate_metric(cls, metric: SuccessMetric) -> Tuple[bool, Optional[str], float]:
        """Validates KPI feasibility and returns (passed, failure_reason, calculated_lift_pct)."""
        base_val = cls.parse_numeric(metric.baseline)
        target_val = cls.parse_numeric(metric.target)

        # 1. Verification platform check
        source_lower = metric.verification_source.lower()
        if not any(plat in source_lower for plat in cls.RECOGNIZED_PLATFORMS):
            return (
                False,
                f"Unrecognized verification source '{metric.verification_source}'. Must use an industry standard platform (e.g. GA4, Shopify Analytics, PostHog).",
                0.0,
            )

        # 2. Parseability check
        if base_val is None or target_val is None:
            return (
                False,
                f"Unable to parse quantitative baseline ('{metric.baseline}') or target ('{metric.target}') into numeric values.",
                0.0,
            )

        if base_val <= 0:
            # Baseline is zero, target must be modest
            if target_val > 500:
                return (
                    False,
                    f"Baseline is 0; target of {target_val} exceeds statistical initial ramp threshold.",
                    0.0,
                )
            return True, None, 100.0

        # Calculate relative lift
        lift_pct = ((target_val - base_val) / base_val) * 100.0

        # Check for inverse metrics (e.g., bounce rate, churn, CAC, cart drop-off)
        inverse_kpis = ["bounce", "churn", "cac", "abandonment", "drop-off", "cost", "latency"]
        is_inverse = any(k in metric.kpi.lower() for k in inverse_kpis)

        if is_inverse:
            if target_val >= base_val:
                return (
                    False,
                    f"For inverse KPI '{metric.kpi}', target ({target_val}) must be lower than baseline ({base_val}).",
                    lift_pct,
                )
            reduction_pct = ((base_val - target_val) / base_val) * 100.0
            if reduction_pct > 80.0:
                return (
                    False,
                    f"Unrealistic reduction of {reduction_pct:.1f}% for KPI '{metric.kpi}' (max credible reduction is 80%).",
                    lift_pct,
                )
        else:
            if target_val <= base_val:
                return (
                    False,
                    f"Target ({target_val}) must improve upon baseline ({base_val}) for growth KPI '{metric.kpi}'.",
                    lift_pct,
                )
            if lift_pct > 400.0:
                return (
                    False,
                    f"Unrealistic growth lift of {lift_pct:.1f}% for KPI '{metric.kpi}' (max credible ceiling is 400%).",
                    lift_pct,
                )

        return True, None, round(lift_pct, 2)

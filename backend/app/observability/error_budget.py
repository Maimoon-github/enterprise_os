"""Error Budget & Multi-Window Burn Rate Calculation Subsystem.

Implements Google SRE multi-window, multi-burn-rate alerting for Enterprise OS SLOs:
- Fast Window (1h): Alert when Burn Rate >= 14.4 (consumes 2% of monthly budget in 1h -> CRITICAL)
- Slow Window (6h): Alert when Burn Rate >= 6.0 (consumes 5% of monthly budget in 6h -> WARNING)
- Computes remaining error budget %, budget exhaustion forecast, and compliance windows.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta
from typing import Any
from pydantic import BaseModel, Field

from app.observability.slo import (
    ProductionSLORegistry,
    SLIComparison,
    SLIDefinition,
    SLIEvaluationResult,
)


class AlertSeverity(str, enum.Enum):
    """Severity tier for multi-window burn rate alerts."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class BurnRateAlert(BaseModel):
    """An alert emitted when an SLO error budget consumption exceeds safe thresholds."""

    alert_id: str
    sli_id: str
    slo_name: str
    severity: AlertSeverity
    window: str  # "1h" or "6h"
    burn_rate: float
    threshold: float
    remaining_budget_percentage: float
    exhaustion_forecast: datetime | None = None
    message: str
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ErrorBudgetSummary(BaseModel):
    """Detailed error budget calculation for a specific SLI."""

    sli_id: str
    slo_name: str
    target_percentage: float
    actual_percentage: float
    compliant: bool
    total_events: int
    good_events: int
    bad_events: int
    allowed_error_fraction: float
    consumed_error_budget_percentage: float
    remaining_error_budget_percentage: float
    burn_rate_1h: float
    burn_rate_6h: float
    exhaustion_forecast: datetime | None = None
    active_alerts: list[BurnRateAlert] = Field(default_factory=list)


class ErrorBudgetCalculator:
    """Calculates error budget burn rates and fires multi-window alerts."""

    FAST_BURN_THRESHOLD_1H = 14.4  # Consumes 2% budget in 1 hour
    SLOW_BURN_THRESHOLD_6H = 6.0   # Consumes 5% budget in 6 hours

    def __init__(self, registry: ProductionSLORegistry | None = None) -> None:
        self.registry = registry or ProductionSLORegistry()

    def evaluate_budget(
        self,
        sli_id: str,
        total_events: int,
        bad_events: int,
        window_events_1h: tuple[int, int] | None = None,  # (total, bad)
        window_events_6h: tuple[int, int] | None = None,  # (total, bad)
        current_time: datetime | None = None,
    ) -> ErrorBudgetSummary:
        """Compute error budget and evaluate 1h/6h burn rate thresholds."""
        slo = self.registry.get(sli_id)
        if slo is None:
            raise ValueError(f"SLO ID '{sli_id}' not found in registry.")

        now = current_time or datetime.now(UTC)
        total = max(0, total_events)
        bad = min(total, max(0, bad_events))
        good = total - bad

        target_pct = slo.target_value
        actual_pct = (good / total * 100.0) if total > 0 else 100.0
        compliant = actual_pct >= target_pct if slo.comparison == SLIComparison.GREATER_THAN_OR_EQUAL else True

        # Allowed error fraction (e.g., target 99.5% -> allowed error 0.005)
        allowed_error = max(0.0001, (100.0 - target_pct) / 100.0)

        # Actual error fraction over evaluation period
        actual_error = (bad / total) if total > 0 else 0.0

        # Budget consumption
        consumed_budget_pct = (actual_error / allowed_error) * 100.0
        remaining_budget_pct = max(0.0, 100.0 - consumed_budget_pct)

        # 1-Hour Fast Burn Rate
        if window_events_1h and window_events_1h[0] > 0:
            w1_total, w1_bad = window_events_1h
            w1_error_rate = w1_bad / w1_total
            burn_rate_1h = round(w1_error_rate / allowed_error, 2)
        else:
            burn_rate_1h = round(actual_error / allowed_error, 2)

        # 6-Hour Slow Burn Rate
        if window_events_6h and window_events_6h[0] > 0:
            w6_total, w6_bad = window_events_6h
            w6_error_rate = w6_bad / w6_total
            burn_rate_6h = round(w6_error_rate / allowed_error, 2)
        else:
            burn_rate_6h = burn_rate_1h

        # Exhaustion Forecast
        exhaustion_forecast: datetime | None = None
        effective_burn = max(burn_rate_1h, burn_rate_6h)
        if effective_burn > 0:
            if remaining_budget_pct <= 0:
                exhaustion_forecast = now  # Budget is already exhausted
            else:
                # 30-day baseline budget = 720 hours
                hours_to_exhaust = (remaining_budget_pct / 100.0) * (720.0 / effective_burn)
                exhaustion_forecast = now + timedelta(hours=hours_to_exhaust)

        # Generate Multi-Window Alerts
        alerts: list[BurnRateAlert] = []

        # 1. Fast Window Alert (1h @ 14.4x)
        if burn_rate_1h >= self.FAST_BURN_THRESHOLD_1H:
            alerts.append(
                BurnRateAlert(
                    alert_id=f"alert-fast-{sli_id}-{int(now.timestamp())}",
                    sli_id=sli_id,
                    slo_name=slo.name,
                    severity=AlertSeverity.CRITICAL,
                    window="1h",
                    burn_rate=burn_rate_1h,
                    threshold=self.FAST_BURN_THRESHOLD_1H,
                    remaining_budget_percentage=remaining_budget_pct,
                    exhaustion_forecast=exhaustion_forecast,
                    message=(
                        f"CRITICAL: Fast window 1h error budget burn rate is {burn_rate_1h}x "
                        f"(threshold {self.FAST_BURN_THRESHOLD_1H}x). "
                        f"Consuming >2% of monthly budget per hour!"
                    ),
                    triggered_at=now,
                )
            )

        # 2. Slow Window Alert (6h @ 6.0x)
        if burn_rate_6h >= self.SLOW_BURN_THRESHOLD_6H:
            alerts.append(
                BurnRateAlert(
                    alert_id=f"alert-slow-{sli_id}-{int(now.timestamp())}",
                    sli_id=sli_id,
                    slo_name=slo.name,
                    severity=AlertSeverity.WARNING,
                    window="6h",
                    burn_rate=burn_rate_6h,
                    threshold=self.SLOW_BURN_THRESHOLD_6H,
                    remaining_budget_percentage=remaining_budget_pct,
                    exhaustion_forecast=exhaustion_forecast,
                    message=(
                        f"WARNING: Slow window 6h error budget burn rate is {burn_rate_6h}x "
                        f"(threshold {self.SLOW_BURN_THRESHOLD_6H}x). "
                        f"Consuming >5% of monthly budget in 6 hours."
                    ),
                    triggered_at=now,
                )
            )

        return ErrorBudgetSummary(
            sli_id=sli_id,
            slo_name=slo.name,
            target_percentage=target_pct,
            actual_percentage=round(actual_pct, 4),
            compliant=compliant,
            total_events=total,
            good_events=good,
            bad_events=bad,
            allowed_error_fraction=allowed_error,
            consumed_error_budget_percentage=round(consumed_budget_pct, 2),
            remaining_error_budget_percentage=round(remaining_budget_pct, 2),
            burn_rate_1h=burn_rate_1h,
            burn_rate_6h=burn_rate_6h,
            exhaustion_forecast=exhaustion_forecast,
            active_alerts=alerts,
        )

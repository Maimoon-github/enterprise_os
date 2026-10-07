"""Production Observability & SLO Certification Runner for Track 5.

Executes a live governed directive through the complete 12-stage lifecycle,
evaluates all 12 certified SLOs, calculates error budgets and multi-window burn rates,
and answers all 11 operator exit-criteria questions directly from telemetry.

Generates the formal certification receipt:
artifacts/observability_slo_certification_receipt.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

# Ensure backend directory is in sys.path
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.observability.directive_runner import (
    InstrumentedDirectiveExecutionHarness,
)
from app.observability.health import check_observability_health
from app.observability.slo_evaluator import (
    ObservabilityTelemetryDisposition,
    SLOCertificationReport,
)


def format_slo_table(report: SLOCertificationReport) -> str:
    lines = [
        "=" * 92,
        f"{'SLO NAME':<40} {'TARGET':<12} {'ACTUAL':<12} {'UNIT':<6} {'STATUS':<10}",
        "=" * 92,
    ]
    for eval_item in report.slo_evaluations:
        status_str = "\033[92mCOMPLIANT\033[0m" if eval_item.compliant else "\033[91mBREACHED\033[0m"
        comp_str = f">= {eval_item.target_value}" if eval_item.comparison.value == "gte" else f"<= {eval_item.target_value}"
        lines.append(
            f"{eval_item.name:<40} {comp_str:<12} {eval_item.actual_value:<12} {eval_item.unit:<6} {status_str:<10}"
        )
    lines.append("-" * 92)
    return "\n".join(lines)


def format_disposition_card(disp: ObservabilityTelemetryDisposition) -> str:
    lines = [
        "=" * 92,
        "TRACK 5 OPERATOR EXIT CRITERIA: TELEMETRY DISPOSITION",
        "=" * 92,
        f"1.  Was execution successful?                   : {'YES' if disp.was_successful else 'NO'}",
        f"2.  Stage latencies breakdown (12 stages)       : {json.dumps(disp.stage_latencies_seconds, indent=4)}",
        f"3.  Primary latency consumer                    : {disp.primary_latency_consumer.upper()}",
        f"4.  Was any retry executed?                     : {'YES' if disp.retry_executed else 'NO'}",
        f"5.  HITL bottleneck classification             : {disp.hitl_bottleneck.upper()}",
        f"6.  Actuation count (strictly 1?)               : {disp.actuation_count} (Exactly-once: {disp.exactly_once_actuation_guaranteed})",
        f"7.  Was any telemetry lost/dropped?             : {'NO (0 dropped)' if disp.telemetry_lost_count == 0 else f'YES ({disp.telemetry_lost_count} dropped)'}",
        f"8.  Sandbox cgroup/resources consumed           : Memory peak={disp.sandbox_resources.get('memory_peak_bytes', 0)/(1024*1024):.1f}MB, CPU={disp.sandbox_resources.get('cpu_usage_usec', 0)}us",
        f"9.  Immutable W3C PROV audit chain              : Length={disp.prov_chain_length}, Root Hash={disp.prov_root_record_hash}",
        f"10. Was error budget consumed?                  : {'YES' if disp.error_budget_consumed else 'NO (0.0% consumed)'}",
        f"11. Would operator be alerted on SLO breach?    : {'YES (Alert fired)' if disp.operator_alert_triggered else 'NO (Zero breaches)'}",
        "-" * 92,
    ]
    return "\n".join(lines)


async def run_certification(output_path: Path | None = None) -> int:
    print("\n" + "=" * 92)
    print("ENTERPRISE OS TRACK 5: PRODUCTION OBSERVABILITY & SLO CERTIFICATION")
    print("=" * 92)

    harness = InstrumentedDirectiveExecutionHarness(tenant_id="tenant-prod-obs-gate")
    report, disposition = await harness.execute_governed_directive(
        directive_text="Deploy enterprise multi-channel campaign with verified isolation",
        simulated_hitl_wait_seconds=0.15,
    )

    print(format_slo_table(report))
    print()
    print(format_disposition_card(disposition))
    print()

    print("=" * 92)
    print("CERTIFICATION SUMMARY")
    print("=" * 92)
    print(f"Report ID                              : {report.report_id}")
    print(f"Total SLOs Evaluated                   : {report.total_slos}")
    print(f"Compliant SLOs                         : {report.compliant_slos}")
    print(f"Pipeline Completeness Ratio            : {report.observability_pipeline_completeness_ratio * 100.0:.2f}%")
    print(f"Collector Queue Saturation             : {report.health_report.queue_saturation_ratio * 100.0:.1f}%")
    print(f"Dropped Telemetry Records              : {report.health_report.total_dropped_telemetry}")
    print(f"Governing SLO Invariant                : {'UPHELD' if report.governing_slo_upheld else 'VIOLATED'}")
    print(f"Certification Verdict                  : {report.certification_verdict}")
    print("=" * 92 + "\n")

    dumped = report.model_dump(mode="json")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dumped, f, indent=2)
        print(f"[RECEIPT WRITTEN] Saved formal certification receipt to: {output_path}")

    return 0 if report.certification_verdict == "CERTIFIED" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Production Observability & SLO Certification Runner")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=_ROOT / "artifacts" / "observability_slo_certification_receipt.json",
        help="Output path for formal JSON certification receipt",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run_certification(output_path=args.output_json))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

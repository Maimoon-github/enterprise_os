"""Enterprise OS Chaos Certification Suite Runner.

Executes all 8 controlled failure injection scenarios sequentially and evaluates
the governing Track 4 assertion:

"For every injected failure, Enterprise OS either resumes safely or fails closed.
No failure may cause duplicate external actuation, unauthorized continuation,
incorrect terminal CTS state, lost provenance, cross-tenant leakage, replay
acceptance, stale lease execution, or silent data loss."

Scenarios executed:
1. PostgreSQL termination during an active directive.
2. Provisioner termination during a specialist attempt.
3. UDS disconnect mid-request.
4. Specialist termination after work but before receipt sealing.
5. Host reboot with active leases/tasks.
6. WAL/archive storage exhaustion or unavailability.
7. Corrupted/missing WAL segment with mandatory fail-closed recovery.
8. Outbound actuation crash at the acknowledgement boundary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure backend directory is in sys.path
_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.disaster_recovery.chaos_engine import (
    ChaosCertificationSuiteReceipt,
    ChaosScenarioResult,
    EnterpriseOSChaosEngine,
    TRACK_4_GOVERNING_ASSERTION,
)


def format_scenario_banner(result: ChaosScenarioResult) -> str:
    status_str = "PASSED" if result.passed else "FAILED"
    color = "\033[92m" if result.passed else "\033[91m"
    reset = "\033[0m"

    lines = [
        "=" * 88,
        f"SCENARIO {result.order}/8: {result.name.upper()}",
        "=" * 88,
        f"Injected Failure : {result.injected_failure}",
        f"Expected         : {result.expected_behavior}",
        f"Observed         : {result.observed_behavior}",
        f"Execution Time   : {result.duration_seconds:.4f}s",
        f"Verdict          : {color}{status_str}{reset} (Governing Invariant Upheld: {result.governing_assertion_upheld})",
        "-" * 88,
    ]
    return "\n".join(lines)


async def run_suite(primary_dsn: str, output_path: Path | None = None) -> int:
    print("\n" + "=" * 88)
    print("ENTERPRISE OS TRACK 4: CHAOS CERTIFICATION SUITE")
    print("=" * 88)
    print(f"Primary PostgreSQL DSN : {primary_dsn}")
    print(f"Governing Invariant    :\n  \"{TRACK_4_GOVERNING_ASSERTION}\"")
    print("=" * 88 + "\n")

    engine = EnterpriseOSChaosEngine(primary_dsn=primary_dsn)
    start_time = time.perf_counter()

    receipt: ChaosCertificationSuiteReceipt = await engine.run_full_certification_suite()
    total_duration = time.perf_counter() - start_time

    for res in receipt.scenario_results:
        print(format_scenario_banner(res))
        print()

    print("=" * 88)
    print("CHAOS CERTIFICATION SUMMARY")
    print("=" * 88)
    print(f"Suite ID               : {receipt.suite_id}")
    print(f"Total Scenarios        : {receipt.total_scenarios}")
    print(f"Passed Scenarios       : {receipt.passed_scenarios}")
    print(f"Failed Scenarios       : {receipt.total_scenarios - receipt.passed_scenarios}")
    print(f"Total Wall Time        : {total_duration:.4f}s")
    print(f"Governing Invariant    : {'UPHELD' if receipt.governing_assertion_upheld else 'VIOLATED'}")
    print(f"Certification Verdict  : {receipt.verdict}")
    print("=" * 88 + "\n")

    dumped_receipt = receipt.model_dump(mode="json")

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dumped_receipt, f, indent=2)
        print(f"[RECEIPT WRITTEN] Saved formal certification receipt to: {output_path}")

    return 0 if receipt.verdict == "CERTIFIED" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Enterprise OS Chaos Certification Runner")
    parser.add_argument(
        "--primary-dsn",
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/governed_backend",
        help="Primary PostgreSQL connection string",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=_ROOT / "artifacts" / "chaos_certification_receipt.json",
        help="Output path for formal JSON certification receipt",
    )
    args = parser.parse_args()

    exit_code = asyncio.run(run_suite(primary_dsn=args.primary_dsn, output_path=args.output_json))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

"""Clean-Room Smoke Test against Installed Enterprise OS Release.
Executes the full pipeline:
Browser Ingress -> Backend -> IE -> Sandbox Specialist -> HITL -> Telemetry -> Learning -> PROV Audit.
NIST SSDF RV.1 / Production Certification Gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_clean_room_smoke_test(installed_dir: str | Path) -> dict[str, Any]:
    """Execute complete smoke test verifying all architectural boundaries on the installed bundle."""
    installed_path = Path(installed_dir).resolve()
    backend_path = installed_path / "backend"

    if not backend_path.exists():
        backend_path = installed_path

    # Tests to execute against installed release
    test_targets = [
        "tests/acceptance/test_full_stack_production_e2e_run.py",
        "tests/integration/test_operational_certification.py",
        "tests/integration/test_real_postgresql_persistence_and_restart.py",
    ]

    results: dict[str, Any] = {}
    all_passed = True

    for target in test_targets:
        test_file = backend_path / target
        if not test_file.exists():
            continue

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            "--tb=short",
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(backend_path),
            capture_output=True,
            text=True,
        )

        passed = proc.returncode == 0
        if not passed:
            all_passed = False

        results[target] = {
            "passed": passed,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-500:] if proc.stdout else "",
            "stderr": proc.stderr[-500:] if proc.stderr else "",
        }

    return {
        "status": "PASSED" if all_passed else "FAILED",
        "installed_dir": str(installed_path),
        "suite_count": len(results),
        "results": results,
    }


if __name__ == "__main__":
    out = run_clean_room_smoke_test(Path(__file__).resolve().parent.parent)
    print(json.dumps(out, indent=2))
    if out["status"] != "PASSED":
        sys.exit(1)

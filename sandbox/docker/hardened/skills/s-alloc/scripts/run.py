#!/usr/bin/env python3
# pyright: reportMissingImports=false
"""S_ALLOC Optimization Modeler Execution Script (STRAT-03 Governed S_ALLOC).

Thin entrypoint for S_ALLOC. Delegates all deterministic math and execution
to canonical s_alloc_core.py without duplicated math or fabricated defaults.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Ensure backend directory is in sys.path when running from repo or tests
_current_dir = os.path.dirname(os.path.abspath(__file__))
# Check candidate paths to locate enterprise_os/backend
for _up in range(1, 8):
    _candidate_root = os.path.abspath(os.path.join(_current_dir, *[".."] * _up))
    _candidate_backend = os.path.join(_candidate_root, "backend")
    if os.path.isfile(os.path.join(_candidate_backend, "app", "integrations", "sandbox", "s_alloc_core.py")):
        if _candidate_backend not in sys.path:
            sys.path.insert(0, _candidate_backend)
        break
    if os.path.isfile(os.path.join(_candidate_root, "s_alloc_core.py")):
        if _candidate_root not in sys.path:
            sys.path.insert(0, _candidate_root)
        break

# Ensure s_alloc_core can be imported in both container and local test environments
try:
    from app.integrations.sandbox.s_alloc_core import (  # type: ignore[import-not-found]
        calculate_roas,
        diminishing_returns_model,
        execute_s_alloc,
        model_media_mix,
        optimize_budget,
        run_s_alloc,
        simulate_funnel,
        simulate_scenarios,
    )
except ImportError:
    try:
        from backend.app.integrations.sandbox.s_alloc_core import (  # type: ignore[import-not-found]
            calculate_roas,
            diminishing_returns_model,
            execute_s_alloc,
            model_media_mix,
            optimize_budget,
            run_s_alloc,
            simulate_funnel,
            simulate_scenarios,
        )
    except ImportError:
        from s_alloc_core import (  # type: ignore[import-not-found]
            calculate_roas,
            diminishing_returns_model,
            execute_s_alloc,
            model_media_mix,
            optimize_budget,
            run_s_alloc,
            simulate_funnel,
            simulate_scenarios,
        )


def main() -> None:
    raw_input = sys.stdin.read()
    data = json.loads(raw_input) if raw_input.strip() else {}
    run_result = run_s_alloc(data)
    sys.stdout.write(json.dumps(run_result))


if __name__ == "__main__":
    main()

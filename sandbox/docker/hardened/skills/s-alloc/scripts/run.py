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
_repo_root = os.path.abspath(os.path.join(_current_dir, "../../../../../../../"))
_backend_path = os.path.join(_repo_root, "backend")
if os.path.isdir(_backend_path) and _backend_path not in sys.path:
    sys.path.insert(0, _backend_path)

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

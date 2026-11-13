"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# NO_ENTERPRISE=1 runs the backend as the community edition even when the
# enterprise submodule is checked out.
#
# CI and self-hosted builds have app/enterprise empty, so every
# `try: import app.enterprise` falls back to community mode. A developer
# checkout has the submodule populated, which switches on plan and
# subscription gating. Setting this makes the import fail the same way, so the
# unit suite (`NO_ENTERPRISE=1 python -m pytest tests/`) and the e2e OSS stack
# behave exactly like a community install.
#
# An env var rather than a flag because the blocker must be installed before
# anything imports app.enterprise — app/__init__.py calls apply() first thing.

import os
import sys


class _BlockEnterprise:
    """Meta-path finder that makes app.enterprise look un-checked-out."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "app.enterprise" or fullname.startswith("app.enterprise."):
            # ModuleNotFoundError, not bare ImportError: that is what an
            # un-checked-out submodule actually raises, and it is what
            # pytest.importorskip and the app's own guards look for.
            raise ModuleNotFoundError(
                f"No module named {fullname!r} (disabled by NO_ENTERPRISE=1)",
                name=fullname,
            )
        return None


def apply() -> None:
    """Install the enterprise blocker when NO_ENTERPRISE=1 (idempotent)."""
    if os.getenv("NO_ENTERPRISE") != "1":
        return
    if not any(isinstance(finder, _BlockEnterprise) for finder in sys.meta_path):
        sys.meta_path.insert(0, _BlockEnterprise())

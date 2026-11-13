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

# agno reports every agent run to api.agno.com unless told not to, and it
# awaits that call inside the run (60s client timeout). When the call is slow
# the run outlives AGENT_RUN_TIMEOUT and the visitor gets an apology instead of
# an answer - for a report nobody here reads, sent from every install.
#
# Off by default (settings.AGNO_TELEMETRY / AGNO_MONITOR, from the environment
# or backend/.env). agno reads these variables before each run report, so
# setting them once per process covers every agent, wherever it is built. With
# both off, AGNO_API_ENABLED=false also stops agno's other calls to its API
# (session logging, playground, evals), which ChatterMate never uses.
#
# Environment variables rather than Agent(telemetry=False) because agents are
# built in many places (chat, transfer, tickets, FAQs, summaries, help center)
# and in separate worker processes - app/__init__.py calls apply() first thing.

import os

from app.core.config import settings

AGNO_SWITCHES = ("AGNO_TELEMETRY", "AGNO_MONITOR")
AGNO_API_SWITCH = "AGNO_API_ENABLED"


def _env_flag(enabled: bool) -> str:
    return "true" if enabled else "false"


def apply() -> None:
    """Hand agno the configured telemetry and monitoring switches (idempotent)."""
    for name in AGNO_SWITCHES:
        os.environ[name] = _env_flag(getattr(settings, name))
    if not any(getattr(settings, name) for name in AGNO_SWITCHES):
        os.environ[AGNO_API_SWITCH] = _env_flag(False)

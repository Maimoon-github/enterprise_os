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

agno reports each agent run to api.agno.com from inside the run unless told
not to; a slow report used to eat the run's timeout and cost the visitor
their answer.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from agno.agent import Agent
from agno.run.response import RunResponse

import app  # noqa: F401 — app/__init__.py, which every process imports first, applies the switches
from app.core import agno_telemetry
from app.core.config import Settings, settings


@pytest.fixture
def configured(monkeypatch):
    """Set the switches as an operator would, and restore the process env after."""
    for name in (*agno_telemetry.AGNO_SWITCHES, agno_telemetry.AGNO_API_SWITCH):
        monkeypatch.delenv(name, raising=False)

    def configure(**switches):
        for name in agno_telemetry.AGNO_SWITCHES:
            monkeypatch.setattr(settings, name, switches.get(name, False))
        agno_telemetry.apply()

    return configure


def test_off_by_default():
    assert Settings.model_fields["AGNO_TELEMETRY"].default is False
    assert Settings.model_fields["AGNO_MONITOR"].default is False


def test_apply_turns_agnos_reporting_off(configured):
    configured()

    assert os.environ["AGNO_TELEMETRY"] == "false"
    assert os.environ["AGNO_MONITOR"] == "false"
    assert os.environ["AGNO_API_ENABLED"] == "false"


@pytest.mark.parametrize("switch", agno_telemetry.AGNO_SWITCHES)
def test_an_operator_can_opt_in(configured, switch):
    configured(**{switch: True})

    assert os.environ[switch] == "true"
    # Their opt-in must still reach agno's API.
    assert agno_telemetry.AGNO_API_SWITCH not in os.environ


@pytest.mark.parametrize("value, expected", [("true", True), ("TRUE", True), ("false", False), ("0", False)])
def test_the_setting_comes_from_the_environment_or_env_file(monkeypatch, value, expected):
    # backend/.env reaches the environment before Settings reads it (config.py's load_dotenv).
    monkeypatch.setenv("AGNO_TELEMETRY", value)

    assert Settings().AGNO_TELEMETRY is expected


def test_the_app_applied_it_on_import():
    for name in agno_telemetry.AGNO_SWITCHES:
        assert os.environ[name] == ("true" if getattr(settings, name) else "false")


def _finished_agent() -> Agent:
    """An agno Agent at the point it reports a run: its response is in hand."""
    agent = Agent()
    agent.run_response = RunResponse(content="done")
    return agent


async def _reports_sent(agent: Agent) -> int:
    with patch("agno.api.agent.acreate_agent_run", new_callable=AsyncMock) as report, \
         patch("agno.api.agent.create_agent_run") as sync_report:
        await agent._alog_agent_run(session_id="session-1")
        agent._log_agent_run(session_id="session-1")
    return report.await_count + sync_report.call_count


@pytest.mark.asyncio
async def test_an_agent_built_with_agnos_defaults_reports_nothing(configured):
    """Guards the env names against an agno upgrade: Agent() still defaults to
    telemetry=True, and only these variables switch it off at run time."""
    configured()
    agent = _finished_agent()
    assert agent.telemetry is True  # agno's own default, overridden per run

    assert await _reports_sent(agent) == 0


@pytest.mark.asyncio
async def test_an_opted_in_agent_does_report(configured):
    """The other half of the guard: with telemetry on, the report does go out -
    so a zero above means switched off, not a test that can't see it."""
    configured(AGNO_TELEMETRY=True)

    assert await _reports_sent(_finished_agent()) == 2

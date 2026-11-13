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

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.outbound_policy import (
    OutboundTargetBlocked,
    check_outbound_target,
    require_public_target,
)
from app.knowledge import url_safety
from app.models.mcp_tool import MCPTransportType
from app.services import db_connector_service
from app.services.db_connector_service import DBConnectorConfig, first_hop
from app.tools.mcp_manager import MCPToolsManager
from app.utils.agno_utils import create_model

INTERNAL_TARGETS = [
    "http://127.0.0.1:11434/v1",
    "http://localhost:11434/v1",
    "localhost:11434/v1",          # no scheme: must not parse as hostless
    "http://169.254.169.254/latest/meta-data/",
    "https://10.1.2.3/mcp",
    "192.168.0.10",                # bare database host
    "::1",                         # bare IPv6 host
    "http://[fd00::1]/mcp",
]


@pytest.fixture
def public_only(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_URL_POLICY", "public_only")


@pytest.fixture
def policy_any(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_URL_POLICY", "any")


def _resolves_to(address):
    return patch.object(url_safety.socket, "getaddrinfo",
                        return_value=[(2, 1, 6, "", (address, 0))])


class TestPolicy:
    def test_default_is_any(self):
        assert settings.OUTBOUND_URL_POLICY == "any"

    @pytest.mark.parametrize("target", INTERNAL_TARGETS)
    def test_any_allows_internal_targets(self, policy_any, target):
        check_outbound_target(target, "Target")

    @pytest.mark.parametrize("target", INTERNAL_TARGETS)
    def test_public_only_refuses_internal_targets(self, public_only, target):
        with pytest.raises(OutboundTargetBlocked, match="Target must be a public address"):
            check_outbound_target(target, "Target")

    def test_public_only_refuses_a_name_resolving_inside(self, public_only):
        with _resolves_to("10.0.0.9"), pytest.raises(OutboundTargetBlocked):
            check_outbound_target("db.internal.example.com", "Database host")

    def test_public_only_allows_a_public_target(self, public_only):
        with _resolves_to("93.184.216.34"):
            check_outbound_target("https://api.example.com/v1", "Base URL")
            check_outbound_target("db.example.com", "Database host")

    def test_an_empty_target_is_left_to_field_validation(self, public_only):
        check_outbound_target(None, "Base URL")
        check_outbound_target("", "Base URL")

    def test_require_public_target_is_a_400(self, public_only):
        with pytest.raises(HTTPException) as exc:
            require_public_target("http://127.0.0.1", "MCP server URL")
        assert exc.value.status_code == 400
        assert "MCP server URL must be a public address" in exc.value.detail


class TestCheckedAgainBeforeConnecting:
    """Saving is not enough: a hostname can be re-pointed after it was saved."""

    def test_ai_base_url(self, public_only):
        with pytest.raises(HTTPException) as exc:
            create_model("OPENAI_COMPATIBLE", "key", "m", base_url="http://127.0.0.1:11434/v1")
        assert "must be a public address" in exc.value.detail

    def test_ai_base_url_allowed_under_any(self, policy_any):
        model = create_model("OPENAI_COMPATIBLE", "key", "m", base_url="http://127.0.0.1:11434/v1")
        assert model.base_url == "http://127.0.0.1:11434/v1"

    @pytest.mark.asyncio
    async def test_mcp_server_url(self, public_only):
        config = SimpleNamespace(
            name="Internal", transport_type=MCPTransportType.HTTP,
            url="http://169.254.169.254/mcp", headers=None, timeout=None,
            sse_read_timeout=None, terminate_on_close=True,
        )
        with patch("app.tools.mcp_manager.MCPTools") as mcp_tools:
            result = await MCPToolsManager(connect_budget=5).test_tool_config(config)

        assert result["success"] is False
        assert "MCP server URL must be a public address" in result["error"]
        mcp_tools.assert_not_called()

    def _db_config(self, **overrides):
        values = dict(
            id=None, organization_id=None, name="c", engine="postgresql",
            host="10.0.0.5", port=5432, database="d", username="u", password="p",
        )
        values.update(overrides)
        return DBConnectorConfig(**values)

    def test_database_host(self, public_only):
        with patch.object(db_connector_service, "_driver_connect") as driver:
            with pytest.raises(OutboundTargetBlocked, match="Database host"):
                with db_connector_service._connection(self._db_config()):
                    pass
        driver.assert_not_called()

    def test_ssh_host_is_the_first_hop_when_tunnelling(self, public_only):
        config = self._db_config(ssh_enabled=True, ssh_host="127.0.0.1", ssh_username="u")
        with patch.object(db_connector_service, "_ssh_tunnel") as tunnel:
            with pytest.raises(OutboundTargetBlocked, match="SSH host"):
                with db_connector_service._connection(config):
                    pass
        tunnel.assert_not_called()

    def test_private_database_behind_a_public_bastion_is_allowed(self, public_only):
        config = self._db_config(ssh_enabled=True, ssh_host="bastion.example.com", ssh_username="u")
        tunnel = MagicMock()
        tunnel.return_value.__enter__.return_value = ("127.0.0.1", 40000)
        with _resolves_to("93.184.216.34"), \
             patch.object(db_connector_service, "_ssh_tunnel", tunnel), \
             patch.object(db_connector_service, "_driver_connect") as driver:
            with db_connector_service._connection(config):
                pass
        driver.assert_called_once_with(config, "127.0.0.1", 40000)


def test_first_hop_picks_the_bastion_only_when_tunnelling():
    assert first_hop(False, "bastion", "db") == ("db", "Database host")
    assert first_hop(True, "bastion", "db") == ("bastion", "SSH host")

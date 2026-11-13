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

"""OUTBOUND_URL_POLICY on the ticket DB connector endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import ticket_db_connectors as api
from app.core.config import settings
from app.models.schemas.ticket_db_connector import (
    DBConnectorCreate,
    DBConnectorDiscoverRequest,
    DBConnectorUpdate,
)

CONNECTION = dict(engine="postgresql", port=5432, database="d", username="u", password="p")


@pytest.fixture
def user():
    return SimpleNamespace(organization_id=uuid4())


@pytest.fixture(autouse=True)
def ticketing_enabled():
    with patch.object(api, "check_ticketing_access"):
        yield


@pytest.fixture
def public_only(monkeypatch):
    monkeypatch.setattr(settings, "OUTBOUND_URL_POLICY", "public_only")


def _stored_connector(**overrides):
    values = dict(ssh_enabled=False, ssh_host=None, host="db.example.com")
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_create_refuses_an_internal_host(public_only, user):
    db = MagicMock()
    payload = DBConnectorCreate(name="c", host="127.0.0.1", **CONNECTION)
    with pytest.raises(HTTPException) as exc:
        await api.create_connector(payload, current_user=user, db=db)
    assert exc.value.status_code == 400
    assert "Database host must be a public address" in exc.value.detail
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_allows_an_internal_host_under_any(monkeypatch, user):
    monkeypatch.setattr(settings, "OUTBOUND_URL_POLICY", "any")
    db = MagicMock()
    payload = DBConnectorCreate(name="c", host="127.0.0.1", **CONNECTION)
    with patch.object(api, "encrypt_api_key", return_value="enc"):
        await api.create_connector(payload, current_user=user, db=db)
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_checks_the_bastion_not_the_database_when_tunnelling(public_only, user):
    db = MagicMock()
    payload = DBConnectorCreate(
        name="c", host="10.0.0.5", ssh_enabled=True, ssh_host="169.254.169.254",
        ssh_username="u", **CONNECTION,
    )
    with pytest.raises(HTTPException) as exc:
        await api.create_connector(payload, current_user=user, db=db)
    assert "SSH host must be a public address" in exc.value.detail


@pytest.mark.asyncio
async def test_discover_refuses_before_connecting(public_only, user):
    payload = DBConnectorDiscoverRequest(host="localhost", **CONNECTION)
    with patch.object(api, "_discover", AsyncMock()) as discover:
        with pytest.raises(HTTPException) as exc:
            await api.discover_tables(payload, current_user=user, db=MagicMock())
    assert exc.value.status_code == 400
    discover.assert_not_called()


@pytest.mark.asyncio
async def test_update_checks_the_resulting_first_hop(public_only, user):
    connector = _stored_connector()
    with patch.object(api, "_get_connector_or_404", return_value=connector):
        with pytest.raises(HTTPException):
            await api.update_connector(uuid4(), DBConnectorUpdate(host="10.9.9.9"),
                                       current_user=user, db=MagicMock())
    assert connector.host == "db.example.com"  # nothing applied


@pytest.mark.asyncio
async def test_update_turning_off_ssh_exposes_the_private_database_host(public_only, user):
    connector = _stored_connector(ssh_enabled=True, ssh_host="bastion.example.com", host="10.0.0.5")
    with patch.object(api, "_get_connector_or_404", return_value=connector):
        with pytest.raises(HTTPException) as exc:
            await api.update_connector(uuid4(), DBConnectorUpdate(ssh_enabled=False),
                                       current_user=user, db=MagicMock())
    assert "Database host" in exc.value.detail

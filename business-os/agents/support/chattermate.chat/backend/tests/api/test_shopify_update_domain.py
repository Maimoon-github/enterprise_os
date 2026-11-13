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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.shopify import update_organization_domain
from app.utils.domain_check import LOCALHOST_DOMAIN_MESSAGE


def _request(domain):
    request = MagicMock()
    request.json = AsyncMock(return_value={"domain": domain})
    return request


def _session(organization):
    return {"db_shop": MagicMock(organization_id=organization.id)}


@pytest.fixture
def cors_refresh(test_organization):
    # The route looks the org up by its id as a string, which SQLite's UUID column can't bind
    with patch("app.api.shopify.OrganizationRepository") as repository, \
            patch("app.api.shopify.update_cors_middleware") as refresh:
        repository.return_value.get_organization.return_value = test_organization
        yield refresh


@pytest.mark.asyncio
async def test_a_new_website_is_stored_as_its_host(db, test_organization, cors_refresh):
    result = await update_organization_domain(
        _request("https://WWW.Store.example/collections"), _session(test_organization), db)

    db.refresh(test_organization)
    assert result["domain"] == test_organization.domain == "www.store.example"
    cors_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_the_website_as_it_already_is_saves_without_a_change(db, test_organization, cors_refresh):
    test_organization.domain = "https://Older.example/"  # stored before websites were checked
    db.commit()

    result = await update_organization_domain(
        _request(" https://older.example/ "), _session(test_organization), db)

    db.refresh(test_organization)
    assert result["success"] is True
    assert test_organization.domain == "https://Older.example/"
    cors_refresh.assert_not_called()


@pytest.mark.asyncio
async def test_a_website_that_cant_be_stored_is_refused_and_nothing_changes(db, test_organization, cors_refresh):
    before = test_organization.domain

    with pytest.raises(HTTPException) as refused:
        await update_organization_domain(_request("localhost:3000"), _session(test_organization), db)

    db.refresh(test_organization)
    assert (refused.value.status_code, refused.value.detail) == (400, LOCALHOST_DOMAIN_MESSAGE)
    assert test_organization.domain == before
    cors_refresh.assert_not_called()

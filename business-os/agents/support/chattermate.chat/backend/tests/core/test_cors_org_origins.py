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

CORS admits each org's site with and without www., however the domain was
typed at signup - the same rule install detection uses.
"""

from types import SimpleNamespace

import pytest

from app.core import cors


@pytest.fixture
def origins_for(monkeypatch):
    def build(*domains, stores=()):
        monkeypatch.setattr("app.repositories.organization.OrganizationRepository.get_active_organizations",
                            lambda self: [SimpleNamespace(id=i, domain=d) for i, d in enumerate(domains)])
        monkeypatch.setattr("app.repositories.shopify_shop_repository.ShopifyShopRepository.list_linked_domains",
                            lambda self: list(stores))
        monkeypatch.setattr("app.repositories.help_center.HelpCenterRepository.list_enabled_slugs", lambda self: [])
        monkeypatch.setattr("app.repositories.help_center.HelpCenterRepository.list_verified_domains", lambda self: [])
        cors.get_cors_origins.cache_clear()
        try:
            return cors.get_cors_origins()
        finally:
            cors.get_cors_origins.cache_clear()
    return build


@pytest.mark.parametrize("typed", ["acme.com", "www.acme.com", "Acme.com", "https://WWW.Acme.com/"])
def test_org_site_admitted_with_and_without_www(origins_for, typed):
    origins = origins_for(typed)
    assert {"https://acme.com", "https://www.acme.com", "http://acme.com", "http://www.acme.com"} <= origins
    assert not any("www.www." in o or "Acme" in o for o in origins)


def test_a_linked_store_is_allowed_alongside_its_orgs_own_website(origins_for):
    # Connecting a store no longer replaces the website, so both must be allowed
    origins = origins_for("sellse.xyz", stores=["ekhyzy-0i.myshopify.com"])
    assert {"https://sellse.xyz", "https://ekhyzy-0i.myshopify.com"} <= origins


def test_blank_domain_adds_nothing(origins_for):
    assert not any(o.endswith("://") or o.endswith("://www.") for o in origins_for("", None))


def test_one_unparsable_website_costs_no_one_else_their_origins(origins_for):
    # Stored before websites were validated: it is skipped, not the whole list
    origins = origins_for("acme.com", "a]b.com", "beta.io", stores=["shop.myshopify.com"])
    assert {"https://acme.com", "https://beta.io", "https://shop.myshopify.com"} <= origins


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

Linking a Shopify store to an organization.
"""

from types import SimpleNamespace
from uuid import uuid4

from app.models.organization import Organization
from app.services.shopify_links import owned_by_another_org, use_shop_domain_if_unset

STORE = "ekhyzy-0i.myshopify.com"


def test_an_org_with_a_website_keeps_it(db, test_organization):
    # Replacing it cut the widget off from that site (it happened to Sellse)
    use_shop_domain_if_unset(db, test_organization.id, STORE)
    db.commit()
    assert db.get(Organization, test_organization.id).domain == "test.com"


def test_an_org_without_a_website_gets_its_stores(db, test_organization):
    test_organization.domain = ""
    db.commit()

    use_shop_domain_if_unset(db, test_organization.id, STORE)
    db.commit()

    assert db.get(Organization, test_organization.id).domain == STORE


def test_a_domain_another_org_has_is_adopted_too(db, test_organization):
    # Websites aren't unique: another org on the same store doesn't stop this one
    db.add(Organization(name="Other", domain=STORE, timezone="UTC"))
    test_organization.domain = ""
    db.commit()

    use_shop_domain_if_unset(db, test_organization.id, STORE)
    db.commit()

    assert db.get(Organization, test_organization.id).domain == STORE


def test_who_owns_a_store():
    mine, theirs = uuid4(), uuid4()
    assert not owned_by_another_org(SimpleNamespace(organization_id=None), mine)
    assert not owned_by_another_org(SimpleNamespace(organization_id=mine), str(mine))
    assert owned_by_another_org(SimpleNamespace(organization_id=theirs), mine)

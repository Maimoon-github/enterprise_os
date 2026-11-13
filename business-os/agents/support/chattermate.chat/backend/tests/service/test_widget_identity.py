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

What a widget token may do to the customer it names.
"""
from uuid import uuid4

import pytest

from app.models.customer import Customer
from app.models.session_to_agent import SessionStatus, SessionToAgent
from app.services.conversation_token import VERIFIED_SCOPE, account_conversation_key
from app.services.widget_identity import (
    can_act_as,
    may_stand_for,
    trusts_identity_in_conversation,
    trusts_identity_in_session,
)


@pytest.fixture
def customer(db, test_organization) -> Customer:
    """A customer the widget created for the browser holding "browser-a"."""
    c = Customer(email="known@acme.com", full_name="Known", organization_id=test_organization.id,
                 conversation_key="browser-a")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _session(db, customer, key) -> SessionToAgent:
    session = SessionToAgent(session_id=uuid4(), customer_id=customer.id,
                             organization_id=customer.organization_id,
                             status=SessionStatus.OPEN, conversation_key=key)
    db.add(session)
    db.commit()
    return session


def test_a_vouched_for_token_may_act_as_anyone_it_names(db, customer):
    _session(db, customer, "browser-a")
    assert can_act_as(db, customer, VERIFIED_SCOPE)


def test_a_widget_token_may_act_as_a_customer_whose_conversations_are_all_its_own(db, customer):
    _session(db, customer, "browser-a")
    assert can_act_as(db, customer, "browser-a")


def test_a_widget_token_may_not_act_as_a_customer_with_someone_elses_conversation(db, customer):
    _session(db, customer, "browser-a")
    _session(db, customer, "browser-b")
    assert not can_act_as(db, customer, "browser-a")


def test_a_keyless_conversation_belongs_to_the_vouched_for_scope(db, customer):
    _session(db, customer, None)
    assert not can_act_as(db, customer, "browser-a")


def test_a_customer_another_browser_created_is_not_owned_even_without_conversations(db, customer):
    assert not can_act_as(db, customer, "browser-b")


def test_a_legacy_token_owns_only_an_anonymous_customer_from_before_keys(db, test_organization):
    anonymous = Customer(email="1738000000000@noemail.com", organization_id=test_organization.id)
    known = Customer(email="someone@acme.com", organization_id=test_organization.id)
    db.add_all([anonymous, known])
    db.commit()

    assert can_act_as(db, anonymous, "jti:abc")
    assert not can_act_as(db, known, "jti:abc")
    assert not can_act_as(db, anonymous, "browser-a")


def test_a_widget_token_may_not_act_as_a_signed_in_customer(db, customer):
    customer.is_authenticated = True
    db.commit()
    assert not can_act_as(db, customer, "browser-a")
    assert not may_stand_for(customer, "browser-a")
    assert may_stand_for(customer, VERIFIED_SCOPE)


def test_no_scope_or_no_customer_grants_nothing(db, customer):
    assert not can_act_as(db, customer, None)
    assert not can_act_as(db, None, VERIFIED_SCOPE)
    assert not may_stand_for(customer, None)


def test_what_we_know_is_only_recited_inside_the_customers_own_conversation(db, customer):
    own = _session(db, customer, "browser-a")

    assert trusts_identity_in_session(db, customer, own.session_id)
    assert not trusts_identity_in_session(db, customer, uuid4())

    claimed = _session(db, customer, "browser-b")
    assert not trusts_identity_in_session(db, customer, claimed.session_id)
    # And once someone else is in, not even the original browser is trusted:
    # the customer is no longer theirs alone.
    assert not trusts_identity_in_session(db, customer, own.session_id)


def test_a_vouched_for_conversation_is_trusted(db, customer):
    verified = _session(db, customer, None)

    assert trusts_identity_in_session(db, customer, verified.session_id)


def test_a_signed_in_account_may_stand_for_and_act_as_its_customer(db, customer):
    """The in-app support chat: our backend vouched for the account, so its key is
    as trusted as the embedding app's - for the conversations it started."""
    customer.is_authenticated = True
    db.commit()
    scope = account_conversation_key("user-1")

    assert may_stand_for(customer, scope)
    assert can_act_as(db, customer, scope)
    assert trusts_identity_in_conversation(db, customer, _session(db, customer, scope))


def test_no_conversation_means_no_trust(db, customer):
    assert not trusts_identity_in_conversation(db, customer, None)

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
from uuid import uuid4

import pytest

from app.models.permission import Permission
from app.services.agent_rooms import may_join_org_inbox


@pytest.fixture
def viewer(db, test_user, test_role):
    permission = Permission(name="view_unassigned_chats")
    db.add(permission)
    test_role.permissions = [*test_role.permissions, permission]
    db.commit()
    return test_user


def _socket(user, org=None):
    return {"user_id": str(user.id), "organization_id": str(org or user.organization_id)}


def test_a_viewer_of_unowned_chats_may_join_their_orgs_room(db, viewer):
    assert may_join_org_inbox(db, _socket(viewer), f"org_inbox_{viewer.organization_id}")


def test_not_another_orgs_room(db, viewer):
    assert not may_join_org_inbox(db, _socket(viewer), f"org_inbox_{uuid4()}")


def test_not_without_the_permission(db, test_user):
    assert not may_join_org_inbox(db, _socket(test_user), f"org_inbox_{test_user.organization_id}")


def test_not_once_deactivated_or_deleted(db, viewer):
    viewer.is_active = False
    db.commit()
    assert not may_join_org_inbox(db, _socket(viewer), f"org_inbox_{viewer.organization_id}")
    ghost = SimpleNamespace(id=uuid4(), organization_id=viewer.organization_id)
    assert not may_join_org_inbox(db, _socket(ghost), f"org_inbox_{viewer.organization_id}")

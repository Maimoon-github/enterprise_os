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

release_connection: a session gives its connection back before a slow await.
"""

from app.database import release_connection
from app.models.organization import Organization


def test_an_open_read_is_ended(db, test_organization):
    db.query(Organization).first()
    assert db.in_transaction()

    release_connection(db)

    assert not db.in_transaction()


def test_pending_work_is_kept_and_objects_still_load(db, test_organization, caplog):
    test_organization.name = "Renamed before the model call"

    release_connection(db)

    # Kept, but said out loud: release points are expected to hold reads only
    assert "unsaved changes" in caplog.text

    db.expire_all()
    assert db.get(Organization, test_organization.id).name == "Renamed before the model call"


def test_an_idle_session_or_none_is_left_alone(db):
    release_connection(None)
    db.rollback()
    release_connection(db)
    assert not db.in_transaction()


def test_reads_alone_commit_quietly(db, test_organization, caplog):
    db.query(Organization).first()
    release_connection(db)
    assert "unsaved changes" not in caplog.text

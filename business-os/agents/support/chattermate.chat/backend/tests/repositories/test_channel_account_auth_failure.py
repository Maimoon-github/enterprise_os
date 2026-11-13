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

import pytest

from app.api.channels.accounts import to_account_out
from app.channels.base import SendResult
from app.repositories.channels import ChannelAccountRepository
from app.repositories.channels.accounts import AUTH_FAILURE_SETTING, needs_reconnect

AUTH_FAILED = SendResult(ok=False, error="Authentication Error", auth_failed=True)


@pytest.fixture
def repo(db):
    return ChannelAccountRepository(db)


@pytest.fixture
def account(repo, test_organization):
    return repo.create_account(
        organization_id=test_organization.id,
        channel_type="whatsapp",
        external_account_id="PN-auth",
        credentials={"access_token": "old"},
        display_name="Test Number",
        settings={"meta_app_id": "123"},
    )


def _reloaded(db, repo, account):
    db.expire_all()
    return repo.get_by_id(account.id)


def test_a_new_account_does_not_need_reconnecting(account):
    assert needs_reconnect(account) is False


def test_an_auth_failure_marks_the_account_and_keeps_its_settings(db, repo, account):
    repo.track_send_result(account, AUTH_FAILED)

    stored = _reloaded(db, repo, account)
    assert needs_reconnect(stored) is True
    assert stored.settings[AUTH_FAILURE_SETTING]["error"] == "Authentication Error"
    assert stored.settings["meta_app_id"] == "123"


def test_repeated_failures_keep_the_first_failure_time(db, repo, account):
    repo.track_send_result(account, AUTH_FAILED)
    first = _reloaded(db, repo, account).settings[AUTH_FAILURE_SETTING]["at"]

    repo.track_send_result(account, SendResult(ok=False, error="later", auth_failed=True))

    stored = _reloaded(db, repo, account)
    assert stored.settings[AUTH_FAILURE_SETTING] == {"error": "Authentication Error", "at": first}


def test_a_failure_that_is_not_about_credentials_changes_nothing(db, repo, account):
    repo.track_send_result(account, SendResult(ok=False, error="Re-engagement message"))
    assert needs_reconnect(_reloaded(db, repo, account)) is False


def test_a_successful_send_clears_the_flag(db, repo, account):
    repo.track_send_result(account, AUTH_FAILED)
    repo.track_send_result(account, SendResult(ok=True, external_message_id="wamid.1"))

    stored = _reloaded(db, repo, account)
    assert needs_reconnect(stored) is False
    assert stored.settings == {"meta_app_id": "123"}


def test_a_failed_send_after_recovery_does_not_clear_or_set_it(db, repo, account):
    """Only a send that worked proves the credentials; a plain failure says
    nothing either way."""
    repo.track_send_result(account, AUTH_FAILED)
    repo.track_send_result(account, SendResult(ok=False, error="Re-engagement message"))
    assert needs_reconnect(_reloaded(db, repo, account)) is True


def test_reconnecting_with_new_credentials_clears_the_flag(db, repo, account):
    repo.track_send_result(account, AUTH_FAILED)

    repo.update_credentials(account, {"access_token": "new"})

    stored = _reloaded(db, repo, account)
    assert needs_reconnect(stored) is False
    assert repo.get_credentials(stored) == {"access_token": "new"}
    assert stored.settings == {"meta_app_id": "123"}


def test_the_account_api_reports_it(db, repo, account):
    assert to_account_out(db, account).needs_reconnect is False

    repo.track_send_result(account, AUTH_FAILED)

    assert to_account_out(db, _reloaded(db, repo, account)).needs_reconnect is True

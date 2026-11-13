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

A source whose worker died partway does not spin forever. Seen in
production: the processor was killed for memory mid-source, restarted, and
only ever picks up pending items - so a new signup's site stayed
"processing" for good (and one from July with it).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import sessionmaker

from app.knowledge.failure_advice import FAILURE_ADVICE, FailureCause
from app.models.knowledge_queue import KnowledgeQueue, QueueStatus
from app.models.notification import Notification, NotificationType
from app.workers import knowledge_processor
from app.workers.knowledge_processor import ABANDONED_AFTER

SITE = "https://ian-vpn.site"


@pytest.fixture
def sessions(db):
    return sessionmaker(bind=db.get_bind())


@pytest.fixture
def push(monkeypatch, sessions):
    monkeypatch.setattr(knowledge_processor, "SessionLocal", sessions)
    sent = AsyncMock()
    monkeypatch.setattr(knowledge_processor, "send_fcm_notification", sent)
    return sent


@pytest.fixture
def queued(db, test_organization):
    def make(status, last_progress_ago, user_id=None, source=SITE, source_type="website"):
        when = datetime.now(timezone.utc) - last_progress_ago
        item = KnowledgeQueue(organization_id=test_organization.id, user_id=user_id, source=source,
                              source_type=source_type, status=status, created_at=when)
        db.add(item)
        db.commit()
        item.updated_at = when  # set explicitly: onupdate would stamp now
        db.commit()
        return item.id
    return make


def state(sessions, item_id):
    with sessions() as db:
        item = db.get(KnowledgeQueue, item_id)
        notes = [n for n in db.query(Notification).all()
                 if (n.notification_metadata or {}).get("queue_id") == item_id]
        return item.status, item.error, [(n.user_id, n.type) for n in notes]


LONG_AGO = ABANDONED_AFTER + timedelta(minutes=1)
JUST_NOW = timedelta(minutes=2)


@pytest.mark.asyncio
async def test_an_abandoned_source_fails_and_its_owner_is_told(push, sessions, queued, test_user):
    item_id = queued(QueueStatus.PROCESSING, LONG_AGO, user_id=test_user.id)

    await knowledge_processor.fail_abandoned_items()

    status, error, notes = state(sessions, item_id)
    assert status == QueueStatus.FAILED
    assert error == FAILURE_ADVICE[FailureCause.INTERRUPTED].format(url=SITE)
    assert notes == [(test_user.id, NotificationType.KNOWLEDGE_FAILED)]
    push.assert_awaited_once()


@pytest.mark.asyncio
async def test_one_with_no_owner_fails_quietly(push, sessions, queued):
    item_id = queued(QueueStatus.PROCESSING, LONG_AGO)  # a Shopify install's site

    await knowledge_processor.fail_abandoned_items()

    assert state(sessions, item_id)[:2] == (QueueStatus.FAILED,
                                            FAILURE_ADVICE[FailureCause.INTERRUPTED].format(url=SITE))
    push.assert_not_called()


@pytest.mark.asyncio
async def test_a_source_still_being_read_is_left_alone(push, sessions, queued, test_user):
    item_id = queued(QueueStatus.PROCESSING, JUST_NOW, user_id=test_user.id)

    await knowledge_processor.fail_abandoned_items()

    assert state(sessions, item_id) == (QueueStatus.PROCESSING, None, [])


@pytest.mark.asyncio
async def test_one_at_the_edge_of_its_time_limit_is_left_alone(push, sessions, queued):
    """A live run stops at its time limit; until well past it, it may still be
    another process's."""
    item_id = queued(QueueStatus.PROCESSING, ABANDONED_AFTER - timedelta(minutes=1))

    await knowledge_processor.fail_abandoned_items()

    assert state(sessions, item_id)[0] == QueueStatus.PROCESSING


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [QueueStatus.PENDING, QueueStatus.COMPLETED, QueueStatus.FAILED])
async def test_only_processing_sources_are_touched(push, sessions, queued, status):
    item_id = queued(status, LONG_AGO)

    await knowledge_processor.fail_abandoned_items()

    assert state(sessions, item_id) == (status, None, [])


def test_abandoned_means_well_past_the_time_limit():
    from app.core.config import settings
    assert ABANDONED_AFTER > timedelta(seconds=settings.KB_SOURCE_TIME_LIMIT_SECONDS)


@pytest.mark.asyncio
async def test_every_processor_run_checks_for_them(push, sessions, queued, monkeypatch):
    item_id = queued(QueueStatus.PROCESSING, LONG_AGO)
    monkeypatch.setattr(knowledge_processor, "process_queue_item", AsyncMock())

    await knowledge_processor.run_processor()

    assert state(sessions, item_id)[0] == QueueStatus.FAILED


@pytest.mark.asyncio
async def test_a_failed_check_never_holds_up_pending_sources(push, sessions, queued, monkeypatch):
    pending = queued(QueueStatus.PENDING, JUST_NOW)
    monkeypatch.setattr(knowledge_processor, "fail_abandoned_items", AsyncMock(side_effect=RuntimeError("db hiccup")))
    processed = AsyncMock()
    monkeypatch.setattr(knowledge_processor, "process_queue_item", processed)

    await knowledge_processor.run_processor()

    processed.assert_awaited_once_with(pending)


@pytest.mark.asyncio
async def test_an_uploaded_file_is_named_by_its_name_not_our_server_path(push, sessions, queued):
    item_id = queued(QueueStatus.PROCESSING, LONG_AGO, source="/app/temp/0e9f1d922da1467f_menu.pdf",
                     source_type="pdf_file")

    await knowledge_processor.fail_abandoned_items()

    error = state(sessions, item_id)[1]
    assert "/app/temp" not in error
    assert error.startswith("0e9f1d922da1467f_menu.pdf could not be read")

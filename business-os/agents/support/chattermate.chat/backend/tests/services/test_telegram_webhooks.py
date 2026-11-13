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

Registering ChatterMate's webhook with Telegram bots — including again for
an agent's bots when its reply buttons are turned on.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.channels import AgentChannelConfigRepository, ChannelAccountRepository
from app.services import telegram_webhooks


def _account(db, organization_id, channel_type, external_id, credentials):
    return ChannelAccountRepository(db).create_account(
        organization_id=organization_id, channel_type=channel_type, external_account_id=external_id,
        credentials=credentials, display_name=external_id)


@pytest.mark.asyncio
async def test_an_agents_telegram_bots_are_registered_again(db, test_organization, test_agent):
    routed = _account(db, test_organization.id, "telegram", "bot1", {"bot_token": "1:a"})
    other_channel = _account(db, test_organization.id, "whatsapp", "PN1", {"access_token": "t"})
    _account(db, test_organization.id, "telegram", "bot2", {"bot_token": "2:b"})  # routed nowhere
    inactive = _account(db, test_organization.id, "telegram", "bot3", {"bot_token": "3:c"})
    ChannelAccountRepository(db).set_active(inactive, False)
    for account in (routed, other_channel, inactive):
        AgentChannelConfigRepository(db).set_agent(account.id, test_agent.id)

    with patch.object(telegram_webhooks.telegram_api, "set_webhook", AsyncMock(return_value=(True, ""))) as set_webhook:
        await telegram_webhooks.reregister_for_agent(db, test_agent.id)

    set_webhook.assert_awaited_once()
    token, url, secret = set_webhook.await_args.args
    assert token == "1:a" and url.endswith(f"/webhooks/telegram/{routed.id}") and secret == routed.webhook_secret


@pytest.mark.asyncio
async def test_a_bot_that_cant_be_reached_doesnt_stop_the_rest(db, test_organization, test_agent):
    for n in range(2):
        account = _account(db, test_organization.id, "telegram", f"bot{n}", {"bot_token": f"{n}:x"})
        AgentChannelConfigRepository(db).set_agent(account.id, test_agent.id)

    with patch.object(telegram_webhooks.telegram_api, "set_webhook",
                      AsyncMock(return_value=(False, "Unauthorized"))) as set_webhook:
        await telegram_webhooks.reregister_for_agent(db, test_agent.id)

    assert set_webhook.await_count == 2


@pytest.mark.asyncio
async def test_a_bad_credential_is_logged_and_the_rest_still_register(db, test_organization, test_agent):
    broken = _account(db, test_organization.id, "telegram", "bot-broken", {"no_token": "x"})
    fine = _account(db, test_organization.id, "telegram", "bot-fine", {"bot_token": "9:z"})
    for account in (broken, fine):
        AgentChannelConfigRepository(db).set_agent(account.id, test_agent.id)

    with patch.object(telegram_webhooks.telegram_api, "set_webhook", AsyncMock(return_value=(True, ""))) as set_webhook:
        await telegram_webhooks.reregister_for_agent(db, test_agent.id)  # no raise

    assert [call.args[0] for call in set_webhook.await_args_list] == ["9:z"]


@pytest.mark.asyncio
async def test_a_database_error_listing_the_bots_is_logged_not_raised(db, test_agent):
    """The agent is already saved: the save must not fail over it."""
    with patch.object(telegram_webhooks.AgentChannelConfigRepository, "list_by_agent",
                      side_effect=RuntimeError("db down")), \
         patch.object(telegram_webhooks.telegram_api, "set_webhook", AsyncMock()) as set_webhook:
        await telegram_webhooks.reregister_for_agent(db, test_agent.id)
    set_webhook.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("buttons_on,channel,registered", [(True, "telegram", True), (False, "telegram", False),
                                                           (True, "whatsapp", False)])
async def test_a_bot_routed_to_an_agent_with_buttons_on_is_registered(db, test_organization, test_agent,
                                                                      buttons_on, channel, registered):
    account = _account(db, test_organization.id, channel, f"{channel}-1", {"bot_token": "1:a", "access_token": "t"})
    test_agent.channel_quick_replies = buttons_on

    with patch.object(telegram_webhooks.telegram_api, "set_webhook", AsyncMock(return_value=(True, ""))) as set_webhook:
        await telegram_webhooks.reregister_if_buttons_on(account, test_agent)

    assert set_webhook.await_count == (1 if registered else 0)

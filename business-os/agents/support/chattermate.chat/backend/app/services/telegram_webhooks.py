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

Registering ChatterMate's webhook with a Telegram bot, with the updates it
must receive. Done on connect, and again for an agent's bots when its reply
buttons are turned on: a bot connected before buttons existed was registered
without button taps, and Telegram keeps a bot's last registration.
"""

import asyncio
import json
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.channels import telegram as telegram_api
from app.core.config import settings
from app.core.security import decrypt_api_key
from app.core.logger import get_logger
from app.models.channels import ChannelAccount, ChannelType
from app.repositories.channels import AgentChannelConfigRepository, ChannelAccountRepository

logger = get_logger(__name__)


def webhook_url(account_id) -> str:
    return f"{settings.BACKEND_URL.rstrip('/')}{settings.API_V1_STR}/webhooks/telegram/{account_id}"


async def register(account: ChannelAccount, bot_token: str) -> Tuple[bool, str]:
    return await telegram_api.set_webhook(bot_token, webhook_url(account.id), account.webhook_secret)


async def reregister_for_agent(db: Session, agent_id: UUID) -> None:
    """Register again, at once, every active Telegram bot routed to this agent
    — its buttons were just turned on."""
    try:
        accounts = ChannelAccountRepository(db)
        bots = [account for account in (accounts.get_by_id(config.channel_account_id)
                                        for config in AgentChannelConfigRepository(db).list_by_agent(agent_id))
                if _is_active_bot(account)]
    except Exception:
        # The agent is already saved; only the re-registration is lost
        logger.exception(f"Could not list agent {agent_id}'s Telegram bots to re-register")
        return
    await asyncio.gather(*(_reregister(account) for account in bots))


async def reregister_if_buttons_on(account: ChannelAccount, agent) -> None:
    """A bot just routed to an agent whose buttons are already on."""
    if _is_active_bot(account) and agent.channel_quick_replies:
        await _reregister(account)


async def _reregister(account: ChannelAccount) -> None:
    """Best effort: a bot that can't be registered keeps working — only its
    button taps don't arrive until it is (turn the agent's buttons off and on
    again, or reconnect the bot)."""
    try:
        bot_token = json.loads(decrypt_api_key(account.encrypted_credentials))["bot_token"]
        ok, error = await register(account, bot_token)
    except Exception as e:
        ok, error = False, f"{type(e).__name__}: {e}"
    if not ok:
        logger.warning(f"Could not re-register Telegram bot {account.id} for button taps: {error}")


def _is_active_bot(account: Optional[ChannelAccount]) -> bool:
    return (account is not None and account.is_active
            and account.channel_type == ChannelType.TELEGRAM.value)

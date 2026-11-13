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

from typing import Optional
from uuid import uuid4

import pytest

from app.channels.base import (
    InboundMessage, InteractiveReply, InteractiveReplyType, SharedLocation,
)
from app.channels.interactive import from_options
from app.channels.interactive_limits import MESSENGER_LIMITS, WHATSAPP_LIMITS
from app.channels.sent_choices import SENT_CHOICES_ATTRIBUTE, encode_sent_choices
from app.repositories.channels import ChannelAccountRepository, ChannelConversationRepository
from app.repositories.chat import ChatRepository
from app.services.channel_replies import inbound_attributes, reply_text

LONG_OPTION = "Reschedule to next Saturday morning"


def _tap(reply_id: str, title: str, reply_to: Optional[str] = "wamid.OFFER", chat: str = "447") -> InboundMessage:
    return InboundMessage(
        external_account_id="PN123", external_conversation_id=chat,
        external_user_id=chat, external_message_id="wamid.IN", text=title,
        interactive=InteractiveReply(type=InteractiveReplyType.LIST_REPLY,
                                     id=reply_id, title=title),
        reply_to_message_id=reply_to,
    )


def _typed(text: str, chat: str = "447") -> InboundMessage:
    return InboundMessage(external_account_id="PN123", external_conversation_id=chat, external_user_id=chat,
                          external_message_id="wamid.IN", text=text)


@pytest.fixture
def account(db, test_organization):
    return ChannelAccountRepository(db).create_account(
        organization_id=test_organization.id, channel_type="whatsapp", external_account_id="PN123",
        credentials={"access_token": "t"}, display_name="+1")


def _session(db, account, chat="447"):
    """A new session of this customer's chat (one per open/close cycle)."""
    session_id = uuid4()
    ChannelConversationRepository(db).create(
        channel_account_id=account.id, channel_type=account.channel_type, external_conversation_id=chat,
        external_user_id=chat, session_id=session_id, organization_id=account.organization_id)
    return session_id


def _offer(db, account, session_id, options, external_message_id="wamid.OFFER", limits=WHATSAPP_LIMITS,
           numbered=False):
    return ChatRepository(db).create_message({
        "message": "What now?",
        "message_type": "bot",
        "session_id": str(session_id),
        "organization_id": str(account.organization_id),
        "external_message_id": external_message_id,
        "attributes": {SENT_CHOICES_ATTRIBUTE: encode_sent_choices(
            from_options("What now?", options, limits), as_text=False, numbered=numbered)},
    })


def test_tap_on_a_cut_option_reads_as_the_full_option(db, account):
    _offer(db, account, _session(db, account), ["Cancel", LONG_OPTION])
    assert reply_text(db, account.id, _tap("qr_1", "Reschedule to next Sat…")) == LONG_OPTION


def test_a_tap_days_later_in_a_new_session_still_reads_as_the_full_option(db, account):
    """The chat closed; the customer's late tap opened a new session."""
    _offer(db, account, _session(db, account), ["Cancel", LONG_OPTION])
    _session(db, account)
    assert reply_text(db, account.id, _tap("qr_1", "Reschedule to next Sat…")) == LONG_OPTION


def test_a_button_cut_to_fit_reads_as_the_full_option(db, account):
    """Messenger has no lists: a long option goes as a cut button title."""
    _offer(db, account, _session(db, account), ["Cancel", LONG_OPTION], limits=MESSENGER_LIMITS)
    assert reply_text(db, account.id, _tap("qr_1", "Reschedule to next…", reply_to=None)) == LONG_OPTION


def test_tap_on_unknown_ids_or_messages_keeps_the_title(db, account):
    _offer(db, account, _session(db, account), ["Cancel"])
    assert reply_text(db, account.id, _tap("attendance:present", "Present")) == "Present"
    assert reply_text(db, account.id, _tap("qr_5", "Gone")) == "Gone"
    assert reply_text(db, account.id, _tap("qr_0", "Lost", reply_to="wamid.NONE")) == "Lost"


def test_tap_never_reads_another_chats_offer(db, account):
    """Telegram numbers messages per chat: another chat can have the same id."""
    _offer(db, account, _session(db, account, chat="999"), ["Cancel", LONG_OPTION], external_message_id="17")
    _offer(db, account, _session(db, account), ["Yes", "No"], external_message_id="17")
    assert reply_text(db, account.id, _tap("qr_1", "No", reply_to="17")) == "No"
    assert reply_text(db, account.id, _tap("qr_1", "Reschedule…", reply_to="17", chat="555")) == "Reschedule…"


def test_tap_never_reads_another_accounts_offer(db, account, test_organization):
    other = ChannelAccountRepository(db).create_account(
        organization_id=test_organization.id, channel_type="whatsapp", external_account_id="PN999",
        credentials={"access_token": "t"}, display_name="+2")
    _offer(db, other, _session(db, other), ["Cancel", LONG_OPTION])
    assert reply_text(db, account.id, _tap("qr_1", "Reschedule…")) == "Reschedule…"


def test_a_tap_without_reply_context_matches_the_latest_offer(db, account):
    """Messenger and Instagram quick-reply taps carry no reply context."""
    session = _session(db, account)
    _offer(db, account, session, ["Cancel", "Old choice"], external_message_id="m1")
    _offer(db, account, session, ["Cancel", LONG_OPTION], external_message_id="m2", limits=MESSENGER_LIMITS)
    assert reply_text(db, account.id, _tap("qr_1", "Reschedule to next…", reply_to=None)) == LONG_OPTION


def test_a_tap_with_no_text_reads_as_its_title(db, account):
    tap = _tap("unknown", "Present", reply_to=None)
    tap.text = None
    assert reply_text(db, account.id, tap) == "Present"


@pytest.mark.parametrize("typed,expected", [("2", LONG_OPTION), ("2.", LONG_OPTION), (" 1 ", "Cancel"),
                                            ("3", "3"), ("0", "0"), ("two", "two"), ("²", "²"), ("①", "①")])
def test_a_typed_number_picks_from_choices_shown_numbered(db, account, typed, expected):
    """Instagram on desktop shows the numbered list, not the buttons."""
    _offer(db, account, _session(db, account), ["Cancel", LONG_OPTION], numbered=True)
    assert reply_text(db, account.id, _typed(typed)) == expected


def test_a_typed_number_is_just_a_number_after_unnumbered_buttons(db, account):
    _offer(db, account, _session(db, account), ["Cancel", LONG_OPTION])
    assert reply_text(db, account.id, _typed("2")) == "2"


def test_a_typed_number_only_answers_our_latest_reply(db, account):
    session = _session(db, account)
    _offer(db, account, session, ["Cancel", LONG_OPTION], numbered=True)
    ChatRepository(db).create_message({"message": "How many seats?", "message_type": "bot",
                                       "session_id": str(session), "organization_id": str(account.organization_id)})
    assert reply_text(db, account.id, _typed("2")) == "2"


def test_a_typed_number_answers_a_persons_question_not_an_older_bot_offer(db, account):
    """A person took over and asked something after the AI's numbered choices."""
    session = _session(db, account)
    _offer(db, account, session, ["Cancel", LONG_OPTION], numbered=True)
    ChatRepository(db).create_message({"message": "How many units?", "message_type": "agent",
                                       "session_id": str(session), "organization_id": str(account.organization_id)})
    assert reply_text(db, account.id, _typed("2")) == "2"


@pytest.mark.parametrize("typed", ["2", "3", "4"])
def test_a_number_that_is_one_of_the_choices_is_that_choice(db, account, typed):
    """Choices that are numbers themselves (guest counts): never read as positions."""
    _offer(db, account, _session(db, account), ["2", "3", "4"], numbered=True)
    assert reply_text(db, account.id, _typed(typed)) == typed


def test_plain_text_is_unchanged(db, account):
    assert reply_text(db, account.id, _typed("hi", chat="1")) == "hi"


def test_attributes_hold_ids_only_never_customer_details():
    inbound = _tap("qr_0", "Cancel")
    inbound.location = SharedLocation(latitude=1.5, longitude=2.5, name="Home", address="1 High St")

    attributes = inbound_attributes(inbound, "whatsapp")

    assert attributes == {
        "channel": "whatsapp",
        "external_message_id": "wamid.IN",
        "interactive_reply": {"type": "list_reply", "id": "qr_0"},
        "reply_to_message_id": "wamid.OFFER",
    }

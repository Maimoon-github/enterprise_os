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

The AI's choices as tappable buttons beyond WhatsApp: Messenger and
Instagram quick replies, Telegram inline keyboards — sending them within
each channel's limits, and reading the taps back.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.channels import get_adapter, telegram
from app.channels.base import (
    InteractiveButton, InteractiveKind, InteractiveMessage, InteractiveReplyType, InteractiveRow,
    InteractiveSection,
)
from app.channels.interactive import from_options, validate_interactive
from app.channels.interactive_limits import (
    INSTAGRAM_LIMITS, MESSENGER_LIMITS, TELEGRAM_LIMITS, WHATSAPP_LIMITS,
)
from tests.channels.test_meta_adapters import _FakeResponse, graph_client  # noqa: F401  (fixture)

LONG = "Reschedule to next Saturday morning"


def _conversation(external_id="PSID1"):
    conversation = MagicMock()
    conversation.external_conversation_id = external_id
    return conversation


# --- building choices within each channel's limits ---

def test_whatsapp_still_gets_a_list_for_long_options():
    assert from_options("Pick", ["Cancel", LONG], WHATSAPP_LIMITS).kind == InteractiveKind.LIST


@pytest.mark.parametrize("limits", [MESSENGER_LIMITS, TELEGRAM_LIMITS])
def test_channels_without_lists_get_buttons(limits):
    message = from_options("Pick", ["Cancel", LONG] + [f"Option {i}" for i in range(8)], limits)
    assert message.kind == InteractiveKind.BUTTONS
    assert len(message.buttons) == 10
    assert all(len(b.title) <= limits.button_title_max for b in message.buttons)
    assert validate_interactive(message, limits) == []


def test_a_cut_button_title_keeps_the_full_option():
    button = from_options("Pick", ["Cancel", LONG], MESSENGER_LIMITS).buttons[1]
    assert button.title.endswith("…") and button.description == LONG


def test_a_list_or_link_button_is_refused_where_the_channel_has_none():
    list_message = InteractiveMessage(kind=InteractiveKind.LIST, body="Pick", list_button_label="Choose",
                                      sections=[InteractiveSection(rows=[InteractiveRow(id="a", title="A")])])
    link = InteractiveMessage(kind=InteractiveKind.CTA_URL, body="Pay", display_text="Pay", url="https://x.io")
    assert "this channel can't show a list" in validate_interactive(list_message, MESSENGER_LIMITS)
    assert "this channel can't show a link button" in validate_interactive(link, TELEGRAM_LIMITS)


def test_telegram_ids_are_limited_in_bytes():
    message = InteractiveMessage(kind=InteractiveKind.BUTTONS, body="Pick",
                                 buttons=[InteractiveButton(id="é" * 33, title="A")])  # 66 bytes, 33 chars
    assert any("bytes" in e for e in validate_interactive(message, TELEGRAM_LIMITS))
    assert validate_interactive(message, MESSENGER_LIMITS) == []


def test_messenger_allows_thirteen_quick_replies():
    buttons = [InteractiveButton(id=str(i), title=str(i)) for i in range(14)]
    message = InteractiveMessage(kind=InteractiveKind.BUTTONS, body="Pick", buttons=buttons[:13])
    assert validate_interactive(message, MESSENGER_LIMITS) == []
    message.buttons = buttons
    assert validate_interactive(message, MESSENGER_LIMITS) != []


@pytest.mark.parametrize("channel,limits", [("whatsapp", WHATSAPP_LIMITS), ("messenger", MESSENGER_LIMITS),
                                            ("instagram", INSTAGRAM_LIMITS), ("telegram", TELEGRAM_LIMITS),
                                            ("slack", None), ("email", None)])
def test_which_channels_can_show_buttons(channel, limits):
    adapter = get_adapter(channel)
    assert adapter.interactive_limits is limits
    assert adapter.supports_interactive is (limits is not None)


# --- Messenger and Instagram ---

@pytest.mark.asyncio
async def test_messenger_sends_quick_replies(graph_client, monkeypatch):  # noqa: F811
    adapter = get_adapter("messenger")
    monkeypatch.setattr(adapter, "access_token", lambda account: "TOKEN")
    graph_client.response = _FakeResponse(200, {"message_id": "m.1"})

    result = await adapter.send_interactive(MagicMock(), _conversation(), from_options("Coming?", ["Yes", "No"],
                                                                                       MESSENGER_LIMITS))

    assert result.external_message_id == "m.1"
    message = graph_client.calls[0]["json"]["message"]
    assert message == {"text": "Coming?", "quick_replies": [
        {"content_type": "text", "title": "Yes", "payload": "qr_0"},
        {"content_type": "text", "title": "No", "payload": "qr_1"}]}


@pytest.mark.asyncio
async def test_instagram_also_writes_the_choices_into_the_text(graph_client, monkeypatch):  # noqa: F811
    """Instagram doesn't show quick replies on desktop or the web."""
    adapter = get_adapter("instagram")
    monkeypatch.setattr(adapter, "access_token", lambda account: "TOKEN")
    graph_client.response = _FakeResponse(200, {"message_id": "m.1"})

    await adapter.send_interactive(MagicMock(), _conversation(), from_options("Coming?", ["Yes", "No"],
                                                                              INSTAGRAM_LIMITS))

    message = graph_client.calls[0]["json"]["message"]
    assert message["text"] == "Coming?\n\n1. Yes\n2. No"
    assert [q["payload"] for q in message["quick_replies"]] == ["qr_0", "qr_1"]


@pytest.mark.asyncio
async def test_messenger_refuses_a_list():
    message = InteractiveMessage(kind=InteractiveKind.LIST, body="Pick", list_button_label="Choose",
                                 sections=[InteractiveSection(rows=[InteractiveRow(id="a", title="A")])])
    assert (await get_adapter("messenger").send_interactive(MagicMock(), _conversation(), message)).ok is False


@pytest.mark.parametrize("channel", ["messenger", "instagram"])
def test_a_quick_reply_tap_is_read(channel):
    payload = {"entry": [{"id": "PAGE", "messaging": [{
        "sender": {"id": "PSID1"}, "timestamp": 1720000000000,
        "message": {"mid": "m.2", "text": "No", "quick_reply": {"payload": "qr_1"}}}]}]}
    [inbound] = get_adapter(channel).parse_inbound(payload)
    assert (inbound.interactive.type, inbound.interactive.id, inbound.interactive.title) == (
        InteractiveReplyType.BUTTON_REPLY, "qr_1", "No")
    assert inbound.reply_to_message_id is None


def test_a_swipe_reply_keeps_its_context_and_plain_text_has_no_tap():
    payload = {"entry": [{"id": "PAGE", "messaging": [{
        "sender": {"id": "PSID1"}, "timestamp": 1720000000000,
        "message": {"mid": "m.3", "text": "That one", "reply_to": {"mid": "m.1"}}}]}]}
    [inbound] = get_adapter("messenger").parse_inbound(payload)
    assert (inbound.interactive, inbound.reply_to_message_id) == (None, "m.1")


# --- Telegram ---

@pytest.fixture
def telegram_api(monkeypatch):
    call = AsyncMock(return_value={"ok": True, "result": {"message_id": 55}})
    monkeypatch.setattr(telegram, "_call_api", call)
    return call


@pytest.mark.asyncio
async def test_telegram_sends_an_inline_keyboard(telegram_api, monkeypatch):
    adapter = get_adapter("telegram")
    monkeypatch.setattr(adapter, "_bot_token", lambda account: "123:abc")

    result = await adapter.send_interactive(MagicMock(), _conversation("222"),
                                            from_options("Coming?", ["Yes", "No"], TELEGRAM_LIMITS))

    assert result.external_message_id == "55"
    method, payload = telegram_api.await_args.args[1], telegram_api.await_args.args[2]
    assert method == "sendMessage"
    assert payload["reply_markup"] == {"inline_keyboard": [[{"text": "Yes", "callback_data": "qr_0"}],
                                                           [{"text": "No", "callback_data": "qr_1"}]]}


@pytest.mark.asyncio
async def test_the_webhook_is_registered_for_taps(telegram_api):
    await telegram.set_webhook("123:abc", "https://x.io/hook", "secret")
    assert telegram_api.await_args.args[2]["allowed_updates"] == ["message", "callback_query"]


def _callback(chat_type="private", data="qr_1", with_message=True, date=1720000000):
    callback = {"id": "cb-9", "from": {"id": 111, "first_name": "Ada"}, "data": data}
    if with_message:
        callback["message"] = {
            "message_id": 41, "date": date, "chat": {"id": 222, "type": chat_type},
            "reply_markup": {"inline_keyboard": [[{"text": "Yes", "callback_data": "qr_0"}],
                                                 [{"text": "No", "callback_data": "qr_1"}]]}}
    return {"update_id": 5, "callback_query": callback}


def test_a_tap_is_read_with_its_title_from_the_keyboard():
    [inbound] = get_adapter("telegram").parse_inbound(_callback())
    assert (inbound.external_message_id, inbound.external_conversation_id, inbound.text) == ("cbq:cb-9", "222", "No")
    assert (inbound.interactive.id, inbound.reply_to_message_id) == ("qr_1", "41")


@pytest.mark.parametrize("update", [
    _callback(chat_type="group"),           # anyone in a group could tap
    _callback(with_message=False),          # the keyboard message is gone
    _callback(date=0),                      # inaccessible message
    _callback(data="qr_9"),                 # not a button on that keyboard
    _callback(data=None),
])
def test_taps_that_cant_be_trusted_are_dropped(update):
    assert get_adapter("telegram").parse_inbound(update) == []


def test_a_tap_is_answered_and_nothing_else_is():
    assert telegram.callback_answer(_callback(), taken=True) == {"method": "answerCallbackQuery",
                                                                 "callback_query_id": "cb-9"}
    assert telegram.callback_answer({"update_id": 1, "message": {"text": "hi"}}, taken=False) is None


def test_a_tap_we_didnt_act_on_says_so():
    assert telegram.callback_answer(_callback(), taken=False)["text"] == telegram.TAP_NOT_TAKEN


def test_one_tap_counts_per_keyboard():
    [first] = get_adapter("telegram").parse_inbound(_callback(data="qr_0"))
    [second] = get_adapter("telegram").parse_inbound(_callback(data="qr_1"))
    assert telegram.dedupe_id(first) == telegram.dedupe_id(second) == "keyboard:41"
    message = get_adapter("telegram").parse_inbound({"update_id": 1, "message": {
        "message_id": 7, "from": {"id": 1}, "chat": {"id": 222, "type": "private"}, "date": 1, "text": "hi"}})[0]
    assert telegram.dedupe_id(message) == "7"


@pytest.mark.asyncio
async def test_the_keyboard_is_taken_off_a_tapped_message(telegram_api, monkeypatch):
    adapter = get_adapter("telegram")
    monkeypatch.setattr(adapter, "_bot_token", lambda account: "123:abc")
    await adapter.clear_buttons(MagicMock(), "222", "41")
    assert telegram_api.await_args.args[1:] == ("editMessageReplyMarkup", {
        "chat_id": "222", "message_id": 41, "reply_markup": {"inline_keyboard": []}})
    telegram_api.side_effect = RuntimeError("message is not modified")
    await adapter.clear_buttons(MagicMock(), "222", "41")  # best effort: no raise


@pytest.mark.parametrize("chat_id,offered", [("222", True), ("-1001234", False)])
def test_telegram_groups_get_no_buttons(chat_id, offered):
    """Anyone in a group could tap them, so taps there are ignored."""
    assert (get_adapter("telegram").choice_limits_for(_conversation(chat_id)) is not None) is offered


def test_other_channels_offer_their_limits_in_every_conversation():
    assert get_adapter("messenger").choice_limits_for(_conversation()) is MESSENGER_LIMITS


@pytest.mark.parametrize("channel,cap", [("messenger", 2000), ("instagram", 1000), ("telegram", 4096)])
def test_a_channels_text_cap_matches_its_limits(channel, cap):
    adapter = get_adapter(channel)
    assert adapter.max_text_length == adapter.interactive_limits.body_max == cap
    assert len(adapter.format_outbound("x" * (cap + 50))) == cap

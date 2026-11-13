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

ChatResponse.quick_replies must be acceptable to every structured-output
path, and a bad value from the model must never fail the turn.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from openai.lib._pydantic import to_strict_json_schema
from sqlalchemy.orm import Session

from app.agents.chat_agent import (
    ChatAgent, _GROQ_JSON_TOOL_SCHEMA, _GROQ_QUICK_REPLIES_PROPERTY,
    _build_chat_response_from_capture, drop_stale_choices,
)
from app.agents.choice_prompt import choice_instructions
from app.channels.interactive_limits import MESSENGER_LIMITS, TELEGRAM_LIMITS, WHATSAPP_LIMITS
from app.channels.constants import MAX_CHOICE_LENGTH, MAX_CHOICE_OPTIONS
from app.models.schemas.chat import ChannelChatResponse, ChatResponse
from app.utils.response_parser import parse_response_content


def _response(**fields) -> ChannelChatResponse:
    return ChannelChatResponse(message="Pick one", transfer_to_human=False, end_chat=False,
                               request_rating=False, create_ticket=False, **fields)


def test_openai_strict_schema_accepts_a_string_list():
    schema = to_strict_json_schema(ChannelChatResponse)
    assert schema["properties"]["quick_replies"]["anyOf"] == [
        {"items": {"type": "string"}, "type": "array"}, {"type": "null"}]


def test_agents_not_offered_choices_keep_their_schema():
    assert "quick_replies" not in to_strict_json_schema(ChatResponse)["properties"]
    assert "quick_replies" not in _GROQ_JSON_TOOL_SCHEMA["properties"]


def test_groq_tool_declares_the_field_only_when_offered():
    assert _GROQ_QUICK_REPLIES_PROPERTY["items"] == {"type": "string"}


def test_groq_capture_carries_quick_replies():
    response = _build_chat_response_from_capture(
        {"message": "When?", "quick_replies": ["Today", "Tomorrow"]}, ChannelChatResponse)
    assert response.quick_replies == ["Today", "Tomorrow"]


def test_options_are_cleaned_and_capped_not_rejected():
    response = _response(quick_replies=["  Yes ", "yes", "", None, "No"]
                         + [f"Option {i}" for i in range(MAX_CHOICE_OPTIONS + 5)])
    assert response.quick_replies[:2] == ["Yes", "No"]
    assert len(response.quick_replies) == MAX_CHOICE_OPTIONS


def test_object_shaped_options_give_their_text_never_a_repr():
    response = _response(quick_replies=[{"title": "Yes"}, {"label": "Maybe"}, {"x": 1}, 7, "No"])
    assert response.quick_replies == ["Yes", "Maybe", "No"]


def test_each_option_is_capped():
    response = _response(quick_replies=["x" * 500])
    assert len(response.quick_replies[0]) == MAX_CHOICE_LENGTH


class TestStaleChoices:
    def test_kept_with_the_reply_the_model_wrote(self):
        response = _response(quick_replies=["Yes"])
        drop_stale_choices(response, "Pick one")
        assert response.quick_replies == ["Yes"]

    def test_dropped_when_the_guardrail_replaced_the_reply(self):
        response = _response(quick_replies=["Yes"])
        drop_stale_choices(response, "the model's original text")
        assert response.quick_replies is None

    def test_dropped_on_a_goodbye(self):
        response = _response(quick_replies=["Yes"])
        response.end_chat = True
        drop_stale_choices(response, "Pick one")
        assert response.quick_replies is None

    def test_plain_responses_are_untouched(self):
        response = ChatResponse(message="x", transfer_to_human=False, end_chat=True,
                                request_rating=False, create_ticket=False)
        drop_stale_choices(response, "y")  # no field to clear, must not raise


def test_a_malformed_value_is_dropped():
    assert _response(quick_replies="Yes, No").quick_replies is None
    assert _response(quick_replies=[]).quick_replies is None
    assert _response().quick_replies is None


def _build_agent(choice_limits) -> ChatAgent:
    """A ChatAgent with everything external stubbed, to read its prompt."""
    agent_data = Mock()
    agent_data.name = "Support"
    agent_data.jira_enabled = False
    agent_data.transfer_to_human = False
    agent_data.ask_for_rating = False
    agent_data.ticketing_enabled = False
    agent_data.instructions = ["You are a helpful assistant"]
    storage = Mock()
    storage.get_session_state.return_value = {"status": "active"}

    with patch('app.agents.chat_agent.get_db') as mock_get_db, \
         patch('app.agents.chat_agent.JiraRepository') as mock_jira_repo, \
         patch('app.tools.knowledge_search_byagent.KnowledgeSearchByAgent', return_value=Mock()), \
         patch('app.agents.chat_agent.EncryptedPostgresAgentStorage', return_value=storage), \
         patch('app.agents.chat_agent.settings.DATABASE_URL', "mock://test"), \
         patch.dict('os.environ', {}, clear=True):
        mock_get_db.return_value = iter([MagicMock(spec=Session)])
        mock_jira_repo.return_value.get_agent_with_jira_config.return_value = agent_data
        return ChatAgent(api_key="test-key", model_name="gpt-4", model_type="openai",
                         org_id=str(uuid4()), agent_id=str(uuid4()),
                         customer_id=str(uuid4()), session_id=str(uuid4()),
                         channel="whatsapp", choice_limits=choice_limits)


def _prompt(agent: ChatAgent) -> str:
    instructions = agent.agent.instructions
    return "\n".join(instructions) if isinstance(instructions, list) else instructions


def test_only_a_channel_with_buttons_gets_the_choice_instructions():
    offered, plain = _build_agent(WHATSAPP_LIMITS), _build_agent(None)
    assert choice_instructions(WHATSAPP_LIMITS) in _prompt(offered)
    assert "tappable choices" not in _prompt(plain)
    assert offered.agent.response_model is ChannelChatResponse
    assert plain.agent.response_model is ChatResponse


def test_choices_survive_a_reply_parsed_from_text_json():
    """Some models answer with JSON in the text instead of structured output."""
    response = parse_response_content(
        SimpleNamespace(content='{"message": "When?", "quick_replies": ["Today", "Tomorrow"]}'),
        ChannelChatResponse)
    assert response.quick_replies == ["Today", "Tomorrow"]


def test_choices_are_dropped_with_an_empty_turn_fallback():
    response = _response(quick_replies=["Yes"])
    response.message = "I'm sorry, I didn't quite catch that."  # the empty-turn fallback
    drop_stale_choices(response, "")
    assert response.quick_replies is None


def test_the_instructions_follow_the_channels_limits():
    assert "up to 3 short options show as buttons, more as a list" in choice_instructions(WHATSAPP_LIMITS)
    telegram = choice_instructions(TELEGRAM_LIMITS)
    assert "at most 10," in telegram and "more as a list" not in telegram
    assert "under 64 characters" in telegram
    messenger = choice_instructions(MESSENGER_LIMITS)
    assert "at most 10," in messenger and "13" not in messenger

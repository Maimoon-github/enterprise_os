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

The transfer reply's model call, against a real session: the history it is handed
is rows of that session, and reading them after the release must not take the
connection back for the length of the call.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agents.transfer_agent import get_agent_availability_response
from app.models.chat_history import ChatHistory


@pytest.mark.asyncio
async def test_the_history_rows_do_not_take_the_connection_back(db, test_organization, test_agent, test_customer):
    for i, kind in enumerate(["user", "bot", "user"]):
        db.add(ChatHistory(organization_id=test_organization.id, agent_id=test_agent.id, customer_id=test_customer.id,
                           message=f"message {i}", message_type=kind))
    db.commit()
    history = db.query(ChatHistory).order_by(ChatHistory.id).all()  # rows of this session, transaction open
    held = []

    class FakeTransferAgent:
        def __init__(self, **kwargs):
            self.agent = SimpleNamespace(tools=[])

        async def get_transfer_response(self, chat_history, **kwargs):
            # What the real one does before its model call: read every row
            lines = [f"{m.message_type}: {m.message}" for m in chat_history]
            held.append(db.in_transaction())
            return {"message": "\n".join(lines), "transfer_to_human": True}

    # A team to hand over to (its members are looked up, not part of this check)
    agent = SimpleNamespace(id=test_agent.id, name="Tom", display_name="Tom", groups=[SimpleNamespace(id="g-1")],
                            jira_enabled=False, organization=None)
    with patch("app.agents.transfer_agent.TransferResponseAgent", FakeTransferAgent), \
         patch("app.agents.transfer_agent.GroupRepository") as groups, \
         patch("app.agents.transfer_agent.CustomerRepository") as customers:
        groups.return_value.get_group_with_users.return_value = SimpleNamespace(users=[])
        customers.return_value.get_customer_email.return_value = None
        response = await get_agent_availability_response(
            agent=agent, customer_id=str(test_customer.id), chat_history=history, db=db,
            api_key="k", model_name="m", model_type="OPENAI", session_id="s")

    assert held == [False]
    assert response["message"] == "user: message 0\nbot: message 1\nuser: message 2"

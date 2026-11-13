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
from datetime import datetime
from sqlalchemy import text
from app.repositories.chat import ChatRepository
from app.models.chat_history import ChatHistory
from app.models.customer import Customer
from app.models.agent import Agent, AgentType
from app.models.session_to_agent import SessionToAgent, SessionStatus
from app.models.user import User, UserGroup
from uuid import uuid4, UUID
from app.channels.interactive import from_options
from app.channels.sent_choices import SENT_CHOICES_ATTRIBUTE, encode_sent_choices
from app.models.schemas.chat import ChatDetailResponse

@pytest.fixture
def chat_repo(db):
    return ChatRepository(db)

@pytest.fixture
def test_data(db, test_organization_id):
    """Create test data including customer, agent, user, and session"""
    customer = Customer(
        id=uuid4(),
        email="customer@test.com",
        full_name="Test Customer",
        organization_id=test_organization_id
    )
    db.add(customer)

    agent = Agent(
        id=uuid4(),
        name="test-agent",
        display_name="Test Agent",
        organization_id=test_organization_id,
        description="Test agent description",
        agent_type=AgentType.CUSTOMER_SUPPORT,
        instructions=["Be helpful"],
        is_active=True
    )
    db.add(agent)

    user = User(
        id=uuid4(),
        email="user@test.com",
        full_name="Test User",
        hashed_password="dummy_hash",
        is_active=True,
        organization_id=test_organization_id
    )
    db.add(user)

    # Create a test group
    group = UserGroup(
        id=uuid4(),
        name="Test Group",
        description="Test group description",
        organization_id=test_organization_id
    )
    db.add(group)
    db.flush()

    session_id = uuid4()
    session = SessionToAgent(
        session_id=session_id,
        organization_id=test_organization_id,
        agent_id=agent.id,
        user_id=user.id,
        customer_id=customer.id,
        status=SessionStatus.OPEN,
        group_id=group.id
    )
    db.add(session)

    # Add some chat messages
    messages = []
    for i in range(3):
        message = ChatHistory(
            organization_id=test_organization_id,
            session_id=session_id,
            customer_id=customer.id,
            agent_id=agent.id,
            user_id=user.id,
            message=f"Test message {i}",
            message_type="text",
            attributes={"key": f"value{i}"}
        )
        messages.append(message)
        db.add(message)

    db.commit()
    
    return {
        "org_id": test_organization_id,
        "customer": customer,
        "agent": agent,
        "user": user,
        "session_id": session_id,
        "messages": messages,
        "group": group
    }

def test_create_message(chat_repo, test_data):
    """Test creating a new chat message"""
    message_data = {
        "organization_id": test_data["org_id"],
        "session_id": test_data["session_id"],
        "customer_id": test_data["customer"].id,
        "agent_id": test_data["agent"].id,
        "user_id": test_data["user"].id,
        "message": "New test message",
        "message_type": "text",
        "attributes": {"test": "value"}
    }

    message = chat_repo.create_message(message_data)
    assert message is not None
    assert message.message == "New test message"
    assert message.message_type == "text"
    assert message.attributes == {"test": "value"}

@pytest.mark.asyncio
async def test_get_session_history(chat_repo, test_data):
    """Test retrieving chat history for a session"""
    history = await chat_repo.get_session_history(test_data["session_id"])
    
    assert len(history) == 3
    for i, msg in enumerate(history):
        assert msg.message == f"Test message {i}"
        assert msg.user is not None
        assert msg.agent is not None

def test_get_user_history(chat_repo, test_data):
    """Test retrieving chat history for a user"""
    history = chat_repo.get_user_history(test_data["user"].id)
    
    assert len(history) == 3
    for msg in history:
        assert msg.user_id == test_data["user"].id

def test_get_recent_chats(chat_repo, test_data):
    """Test retrieving recent chat overviews"""
    chats = chat_repo.get_recent_chats(
        organization_id=test_data["org_id"],
        user_id=test_data["user"].id,
        user_groups=[str(test_data["group"].id)]
    )
    
    assert len(chats) == 1
    chat = chats[0]
    assert chat["customer"]["email"] == "customer@test.com"
    assert chat["agent"]["name"] == "test-agent"
    assert chat["message_count"] == 3
    assert chat["status"] == SessionStatus.OPEN
    assert chat["group_id"] == str(test_data["group"].id)


def test_get_recent_chats_preview_is_the_latest_message(chat_repo, test_data, db):
    """The preview is the newest message, decrypted — not the lexicographic max,
    which is what an aggregate over ciphertext would return."""
    db.add(ChatHistory(
        organization_id=test_data["org_id"],
        session_id=test_data["session_id"],
        customer_id=test_data["customer"].id,
        agent_id=test_data["agent"].id,
        user_id=test_data["user"].id,
        # Sorts before every "Test message N" alphabetically, so a max() would miss it.
        message="A final reply from the agent",
        message_type="text",
    ))
    db.commit()

    chats = chat_repo.get_recent_chats(
        organization_id=test_data["org_id"],
        user_id=test_data["user"].id,
        user_groups=[str(test_data["group"].id)]
    )

    assert chats[0]["last_message"] == "A final reply from the agent"


def test_get_recent_chats_preview_reads_legacy_plaintext(chat_repo, test_data, db):
    """Rows written before encryption at rest have no prefix and must still show."""
    legacy = ChatHistory(
        organization_id=test_data["org_id"],
        session_id=test_data["session_id"],
        customer_id=test_data["customer"].id,
        agent_id=test_data["agent"].id,
        user_id=test_data["user"].id,
        message="placeholder",
        message_type="text",
        created_at=datetime(2030, 1, 1),
    )
    db.add(legacy)
    db.commit()
    # Overwrite in raw SQL so the value stays plaintext, as it would be in a row
    # written before encryption at rest.
    db.execute(
        text("UPDATE chat_history SET message = :message WHERE id = :id"),
        {"message": "legacy plaintext message", "id": legacy.id},
    )
    db.commit()

    chats = chat_repo.get_recent_chats(
        organization_id=test_data["org_id"],
        user_id=test_data["user"].id,
        user_groups=[str(test_data["group"].id)]
    )

    assert chats[0]["last_message"] == "legacy plaintext message"

@pytest.mark.asyncio
async def test_check_session_access(chat_repo, test_data):
    """Test checking session access"""
    # Test access with user_id
    has_access = await chat_repo.check_session_access(
        test_data["session_id"],
        test_data["user"].id,
        [str(test_data["group"].id)]
    )
    assert has_access is True

    # Test access with group
    has_access = await chat_repo.check_session_access(
        test_data["session_id"],
        uuid4(),  # Different user
        [str(test_data["group"].id)]
    )
    assert has_access is True

    # Test no access
    has_access = await chat_repo.check_session_access(
        test_data["session_id"],
        uuid4(),  # Different user
        [str(uuid4())]  # Different group
    )
    assert has_access is False

@pytest.mark.asyncio
async def test_get_chat_detail(chat_repo, test_data):
    """Test retrieving detailed chat information"""
    detail = await chat_repo.get_chat_detail(
        test_data["session_id"],
        test_data["org_id"]
    )
    
    assert detail is not None
    assert detail["customer"]["email"] == "customer@test.com"
    assert detail["customer"]["meta_data"] is None
    assert detail["agent"]["name"] == "test-agent"
    assert detail["status"] == SessionStatus.OPEN
    assert detail["group_id"] == str(test_data["group"].id)
    assert detail["user_id"] == test_data["user"].id
    assert detail["user_name"] == "Test User"
    assert len(detail["messages"]) == 3

@pytest.mark.asyncio
async def test_get_nonexistent_chat_detail(chat_repo):
    """Test retrieving detail for nonexistent chat"""
    detail = await chat_repo.get_chat_detail(uuid4(), uuid4())
    assert detail is None

@pytest.mark.asyncio
async def test_get_chat_detail_includes_customer_meta_data(chat_repo, db, test_data):
    """meta_data set on the customer (e.g. via /generate-token custom_data) is
    surfaced in the chat detail response so the inbox can display it."""
    test_data["customer"].meta_data = {
        "student_name": "Aarav Krishnan",
        "center_name": "Special Academy U12"
    }
    db.commit()

    detail = await chat_repo.get_chat_detail(
        test_data["session_id"],
        test_data["org_id"]
    )

    assert detail["customer"]["meta_data"] == {
        "student_name": "Aarav Krishnan",
        "center_name": "Special Academy U12"
    } 

@pytest.mark.asyncio
async def test_get_chat_detail_exposes_channel_delivery_fields(chat_repo, db, test_data):
    """The inbox matches receipts by id, shows ticks, and reads the sent
    choices decrypted — and the response schema must not strip any of it."""

    sent = chat_repo.create_message({
        "message": "Confirm?", "message_type": "bot",
        "session_id": test_data["session_id"], "organization_id": test_data["org_id"],
        "external_message_id": "wamid.X",
        "attributes": {SENT_CHOICES_ATTRIBUTE: encode_sent_choices(
            from_options("Confirm?", ["Yes", "No"]), as_text=False)},
    })
    sent.channel_status = "read"
    db.commit()

    detail = await chat_repo.get_chat_detail(test_data["session_id"], test_data["org_id"])
    message = ChatDetailResponse(**detail).model_dump()["messages"][-1]

    assert message["id"] == sent.id
    assert message["external_message_id"] == "wamid.X"
    assert message["channel_status"] == "read"
    assert [c["text"] for c in message["attributes"][SENT_CHOICES_ATTRIBUTE]["choices"]] == ["Yes", "No"]
    # still encrypted at rest
    db.refresh(sent)
    assert "Yes" not in str(sent.attributes)



def test_app_sent_messages_cost_no_ai_quota(chat_repo, test_data):
    common = {"session_id": test_data["session_id"], "organization_id": test_data["org_id"],
              "message_type": "bot"}
    before = chat_repo.get_message_count_for_period(test_data["org_id"], None, None)
    chat_repo.create_message({**common, "message": "AI answer", "attributes": {"source": "ai"}})
    chat_repo.create_message({**common, "message": "Old reply"})
    chat_repo.create_message({**common, "message": "Fee reminder", "attributes": {"source": "app"}})

    assert chat_repo.get_message_count_for_period(test_data["org_id"], None, None) == before + 2

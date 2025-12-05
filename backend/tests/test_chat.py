"""
Tests for chat/tutor API endpoints.
Tests conversation management, message sending, and LLM tutor interaction.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import select
from src.models.user import User, UserRole, SkillLevel
from src.models.conversation import Conversation, Message, MessageRole
from src.models.user_memory import UserMemory
from src.services.llm.base_provider import Message as LLMMessage, LLMResponse
from datetime import datetime


@pytest.fixture
async def authenticated_user(db_session):
    """
    Create an authenticated test user with profile data.
    """
    user = User(
        email="tutor_test@example.com",
        password_hash="hashed_password",
        name="Tutor Test User",
        role=UserRole.STUDENT,
        email_verified=True,
        is_active=True,
        onboarding_completed=True,
        programming_language="python",
        skill_level=SkillLevel.INTERMEDIATE,
        career_goals="Backend developer",
        learning_style="hands-on",
        time_commitment="1-2 hours/day"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    # Create user memory
    memory = UserMemory(
        user_id=user.id,
        learning_pace="moderate",
        identified_strengths={"topics": ["arrays", "functions"]},
        identified_weaknesses={"topics": ["recursion"]},
        topic_mastery={"arrays": 0.85, "functions": 0.75, "recursion": 0.35},
        total_exercises_completed=10
    )
    db_session.add(memory)
    await db_session.flush()

    return user


@pytest.fixture
def mock_llm_service():
    """
    Mock LLM service for testing.
    """
    from unittest.mock import AsyncMock, patch, MagicMock

    mock_service = AsyncMock()
    mock_response = LLMResponse(
        content="Great question! Let me help you understand recursion. What do you already know about it?",
        model="llama-3.1-8b-instant",
        provider="groq",
        tokens_used=150,
        prompt_tokens=100,
        completion_tokens=50,
        finish_reason="stop",
        response_time_ms=500,
        timestamp=datetime.utcnow(),
        cached=False,
        cost_usd=0.0001
    )
    mock_service.generate_completion = AsyncMock(return_value=mock_response)

    # Mock the llm_manager access pattern
    mock_manager = MagicMock()
    mock_manager.llm_service = mock_service

    with patch('src.api.chat.llm_manager', mock_manager):
        yield mock_service


@pytest.fixture
async def mock_jwt_auth(authenticated_user, app):
    """
    Mock JWT authentication by patching AuthService methods and setting user context.
    """
    from unittest.mock import patch, AsyncMock

    # Mock the auth service methods that require_auth decorator uses
    async def mock_validate_session(token):
        return True

    mock_payload = {
        "user_id": authenticated_user.id,
        "email": authenticated_user.email,
        "role": authenticated_user.role.value,
        "jti": "test-jti"
    }

    with patch('src.services.auth_service.AuthService.verify_jwt_token', return_value=mock_payload):
        with patch('src.services.auth_service.AuthService.validate_session', new_callable=AsyncMock, side_effect=mock_validate_session):
            yield


@pytest.mark.asyncio
async def test_send_message_creates_new_conversation(
    client,
    authenticated_user,
    mock_llm_service,
    mock_jwt_auth,
    patched_get_session
):
    """
    Test POST /api/v1/chat/message creates new conversation and returns correct response.
    """
    message_data = {
        "message": "How do I implement recursion in Python?"
    }

    response = await client.post(
        "/api/v1/chat/message",
        json=message_data,
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 200

    data = await response.get_json()
    assert "conversation_id" in data
    assert "response" in data
    assert "message_id" in data
    assert "tokens_used" in data
    assert "model" in data

    # Verify LLM response is returned
    assert data["response"] == "Great question! Let me help you understand recursion. What do you already know about it?"
    assert data["tokens_used"] == 150
    assert data["model"] == "llama-3.1-8b-instant"

    # Verify conversation ID is valid (positive integer)
    assert isinstance(data["conversation_id"], int)
    assert data["conversation_id"] > 0


@pytest.mark.asyncio
async def test_send_message_to_existing_conversation(
    client,
    db_session,
    authenticated_user,
    mock_llm_service,
    mock_jwt_auth,
    patched_get_session
):
    """
    Test POST /api/v1/chat/message adds to existing conversation.
    """
    # Create existing conversation
    conversation = Conversation(
        user_id=authenticated_user.id,
        title="Recursion Discussion",
        message_count=2
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)

    # Add previous messages
    previous_messages = [
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="What is recursion?"
        ),
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Recursion is when a function calls itself."
        )
    ]
    for msg in previous_messages:
        db_session.add(msg)
    await db_session.flush()

    conversation_id = conversation.id

    # Send new message to existing conversation
    message_data = {
        "message": "Can you show me an example?",
        "conversation_id": conversation_id
    }

    response = await client.post(
        "/api/v1/chat/message",
        json=message_data,
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 200

    data = await response.get_json()
    assert data["conversation_id"] == conversation_id
    assert "response" in data
    assert "message_id" in data

    # Verify LLM service was called with conversation history
    mock_llm_service.generate_completion.assert_called_once()
    call_args = mock_llm_service.generate_completion.call_args
    messages = call_args.kwargs.get('messages')

    # Should include previous messages + new user message
    assert len(messages) >= 3  # 2 previous + 1 new


@pytest.mark.asyncio
async def test_send_message_injects_user_context(
    client,
    db_session,
    authenticated_user,
    mock_llm_service,
    mock_jwt_auth,
    patched_get_session
):
    """
    RED: Test that user context (profile, memory) is injected into LLM prompts.
    This test SHOULD FAIL initially.
    """
    message_data = {
        "message": "Help me with arrays"
    }

    response = await client.post(
        "/api/v1/chat/message",
        json=message_data,
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 200

    # Verify LLM service was called with personalized context
    mock_llm_service.generate_completion.assert_called_once()
    call_args = mock_llm_service.generate_completion.call_args

    # Check that system prompt includes user context
    system_prompt = call_args.kwargs.get('system_prompt')
    assert system_prompt is not None
    # System prompt should mention skill level
    assert 'intermediate' in system_prompt.lower() or 'INTERMEDIATE' in system_prompt

    # Messages should include conversation history
    messages = call_args.kwargs.get('messages')
    assert len(messages) > 0
    assert messages[-1].content == "Help me with arrays"


@pytest.mark.asyncio
async def test_send_message_unauthorized(client):
    """
    Test POST /api/v1/chat/message without auth returns 401.
    """
    message_data = {
        "message": "Help me with Python"
    }

    response = await client.post("/api/v1/chat/message", json=message_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_send_message_missing_message_field(client, mock_jwt_auth):
    """
    Test POST /api/v1/chat/message without message field returns 400.
    """
    response = await client.post(
        "/api/v1/chat/message",
        json={},
        headers={"Authorization": "Bearer fake_token"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_conversations_list(
    client,
    db_session,
    authenticated_user,
    mock_jwt_auth,
    patched_get_session
):
    """
    RED: Test GET /api/v1/chat/conversations returns user's conversations.
    This test SHOULD FAIL initially.
    """
    # Create some conversations
    conversations = [
        Conversation(
            user_id=authenticated_user.id,
            title="Python Basics",
            message_count=5,
            context_type="general"
        ),
        Conversation(
            user_id=authenticated_user.id,
            title="Recursion Help",
            message_count=3,
            context_type="general"
        ),
    ]
    for conv in conversations:
        db_session.add(conv)
    await db_session.flush()

    # Add a message to first conversation to set updated_at
    msg = Message(
        conversation_id=conversations[0].id,
        role=MessageRole.USER,
        content="Hello"
    )
    db_session.add(msg)
    await db_session.flush()

    response = await client.get(
        "/api/v1/chat/conversations",
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 200

    data = await response.get_json()
    assert "conversations" in data
    assert len(data["conversations"]) == 2

    # Conversations should be ordered by updated_at desc (most recent first)
    conv_data = data["conversations"][0]
    assert "id" in conv_data
    assert "title" in conv_data
    assert "message_count" in conv_data
    assert "last_message_at" in conv_data


@pytest.mark.asyncio
async def test_get_conversation_history(
    client,
    db_session,
    authenticated_user,
    mock_jwt_auth,
    patched_get_session
):
    """
    RED: Test GET /api/v1/chat/conversations/<id> returns conversation messages.
    This test SHOULD FAIL initially.
    """
    # Create conversation with messages
    conversation = Conversation(
        user_id=authenticated_user.id,
        title="Test Conversation",
        message_count=3
    )
    db_session.add(conversation)
    await db_session.flush()
    await db_session.refresh(conversation)

    messages = [
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="What is Python?"
        ),
        Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Python is a programming language."
        ),
        Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Tell me more"
        ),
    ]
    for msg in messages:
        db_session.add(msg)
    await db_session.flush()

    response = await client.get(
        f"/api/v1/chat/conversations/{conversation.id}",
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 200

    data = await response.get_json()
    assert "conversation" in data
    assert data["conversation"]["id"] == conversation.id
    assert "messages" in data
    assert len(data["messages"]) == 3
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "What is Python?"
    assert data["messages"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_get_conversation_not_found(
    client,
    authenticated_user,
    mock_jwt_auth,
    patched_get_session
):
    """
    Test GET /api/v1/chat/conversations/<id> with non-existent ID returns 404.
    """
    response = await client.get(
        "/api/v1/chat/conversations/99999",
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_conversation_unauthorized_access(
    client,
    db_session,
    authenticated_user,
    mock_jwt_auth,
    patched_get_session
):
    """
    Test user cannot access another user's conversation.
    """
    # Create another user and their conversation
    other_user = User(
        email="other@example.com",
        password_hash="hashed",
        name="Other User",
        role=UserRole.STUDENT,
        email_verified=True,
        is_active=True
    )
    db_session.add(other_user)
    await db_session.flush()
    await db_session.refresh(other_user)

    other_conversation = Conversation(
        user_id=other_user.id,
        title="Private Conversation",
        message_count=1
    )
    db_session.add(other_conversation)
    await db_session.flush()
    await db_session.refresh(other_conversation)

    # Try to access other user's conversation
    response = await client.get(
        f"/api/v1/chat/conversations/{other_conversation.id}",
        headers={"Authorization": "Bearer fake_token"}
    )

    assert response.status_code == 403

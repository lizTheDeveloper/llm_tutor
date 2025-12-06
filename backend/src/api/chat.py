"""
Chat/Tutor API endpoints.
Handles conversations with the LLM tutor.
"""
from quart import Blueprint, request, jsonify
from typing import Dict, Any, Optional
from sqlalchemy import select, desc
from datetime import datetime
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.middleware.auth_middleware import require_auth, require_verified_email, get_current_user_id
from src.middleware.rate_limiter import llm_rate_limit
from src.models.conversation import Conversation, Message, MessageRole
from src.models.user import User
from src.models.user_memory import UserMemory
from src.services.llm.base_provider import Message as LLMMessage
from src.services.llm.prompt_templates import PromptTemplateManager, PromptType
from src.utils.database import get_async_db_session as get_session
from src.schemas.chat import SendMessageRequest
from pydantic import ValidationError

logger = get_logger(__name__)
chat_bp = Blueprint("chat", __name__)

# Global LLM manager (will be initialized in app factory)
llm_manager = None


@chat_bp.route("/message", methods=["POST"])
@require_auth
@require_verified_email
@llm_rate_limit("chat")
async def send_message() -> Dict[str, Any]:
    """
    Send a message to the LLM tutor.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "message": "How do I implement a binary search?",
            "conversation_id": "optional_conversation_id"
        }

    Returns:
        JSON response with tutor's reply
    """
    try:
        # Get current user
        user_id = get_current_user_id()

        # Get request data and validate (SEC-3-INPUT)
        data = await request.get_json()

        try:
            validated_data = SendMessageRequest(**data)
        except ValidationError as validation_error:
            errors = validation_error.errors()
            error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
            raise APIError(
                f"Validation error: {'; '.join(error_messages)}",
                status_code=400,
            )

        user_message = validated_data.message  # Already sanitized by schema
        conversation_id = validated_data.conversation_id

        async with get_session() as session:
            # Load user profile
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user:
                raise APIError("User not found", status_code=404)

            # Load user memory for personalization
            memory_result = await session.execute(
                select(UserMemory).where(UserMemory.user_id == user_id)
            )
            user_memory = memory_result.scalar_one_or_none()

            # Get or create conversation
            conversation = None
            conversation_history = []

            if conversation_id:
                # Load existing conversation
                conv_result = await session.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.user_id == user_id
                    )
                )
                conversation = conv_result.scalar_one_or_none()

                if not conversation:
                    raise APIError("Conversation not found or access denied", status_code=404)

                # Load conversation history
                history_result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                )
                messages = history_result.scalars().all()
                conversation_history = [
                    LLMMessage(role=msg.role.value, content=msg.content)
                    for msg in messages
                ]
            else:
                # Create new conversation
                conversation = Conversation(
                    user_id=user_id,
                    title="Chat Session",
                    message_count=0,
                    context_type="general"
                )
                session.add(conversation)
                await session.flush()
                await session.refresh(conversation)

            # Build personalized system prompt
            skill_level = user.skill_level.value if user.skill_level else "intermediate"
            language = user.programming_language or "Python"
            career_goal = user.career_goals or "software development"

            system_prompt = PromptTemplateManager.get_system_prompt(
                PromptType.TUTOR_GREETING
            )
            system_prompt += f"\n\nStudent Context:\n- Skill Level: {skill_level}\n- Programming Language: {language}\n- Career Goal: {career_goal}"

            if user_memory:
                if user_memory.identified_strengths:
                    strengths = user_memory.identified_strengths.get("topics", [])
                    if strengths:
                        system_prompt += f"\n- Strengths: {', '.join(strengths)}"
                if user_memory.identified_weaknesses:
                    weaknesses = user_memory.identified_weaknesses.get("topics", [])
                    if weaknesses:
                        system_prompt += f"\n- Areas for improvement: {', '.join(weaknesses)}"

            # Add user message to history
            conversation_history.append(
                LLMMessage(role="user", content=user_message)
            )

            # Call LLM service
            if not llm_manager or not llm_manager.llm_service:
                raise APIError("LLM service not available", status_code=503)

            llm_response = await llm_manager.llm_service.generate_completion(
                messages=conversation_history,
                user_id=str(user_id),
                system_prompt=system_prompt,
                use_cache=True,
                trim_context=True
            )

            # Store user message
            user_msg = Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=user_message
            )
            session.add(user_msg)
            await session.flush()
            await session.refresh(user_msg)

            # Store assistant response
            assistant_msg = Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=llm_response.content,
                tokens_used=llm_response.tokens_used,
                model_used=llm_response.model,
                message_metadata={
                    "provider": llm_response.provider,
                    "finish_reason": llm_response.finish_reason,
                    "cached": llm_response.cached,
                    "response_time_ms": llm_response.response_time_ms
                }
            )
            session.add(assistant_msg)
            await session.flush()
            await session.refresh(assistant_msg)

            # Update conversation message count
            conversation.message_count += 2
            await session.flush()
            await session.commit()

            logger.info(
                "Chat message processed",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation.id,
                    "message_id": assistant_msg.id,
                    "tokens_used": llm_response.tokens_used
                }
            )

            return jsonify({
                "conversation_id": conversation.id,
                "message_id": assistant_msg.id,
                "response": llm_response.content,
                "model": llm_response.model,
                "tokens_used": llm_response.tokens_used
            }), 200

    except APIError:
        raise
    except Exception as error:
        logger.error(
            "Error processing chat message",
            exc_info=True,
            extra={"error": str(error)}
        )
        raise APIError("Failed to process message", status_code=500)


@chat_bp.route("/conversations", methods=["GET"])
@require_auth
@require_verified_email
async def get_conversations() -> Dict[str, Any]:
    """
    Get list of user's conversations.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        limit: Number of conversations (default: 20)
        offset: Pagination offset (default: 0)

    Returns:
        JSON response with conversation list
    """
    try:
        # Get current user
        user_id = get_current_user_id()

        # Get pagination parameters
        limit = request.args.get("limit", default=20, type=int)
        offset = request.args.get("offset", default=0, type=int)

        async with get_session() as session:
            # Fetch user's conversations
            result = await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(desc(Conversation.updated_at))
                .limit(limit)
                .offset(offset)
            )
            conversations = result.scalars().all()

            # Build response
            conversation_list = []
            for conv in conversations:
                # Get last message timestamp
                last_msg_result = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(desc(Message.created_at))
                    .limit(1)
                )
                last_msg = last_msg_result.scalar_one_or_none()

                conversation_list.append({
                    "id": conv.id,
                    "title": conv.title,
                    "message_count": conv.message_count,
                    "context_type": conv.context_type,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "last_message_at": last_msg.created_at.isoformat() if last_msg else conv.updated_at.isoformat()
                })

            logger.info(
                "Conversations retrieved",
                extra={
                    "user_id": user_id,
                    "count": len(conversation_list),
                    "limit": limit,
                    "offset": offset
                }
            )

            return jsonify({
                "conversations": conversation_list,
                "total": len(conversation_list),
                "limit": limit,
                "offset": offset
            }), 200

    except APIError:
        raise
    except Exception as error:
        logger.error(
            "Error retrieving conversations",
            exc_info=True,
            extra={"error": str(error)}
        )
        raise APIError("Failed to retrieve conversations", status_code=500)


@chat_bp.route("/conversations/<int:conversation_id>", methods=["GET"])
@require_auth
@require_verified_email
async def get_conversation(conversation_id: int) -> Dict[str, Any]:
    """
    Get specific conversation history.

    Args:
        conversation_id: Conversation identifier

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with conversation messages
    """
    try:
        # Get current user
        user_id = get_current_user_id()

        async with get_session() as session:
            # Fetch conversation and verify ownership
            conv_result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()

            if not conversation:
                raise APIError("Conversation not found", status_code=404)

            if conversation.user_id != user_id:
                raise APIError("Access denied", status_code=403)

            # Fetch all messages in conversation
            messages_result = await session.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )
            messages = messages_result.scalars().all()

            # Build response
            message_list = [
                {
                    "id": msg.id,
                    "role": msg.role.value,
                    "content": msg.content,
                    "tokens_used": msg.tokens_used,
                    "model_used": msg.model_used,
                    "created_at": msg.created_at.isoformat(),
                    "metadata": msg.message_metadata
                }
                for msg in messages
            ]

            logger.info(
                "Conversation retrieved",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "message_count": len(message_list)
                }
            )

            return jsonify({
                "conversation": {
                    "id": conversation.id,
                    "title": conversation.title,
                    "message_count": conversation.message_count,
                    "context_type": conversation.context_type,
                    "created_at": conversation.created_at.isoformat(),
                    "updated_at": conversation.updated_at.isoformat()
                },
                "messages": message_list
            }), 200

    except APIError:
        raise
    except Exception as error:
        logger.error(
            "Error retrieving conversation",
            exc_info=True,
            extra={"error": str(error), "conversation_id": conversation_id}
        )
        raise APIError("Failed to retrieve conversation", status_code=500)


@chat_bp.route("/conversations/<int:conversation_id>", methods=["DELETE"])
@require_auth
@require_verified_email
async def delete_conversation(conversation_id: int) -> Dict[str, Any]:
    """
    Delete a conversation.

    Args:
        conversation_id: Conversation identifier

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response confirming deletion
    """
    try:
        # Get current user
        user_id = get_current_user_id()

        async with get_session() as session:
            # Fetch conversation and verify ownership
            conv_result = await session.execute(
                select(Conversation).where(Conversation.id == conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()

            if not conversation:
                raise APIError("Conversation not found", status_code=404)

            if conversation.user_id != user_id:
                raise APIError("Access denied", status_code=403)

            # Delete conversation (cascade will delete messages)
            await session.delete(conversation)
            await session.commit()

            logger.info(
                "Conversation deleted",
                extra={
                    "user_id": user_id,
                    "conversation_id": conversation_id
                }
            )

            return jsonify({
                "message": "Conversation deleted successfully",
                "conversation_id": conversation_id
            }), 200

    except APIError:
        raise
    except Exception as error:
        logger.error(
            "Error deleting conversation",
            exc_info=True,
            extra={"error": str(error), "conversation_id": conversation_id}
        )
        raise APIError("Failed to delete conversation", status_code=500)


@chat_bp.route("/stream", methods=["POST"])
@require_auth
@require_verified_email
@llm_rate_limit("chat")
async def stream_message() -> Any:
    """
    Send a message and stream the response.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "message": "Explain recursion",
            "conversation_id": "optional_conversation_id"
        }

    Returns:
        Server-Sent Events stream of response tokens
    """
    # TODO: Set up SSE streaming
    # TODO: Call LLM with streaming enabled
    # TODO: Stream response tokens to client
    # TODO: Store complete response when done

    raise APIError("Stream message not yet implemented", status_code=501)

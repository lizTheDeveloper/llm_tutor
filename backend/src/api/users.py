"""
User management API endpoints.
Handles user profiles, preferences, and progress tracking.
"""
from quart import Blueprint, request, jsonify
from typing import Dict, Any
from pydantic import ValidationError
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.middleware.auth_middleware import require_auth, require_verified_email, get_current_user_id
from src.services.profile_service import ProfileService
from src.schemas.profile import (
    OnboardingRequest,
    OnboardingResponse,
    ProfileUpdateRequest,
    UserProfileResponse,
    UserProgressResponse,
    OnboardingQuestionsResponse
)
from src.utils.database import get_async_db_session as get_session
from quart import g

logger = get_logger(__name__)
users_bp = Blueprint("users", __name__)


@users_bp.route("/me", methods=["GET"])
@require_auth
async def get_current_user() -> Dict[str, Any]:
    """
    Get current authenticated user's profile.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with user profile data
    """
    user_id = get_current_user_id()

    async with get_session() as session:
        user = await ProfileService.get_user_profile(session, user_id)

        # Convert to response schema
        profile = UserProfileResponse.model_validate(user)

        logger.info(
            "User profile retrieved",
            extra={"user_id": user_id}
        )

        return jsonify(profile.model_dump(mode='json')), 200


@users_bp.route("/me", methods=["PUT"])
@require_auth
@require_verified_email
async def update_current_user() -> Dict[str, Any]:
    """
    Update current user's profile.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "name": "Updated Name",
            "programming_language": "python",
            "skill_level": "intermediate",
            "career_goals": "Backend developer"
        }

    Returns:
        JSON response with updated user profile
    """
    user_id = get_current_user_id()
    data = await request.get_json()

    try:
        # Validate update data
        update_data = ProfileUpdateRequest.model_validate(data)

        async with get_session() as session:
            # Update user profile
            user = await ProfileService.update_user_profile(
                session,
                user_id,
                update_data
            )
            await session.commit()

            # Convert to response schema
            profile = UserProfileResponse.model_validate(user)

            logger.info(
                "User profile updated",
                extra={"user_id": user_id}
            )

            return jsonify({
                "message": "Profile updated successfully",
                "profile": profile.model_dump(mode='json')
            }), 200

    except ValidationError as validation_error:
        logger.warning(
            "Invalid profile update data",
            extra={"user_id": user_id, "errors": validation_error.errors()}
        )
        raise APIError(
            f"Validation error: {validation_error}",
            status_code=400
        )


@users_bp.route("/me/profile", methods=["GET"])
@require_auth
async def get_user_profile() -> Dict[str, Any]:
    """
    Get detailed user profile with learning history.
    (Alias for GET /me)

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with detailed profile
    """
    return await get_current_user()


@users_bp.route("/me/progress", methods=["GET"])
@require_auth
async def get_user_progress() -> Dict[str, Any]:
    """
    Get user's learning progress and statistics.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with progress data
    """
    user_id = get_current_user_id()

    async with get_session() as session:
        progress_data = await ProfileService.get_user_progress(session, user_id)

        # Convert to response schema
        progress = UserProgressResponse.model_validate(progress_data)

        logger.info(
            "User progress retrieved",
            extra={"user_id": user_id}
        )

        return jsonify(progress.model_dump(mode='json')), 200


@users_bp.route("/onboarding/questions", methods=["GET"])
@require_auth
async def get_onboarding_questions() -> Dict[str, Any]:
    """
    Get onboarding interview questions.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with onboarding questions
    """
    user_id = get_current_user_id()

    # Get questions
    questions_data = ProfileService.get_onboarding_questions()

    # Convert to response schema
    response = OnboardingQuestionsResponse.model_validate(questions_data)

    logger.info(
        "Onboarding questions retrieved",
        extra={"user_id": user_id}
    )

    return jsonify(response.model_dump(mode='json')), 200


@users_bp.route("/onboarding/status", methods=["GET"])
@require_auth
async def get_onboarding_status() -> Dict[str, Any]:
    """
    Check user's onboarding status.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with onboarding status
    """
    user_id = get_current_user_id()

    async with get_session() as session:
        status = await ProfileService.check_onboarding_status(session, user_id)

        logger.info(
            "Onboarding status checked",
            extra={"user_id": user_id, "completed": status["onboarding_completed"]}
        )

        return jsonify(status), 200


@users_bp.route("/onboarding", methods=["POST"])
@require_auth
@require_verified_email
async def complete_onboarding() -> Dict[str, Any]:
    """
    Complete user onboarding interview.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "programming_language": "python",
            "skill_level": "beginner",
            "career_goals": "Become a full-stack developer",
            "learning_style": "hands-on",
            "time_commitment": "1-2 hours/day"
        }

    Returns:
        JSON response with updated user profile
    """
    user_id = get_current_user_id()
    data = await request.get_json()

    try:
        # Validate onboarding data
        onboarding_data = OnboardingRequest.model_validate(data)

        async with get_session() as session:
            # Complete onboarding
            user = await ProfileService.complete_onboarding(
                session,
                user_id,
                onboarding_data
            )
            await session.commit()

            # Create response
            response = OnboardingResponse(
                user_id=user.id,
                email=user.email,
                name=user.name,
                programming_language=user.programming_language,
                skill_level=user.skill_level,
                career_goals=user.career_goals,
                learning_style=user.learning_style,
                time_commitment=user.time_commitment,
                onboarding_completed=user.onboarding_completed,
                message="Onboarding completed successfully! You're ready to start learning."
            )

            logger.info(
                "User onboarding completed",
                extra={"user_id": user_id}
            )

            return jsonify(response.model_dump(mode='json')), 200

    except ValidationError as validation_error:
        logger.warning(
            "Invalid onboarding data",
            extra={"user_id": user_id, "errors": validation_error.errors()}
        )
        raise APIError(
            f"Validation error: {validation_error}",
            status_code=400
        )


@users_bp.route("/me/preferences", methods=["GET"])
@require_auth
async def get_user_preferences() -> Dict[str, Any]:
    """
    Get user preferences and settings.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with user preferences
    """
    user_id = get_current_user_id()

    async with get_session() as session:
        user = await ProfileService.get_user_profile(session, user_id)

        # Extract preferences
        preferences = {
            "programming_language": user.programming_language,
            "skill_level": user.skill_level.value if user.skill_level else None,
            "career_goals": user.career_goals,
            "learning_style": user.learning_style,
            "time_commitment": user.time_commitment,
        }

        logger.info(
            "User preferences retrieved",
            extra={"user_id": user_id}
        )

        return jsonify(preferences), 200


@users_bp.route("/me/preferences", methods=["PUT"])
@require_auth
@require_verified_email
async def update_user_preferences() -> Dict[str, Any]:
    """
    Update user preferences and settings.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "programming_language": "python",
            "skill_level": "intermediate",
            "learning_style": "hands-on"
        }

    Returns:
        JSON response with updated preferences
    """
    user_id = get_current_user_id()
    data = await request.get_json()

    try:
        # Validate using ProfileUpdateRequest schema
        update_data = ProfileUpdateRequest.model_validate(data)

        async with get_session() as session:
            # Update user profile
            user = await ProfileService.update_user_profile(
                session,
                user_id,
                update_data
            )
            await session.commit()

            # Extract updated preferences
            preferences = {
                "programming_language": user.programming_language,
                "skill_level": user.skill_level.value if user.skill_level else None,
                "career_goals": user.career_goals,
                "learning_style": user.learning_style,
                "time_commitment": user.time_commitment,
            }

            logger.info(
                "User preferences updated",
                extra={"user_id": user_id}
            )

            return jsonify({
                "message": "Preferences updated successfully",
                "preferences": preferences
            }), 200

    except ValidationError as validation_error:
        logger.warning(
            "Invalid preferences data",
            extra={"user_id": user_id, "errors": validation_error.errors()}
        )
        raise APIError(
            f"Validation error: {validation_error}",
            status_code=400
        )


@users_bp.route("/me/achievements", methods=["GET"])
@require_auth
async def get_user_achievements() -> Dict[str, Any]:
    """
    Get user's achievement badges.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with achievements
    """
    # TODO: Implement achievements system in future workstream
    # For now, return empty achievements
    user_id = get_current_user_id()

    logger.info(
        "User achievements retrieved (placeholder)",
        extra={"user_id": user_id}
    )

    return jsonify({
        "achievements": [],
        "total_earned": 0,
        "total_available": 0,
        "message": "Achievements system coming soon!"
    }), 200

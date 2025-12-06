"""
Exercise management API endpoints.
Handles daily exercises, submissions, and progress tracking.
"""
from quart import Blueprint, request, jsonify
from typing import Dict, Any
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.middleware.auth_middleware import require_auth, get_current_user_id
from src.services.exercise_service import ExerciseService
from src.schemas.exercise import (
    ExerciseSubmissionRequest,
    HintRequest,
    ExerciseGenerateRequest
)
from src.utils.database import get_async_db_session as get_session

logger = get_logger(__name__)
exercises_bp = Blueprint("exercises", __name__)


@exercises_bp.route("/daily", methods=["GET"])
@require_auth
async def get_daily_exercise() -> Dict[str, Any]:
    """
    Get current day's exercise for authenticated user.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with daily exercise
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ExerciseService(session)
            exercise, user_exercise, is_new = await service.get_or_generate_daily_exercise(user_id)

            # Serialize exercise (exclude solution)
            exercise_data = {
                "id": exercise.id,
                "title": exercise.title,
                "description": exercise.description,
                "instructions": exercise.instructions,
                "starter_code": exercise.starter_code,
                "exercise_type": exercise.exercise_type.value,
                "difficulty": exercise.difficulty.value,
                "programming_language": exercise.programming_language,
                "topics": exercise.topics,
                "test_cases": exercise.test_cases,
                "generated_by_ai": exercise.generated_by_ai,
            }

            return jsonify({
                "exercise": exercise_data,
                "user_exercise_id": user_exercise.id,
                "status": user_exercise.status.value,
                "hints_used": user_exercise.hints_requested,
                "is_new": is_new,
            }), 200

    except Exception as error:
        logger.error("Error getting daily exercise", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get daily exercise: {str(error)}", status_code=500)


@exercises_bp.route("/<int:exercise_id>", methods=["GET"])
@require_auth
async def get_exercise(exercise_id: int) -> Dict[str, Any]:
    """
    Get specific exercise by ID.

    Args:
        exercise_id: Exercise identifier

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with exercise details
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ExerciseService(session)
            exercise = await service.get_exercise_by_id(exercise_id)

            # Serialize exercise (exclude solution)
            return jsonify({
                "id": exercise.id,
                "title": exercise.title,
                "description": exercise.description,
                "instructions": exercise.instructions,
                "starter_code": exercise.starter_code,
                "exercise_type": exercise.exercise_type.value,
                "difficulty": exercise.difficulty.value,
                "programming_language": exercise.programming_language,
                "topics": exercise.topics,
                "test_cases": exercise.test_cases,
                "generated_by_ai": exercise.generated_by_ai,
            }), 200

    except ValueError as error:
        raise APIError(str(error), status_code=404)
    except Exception as error:
        logger.error("Error getting exercise", extra={"error": str(error), "exercise_id": exercise_id})
        raise APIError(f"Failed to get exercise: {str(error)}", status_code=500)


@exercises_bp.route("/<int:exercise_id>/submit", methods=["POST"])
@require_auth
async def submit_exercise(exercise_id: int) -> Dict[str, Any]:
    """
    Submit solution for an exercise.

    Args:
        exercise_id: Exercise identifier

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "solution": "code solution here",
            "time_spent": 300
        }

    Returns:
        JSON response with feedback and evaluation
    """
    try:
        user_id = get_current_user_id()

        # Get request data
        data = await request.get_json()
        if not data or "solution" not in data:
            raise APIError("Solution field is required", status_code=400)

        solution = data.get("solution")
        time_spent = data.get("time_spent")

        async with get_session() as session:
            service = ExerciseService(session)
            result = await service.submit_exercise(
                user_id=user_id,
                exercise_id=exercise_id,
                solution=solution,
                time_spent=time_spent
            )

            return jsonify(result), 200

    except ValueError as error:
        raise APIError(str(error), status_code=404)
    except Exception as error:
        logger.error("Error submitting exercise", extra={
            "error": str(error),
            "user_id": user_id,
            "exercise_id": exercise_id
        })
        raise APIError(f"Failed to submit exercise: {str(error)}", status_code=500)


@exercises_bp.route("/<int:exercise_id>/hint", methods=["POST"])
@require_auth
async def request_hint(exercise_id: int) -> Dict[str, Any]:
    """
    Request a hint for an exercise.

    Args:
        exercise_id: Exercise identifier

    Headers:
        Authorization: Bearer <access_token>

    Request Body (optional):
        {
            "context": "User's question or context",
            "current_code": "User's current code"
        }

    Returns:
        JSON response with hint
    """
    try:
        user_id = get_current_user_id()

        # Get request data (optional)
        data = await request.get_json() if request.content_length else {}
        context = data.get("context") if data else None
        current_code = data.get("current_code") if data else None

        async with get_session() as session:
            service = ExerciseService(session)
            result = await service.request_hint(
                user_id=user_id,
                exercise_id=exercise_id,
                context=context,
                current_code=current_code
            )

            return jsonify(result), 200

    except ValueError as error:
        raise APIError(str(error), status_code=404)
    except Exception as error:
        logger.error("Error requesting hint", extra={
            "error": str(error),
            "user_id": user_id,
            "exercise_id": exercise_id
        })
        raise APIError(f"Failed to generate hint: {str(error)}", status_code=500)


@exercises_bp.route("/<int:exercise_id>/complete", methods=["POST"])
@require_auth
async def mark_complete(exercise_id: int) -> Dict[str, Any]:
    """
    Mark exercise as complete.

    Args:
        exercise_id: Exercise identifier

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response confirming completion
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ExerciseService(session)
            result = await service.mark_complete(
                user_id=user_id,
                exercise_id=exercise_id
            )

            return jsonify(result), 200

    except ValueError as error:
        raise APIError(str(error), status_code=404)
    except Exception as error:
        logger.error("Error marking exercise complete", extra={
            "error": str(error),
            "user_id": user_id,
            "exercise_id": exercise_id
        })
        raise APIError(f"Failed to mark exercise complete: {str(error)}", status_code=500)


@exercises_bp.route("/<int:exercise_id>/skip", methods=["POST"])
@require_auth
async def skip_exercise(exercise_id: int) -> Dict[str, Any]:
    """
    Skip current exercise.

    Args:
        exercise_id: Exercise identifier

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response confirming skip
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ExerciseService(session)

            # Get user exercise
            user_exercise = await service.get_user_exercise(user_id, exercise_id)
            if not user_exercise:
                raise ValueError(f"User exercise not found for exercise {exercise_id}")

            # Import ExerciseStatus
            from src.models.exercise import ExerciseStatus

            # Mark as skipped
            user_exercise.status = ExerciseStatus.SKIPPED
            await session.flush()

            return jsonify({
                "message": "Exercise skipped successfully",
                "exercise_id": exercise_id,
                "status": "skipped"
            }), 200

    except ValueError as error:
        raise APIError(str(error), status_code=404)
    except Exception as error:
        logger.error("Error skipping exercise", extra={
            "error": str(error),
            "user_id": user_id,
            "exercise_id": exercise_id
        })
        raise APIError(f"Failed to skip exercise: {str(error)}", status_code=500)


@exercises_bp.route("/history", methods=["GET"])
@require_auth
async def get_exercise_history() -> Dict[str, Any]:
    """
    Get user's exercise history.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        limit: Number of exercises to return (default: 20)
        offset: Pagination offset (default: 0)
        status: Filter by status (completed, skipped, pending)

    Returns:
        JSON response with exercise history
    """
    try:
        user_id = get_current_user_id()

        # Get query parameters
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        status = request.args.get("status")

        async with get_session() as session:
            service = ExerciseService(session)
            exercises, total = await service.list_user_exercises(
                user_id=user_id,
                limit=limit,
                offset=offset,
                status=status
            )

            return jsonify({
                "exercises": exercises,
                "total": total,
                "limit": limit,
                "offset": offset
            }), 200

    except Exception as error:
        logger.error("Error getting exercise history", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get exercise history: {str(error)}", status_code=500)


@exercises_bp.route("/generate", methods=["POST"])
@require_auth
async def generate_exercise() -> Dict[str, Any]:
    """
    Generate a new personalized exercise.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "topic": "algorithms",
            "difficulty": "intermediate",
            "exercise_type": "algorithm"
        }

    Returns:
        JSON response with generated exercise
    """
    try:
        user_id = get_current_user_id()

        # Get request data
        data = await request.get_json() if request.content_length else {}
        topic = data.get("topic") if data else None
        difficulty = data.get("difficulty") if data else None
        exercise_type_str = data.get("exercise_type") if data else None

        # Convert exercise_type string to enum
        exercise_type = None
        if exercise_type_str:
            from src.models.exercise import ExerciseType
            try:
                exercise_type = ExerciseType(exercise_type_str)
            except ValueError:
                raise APIError(f"Invalid exercise type: {exercise_type_str}", status_code=400)

        async with get_session() as session:
            service = ExerciseService(session)
            exercise, user_exercise = await service.generate_personalized_exercise(
                user_id=user_id,
                topic=topic,
                difficulty=difficulty,
                exercise_type=exercise_type
            )

            # Serialize exercise (exclude solution)
            exercise_data = {
                "id": exercise.id,
                "title": exercise.title,
                "description": exercise.description,
                "instructions": exercise.instructions,
                "starter_code": exercise.starter_code,
                "exercise_type": exercise.exercise_type.value,
                "difficulty": exercise.difficulty.value,
                "programming_language": exercise.programming_language,
                "topics": exercise.topics,
                "test_cases": exercise.test_cases,
                "generated_by_ai": exercise.generated_by_ai,
            }

            return jsonify({
                "exercise": exercise_data,
                "user_exercise_id": user_exercise.id,
                "status": user_exercise.status.value,
            }), 201

    except Exception as error:
        logger.error("Error generating exercise", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to generate exercise: {str(error)}", status_code=500)

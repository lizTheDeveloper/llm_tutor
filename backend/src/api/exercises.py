"""
Exercise management API endpoints.
Handles daily exercises, submissions, and progress tracking.
"""
from quart import Blueprint, request, jsonify
from typing import Dict, Any
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.middleware.auth_middleware import require_auth, require_verified_email, get_current_user_id
from src.middleware.rate_limiter import llm_rate_limit
from src.services.exercise_service import ExerciseService
from src.services.difficulty_service import DifficultyService
from src.schemas.exercise import (
    ExerciseSubmissionRequest,
    HintRequest,
    ExerciseGenerateRequest
)
from src.schemas.difficulty import (
    DifficultyAdjustmentRequest,
    PerformanceAnalysisRequest
)
from src.utils.database import get_async_db_session as get_session

logger = get_logger(__name__)
exercises_bp = Blueprint("exercises", __name__)


@exercises_bp.route("/daily", methods=["GET"])
@require_auth
@require_verified_email
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
@require_verified_email
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
@require_verified_email
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
@require_verified_email
@llm_rate_limit("hint")
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
@require_verified_email
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
@require_verified_email
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
@require_verified_email
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
@require_verified_email
@llm_rate_limit("exercise_generation")
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


# ===================================================================
# DIFFICULTY ADAPTATION ENDPOINTS (Work Stream D3)
# ===================================================================

@exercises_bp.route("/difficulty/analyze", methods=["GET"])
@require_auth
async def analyze_difficulty() -> Dict[str, Any]:
    """
    Analyze user's recent performance and get difficulty adjustment recommendation.

    Implements REQ-EXERCISE-003: Adaptive difficulty adjustment.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        limit: Number of recent exercises to analyze (default: 10)

    Returns:
        JSON response with difficulty adjustment recommendation
        {
            "user_id": 123,
            "should_adjust": true,
            "current_difficulty": "medium",
            "recommended_difficulty": "hard",
            "reason": "increase",
            "message": "Great job! You've successfully completed 3 exercises...",
            "consecutive_successes": 3,
            "consecutive_struggles": 0,
            "performance_metrics": {...}
        }
    """
    try:
        user_id = get_current_user_id()
        limit = int(request.args.get("limit", 10))

        async with get_session() as session:
            difficulty_service = DifficultyService(session)

            # Analyze performance and get recommendation
            result = await difficulty_service.analyze_and_adjust_difficulty(user_id)

            # Serialize response
            response = {
                "user_id": result.user_id,
                "should_adjust": result.should_adjust,
                "current_difficulty": result.current_difficulty.value if result.current_difficulty else None,
                "recommended_difficulty": result.recommended_difficulty.value if result.recommended_difficulty else None,
                "reason": result.reason,
                "message": result.message,
                "consecutive_successes": result.consecutive_successes,
                "consecutive_struggles": result.consecutive_struggles,
            }

            # Include performance metrics if requested
            if result.performance_metrics:
                response["performance_metrics"] = {
                    "total_exercises_analyzed": result.performance_metrics.total_exercises_analyzed,
                    "average_grade": result.performance_metrics.average_grade,
                    "average_hints": result.performance_metrics.average_hints,
                    "completion_rate": result.performance_metrics.completion_rate,
                }

            return jsonify(response), 200

    except Exception as error:
        logger.error("Error analyzing difficulty", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to analyze difficulty: {str(error)}", status_code=500)


@exercises_bp.route("/difficulty/adjust", methods=["POST"])
@require_auth
async def adjust_difficulty() -> Dict[str, Any]:
    """
    Apply a difficulty adjustment (manual or automatic).

    Allows users to manually override their difficulty level.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "difficulty": "hard",
            "reason": "I want more challenging exercises"
        }

    Returns:
        JSON response confirming adjustment
        {
            "message": "Difficulty adjusted successfully",
            "user_id": 123,
            "new_difficulty": "hard",
            "notification": {...}
        }
    """
    try:
        user_id = get_current_user_id()

        # Get request data
        data = await request.get_json()
        if not data or "difficulty" not in data:
            raise APIError("Difficulty field is required", status_code=400)

        difficulty_str = data.get("difficulty")
        reason = data.get("reason")

        # Convert difficulty string to enum
        from src.models.exercise import ExerciseDifficulty
        try:
            new_difficulty = ExerciseDifficulty(difficulty_str)
        except ValueError:
            raise APIError(
                f"Invalid difficulty: {difficulty_str}. Must be 'easy', 'medium', or 'hard'",
                status_code=400
            )

        async with get_session() as session:
            difficulty_service = DifficultyService(session)

            # Apply manual difficulty adjustment
            success = await difficulty_service.set_manual_difficulty(
                user_id=user_id,
                difficulty=new_difficulty,
                reason=reason
            )

            if not success:
                raise APIError("Failed to apply difficulty adjustment", status_code=500)

            # Create notification about the change
            # For manual changes, we need to get the previous difficulty
            metrics = await difficulty_service.get_recent_performance(user_id, limit=1)
            previous_difficulty = metrics.current_difficulty or ExerciseDifficulty.MEDIUM

            notification = await difficulty_service.create_difficulty_change_notification(
                user_id=user_id,
                previous_difficulty=previous_difficulty,
                new_difficulty=new_difficulty
            )

            return jsonify({
                "message": "Difficulty adjusted successfully",
                "user_id": user_id,
                "new_difficulty": new_difficulty.value,
                "notification": {
                    "message": notification.message,
                    "change_type": notification.change_type,
                    "reason": notification.reason,
                }
            }), 200

    except ValueError as error:
        raise APIError(str(error), status_code=400)
    except Exception as error:
        logger.error("Error adjusting difficulty", extra={
            "error": str(error),
            "user_id": user_id
        })
        raise APIError(f"Failed to adjust difficulty: {str(error)}", status_code=500)


@exercises_bp.route("/difficulty/performance", methods=["GET"])
@require_auth
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get detailed performance metrics for the authenticated user.

    Implements REQ-EXERCISE-004: Exercise completion metrics tracking.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        limit: Number of recent exercises to include (default: 10, max: 50)

    Returns:
        JSON response with detailed performance metrics
        {
            "user_id": 123,
            "total_exercises_analyzed": 10,
            "average_grade": 85.5,
            "average_hints": 1.2,
            "average_time_seconds": 720,
            "completion_rate": 90.0,
            "consecutive_successes": 3,
            "consecutive_struggles": 0,
            "current_difficulty": "medium",
            "recent_exercises": [...]
        }
    """
    try:
        user_id = get_current_user_id()
        limit = min(int(request.args.get("limit", 10)), 50)

        async with get_session() as session:
            difficulty_service = DifficultyService(session)

            # Get performance metrics
            metrics = await difficulty_service.get_recent_performance(user_id, limit=limit)

            # Serialize recent exercises
            recent_exercises = [
                {
                    "exercise_id": ex.exercise_id,
                    "difficulty": ex.difficulty.value,
                    "status": ex.status.value,
                    "grade": ex.grade,
                    "hints_requested": ex.hints_requested,
                    "time_spent_seconds": ex.time_spent_seconds,
                    "completed_at": ex.completed_at.isoformat() if ex.completed_at else None,
                    "is_success": ex.is_success,
                    "is_struggle": ex.is_struggle,
                }
                for ex in metrics.recent_exercises
            ]

            return jsonify({
                "user_id": metrics.user_id,
                "total_exercises_analyzed": metrics.total_exercises_analyzed,
                "average_grade": metrics.average_grade,
                "average_hints": metrics.average_hints,
                "average_time_seconds": metrics.average_time_seconds,
                "completion_rate": metrics.completion_rate,
                "consecutive_successes": metrics.consecutive_successes,
                "consecutive_struggles": metrics.consecutive_struggles,
                "current_difficulty": metrics.current_difficulty.value if metrics.current_difficulty else None,
                "days_since_last_exercise": metrics.days_since_last_exercise,
                "recent_exercises": recent_exercises,
            }), 200

    except Exception as error:
        logger.error("Error getting performance metrics", extra={
            "error": str(error),
            "user_id": user_id
        })
        raise APIError(f"Failed to get performance metrics: {str(error)}", status_code=500)

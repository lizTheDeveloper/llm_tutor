"""
Progress tracking and achievement API endpoints.
Handles user progress metrics, achievements, streaks, and statistics.
"""
from quart import Blueprint, request, jsonify, Response
from typing import Dict, Any
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.middleware.auth_middleware import require_auth, get_current_user_id
from src.services.progress_service import ProgressService
from src.schemas.progress import (
    StreakUpdateRequest,
    ProgressHistoryRequest,
    StatisticsRequest,
    ExportRequest,
    SkillLevelCalculationRequest
)
from src.utils.database import get_async_db_session as get_session

logger = get_logger(__name__)
progress_bp = Blueprint("progress", __name__)


@progress_bp.route("", methods=["GET"])
@require_auth
async def get_progress_metrics() -> Dict[str, Any]:
    """
    Get comprehensive progress metrics for authenticated user.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with progress metrics
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ProgressService(session)
            metrics = await service.get_user_progress_metrics(user_id)

            return jsonify(metrics), 200

    except Exception as error:
        logger.error("Error getting progress metrics", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get progress metrics: {str(error)}", status_code=500)


@progress_bp.route("/achievements", methods=["GET"])
@require_auth
async def get_achievements() -> Dict[str, Any]:
    """
    Get all achievements with user's progress and unlock status.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with achievements list
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ProgressService(session)
            achievements = await service.get_user_achievements(user_id)

            # Calculate summary stats
            unlocked_count = sum(1 for a in achievements if a["unlocked"])
            total_points = sum(a["points"] for a in achievements if a["unlocked"])

            return jsonify({
                "achievements": achievements,
                "total_points": total_points,
                "unlocked_count": unlocked_count,
                "total_count": len(achievements)
            }), 200

    except Exception as error:
        logger.error("Error getting achievements", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get achievements: {str(error)}", status_code=500)


@progress_bp.route("/update-streak", methods=["POST"])
@require_auth
async def update_streak() -> Dict[str, Any]:
    """
    Update user's streak based on exercise completion.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "completed_today": true,
            "user_timezone": "America/New_York" (optional)
        }

    Returns:
        JSON response with streak update results
    """
    try:
        user_id = get_current_user_id()
        data = await request.get_json()

        # Validate request
        streak_request = StreakUpdateRequest(**data)

        async with get_session() as session:
            service = ProgressService(session)
            result = await service.update_streak(
                user_id,
                streak_request.completed_today,
                streak_request.user_timezone
            )

            await session.commit()

            return jsonify(result), 200

    except Exception as error:
        logger.error("Error updating streak", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to update streak: {str(error)}", status_code=500)


@progress_bp.route("/statistics", methods=["GET"])
@require_auth
async def get_statistics() -> Dict[str, Any]:
    """
    Get performance statistics for authenticated user.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        period: Time period (daily, weekly, monthly, all)

    Returns:
        JSON response with statistics
    """
    try:
        user_id = get_current_user_id()

        # Get query parameters
        period = request.args.get("period", "all")

        # Validate
        if period:
            StatisticsRequest(period=period)

        async with get_session() as session:
            service = ProgressService(session)
            statistics = await service.get_performance_statistics(user_id, period)

            return jsonify(statistics), 200

    except Exception as error:
        logger.error("Error getting statistics", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get statistics: {str(error)}", status_code=500)


@progress_bp.route("/history", methods=["GET"])
@require_auth
async def get_progress_history() -> Dict[str, Any]:
    """
    Get historical progress data for authenticated user.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        days: Number of days of history (default: 30)
        start_date: Custom start date (YYYY-MM-DD)
        end_date: Custom end date (YYYY-MM-DD)

    Returns:
        JSON response with progress history
    """
    try:
        user_id = get_current_user_id()

        # Get query parameters
        days = request.args.get("days", type=int)
        start_date_str = request.args.get("start_date")
        end_date_str = request.args.get("end_date")

        # Parse dates if provided
        start_date = None
        end_date = None

        if start_date_str:
            from datetime import datetime
            start_date = datetime.fromisoformat(start_date_str).date()

        if end_date_str:
            from datetime import datetime
            end_date = datetime.fromisoformat(end_date_str).date()

        async with get_session() as session:
            service = ProgressService(session)
            history = await service.get_progress_history(
                user_id,
                days=days,
                start_date=start_date,
                end_date=end_date
            )

            return jsonify(history), 200

    except Exception as error:
        logger.error("Error getting progress history", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get progress history: {str(error)}", status_code=500)


@progress_bp.route("/badges", methods=["GET"])
@require_auth
async def get_badges() -> Dict[str, Any]:
    """
    Get user's badges (earned and available).

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with badges
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ProgressService(session)
            badges_data = await service.get_user_badges(user_id)

            return jsonify(badges_data), 200

    except Exception as error:
        logger.error("Error getting badges", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get badges: {str(error)}", status_code=500)


@progress_bp.route("/skill-levels", methods=["GET"])
@require_auth
async def get_skill_levels() -> Dict[str, Any]:
    """
    Get user's skill levels across all topics.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response with skill levels
    """
    try:
        user_id = get_current_user_id()

        async with get_session() as session:
            service = ProgressService(session)
            skill_levels = await service.get_skill_levels(user_id)

            return jsonify(skill_levels), 200

    except Exception as error:
        logger.error("Error getting skill levels", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to get skill levels: {str(error)}", status_code=500)


@progress_bp.route("/calculate-skill-level", methods=["POST"])
@require_auth
async def calculate_skill_level() -> Dict[str, Any]:
    """
    Calculate and update skill level for a specific topic.

    Headers:
        Authorization: Bearer <access_token>

    Request Body:
        {
            "topic": "algorithms"
        }

    Returns:
        JSON response with skill level calculation results
    """
    try:
        user_id = get_current_user_id()
        data = await request.get_json()

        # Validate request
        calc_request = SkillLevelCalculationRequest(**data)

        async with get_session() as session:
            service = ProgressService(session)
            result = await service.calculate_skill_level(user_id, calc_request.topic)

            await session.commit()

            return jsonify(result), 200

    except Exception as error:
        logger.error("Error calculating skill level", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to calculate skill level: {str(error)}", status_code=500)


@progress_bp.route("/export", methods=["GET"])
@require_auth
async def export_progress() -> Any:
    """
    Export user's progress data in JSON or CSV format.

    Headers:
        Authorization: Bearer <access_token>

    Query Parameters:
        format: Export format (json or csv, default: json)

    Returns:
        JSON response or CSV file with progress data
    """
    try:
        user_id = get_current_user_id()

        # Get query parameters
        export_format = request.args.get("format", "json")

        # Validate format
        ExportRequest(format=export_format)

        async with get_session() as session:
            service = ProgressService(session)
            export_data = await service.export_progress_data(user_id, export_format)

            if export_format == "json":
                return jsonify(export_data), 200
            elif export_format == "csv":
                # Return CSV as text/csv
                return Response(
                    export_data,
                    mimetype="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=progress_export_{user_id}.csv"
                    }
                )

    except Exception as error:
        logger.error("Error exporting progress", extra={"error": str(error), "user_id": user_id})
        raise APIError(f"Failed to export progress: {str(error)}", status_code=500)

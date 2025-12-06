"""
Rate limiting middleware for API endpoints.
Uses Redis to track request counts per user/IP.

SEC-3 Enhancement:
- Tiered rate limiting based on user role
- Cost tracking for LLM operations
- Daily cost limit enforcement
- Per-endpoint rate limits for expensive operations
"""
from functools import wraps
from typing import Optional, Callable, Dict, Any
import time
from datetime import datetime
from quart import request, jsonify
from sqlalchemy import select
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.utils.redis_client import get_redis
from src.config import settings
from src.models.user import User, UserRole

logger = get_logger(__name__)


def get_client_identifier() -> str:
    """
    Get unique identifier for rate limiting.
    Uses authenticated user ID if available, otherwise IP address.

    Returns:
        Unique identifier string
    """
    # Try to get user ID from request context (set by auth middleware)
    user_id = getattr(request, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    if "," in ip_address:
        # Take first IP if there are multiple (proxy chain)
        ip_address = ip_address.split(",")[0].strip()

    return f"ip:{ip_address}"


async def check_rate_limit(
    identifier: str,
    limit: int,
    window: int,
    endpoint: str,
) -> tuple[bool, Optional[int]]:
    """
    Check if request is within rate limit.

    Args:
        identifier: Unique client identifier
        limit: Maximum requests allowed
        window: Time window in seconds
        endpoint: API endpoint being accessed

    Returns:
        Tuple of (allowed, retry_after_seconds)
    """
    redis_manager = get_redis()
    current_time = int(time.time())
    window_start = current_time - window

    # Use sorted set to track requests in time window
    key = f"rate_limit:{endpoint}:{identifier}"

    # Remove old requests outside the window
    await redis_manager.async_client.zremrangebyscore(key, 0, window_start)

    # Count requests in current window
    request_count = await redis_manager.async_client.zcard(key)

    if request_count >= limit:
        # Get oldest request in window
        oldest = await redis_manager.async_client.zrange(key, 0, 0, withscores=True)
        if oldest:
            oldest_time = int(oldest[0][1])
            retry_after = window - (current_time - oldest_time)
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "identifier": identifier,
                    "endpoint": endpoint,
                    "count": request_count,
                    "limit": limit,
                },
            )
            return False, max(1, retry_after)

    # Add current request
    await redis_manager.async_client.zadd(key, {str(current_time): current_time})

    # Set expiration on the key
    await redis_manager.async_client.expire(key, window)

    return True, None


def rate_limit(
    requests_per_minute: Optional[int] = None,
    requests_per_hour: Optional[int] = None,
):
    """
    Decorator for rate limiting API endpoints.

    Args:
        requests_per_minute: Max requests per minute (None to use default)
        requests_per_hour: Max requests per hour (None to skip)

    Usage:
        @rate_limit(requests_per_minute=10)
        @app.route("/api/endpoint")
        async def endpoint():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            identifier = get_client_identifier()
            endpoint = request.path

            # Check minute limit
            if requests_per_minute is not None:
                rpm = requests_per_minute
            else:
                rpm = settings.rate_limit_per_minute

            allowed, retry_after = await check_rate_limit(
                identifier,
                limit=rpm,
                window=60,
                endpoint=endpoint,
            )

            if not allowed:
                response = jsonify({
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests. Please try again in {retry_after} seconds.",
                    }
                })
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                response.headers["X-RateLimit-Limit"] = str(rpm)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["X-RateLimit-Reset"] = str(int(time.time()) + retry_after)
                return response

            # Check hour limit if specified
            if requests_per_hour is not None:
                allowed, retry_after = await check_rate_limit(
                    identifier,
                    limit=requests_per_hour,
                    window=3600,
                    endpoint=f"{endpoint}:hour",
                )

                if not allowed:
                    response = jsonify({
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Hourly rate limit exceeded. Please try again in {retry_after // 60} minutes.",
                        }
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    return response

            # Request is allowed, execute the endpoint
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def get_rate_limit_for_user(
    user_id: int,
    endpoint_type: str,
) -> Dict[str, int]:
    """
    Get rate limits for a user based on their role.

    Args:
        user_id: User identifier
        endpoint_type: Type of endpoint (chat, exercise_generation, hint)

    Returns:
        Dictionary with per_minute and per_day/per_hour limits
    """
    from src.utils.database import get_async_db_session

    # Fetch user role from database
    async with get_async_db_session() as session:
        result = await session.execute(
            select(User.role).where(User.id == user_id)
        )
        user_role = result.scalar_one_or_none()

    if user_role is None:
        # Default to student limits if user not found
        user_role = UserRole.STUDENT

    # Determine limits based on role and endpoint type
    is_admin = user_role in [UserRole.ADMIN, UserRole.MODERATOR]

    if endpoint_type == "chat":
        return {
            "per_minute": settings.rate_limit_chat_per_minute_admin if is_admin else settings.rate_limit_chat_per_minute_student,
            "per_day": 1000 if is_admin else 200,  # Daily chat limit
        }
    elif endpoint_type == "exercise_generation":
        return {
            "per_hour": settings.rate_limit_exercise_generation_per_hour_admin if is_admin else settings.rate_limit_exercise_generation_per_hour,
            "per_day": 20 if is_admin else 5,  # Daily exercise generation limit
        }
    elif endpoint_type == "hint":
        return {
            "per_hour": settings.rate_limit_hint_per_hour_admin if is_admin else settings.rate_limit_hint_per_hour,
            "per_day": 30 if is_admin else 10,  # Daily hint limit
        }
    else:
        # Default limits
        return {
            "per_minute": settings.rate_limit_per_minute,
            "per_day": 1000,
        }


def llm_rate_limit(endpoint_type: str):
    """
    Enhanced rate limiting decorator for LLM endpoints with cost tracking.

    Enforces:
    1. Role-based rate limits (tiered by user role)
    2. Daily cost limits (prevents cost overruns)
    3. Per-endpoint specific limits

    Args:
        endpoint_type: Type of endpoint (chat, exercise_generation, hint)

    Usage:
        @llm_rate_limit("chat")
        @app.route("/api/chat/message")
        async def chat_endpoint():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user ID from request context (set by auth middleware)
            user_id = getattr(request, "user_id", None)

            if user_id is None:
                # Not authenticated - use IP-based rate limiting
                return await rate_limit(
                    requests_per_minute=5,
                    requests_per_hour=20
                )(func)(*args, **kwargs)

            # Get role-based rate limits
            limits = await get_rate_limit_for_user(user_id, endpoint_type)
            identifier = f"user:{user_id}"
            endpoint = request.path

            # Check minute limit if applicable
            if "per_minute" in limits:
                allowed, retry_after = await check_rate_limit(
                    identifier,
                    limit=limits["per_minute"],
                    window=60,
                    endpoint=endpoint,
                )

                if not allowed:
                    response = jsonify({
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Rate limit exceeded: {limits['per_minute']} requests per minute. Retry in {retry_after}s.",
                        }
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    response.headers["X-RateLimit-Limit"] = str(limits["per_minute"])
                    response.headers["X-RateLimit-Remaining"] = "0"
                    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + retry_after)
                    return response

            # Check hourly limit if applicable
            if "per_hour" in limits:
                allowed, retry_after = await check_rate_limit(
                    identifier,
                    limit=limits["per_hour"],
                    window=3600,
                    endpoint=f"{endpoint}:hour",
                )

                if not allowed:
                    response = jsonify({
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Hourly rate limit exceeded: {limits['per_hour']} requests per hour. Retry in {retry_after // 60} minutes.",
                        }
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    return response

            # Check daily cost limit
            from src.services.llm.cost_tracker import CostTracker
            from src.utils.redis_client import get_redis

            redis = get_redis()
            cost_tracker = CostTracker(redis.async_client)

            # Fetch user role to determine cost limit
            from src.utils.database import get_async_db_session
            async with get_async_db_session() as session:
                result = await session.execute(
                    select(User.role).where(User.id == user_id)
                )
                user_role = result.scalar_one_or_none()

            is_admin = user_role in [UserRole.ADMIN, UserRole.MODERATOR] if user_role else False
            daily_cost_limit = settings.daily_cost_limit_admin if is_admin else settings.daily_cost_limit_student

            # Check if user is within cost limit
            within_limit, current_cost = await cost_tracker.check_cost_limit(
                user_id,
                daily_cost_limit
            )

            if not within_limit:
                response = jsonify({
                    "error": {
                        "code": "COST_LIMIT_EXCEEDED",
                        "message": f"Daily cost limit of ${daily_cost_limit:.2f} exceeded (current: ${current_cost:.2f}). Limit resets at midnight UTC.",
                    }
                })
                response.status_code = 429
                response.headers["X-Cost-Limit"] = str(daily_cost_limit)
                response.headers["X-Cost-Current"] = str(current_cost)
                return response

            # Check if approaching cost limit (warning)
            if await cost_tracker.check_cost_warning(user_id, daily_cost_limit, settings.cost_warning_threshold):
                logger.warning(
                    "User approaching daily cost limit",
                    extra={
                        "user_id": user_id,
                        "current_cost": current_cost,
                        "limit": daily_cost_limit,
                        "threshold": settings.cost_warning_threshold,
                    }
                )

            # Request is allowed, execute the endpoint
            return await func(*args, **kwargs)

        return wrapper

    return decorator

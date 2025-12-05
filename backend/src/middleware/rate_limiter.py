"""
Rate limiting middleware for API endpoints.
Uses Redis to track request counts per user/IP.
"""
from functools import wraps
from typing import Optional, Callable
import time
from datetime import datetime
from quart import request, jsonify
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.utils.redis_client import get_redis
from src.config import settings

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

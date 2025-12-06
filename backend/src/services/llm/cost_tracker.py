"""
LLM Cost Tracking Service.

Tracks and enforces daily cost limits for LLM API usage per user.
Prevents cost overruns and provides visibility into usage patterns.

Features:
- Per-user daily cost tracking
- Cost limit enforcement
- Operation metadata storage
- Warning threshold alerts
- Automatic Redis expiration
"""
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import redis.asyncio as aioredis
from src.logging_config import get_logger

logger = get_logger(__name__)


class CostTracker:
    """Track and enforce LLM API costs per user."""

    # Cost per 1M tokens (approximate, adjust based on actual provider pricing)
    COST_PER_MILLION_TOKENS = {
        "llama-3.3-70b-versatile": 0.50,  # GROQ pricing
        "gpt-3.5-turbo": 1.50,  # OpenAI pricing
        "gpt-4": 30.00,  # OpenAI pricing
        "claude-3-haiku": 0.25,  # Anthropic pricing
        "claude-3-sonnet": 3.00,  # Anthropic pricing
    }

    def __init__(self, redis_client: aioredis.Redis):
        """
        Initialize cost tracker.

        Args:
            redis_client: Redis client for storing cost data
        """
        self.redis = redis_client
        self.logger = logger

    async def track_cost(
        self,
        user_id: int,
        operation_type: str,
        cost: float,
    ) -> None:
        """
        Track cost for a user's LLM operation.

        Args:
            user_id: User identifier
            operation_type: Type of operation (chat, exercise_generation, hint)
            cost: Cost in dollars
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cost_key = f"llm_cost:daily:{user_id}:{today}"

        # Increment daily cost
        await self.redis.incrbyfloat(cost_key, cost)

        # Set expiration to end of next day (ensure we don't lose data on day boundary)
        await self.redis.expire(cost_key, 86400 * 2)

        self.logger.info(
            "LLM cost tracked",
            extra={
                "user_id": user_id,
                "operation_type": operation_type,
                "cost": cost,
                "date": today,
            },
        )

    async def track_operation(
        self,
        user_id: int,
        operation_id: str,
        operation_type: str,
        cost: float,
        tokens_used: int,
        model: str,
    ) -> None:
        """
        Track operation with full metadata.

        Args:
            user_id: User identifier
            operation_id: Unique operation identifier
            operation_type: Type of operation
            cost: Cost in dollars
            tokens_used: Number of tokens consumed
            model: LLM model used
        """
        # Track daily cost
        await self.track_cost(user_id, operation_type, cost)

        # Store operation metadata
        metadata_key = f"llm_operation:{operation_id}"
        metadata = {
            "user_id": user_id,
            "operation_type": operation_type,
            "cost": cost,
            "tokens_used": tokens_used,
            "model": model,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await self.redis.setex(
            metadata_key,
            86400 * 7,  # Keep metadata for 7 days
            json.dumps(metadata),
        )

    async def get_daily_cost(self, user_id: int) -> float:
        """
        Get total cost for user today.

        Args:
            user_id: User identifier

        Returns:
            Total cost in dollars
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cost_key = f"llm_cost:daily:{user_id}:{today}"

        cost_str = await self.redis.get(cost_key)
        if cost_str is None:
            return 0.0

        return float(cost_str)

    async def get_operation_metadata(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific operation.

        Args:
            operation_id: Unique operation identifier

        Returns:
            Operation metadata dictionary or None if not found
        """
        metadata_key = f"llm_operation:{operation_id}"
        metadata_str = await self.redis.get(metadata_key)

        if metadata_str is None:
            return None

        return json.loads(metadata_str)

    async def check_cost_limit(
        self,
        user_id: int,
        daily_limit: float,
    ) -> tuple[bool, float]:
        """
        Check if user is within daily cost limit.

        Args:
            user_id: User identifier
            daily_limit: Maximum daily cost in dollars

        Returns:
            Tuple of (is_within_limit, current_cost)
        """
        current_cost = await self.get_daily_cost(user_id)

        is_within_limit = current_cost < daily_limit

        if not is_within_limit:
            self.logger.warning(
                "Daily cost limit exceeded",
                extra={
                    "user_id": user_id,
                    "current_cost": current_cost,
                    "daily_limit": daily_limit,
                },
            )

        return is_within_limit, current_cost

    async def check_cost_warning(
        self,
        user_id: int,
        limit: float,
        threshold: float = 0.8,
    ) -> bool:
        """
        Check if user has exceeded warning threshold.

        Args:
            user_id: User identifier
            limit: Daily cost limit in dollars
            threshold: Warning threshold (0.0-1.0, default 0.8 = 80%)

        Returns:
            True if warning threshold exceeded
        """
        current_cost = await self.get_daily_cost(user_id)
        warning_level = limit * threshold

        if current_cost >= warning_level:
            self.logger.warning(
                "Cost warning threshold exceeded",
                extra={
                    "user_id": user_id,
                    "current_cost": current_cost,
                    "warning_level": warning_level,
                    "limit": limit,
                    "threshold_percentage": threshold * 100,
                },
            )
            return True

        return False

    async def estimate_cost(
        self,
        tokens: int,
        model: str,
    ) -> float:
        """
        Estimate cost for a given number of tokens and model.

        Args:
            tokens: Number of tokens
            model: LLM model name

        Returns:
            Estimated cost in dollars
        """
        cost_per_million = self.COST_PER_MILLION_TOKENS.get(
            model,
            1.00,  # Default fallback
        )

        cost = (tokens / 1_000_000) * cost_per_million

        return cost

    async def get_usage_stats(
        self,
        user_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a user over specified days.

        Args:
            user_id: User identifier
            days: Number of days to look back

        Returns:
            Dictionary with usage statistics
        """
        stats = {
            "daily_costs": {},
            "total_cost": 0.0,
            "average_daily_cost": 0.0,
        }

        today = datetime.utcnow()

        for i in range(days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            cost_key = f"llm_cost:daily:{user_id}:{date}"

            cost_str = await self.redis.get(cost_key)
            cost = float(cost_str) if cost_str else 0.0

            stats["daily_costs"][date] = cost
            stats["total_cost"] += cost

        stats["average_daily_cost"] = stats["total_cost"] / days if days > 0 else 0.0

        return stats

"""
Cache Service - Redis caching for frequently accessed data (PERF-1).

This service provides caching for:
1. User profiles (TTL: 5 minutes)
2. Exercises (TTL: 1 hour)
3. Exercise lists (TTL: 2 minutes)

Cache invalidation:
- User profile: On profile update
- Exercise: On exercise update (rare, exercises are mostly static)

Performance Impact:
- User profile cache hit rate: Expected >80%
- Exercise cache hit rate: Expected >90%
- Reduces database read load by 60-70%
"""
import json
from typing import Optional, Dict, Any, List
from datetime import timedelta

from src.utils.redis_client import get_redis
from src.logging_config import get_logger

logger = get_logger(__name__)


class CacheService:
    """Service for caching frequently accessed data in Redis."""

    # Cache key prefixes
    USER_PROFILE_PREFIX = "user:profile:"
    EXERCISE_PREFIX = "exercise:"
    EXERCISE_LIST_PREFIX = "exercise:list:"

    # Cache TTLs (in seconds)
    USER_PROFILE_TTL = 300  # 5 minutes
    EXERCISE_TTL = 3600  # 1 hour
    EXERCISE_LIST_TTL = 120  # 2 minutes

    def __init__(self):
        """Initialize cache service with Redis client."""
        self.redis_client = get_redis()

    # =========================================================================
    # USER PROFILE CACHING
    # =========================================================================

    async def get_cached_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user profile from cache.

        Args:
            user_id: User ID

        Returns:
            User profile dict if cached, None if not in cache
        """
        cache_key = f"{self.USER_PROFILE_PREFIX}{user_id}"

        try:
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                logger.info(
                    "User profile cache HIT",
                    extra={"user_id": user_id, "cache_key": cache_key}
                )
                return json.loads(cached_data)

            logger.info(
                "User profile cache MISS",
                extra={"user_id": user_id, "cache_key": cache_key}
            )
            return None

        except Exception as error:
            logger.error(
                "Error getting cached user profile",
                exc_info=True,
                extra={"user_id": user_id, "error": str(error)}
            )
            return None  # Fail gracefully, fetch from DB

    async def cache_user_profile(
        self,
        user_id: int,
        profile_data: Dict[str, Any]
    ) -> bool:
        """
        Cache user profile in Redis.

        Args:
            user_id: User ID
            profile_data: User profile dict to cache

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = f"{self.USER_PROFILE_PREFIX}{user_id}"

        try:
            await self.redis_client.setex(
                cache_key,
                self.USER_PROFILE_TTL,
                json.dumps(profile_data)
            )

            logger.info(
                "User profile cached",
                extra={
                    "user_id": user_id,
                    "cache_key": cache_key,
                    "ttl_seconds": self.USER_PROFILE_TTL
                }
            )
            return True

        except Exception as error:
            logger.error(
                "Error caching user profile",
                exc_info=True,
                extra={"user_id": user_id, "error": str(error)}
            )
            return False

    async def invalidate_user_profile(self, user_id: int) -> bool:
        """
        Invalidate (delete) user profile from cache.

        Call this after:
        - Profile update
        - Onboarding completion
        - User settings change

        Args:
            user_id: User ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        cache_key = f"{self.USER_PROFILE_PREFIX}{user_id}"

        try:
            deleted_count = await self.redis_client.delete(cache_key)

            logger.info(
                "User profile cache invalidated",
                extra={
                    "user_id": user_id,
                    "cache_key": cache_key,
                    "was_cached": deleted_count > 0
                }
            )
            return True

        except Exception as error:
            logger.error(
                "Error invalidating user profile cache",
                exc_info=True,
                extra={"user_id": user_id, "error": str(error)}
            )
            return False

    # =========================================================================
    # EXERCISE CACHING
    # =========================================================================

    async def get_cached_exercise(self, exercise_id: int) -> Optional[Dict[str, Any]]:
        """
        Get exercise from cache.

        Args:
            exercise_id: Exercise ID

        Returns:
            Exercise dict if cached, None if not in cache
        """
        cache_key = f"{self.EXERCISE_PREFIX}{exercise_id}"

        try:
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                logger.info(
                    "Exercise cache HIT",
                    extra={"exercise_id": exercise_id, "cache_key": cache_key}
                )
                return json.loads(cached_data)

            logger.info(
                "Exercise cache MISS",
                extra={"exercise_id": exercise_id, "cache_key": cache_key}
            )
            return None

        except Exception as error:
            logger.error(
                "Error getting cached exercise",
                exc_info=True,
                extra={"exercise_id": exercise_id, "error": str(error)}
            )
            return None

    async def cache_exercise(
        self,
        exercise_id: int,
        exercise_data: Dict[str, Any]
    ) -> bool:
        """
        Cache exercise in Redis.

        Note: Only cache Exercise data, NOT UserExercise data
        (UserExercise changes frequently per user).

        Args:
            exercise_id: Exercise ID
            exercise_data: Exercise dict to cache (exclude solution)

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = f"{self.EXERCISE_PREFIX}{exercise_id}"

        try:
            await self.redis_client.setex(
                cache_key,
                self.EXERCISE_TTL,
                json.dumps(exercise_data)
            )

            logger.info(
                "Exercise cached",
                extra={
                    "exercise_id": exercise_id,
                    "cache_key": cache_key,
                    "ttl_seconds": self.EXERCISE_TTL
                }
            )
            return True

        except Exception as error:
            logger.error(
                "Error caching exercise",
                exc_info=True,
                extra={"exercise_id": exercise_id, "error": str(error)}
            )
            return False

    async def invalidate_exercise(self, exercise_id: int) -> bool:
        """
        Invalidate (delete) exercise from cache.

        Call this after:
        - Exercise update (rare)
        - Exercise deletion

        Args:
            exercise_id: Exercise ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        cache_key = f"{self.EXERCISE_PREFIX}{exercise_id}"

        try:
            deleted_count = await self.redis_client.delete(cache_key)

            logger.info(
                "Exercise cache invalidated",
                extra={
                    "exercise_id": exercise_id,
                    "cache_key": cache_key,
                    "was_cached": deleted_count > 0
                }
            )
            return True

        except Exception as error:
            logger.error(
                "Error invalidating exercise cache",
                exc_info=True,
                extra={"exercise_id": exercise_id, "error": str(error)}
            )
            return False

    # =========================================================================
    # EXERCISE LIST CACHING
    # =========================================================================

    async def get_cached_exercise_list(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Get exercise list from cache.

        Cache key includes pagination params to cache different pages.

        Args:
            user_id: User ID
            status: Optional status filter
            limit: Pagination limit
            offset: Pagination offset

        Returns:
            Exercise list dict if cached, None if not in cache
        """
        cache_key = f"{self.EXERCISE_LIST_PREFIX}{user_id}:{status}:{limit}:{offset}"

        try:
            cached_data = await self.redis_client.get(cache_key)

            if cached_data:
                logger.info(
                    "Exercise list cache HIT",
                    extra={
                        "user_id": user_id,
                        "cache_key": cache_key,
                        "status": status,
                        "limit": limit,
                        "offset": offset
                    }
                )
                return json.loads(cached_data)

            logger.info(
                "Exercise list cache MISS",
                extra={
                    "user_id": user_id,
                    "cache_key": cache_key
                }
            )
            return None

        except Exception as error:
            logger.error(
                "Error getting cached exercise list",
                exc_info=True,
                extra={"user_id": user_id, "error": str(error)}
            )
            return None

    async def cache_exercise_list(
        self,
        user_id: int,
        exercises_data: Dict[str, Any],
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> bool:
        """
        Cache exercise list in Redis.

        Short TTL (2 minutes) because UserExercise status changes frequently.

        Args:
            user_id: User ID
            exercises_data: Exercise list dict to cache
            status: Optional status filter
            limit: Pagination limit
            offset: Pagination offset

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = f"{self.EXERCISE_LIST_PREFIX}{user_id}:{status}:{limit}:{offset}"

        try:
            await self.redis_client.setex(
                cache_key,
                self.EXERCISE_LIST_TTL,
                json.dumps(exercises_data)
            )

            logger.info(
                "Exercise list cached",
                extra={
                    "user_id": user_id,
                    "cache_key": cache_key,
                    "ttl_seconds": self.EXERCISE_LIST_TTL
                }
            )
            return True

        except Exception as error:
            logger.error(
                "Error caching exercise list",
                exc_info=True,
                extra={"user_id": user_id, "error": str(error)}
            )
            return False

    async def invalidate_user_exercise_lists(self, user_id: int) -> bool:
        """
        Invalidate ALL exercise lists for a user.

        Call this after:
        - Exercise submission
        - Exercise completion
        - Exercise skip

        Uses pattern matching to delete all cached lists for user.

        Args:
            user_id: User ID

        Returns:
            True if invalidated successfully, False otherwise
        """
        pattern = f"{self.EXERCISE_LIST_PREFIX}{user_id}:*"

        try:
            # Get all keys matching pattern
            cursor = 0
            deleted_count = 0

            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100
                )

                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    deleted_count += deleted

                if cursor == 0:
                    break

            logger.info(
                "User exercise lists cache invalidated",
                extra={
                    "user_id": user_id,
                    "pattern": pattern,
                    "deleted_count": deleted_count
                }
            )
            return True

        except Exception as error:
            logger.error(
                "Error invalidating user exercise lists cache",
                exc_info=True,
                extra={"user_id": user_id, "error": str(error)}
            )
            return False

    # =========================================================================
    # CACHE STATISTICS
    # =========================================================================

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache statistics
        """
        try:
            info = await self.redis_client.info("stats")

            return {
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "evicted_keys": info.get("evicted_keys", 0),
                "expired_keys": info.get("expired_keys", 0)
            }

        except Exception as error:
            logger.error(
                "Error getting cache stats",
                exc_info=True,
                extra={"error": str(error)}
            )
            return {}

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """
        Calculate cache hit rate percentage.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses

        Returns:
            Hit rate percentage (0-100)
        """
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100


# Global cache service instance
_cache_service = None


def get_cache_service() -> CacheService:
    """
    Get global cache service instance (singleton pattern).

    Returns:
        CacheService instance
    """
    global _cache_service

    if _cache_service is None:
        _cache_service = CacheService()
        logger.info("Cache service initialized")

    return _cache_service

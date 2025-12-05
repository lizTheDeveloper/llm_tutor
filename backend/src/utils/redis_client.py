"""
Redis client configuration and management for CodeMentor backend.
Provides Redis connection pooling for caching and session management.
"""
from typing import Optional, Any
import json
import threading
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.connection import ConnectionPool
from redis.asyncio.connection import ConnectionPool as AsyncConnectionPool

from ..utils.logger import get_logger

logger = get_logger(__name__)


class RedisManager:
    """
    Redis connection and operation management.
    Handles both sync and async Redis clients.
    """

    def __init__(
        self,
        redis_url: str,
        session_db: int = 1,
        decode_responses: bool = True,
        max_connections: int = 50,
    ):
        """
        Initialize Redis manager.

        Args:
            redis_url: Redis connection URL
            session_db: Database number for session storage
            decode_responses: Automatically decode responses to strings
            max_connections: Maximum connections in pool
        """
        self.redis_url = redis_url
        self.session_db = session_db
        self.decode_responses = decode_responses
        self.max_connections = max_connections

        # Initialize connection pools
        self._sync_pool = None
        self._async_pool = None
        self._sync_client = None
        self._async_client = None
        self._session_client = None

        logger.info(
            "Redis manager initialized",
            extra={
                "redis_url": redis_url,
                "session_db": session_db,
            },
        )

    @property
    def sync_pool(self) -> ConnectionPool:
        """Get or create synchronous connection pool."""
        if self._sync_pool is None:
            self._sync_pool = ConnectionPool.from_url(
                self.redis_url,
                decode_responses=self.decode_responses,
                max_connections=self.max_connections,
            )
            logger.info("Synchronous Redis connection pool created")
        return self._sync_pool

    @property
    def async_pool(self) -> AsyncConnectionPool:
        """Get or create asynchronous connection pool."""
        if self._async_pool is None:
            self._async_pool = AsyncConnectionPool.from_url(
                self.redis_url,
                decode_responses=self.decode_responses,
                max_connections=self.max_connections,
            )
            logger.info("Asynchronous Redis connection pool created")
        return self._async_pool

    @property
    def client(self) -> Redis:
        """Get or create synchronous Redis client."""
        if self._sync_client is None:
            self._sync_client = Redis(connection_pool=self.sync_pool)
            logger.info("Synchronous Redis client created")
        return self._sync_client

    @property
    def async_client(self) -> AsyncRedis:
        """Get or create asynchronous Redis client."""
        if self._async_client is None:
            self._async_client = AsyncRedis(connection_pool=self.async_pool)
            logger.info("Asynchronous Redis client created")
        return self._async_client

    @property
    def session_client(self) -> Redis:
        """Get or create synchronous Redis client for session storage."""
        if self._session_client is None:
            session_url = self.redis_url.rsplit("/", 1)[0] + f"/{self.session_db}"
            session_pool = ConnectionPool.from_url(
                session_url,
                decode_responses=False,  # Sessions stored as bytes
                max_connections=self.max_connections,
            )
            self._session_client = Redis(connection_pool=session_pool)
            logger.info(
                "Session Redis client created",
                extra={"db": self.session_db},
            )
        return self._session_client

    async def set_cache(
        self,
        key: str,
        value: Any,
        expiration: Optional[int] = None,
    ) -> bool:
        """
        Set cache value with optional expiration.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            expiration: Expiration time in seconds (None for no expiration)

        Returns:
            True if successful
        """
        try:
            serialized_value = json.dumps(value)
            if expiration:
                await self.async_client.setex(key, expiration, serialized_value)
            else:
                await self.async_client.set(key, serialized_value)
            logger.debug(
                "Cache set",
                extra={"key": key, "expiration": expiration},
            )
            return True
        except Exception as exception:
            logger.error(
                "Failed to set cache",
                exc_info=True,
                extra={"key": key, "exception": str(exception)},
            )
            return False

    async def get_cache(self, key: str) -> Optional[Any]:
        """
        Get cache value by key.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            value = await self.async_client.get(key)
            if value:
                logger.debug("Cache hit", extra={"key": key})
                return json.loads(value)
            logger.debug("Cache miss", extra={"key": key})
            return None
        except Exception as exception:
            logger.error(
                "Failed to get cache",
                exc_info=True,
                extra={"key": key, "exception": str(exception)},
            )
            return None

    async def delete_cache(self, key: str) -> bool:
        """
        Delete cache entry by key.

        Args:
            key: Cache key

        Returns:
            True if key was deleted
        """
        try:
            result = await self.async_client.delete(key)
            logger.debug("Cache deleted", extra={"key": key, "deleted": bool(result)})
            return bool(result)
        except Exception as exception:
            logger.error(
                "Failed to delete cache",
                exc_info=True,
                extra={"key": key, "exception": str(exception)},
            )
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        try:
            return bool(await self.async_client.exists(key))
        except Exception as exception:
            logger.error(
                "Failed to check key existence",
                exc_info=True,
                extra={"key": key, "exception": str(exception)},
            )
            return False

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment counter by amount.

        Args:
            key: Counter key
            amount: Amount to increment

        Returns:
            New counter value or None on error
        """
        try:
            result = await self.async_client.incrby(key, amount)
            return result
        except Exception as exception:
            logger.error(
                "Failed to increment counter",
                exc_info=True,
                extra={"key": key, "exception": str(exception)},
            )
            return None

    async def set_expiration(self, key: str, seconds: int) -> bool:
        """
        Set expiration time for key.

        Args:
            key: Redis key
            seconds: Expiration time in seconds

        Returns:
            True if successful
        """
        try:
            return bool(await self.async_client.expire(key, seconds))
        except Exception as exception:
            logger.error(
                "Failed to set expiration",
                exc_info=True,
                extra={"key": key, "exception": str(exception)},
            )
            return False

    def ping(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            True if Redis is reachable
        """
        try:
            return self.client.ping()
        except Exception as exception:
            logger.error(
                "Redis ping failed",
                exc_info=True,
                extra={"exception": str(exception)},
            )
            return False

    async def close(self):
        """Close Redis connections."""
        if self._async_client:
            await self._async_client.close()
            logger.info("Async Redis client closed")
        if self._sync_client:
            self._sync_client.close()
            logger.info("Sync Redis client closed")
        if self._session_client:
            self._session_client.close()
            logger.info("Session Redis client closed")


# Global Redis manager instance and thread lock
_redis_manager: Optional[RedisManager] = None
_redis_lock = threading.Lock()


def init_redis(
    redis_url: str,
    session_db: int = 1,
) -> RedisManager:
    """
    Initialize global Redis manager (thread-safe).

    Args:
        redis_url: Redis connection URL
        session_db: Database number for session storage

    Returns:
        Initialized RedisManager instance
    """
    global _redis_manager

    with _redis_lock:
        if _redis_manager is None:
            _redis_manager = RedisManager(
                redis_url=redis_url,
                session_db=session_db,
            )
            logger.info("Global Redis manager initialized")

    return _redis_manager


def get_redis() -> RedisManager:
    """
    Get the global Redis manager instance.

    Returns:
        RedisManager instance

    Raises:
        RuntimeError: If Redis not initialized
    """
    if _redis_manager is None:
        raise RuntimeError(
            "Redis not initialized. Call init_redis() first."
        )
    return _redis_manager

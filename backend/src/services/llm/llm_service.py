"""
Main LLM service for CodeMentor.
Orchestrates LLM providers, caching, rate limiting, and context management.
"""
import hashlib
import json
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as aioredis

from .base_provider import BaseLLMProvider, LLMRequest, LLMResponse, Message
from .groq_provider import GroqProvider
from .prompt_templates import PromptTemplateManager, PromptType


class RateLimiter:
    """Rate limiter using Redis for distributed rate limiting."""

    def __init__(self, redis_client: aioredis.Redis, logger):
        """
        Initialize rate limiter.

        Args:
            redis_client: Redis client for storing rate limit counters
            logger: Logger instance
        """
        self.redis = redis_client
        self.logger = logger

    async def check_rate_limit(
        self,
        user_id: str,
        requests_per_minute: int,
        requests_per_day: int,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if user has exceeded rate limits.

        Args:
            user_id: User identifier
            requests_per_minute: Maximum requests per minute
            requests_per_day: Maximum requests per day

        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        minute_key = f"rate_limit:minute:{user_id}:{int(time.time() // 60)}"
        day_key = f"rate_limit:day:{user_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"

        # Check minute limit
        minute_count = await self.redis.incr(minute_key)
        if minute_count == 1:
            await self.redis.expire(minute_key, 60)

        if minute_count > requests_per_minute:
            self.logger.warning(
                "Rate limit exceeded (minute)",
                extra={
                    "user_id": user_id,
                    "count": minute_count,
                    "limit": requests_per_minute,
                },
            )
            retry_after = 60 - (int(time.time()) % 60)
            return False, retry_after

        # Check day limit
        day_count = await self.redis.incr(day_key)
        if day_count == 1:
            await self.redis.expire(day_key, 86400)

        if day_count > requests_per_day:
            self.logger.warning(
                "Rate limit exceeded (day)",
                extra={
                    "user_id": user_id,
                    "count": day_count,
                    "limit": requests_per_day,
                },
            )
            # Calculate seconds until midnight UTC
            now = datetime.utcnow()
            midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            retry_after = int((midnight - now).total_seconds())
            return False, retry_after

        return True, None

    async def get_usage(self, user_id: str) -> Dict[str, int]:
        """
        Get current usage for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with current minute and day usage
        """
        minute_key = f"rate_limit:minute:{user_id}:{int(time.time() // 60)}"
        day_key = f"rate_limit:day:{user_id}:{datetime.utcnow().strftime('%Y-%m-%d')}"

        minute_count = await self.redis.get(minute_key)
        day_count = await self.redis.get(day_key)

        return {
            "requests_this_minute": int(minute_count) if minute_count else 0,
            "requests_today": int(day_count) if day_count else 0,
        }


class ResponseCache:
    """Cache for LLM responses using Redis."""

    def __init__(self, redis_client: aioredis.Redis, logger, ttl: int = 3600):
        """
        Initialize response cache.

        Args:
            redis_client: Redis client
            logger: Logger instance
            ttl: Time to live for cached responses in seconds (default: 1 hour)
        """
        self.redis = redis_client
        self.logger = logger
        self.ttl = ttl

    def _generate_cache_key(self, request: LLMRequest) -> str:
        """
        Generate a cache key from an LLM request.

        Args:
            request: The LLM request

        Returns:
            Cache key string
        """
        # Create a deterministic hash of the request
        request_data = {
            "messages": [(msg.role, msg.content) for msg in request.messages],
            "system_prompt": request.system_prompt,
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        request_json = json.dumps(request_data, sort_keys=True)
        cache_hash = hashlib.sha256(request_json.encode()).hexdigest()
        return f"llm_cache:{cache_hash}"

    async def get(self, request: LLMRequest) -> Optional[LLMResponse]:
        """
        Get a cached response for a request.

        Args:
            request: The LLM request

        Returns:
            Cached LLMResponse if found, None otherwise
        """
        cache_key = self._generate_cache_key(request)

        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                response = LLMResponse(
                    content=data["content"],
                    model=data["model"],
                    provider=data["provider"],
                    tokens_used=data["tokens_used"],
                    prompt_tokens=data["prompt_tokens"],
                    completion_tokens=data["completion_tokens"],
                    finish_reason=data["finish_reason"],
                    response_time_ms=data["response_time_ms"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    cached=True,
                    cost_usd=data["cost_usd"],
                )

                self.logger.info("Cache hit", extra={"cache_key": cache_key})
                return response

        except Exception as error:
            self.logger.error(
                "Cache get error",
                extra={
                    "error": str(error),
                    "cache_key": cache_key,
                },
            )

        return None

    async def set(self, request: LLMRequest, response: LLMResponse) -> None:
        """
        Cache a response for a request.

        Args:
            request: The LLM request
            response: The LLM response to cache
        """
        cache_key = self._generate_cache_key(request)

        try:
            data = {
                "content": response.content,
                "model": response.model,
                "provider": response.provider,
                "tokens_used": response.tokens_used,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "finish_reason": response.finish_reason,
                "response_time_ms": response.response_time_ms,
                "timestamp": response.timestamp.isoformat(),
                "cost_usd": response.cost_usd,
            }

            await self.redis.setex(
                cache_key,
                self.ttl,
                json.dumps(data),
            )

            self.logger.info("Cache set", extra={"cache_key": cache_key, "ttl": self.ttl})

        except Exception as error:
            self.logger.error(
                "Cache set error",
                extra={
                    "error": str(error),
                    "cache_key": cache_key,
                },
            )


class ContextManager:
    """Manages conversation context with sliding window."""

    def __init__(self, max_context_messages: int = 10, max_context_tokens: int = 4000):
        """
        Initialize context manager.

        Args:
            max_context_messages: Maximum number of messages to keep in context
            max_context_tokens: Maximum total tokens in context (rough estimate)
        """
        self.max_context_messages = max_context_messages
        self.max_context_tokens = max_context_tokens

    def trim_context(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
    ) -> List[Message]:
        """
        Trim context to fit within limits using sliding window.

        Args:
            messages: List of messages
            system_prompt: Optional system prompt

        Returns:
            Trimmed list of messages
        """
        # Start with all messages or trim by message count
        if len(messages) > self.max_context_messages:
            trimmed = messages[-self.max_context_messages:]
        else:
            trimmed = messages

        # Rough token estimation (4 chars per token)
        total_chars = sum(len(msg.content) for msg in trimmed)
        if system_prompt:
            total_chars += len(system_prompt)

        estimated_tokens = total_chars // 4

        # Trim based on token limit
        while estimated_tokens > self.max_context_tokens and len(trimmed) > 1:
            trimmed = trimmed[1:]  # Remove oldest message
            total_chars = sum(len(msg.content) for msg in trimmed)
            if system_prompt:
                total_chars += len(system_prompt)
            estimated_tokens = total_chars // 4

        return trimmed


class LLMService:
    """Main LLM service orchestrating all LLM operations."""

    def __init__(
        self,
        groq_provider: GroqProvider,
        redis_client: aioredis.Redis,
        logger,
        enable_caching: bool = True,
        enable_rate_limiting: bool = True,
        cache_ttl: int = 3600,
    ):
        """
        Initialize LLM service.

        Args:
            groq_provider: GROQ provider instance
            redis_client: Redis client for caching and rate limiting
            logger: Logger instance
            enable_caching: Whether to enable response caching
            enable_rate_limiting: Whether to enable rate limiting
            cache_ttl: Cache time-to-live in seconds
        """
        self.primary_provider = groq_provider
        self.logger = logger

        # Initialize components
        self.rate_limiter = RateLimiter(redis_client, logger) if enable_rate_limiting else None
        self.cache = ResponseCache(redis_client, logger, cache_ttl) if enable_caching else None
        self.context_manager = ContextManager()
        self.prompt_manager = PromptTemplateManager()

        self.logger.info(
            "LLM service initialized",
            extra={
                "provider": "groq",
                "caching_enabled": enable_caching,
                "rate_limiting_enabled": enable_rate_limiting,
            },
        )

    async def generate_completion(
        self,
        messages: List[Message],
        user_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
        trim_context: bool = True,
    ) -> LLMResponse:
        """
        Generate a completion with rate limiting, caching, and context management.

        Args:
            messages: List of conversation messages
            user_id: User identifier for rate limiting
            system_prompt: Optional system prompt
            model: Model to use (defaults to provider default)
            temperature: Temperature parameter
            max_tokens: Maximum tokens to generate
            use_cache: Whether to use cache
            trim_context: Whether to trim context

        Returns:
            LLMResponse object

        Raises:
            RateLimitError: If rate limit is exceeded
            LLMProviderError: If generation fails
        """
        # Check rate limit if enabled and user_id provided
        if self.rate_limiter and user_id:
            rate_limits = self.primary_provider.get_rate_limits()
            allowed, retry_after = await self.rate_limiter.check_rate_limit(
                user_id,
                rate_limits["requests_per_minute"],
                rate_limits["requests_per_day"],
            )

            if not allowed:
                from .base_provider import RateLimitError
                raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds.")

        # Trim context if needed
        if trim_context:
            messages = self.context_manager.trim_context(messages, system_prompt)

        # Create request
        request = LLMRequest(
            messages=messages,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Check cache if enabled
        if self.cache and use_cache:
            cached_response = await self.cache.get(request)
            if cached_response:
                self.logger.info("Using cached response", extra={"user_id": user_id})
                return cached_response

        # Generate completion
        response = await self.primary_provider.generate_completion(request)

        # Cache response if enabled
        if self.cache and use_cache:
            await self.cache.set(request, response)

        # Log usage
        if user_id:
            self.logger.info(
                "LLM completion generated",
                extra={
                    "user_id": user_id,
                    "model": response.model,
                    "tokens_used": response.tokens_used,
                    "cost_usd": response.cost_usd,
                    "cached": response.cached,
                },
            )

        return response

    async def get_user_usage(self, user_id: str) -> Dict[str, Any]:
        """
        Get usage statistics for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with usage statistics
        """
        if not self.rate_limiter:
            return {}

        usage = await self.rate_limiter.get_usage(user_id)
        rate_limits = self.primary_provider.get_rate_limits()

        return {
            **usage,
            "limits": rate_limits,
        }

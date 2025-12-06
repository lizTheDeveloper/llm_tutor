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

    # ===================================================================
    # EXERCISE-SPECIFIC METHODS
    # ===================================================================

    async def generate_exercise(
        self,
        user_id: str,
        language: str,
        skill_level: str,
        interests: str,
        recent_topics: List[str],
        difficulty: str,
        estimated_time: int = 30,
    ) -> Dict[str, Any]:
        """
        Generate a personalized coding exercise using LLM.

        Args:
            user_id: User identifier for rate limiting
            language: Programming language
            skill_level: User's skill level (beginner, intermediate, advanced)
            interests: User's interests
            recent_topics: Recently covered topics to avoid repetition
            difficulty: Target difficulty level
            estimated_time: Estimated completion time in minutes

        Returns:
            Dictionary with exercise data:
            {
                "title": str,
                "description": str,
                "objectives": List[str],
                "requirements": str,
                "example_input": Optional[str],
                "example_output": Optional[str],
                "hints": List[str],
                "test_cases": Optional[List[Dict]]
            }
        """
        from .prompt_templates import PromptType

        # Build user prompt with context
        user_prompt = self.prompt_manager.build_prompt(
            PromptType.EXERCISE_GENERATION,
            language=language,
            skill_level=skill_level,
            interests=interests,
            recent_topics=", ".join(recent_topics) if recent_topics else "None",
            difficulty=difficulty,
            estimated_time=estimated_time,
        )

        # Get system prompt
        system_prompt = self.prompt_manager.get_system_prompt(PromptType.EXERCISE_GENERATION)

        # Add structured output format to prompt
        user_prompt += """

Return the exercise in the following JSON format:
{
    "title": "Exercise title",
    "description": "Detailed description of the exercise",
    "objectives": ["Learning objective 1", "Learning objective 2"],
    "requirements": "What the student needs to implement",
    "example_input": "Example input (if applicable)",
    "example_output": "Expected output (if applicable)",
    "hints": ["Hint 1", "Hint 2"],
    "test_cases": [{"input": "...", "expected_output": "..."}]
}

Ensure all fields are filled appropriately for a {difficulty} level {language} exercise.""".format(
            difficulty=difficulty,
            language=language,
        )

        # Generate completion
        messages = [Message(role="user", content=user_prompt)]
        response = await self.generate_completion(
            messages=messages,
            user_id=user_id,
            system_prompt=system_prompt,
            temperature=0.8,  # Higher creativity for exercise generation
            max_tokens=2000,
        )

        # Parse JSON response
        try:
            # Try to extract JSON from markdown code blocks if present
            content = response.content.strip()
            if "```json" in content:
                # Extract JSON from code block
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                # Extract from generic code block
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            exercise_data = json.loads(content)

            # Validate required fields
            required_fields = ["title", "description", "objectives", "requirements"]
            for field in required_fields:
                if field not in exercise_data:
                    self.logger.warning(
                        f"Missing required field in exercise generation: {field}",
                        extra={"user_id": user_id, "content": content}
                    )
                    exercise_data[field] = ""

            return exercise_data

        except json.JSONDecodeError as error:
            self.logger.error(
                "Failed to parse exercise JSON",
                extra={
                    "error": str(error),
                    "content": response.content,
                    "user_id": user_id,
                }
            )
            # Return a fallback exercise structure
            return {
                "title": "Custom Exercise",
                "description": response.content,
                "objectives": [],
                "requirements": "See description",
                "example_input": None,
                "example_output": None,
                "hints": [],
                "test_cases": None,
            }

    async def generate_hint(
        self,
        user_id: str,
        exercise_description: str,
        student_code: Optional[str],
        student_question: Optional[str],
        skill_level: str,
        hints_count: int,
    ) -> str:
        """
        Generate a contextual hint for an exercise without revealing the solution.

        Args:
            user_id: User identifier for rate limiting
            exercise_description: The exercise description
            student_code: Student's current code (if any)
            student_question: Student's specific question (if any)
            skill_level: User's skill level
            hints_count: Number of hints already given

        Returns:
            Hint text as string
        """
        from .prompt_templates import PromptType

        # Build context
        user_prompt = self.prompt_manager.build_prompt(
            PromptType.HINT_GENERATION,
            exercise_description=exercise_description,
            student_code=student_code or "No code submitted yet",
            student_question=student_question or "General hint request",
            skill_level=skill_level,
            hints_count=hints_count,
        )

        # Get system prompt
        system_prompt = self.prompt_manager.get_system_prompt(PromptType.HINT_GENERATION)

        # Add guidance based on hint count
        if hints_count == 0:
            user_prompt += "\n\nThis is the first hint. Be subtle and guide with questions."
        elif hints_count == 1:
            user_prompt += "\n\nThis is the second hint. Be more specific but don't give away the solution."
        else:
            user_prompt += "\n\nThis is hint #{hints_count}. The student is struggling. Provide more concrete guidance but still encourage them to think.".format(hints_count=hints_count + 1)

        # Generate completion
        messages = [Message(role="user", content=user_prompt)]
        response = await self.generate_completion(
            messages=messages,
            user_id=user_id,
            system_prompt=system_prompt,
            temperature=0.7,  # Balanced creativity
            max_tokens=500,
        )

        return response.content

    async def evaluate_submission(
        self,
        user_id: str,
        exercise_description: str,
        student_code: str,
        skill_level: str,
        learning_style: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a student's code submission and provide feedback.

        Args:
            user_id: User identifier for rate limiting
            exercise_description: The exercise description
            student_code: Student's submitted code
            skill_level: User's skill level
            learning_style: User's preferred learning style (optional)

        Returns:
            Dictionary with evaluation results:
            {
                "is_correct": bool,
                "score": int (0-100),
                "feedback": str,
                "strengths": List[str],
                "improvements": List[str],
                "next_steps": List[str]
            }
        """
        from .prompt_templates import PromptType

        # Build evaluation prompt
        criteria = """
1. Correctness: Does the code solve the problem correctly?
2. Code quality: Is the code clean, readable, and well-structured?
3. Best practices: Does it follow language best practices?
4. Efficiency: Is the solution reasonably efficient?
5. Edge cases: Does it handle edge cases properly?
"""

        user_prompt = self.prompt_manager.build_prompt(
            PromptType.FEEDBACK_GENERATION,
            exercise_description=exercise_description,
            student_code=student_code,
            criteria=criteria,
            skill_level=skill_level,
            learning_style=learning_style or "balanced",
        )

        # Request structured evaluation
        user_prompt += """

Please evaluate the submission and return your assessment in the following JSON format:
{
    "is_correct": true/false,
    "score": 0-100,
    "feedback": "Overall feedback paragraph",
    "strengths": ["What they did well 1", "What they did well 2"],
    "improvements": ["Area for improvement 1", "Area for improvement 2"],
    "next_steps": ["Suggested next step 1", "Suggested next step 2"]
}

Be encouraging and constructive in your feedback."""

        # Get system prompt
        system_prompt = self.prompt_manager.get_system_prompt(PromptType.FEEDBACK_GENERATION)

        # Generate completion
        messages = [Message(role="user", content=user_prompt)]
        response = await self.generate_completion(
            messages=messages,
            user_id=user_id,
            system_prompt=system_prompt,
            temperature=0.6,  # Lower temperature for consistent evaluation
            max_tokens=1000,
        )

        # Parse JSON response
        try:
            # Try to extract JSON from markdown code blocks if present
            content = response.content.strip()
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            evaluation = json.loads(content)

            # Validate and set defaults
            if "is_correct" not in evaluation:
                evaluation["is_correct"] = False
            if "score" not in evaluation:
                evaluation["score"] = 0
            if "feedback" not in evaluation:
                evaluation["feedback"] = response.content
            if "strengths" not in evaluation:
                evaluation["strengths"] = []
            if "improvements" not in evaluation:
                evaluation["improvements"] = []
            if "next_steps" not in evaluation:
                evaluation["next_steps"] = []

            return evaluation

        except json.JSONDecodeError as error:
            self.logger.error(
                "Failed to parse evaluation JSON",
                extra={
                    "error": str(error),
                    "content": response.content,
                    "user_id": user_id,
                }
            )
            # Return a fallback evaluation
            return {
                "is_correct": False,
                "score": 50,
                "feedback": response.content,
                "strengths": [],
                "improvements": [],
                "next_steps": [],
            }

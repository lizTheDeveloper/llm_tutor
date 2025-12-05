"""
Embedding generation service for creating vector embeddings.
Uses GROQ LLM service for generating embeddings from text.
"""
import json
import hashlib
import numpy as np
from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
import redis.asyncio as aioredis

from ..utils.logger import get_logger
from ..config import settings

logger = get_logger(__name__)


class EmbeddingService:
    """
    Service for generating vector embeddings from text using OpenAI API.
    Provides caching and batch processing capabilities.
    """

    def __init__(
        self,
        redis_client: Optional[aioredis.Redis] = None,
        cache_ttl: int = 86400  # 24 hours
    ):
        """
        Initialize embedding service.

        Args:
            redis_client: Optional Redis client for caching embeddings
            cache_ttl: Cache time-to-live in seconds
        """
        self.redis = redis_client
        self.cache_ttl = cache_ttl
        self.embedding_model = "text-embedding-ada-002"
        self.embedding_dimension = 1536

        # Initialize OpenAI client with API key from settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

        logger.info(
            "EmbeddingService initialized",
            extra={
                "model": self.embedding_model,
                "dimension": self.embedding_dimension,
                "caching_enabled": self.redis is not None,
                "api_key_configured": self.client is not None
            }
        )

    async def generate_text_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector from text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        if not text or text.strip() == "":
            logger.warning("Empty text provided for embedding generation")
            return None

        # Check cache first
        if self.redis:
            cached = await self._get_cached_embedding(text)
            if cached:
                logger.debug("Retrieved embedding from cache")
                return cached

        try:
            # Generate embedding using OpenAI API
            embedding = await self._call_embedding_api(text)

            # Cache the result
            if self.redis and embedding:
                await self._cache_embedding(text, embedding)

            return embedding

        except Exception as error:
            logger.error(
                "Failed to generate embedding",
                extra={"error": str(error), "text_length": len(text)},
                exc_info=True
            )
            return None

    async def generate_profile_embedding(self, user_data: Dict[str, Any]) -> Optional[List[float]]:
        """
        Generate embedding from user profile data.

        Args:
            user_data: Dictionary containing user profile attributes

        Returns:
            Embedding vector or None
        """
        # Create a structured text representation of the profile
        profile_text = self._user_data_to_text(user_data)

        logger.debug(
            "Generating profile embedding",
            extra={"profile_text_length": len(profile_text)}
        )

        return await self.generate_text_embedding(profile_text)

    async def generate_interaction_embedding(self, interaction_data: Dict[str, Any]) -> Optional[List[float]]:
        """
        Generate embedding from interaction log data.

        Args:
            interaction_data: Dictionary containing interaction details

        Returns:
            Embedding vector or None
        """
        # Create text representation of interaction
        interaction_text = self._interaction_data_to_text(interaction_data)

        logger.debug(
            "Generating interaction embedding",
            extra={"interaction_type": interaction_data.get("interaction_type")}
        )

        return await self.generate_text_embedding(interaction_text)

    async def generate_learning_pattern_embedding(self, learning_history: Dict[str, Any]) -> Optional[List[float]]:
        """
        Generate embedding from learning history and patterns.

        Args:
            learning_history: Dictionary containing learning patterns and metrics

        Returns:
            Embedding vector or None
        """
        # Create text representation of learning patterns
        pattern_text = self._learning_history_to_text(learning_history)

        logger.debug(
            "Generating learning pattern embedding",
            extra={"pattern_text_length": len(pattern_text)}
        )

        return await self.generate_text_embedding(pattern_text)

    async def batch_generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not self.client:
            logger.error("OpenAI client not configured for batch embedding generation")
            return []

        try:
            # Filter out empty texts
            valid_texts = [t for t in texts if t and t.strip()]

            if not valid_texts:
                return []

            # Call API with batch
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=valid_texts
            )

            embeddings = [item.embedding for item in response.data]

            logger.info(
                "Batch embeddings generated",
                extra={"count": len(embeddings)}
            )

            return embeddings

        except Exception as error:
            logger.error(
                "Failed to generate batch embeddings",
                extra={"error": str(error), "count": len(texts)},
                exc_info=True
            )
            return []

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two embedding vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        if not vec1 or not vec2:
            return 0.0

        # Convert to numpy arrays for efficient computation
        v1 = np.array(vec1)
        v2 = np.array(vec2)

        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        # Ensure result is between 0 and 1
        return float(max(0.0, min(1.0, similarity)))

    async def _call_embedding_api(self, text: str) -> List[float]:
        """
        Call OpenAI API to generate embedding.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            Exception: If API call fails
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured")

        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=text
        )

        embedding = response.data[0].embedding

        logger.debug(
            "Embedding generated via API",
            extra={"text_length": len(text), "embedding_dimension": len(embedding)}
        )

        return embedding

    async def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get cached embedding from Redis."""
        if not self.redis:
            return None

        cache_key = self._generate_cache_key(text)

        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as error:
            logger.warning(
                "Failed to retrieve cached embedding",
                extra={"error": str(error)}
            )

        return None

    async def _cache_embedding(self, text: str, embedding: List[float]) -> None:
        """Cache embedding in Redis."""
        if not self.redis:
            return

        cache_key = self._generate_cache_key(text)

        try:
            await self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(embedding)
            )
        except Exception as error:
            logger.warning(
                "Failed to cache embedding",
                extra={"error": str(error)}
            )

    def _generate_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return f"embedding:{self.embedding_model}:{text_hash}"

    def _user_data_to_text(self, user_data: Dict[str, Any]) -> str:
        """Convert user profile data to structured text."""
        parts = []

        if user_data.get("programming_language"):
            parts.append(f"Programming language: {user_data['programming_language']}")

        if user_data.get("skill_level"):
            parts.append(f"Skill level: {user_data['skill_level']}")

        if user_data.get("career_goals"):
            parts.append(f"Career goals: {user_data['career_goals']}")

        if user_data.get("learning_style"):
            parts.append(f"Learning style: {user_data['learning_style']}")

        if user_data.get("bio"):
            parts.append(f"Bio: {user_data['bio']}")

        return " | ".join(parts)

    def _interaction_data_to_text(self, interaction_data: Dict[str, Any]) -> str:
        """Convert interaction data to structured text."""
        parts = []

        parts.append(f"Type: {interaction_data.get('interaction_type', 'unknown')}")

        if interaction_data.get("context_type"):
            parts.append(f"Context: {interaction_data['context_type']}")

        if interaction_data.get("exercise_title"):
            parts.append(f"Exercise: {interaction_data['exercise_title']}")

        if "success" in interaction_data:
            parts.append(f"Success: {interaction_data['success']}")

        if "time_taken_seconds" in interaction_data:
            parts.append(f"Time: {interaction_data['time_taken_seconds']}s")

        if "hints_used" in interaction_data:
            parts.append(f"Hints: {interaction_data['hints_used']}")

        if "code_quality_score" in interaction_data:
            parts.append(f"Quality: {interaction_data['code_quality_score']}")

        return " | ".join(parts)

    def _learning_history_to_text(self, learning_history: Dict[str, Any]) -> str:
        """Convert learning history to structured text."""
        parts = []

        if learning_history.get("topic_mastery"):
            mastery = learning_history["topic_mastery"]
            mastery_text = ", ".join([f"{topic}: {score:.2f}" for topic, score in mastery.items()])
            parts.append(f"Topic mastery: {mastery_text}")

        if learning_history.get("identified_strengths"):
            strengths = ", ".join(learning_history["identified_strengths"])
            parts.append(f"Strengths: {strengths}")

        if learning_history.get("identified_weaknesses"):
            weaknesses = ", ".join(learning_history["identified_weaknesses"])
            parts.append(f"Weaknesses: {weaknesses}")

        if learning_history.get("learning_pace"):
            parts.append(f"Learning pace: {learning_history['learning_pace']}")

        if "average_completion_time_minutes" in learning_history:
            parts.append(f"Avg completion time: {learning_history['average_completion_time_minutes']} min")

        if "average_grade" in learning_history:
            parts.append(f"Avg grade: {learning_history['average_grade']}")

        return " | ".join(parts)

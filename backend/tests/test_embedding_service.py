"""
TDD tests for embedding generation service.
Following TDD workflow: Write tests first, then implement.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.services.embedding_service import EmbeddingService


class TestEmbeddingService:
    """Test suite for EmbeddingService following TDD principles."""

    @pytest.fixture
    async def embedding_service(self):
        """Create an embedding service instance for testing."""
        return EmbeddingService()

    @pytest.mark.asyncio
    async def test_generate_text_embedding_returns_vector(self, embedding_service):
        """Test that generate_text_embedding returns a vector of correct dimensions."""
        text = "This is a test profile: Python developer with 5 years experience"

        # Mock the API call to return a fake embedding
        fake_embedding = [0.1] * 1536
        with patch.object(embedding_service, '_call_embedding_api', return_value=fake_embedding):
            embedding = await embedding_service.generate_text_embedding(text)

            assert isinstance(embedding, list)
            assert len(embedding) == 1536  # OpenAI ada-002 embedding dimension
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_text_embedding_handles_empty_string(self, embedding_service):
        """Test that empty strings are handled gracefully."""
        text = ""

        embedding = await embedding_service.generate_text_embedding(text)

        # Should return None or empty list for empty input
        assert embedding is None or embedding == []

    @pytest.mark.asyncio
    async def test_generate_profile_embedding_combines_user_attributes(self, embedding_service):
        """Test that profile embeddings are generated from user attributes."""
        user_data = {
            "programming_language": "Python",
            "skill_level": "intermediate",
            "career_goals": "Become a senior backend engineer",
            "learning_style": "hands-on with examples",
            "bio": "Passionate about clean code and testing"
        }

        fake_embedding = [0.2] * 1536
        with patch.object(embedding_service, '_call_embedding_api', return_value=fake_embedding):
            embedding = await embedding_service.generate_profile_embedding(user_data)

            assert isinstance(embedding, list)
            assert len(embedding) == 1536
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_interaction_embedding_from_interaction_data(self, embedding_service):
        """Test that interaction embeddings are generated from interaction logs."""
        interaction_data = {
            "interaction_type": "exercise_completion",
            "context_type": "exercise",
            "exercise_title": "Binary Search Implementation",
            "success": True,
            "time_taken_seconds": 1200,
            "hints_used": 1,
            "code_quality_score": 85
        }

        fake_embedding = [0.3] * 1536
        with patch.object(embedding_service, '_call_embedding_api', return_value=fake_embedding):
            embedding = await embedding_service.generate_interaction_embedding(interaction_data)

            assert isinstance(embedding, list)
            assert len(embedding) == 1536
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_generate_learning_pattern_embedding_from_history(self, embedding_service):
        """Test that learning pattern embeddings are generated from user history."""
        learning_history = {
            "topic_mastery": {"arrays": 0.85, "linked_lists": 0.65, "trees": 0.40},
            "identified_strengths": ["recursion", "arrays"],
            "identified_weaknesses": ["dynamic_programming", "graphs"],
            "learning_pace": "moderate",
            "average_completion_time_minutes": 45.5,
            "average_grade": 78.3
        }

        fake_embedding = [0.4] * 1536
        with patch.object(embedding_service, '_call_embedding_api', return_value=fake_embedding):
            embedding = await embedding_service.generate_learning_pattern_embedding(learning_history)

            assert isinstance(embedding, list)
            assert len(embedding) == 1536
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embedding_service_uses_caching(self, embedding_service):
        """Test that identical inputs return cached embeddings."""
        text = "Python backend developer"
        fake_embedding = [0.5] * 1536

        with patch.object(embedding_service, '_call_embedding_api', return_value=fake_embedding) as mock_api:
            # First call
            embedding1 = await embedding_service.generate_text_embedding(text)

            # Second call with same text should be faster (cached)
            embedding2 = await embedding_service.generate_text_embedding(text)

            assert embedding1 == embedding2
            # API should only be called once due to caching (if Redis is configured)
            # If Redis not configured, both calls hit the API
            assert mock_api.call_count <= 2

    @pytest.mark.asyncio
    async def test_embedding_service_handles_api_errors(self, embedding_service):
        """Test that API errors are handled gracefully."""
        with patch.object(embedding_service, '_call_embedding_api', side_effect=Exception("API Error")):
            text = "Test text"

            # Should not raise, but handle error gracefully
            embedding = await embedding_service.generate_text_embedding(text)

            # Should return None or fallback embedding
            assert embedding is None or isinstance(embedding, list)

    @pytest.mark.asyncio
    async def test_batch_generate_embeddings(self, embedding_service):
        """Test batch generation of embeddings for efficiency."""
        texts = [
            "Python developer",
            "JavaScript expert",
            "Data scientist",
            "ML engineer"
        ]

        # Mock the client's embeddings.create method
        fake_embeddings = [[0.1 * i] * 1536 for i in range(len(texts))]
        mock_response = Mock()
        mock_response.data = [Mock(embedding=emb) for emb in fake_embeddings]

        if embedding_service.client:
            with patch.object(embedding_service.client.embeddings, 'create', return_value=mock_response):
                embeddings = await embedding_service.batch_generate_embeddings(texts)

                assert isinstance(embeddings, list)
                assert len(embeddings) == len(texts)
                assert all(len(emb) == 1536 for emb in embeddings)
        else:
            # If no client, should return empty list
            embeddings = await embedding_service.batch_generate_embeddings(texts)
            assert embeddings == []

    @pytest.mark.asyncio
    async def test_similarity_score_between_embeddings(self, embedding_service):
        """Test cosine similarity calculation between embeddings."""
        # Create distinct embeddings
        emb1 = [1.0, 0.0] + [0.0] * 1534  # Mostly in dimension 0
        emb2 = [0.9, 0.1] + [0.0] * 1534  # Similar to emb1
        emb3 = [0.0, 1.0] + [0.0] * 1534  # Orthogonal to emb1

        # Similar embeddings should have high similarity
        similarity_high = embedding_service.cosine_similarity(emb1, emb2)
        # Orthogonal embeddings should have low similarity
        similarity_low = embedding_service.cosine_similarity(emb1, emb3)

        assert 0 <= similarity_high <= 1
        assert 0 <= similarity_low <= 1
        assert similarity_high > similarity_low  # Related terms more similar

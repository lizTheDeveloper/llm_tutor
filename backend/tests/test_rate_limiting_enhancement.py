"""
Integration tests for SEC-3: Rate Limiting Enhancement.

This test suite verifies:
1. Tiered rate limiting based on user role
2. Cost tracking for LLM operations
3. Per-endpoint rate limits for expensive operations
4. Daily cost limit enforcement
5. Clear error messages when limits exceeded

Test Strategy:
- Test real interactions with rate limiting decorator
- Mock only external LLM APIs (not internal components)
- Verify Redis-based rate limit tracking
- Test all LLM endpoints (chat, exercise generation, hints)
- Verify cost accumulation and limits
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from src.middleware.rate_limiter import rate_limit, get_client_identifier, check_rate_limit
from src.models.user import User, UserRole
from src.utils.redis_client import get_redis
import time


class TestTieredRateLimiting:
    """Tests for tiered rate limiting based on user role."""

    @pytest.mark.asyncio
    async def test_student_chat_rate_limit(self, test_client, auth_headers, db_session):
        """Test chat endpoint rate limiting for student users."""
        # Create student user
        user = User(
            email="student@test.com",
            password_hash="hash",
            email_verified=True,
            role=UserRole.STUDENT,
            onboarding_completed=True
        )
        db_session.add(user)
        await db_session.commit()

        # Mock LLM response
        with patch('src.services.llm.llm_service.LLMService.generate_completion') as mock_llm:
            mock_llm.return_value = Mock(
                content="Test response",
                model="llama-3.3-70b-versatile",
                tokens_used=100,
                finish_reason="stop"
            )

            # Make requests up to student limit (should be lower than admin)
            # Students: 10 chat requests per minute
            for i in range(10):
                response = await test_client.post(
                    "/api/chat/message",
                    json={"message": f"Test message {i}"},
                    headers=auth_headers
                )
                assert response.status_code in [200, 201], f"Request {i} failed"

            # 11th request should be rate limited
            response = await test_client.post(
                "/api/chat/message",
                json={"message": "Should be rate limited"},
                headers=auth_headers
            )
            assert response.status_code == 429
            data = await response.get_json()
            assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_admin_higher_rate_limit(self, test_client, db_session):
        """Test that admin users have higher rate limits than students."""
        # Create admin user
        admin = User(
            email="admin@test.com",
            password_hash="hash",
            email_verified=True,
            role=UserRole.ADMIN,
            onboarding_completed=True
        )
        db_session.add(admin)
        await db_session.commit()

        # Generate admin auth token
        from src.services.auth_service import AuthService
        auth_service = AuthService(db_session)
        tokens = await auth_service.create_access_token(admin.id)
        admin_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        with patch('src.services.llm.llm_service.LLMService.generate_completion') as mock_llm:
            mock_llm.return_value = Mock(
                content="Test response",
                model="llama-3.3-70b-versatile",
                tokens_used=100,
                finish_reason="stop"
            )

            # Admins: 30 chat requests per minute (3x student limit)
            for i in range(30):
                response = await test_client.post(
                    "/api/chat/message",
                    json={"message": f"Admin test {i}"},
                    headers=admin_headers
                )
                assert response.status_code in [200, 201], f"Admin request {i} should succeed"

            # 31st request should be rate limited
            response = await test_client.post(
                "/api/chat/message",
                json={"message": "Should be rate limited"},
                headers=admin_headers
            )
            assert response.status_code == 429


class TestLLMEndpointRateLimits:
    """Tests for per-endpoint rate limits on expensive LLM operations."""

    @pytest.mark.asyncio
    async def test_exercise_generation_rate_limit(self, test_client, auth_headers, db_session):
        """Test exercise generation endpoint has stricter rate limiting."""
        # Exercise generation: 3 per hour (expensive operation)
        with patch('src.services.exercise_service.ExerciseService.generate_personalized_exercise') as mock_gen:
            mock_gen.return_value = Mock(
                id=1,
                title="Test Exercise",
                description="Test",
                instructions="Test",
                starter_code="# test",
                exercise_type="ALGORITHM",
                difficulty="MEDIUM",
                programming_language="python",
                topics=["arrays"],
                test_cases=[],
                generated_by_ai=True
            )

            # Make 3 requests (should succeed)
            for i in range(3):
                response = await test_client.post(
                    "/api/exercises/generate",
                    json={
                        "programming_language": "python",
                        "difficulty": "MEDIUM",
                        "topics": ["arrays"]
                    },
                    headers=auth_headers
                )
                assert response.status_code in [200, 201], f"Request {i} should succeed"

            # 4th request should be rate limited
            response = await test_client.post(
                "/api/exercises/generate",
                json={
                    "programming_language": "python",
                    "difficulty": "MEDIUM",
                    "topics": ["arrays"]
                },
                headers=auth_headers
            )
            assert response.status_code == 429
            data = await response.get_json()
            assert "hour" in data["error"]["message"].lower() or "3" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_hint_request_rate_limit(self, test_client, auth_headers, db_session):
        """Test hint request endpoint has moderate rate limiting."""
        # Hints: 5 per hour (moderate cost)
        with patch('src.services.exercise_service.ExerciseService.generate_hint') as mock_hint:
            mock_hint.return_value = "Test hint"

            # Make 5 requests (should succeed)
            for i in range(5):
                response = await test_client.post(
                    f"/api/exercises/1/hint",
                    json={"current_code": "# test code"},
                    headers=auth_headers
                )
                # May fail due to exercise not existing, but not due to rate limit
                if response.status_code == 429:
                    pytest.fail(f"Request {i} was rate limited (should allow 5)")

            # 6th request should be rate limited
            response = await test_client.post(
                f"/api/exercises/1/hint",
                json={"current_code": "# test code"},
                headers=auth_headers
            )
            assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_chat_stream_rate_limit(self, test_client, auth_headers):
        """Test streaming chat endpoint has same limits as regular chat."""
        # Chat stream: 10 per minute for students
        with patch('src.services.llm.llm_service.LLMService.generate_completion_stream') as mock_stream:
            async def mock_generator():
                yield "chunk1"
                yield "chunk2"
            mock_stream.return_value = mock_generator()

            # Make 10 requests
            for i in range(10):
                response = await test_client.post(
                    "/api/chat/stream",
                    json={"message": f"Stream test {i}"},
                    headers=auth_headers
                )
                assert response.status_code in [200, 201], f"Request {i} should succeed"

            # 11th request should be rate limited
            response = await test_client.post(
                "/api/chat/stream",
                json={"message": "Should be rate limited"},
                headers=auth_headers
            )
            assert response.status_code == 429


class TestCostTracking:
    """Tests for LLM cost tracking and daily limits."""

    @pytest.mark.asyncio
    async def test_cost_accumulation(self, db_session):
        """Test that LLM costs accumulate correctly in Redis."""
        redis = get_redis()
        user_id = 123
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cost_key = f"llm_cost:daily:{user_id}:{today}"

        # Clear existing cost
        await redis.async_client.delete(cost_key)

        # Track multiple LLM calls with different costs
        from src.services.llm.cost_tracker import CostTracker
        tracker = CostTracker(redis.async_client)

        await tracker.track_cost(user_id, "chat", 0.05)  # $0.05
        await tracker.track_cost(user_id, "exercise_generation", 0.15)  # $0.15
        await tracker.track_cost(user_id, "hint", 0.03)  # $0.03

        # Total should be $0.23
        total_cost = await tracker.get_daily_cost(user_id)
        assert abs(total_cost - 0.23) < 0.001  # Float comparison with tolerance

    @pytest.mark.asyncio
    async def test_daily_cost_limit_enforcement(self, test_client, auth_headers, db_session):
        """Test that daily cost limits are enforced."""
        # Set daily cost limit to $1.00 for students
        redis = get_redis()
        user_id = 1  # Assume auth_headers is for user_id=1
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cost_key = f"llm_cost:daily:{user_id}:{today}"

        # Simulate user already at $0.95 cost
        await redis.async_client.set(cost_key, "0.95")
        await redis.async_client.expire(cost_key, 86400)

        with patch('src.services.llm.llm_service.LLMService.generate_completion') as mock_llm:
            # Mock response with cost that would exceed limit
            mock_llm.return_value = Mock(
                content="Response",
                model="llama-3.3-70b-versatile",
                tokens_used=1000,  # High token count = high cost
                finish_reason="stop"
            )

            # Request should be blocked due to cost limit
            response = await test_client.post(
                "/api/chat/message",
                json={"message": "This would exceed cost limit"},
                headers=auth_headers
            )
            assert response.status_code == 429
            data = await response.get_json()
            assert "cost limit" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_cost_tracking_metadata(self, db_session):
        """Test that cost metadata is stored with each operation."""
        redis = get_redis()
        user_id = 456
        operation_id = "op_123"

        from src.services.llm.cost_tracker import CostTracker
        tracker = CostTracker(redis.async_client)

        # Track operation with metadata
        await tracker.track_operation(
            user_id=user_id,
            operation_id=operation_id,
            operation_type="exercise_generation",
            cost=0.15,
            tokens_used=500,
            model="llama-3.3-70b-versatile"
        )

        # Retrieve operation metadata
        metadata = await tracker.get_operation_metadata(operation_id)
        assert metadata["user_id"] == user_id
        assert metadata["operation_type"] == "exercise_generation"
        assert abs(metadata["cost"] - 0.15) < 0.001
        assert metadata["tokens_used"] == 500
        assert metadata["model"] == "llama-3.3-70b-versatile"


class TestRateLimitHeaders:
    """Tests for rate limit response headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, test_client, auth_headers):
        """Test that rate limit headers are included in responses."""
        with patch('src.services.llm.llm_service.LLMService.generate_completion') as mock_llm:
            mock_llm.return_value = Mock(
                content="Response",
                model="llama-3.3-70b-versatile",
                tokens_used=100,
                finish_reason="stop"
            )

            response = await test_client.post(
                "/api/chat/message",
                json={"message": "Test"},
                headers=auth_headers
            )

            # Check for X-RateLimit headers
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_retry_after_header_on_limit(self, test_client, auth_headers):
        """Test that Retry-After header is present when rate limited."""
        with patch('src.services.llm.llm_service.LLMService.generate_completion') as mock_llm:
            mock_llm.return_value = Mock(
                content="Response",
                model="llama-3.3-70b-versatile",
                tokens_used=100,
                finish_reason="stop"
            )

            # Exhaust rate limit
            for _ in range(10):
                await test_client.post(
                    "/api/chat/message",
                    json={"message": "Test"},
                    headers=auth_headers
                )

            # Next request should include Retry-After
            response = await test_client.post(
                "/api/chat/message",
                json={"message": "Test"},
                headers=auth_headers
            )
            assert response.status_code == 429
            assert "Retry-After" in response.headers
            retry_after = int(response.headers["Retry-After"])
            assert 0 < retry_after <= 60  # Should be within 1 minute


class TestRateLimitConfiguration:
    """Tests for rate limit configuration and tiering."""

    @pytest.mark.asyncio
    async def test_rate_limits_from_config(self):
        """Test that rate limits are loaded from configuration."""
        from src.config import settings

        # Verify rate limit settings exist
        assert hasattr(settings, "rate_limit_chat_per_minute_student")
        assert hasattr(settings, "rate_limit_chat_per_minute_admin")
        assert hasattr(settings, "rate_limit_exercise_generation_per_hour")
        assert hasattr(settings, "rate_limit_hint_per_hour")
        assert hasattr(settings, "daily_cost_limit_student")
        assert hasattr(settings, "daily_cost_limit_admin")

    @pytest.mark.asyncio
    async def test_tiered_limits_by_role(self, db_session):
        """Test that different user roles have different rate limits."""
        from src.middleware.rate_limiter import get_rate_limit_for_user

        # Create users with different roles
        student = User(
            id=1,
            email="student@test.com",
            role=UserRole.STUDENT,
            email_verified=True
        )
        admin = User(
            id=2,
            email="admin@test.com",
            role=UserRole.ADMIN,
            email_verified=True
        )

        db_session.add_all([student, admin])
        await db_session.commit()

        # Get rate limits for each role
        student_limits = await get_rate_limit_for_user(student.id, "chat")
        admin_limits = await get_rate_limit_for_user(admin.id, "chat")

        # Admin should have higher limits
        assert admin_limits["per_minute"] > student_limits["per_minute"]
        assert admin_limits["per_day"] > student_limits["per_day"]


class TestCostAlerts:
    """Tests for cost monitoring and alerting."""

    @pytest.mark.asyncio
    async def test_cost_threshold_warning(self, db_session):
        """Test that warnings are logged when approaching cost limits."""
        redis = get_redis()
        user_id = 789
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cost_key = f"llm_cost:daily:{user_id}:{today}"

        # Set cost to 90% of limit ($0.90 of $1.00)
        await redis.async_client.set(cost_key, "0.90")

        from src.services.llm.cost_tracker import CostTracker
        tracker = CostTracker(redis.async_client)

        # Check if warning threshold exceeded
        is_warning = await tracker.check_cost_warning(user_id, limit=1.00, threshold=0.8)
        assert is_warning is True

        # Add more cost to trigger alert
        await tracker.track_cost(user_id, "chat", 0.05)

        # Should now be at 95%, still warning
        is_warning = await tracker.check_cost_warning(user_id, limit=1.00, threshold=0.8)
        assert is_warning is True

    @pytest.mark.asyncio
    async def test_cost_limit_blocks_requests(self, test_client, auth_headers, db_session):
        """Test that exceeding cost limit blocks further LLM requests."""
        redis = get_redis()
        user_id = 1
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cost_key = f"llm_cost:daily:{user_id}:{today}"

        # Set cost to exactly at limit
        await redis.async_client.set(cost_key, "1.00")

        with patch('src.services.llm.llm_service.LLMService.generate_completion'):
            # Any LLM request should now be blocked
            response = await test_client.post(
                "/api/chat/message",
                json={"message": "Should be blocked by cost limit"},
                headers=auth_headers
            )
            assert response.status_code == 429
            data = await response.get_json()
            assert "cost limit" in data["error"]["message"].lower()

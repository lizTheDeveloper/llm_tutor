"""
Integration tests for SEC-2-AUTH: Email Verification Enforcement.

This test suite follows Test-Driven Development (TDD) principles:
1. Tests written FIRST (red phase)
2. Implementation to make tests pass (green phase)
3. Refactor as needed

Test Coverage:
- require_verified_email decorator functionality
- Email verification workflow (send, verify, resend)
- Route protection for unverified users
- Appropriate routes have email verification requirement
- Error handling and edge cases

Priority: P0 - CRITICAL BLOCKER
Requirement: REQ-AUTH-001 (email verification)
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from src.models.user import User, UserRole
from src.services.auth_service import AuthService
from src.utils.redis_client import get_redis
import json


class TestRequireVerifiedEmailDecorator:
    """Test the require_verified_email decorator implementation."""

    @pytest.mark.asyncio
    async def test_decorator_blocks_unverified_user(
        self, client, test_user_unverified, auth_headers_unverified,
        mock_jwt_auth_factory, patched_get_session
    ):
        """
        Test that require_verified_email decorator blocks unverified users.

        Given: A user with email_verified=False
        When: User attempts to access a protected route
        Then: Request is rejected with 403 status
        """
        # Try to access a protected route (will use daily exercise endpoint)
        with mock_jwt_auth_factory(test_user_unverified):
            response = await client.get(
                "/api/exercises/daily",
                headers=auth_headers_unverified
            )

            assert response.status_code == 403
            data = await response.get_json()
            assert "email verification" in data["error"].lower()
            assert "verify your email" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_decorator_allows_verified_user(
        self, client, test_user, auth_headers
    ):
        """
        Test that require_verified_email decorator allows verified users.

        Given: A user with email_verified=True
        When: User attempts to access a protected route
        Then: Request is allowed (may fail for other reasons, but not email verification)
        """
        # Try to access a protected route
        response = await client.get(
            "/api/exercises/daily",
            headers=auth_headers
        )

        # Should NOT get 403 for email verification
        # (may get 404 or 200 depending on data, but not 403 email verification)
        assert response.status_code != 403 or "email verification" not in (await response.get_json()).get("error", "").lower()

    @pytest.mark.asyncio
    async def test_decorator_without_auth_raises_401(
        self, client
    ):
        """
        Test that require_verified_email without authentication raises 401.

        Given: No authentication token
        When: User attempts to access a protected route
        Then: Request is rejected with 401 (not 403)
        """
        response = await client.get("/api/exercises/daily")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_decorator_with_oauth_user_allows_access(
        self, client, test_user_oauth, auth_headers_oauth,
        mock_jwt_auth_factory, patched_get_session
    ):
        """
        Test that OAuth users (auto-verified) can access protected routes.

        Given: A user created via OAuth (email_verified=True by default)
        When: User attempts to access a protected route
        Then: Request is allowed
        """
        with mock_jwt_auth_factory(test_user_oauth):
            response = await client.get(
                "/api/exercises/daily",
                headers=auth_headers_oauth
            )

            # Should NOT get 403 for email verification
            assert response.status_code != 403 or "email verification" not in (await response.get_json()).get("error", "").lower()


class TestEmailVerificationWorkflow:
    """Test the complete email verification workflow."""

    @pytest.mark.asyncio
    async def test_registration_sends_verification_email(
        self, client, db_session
    ):
        """
        Test that registration automatically sends verification email.

        Given: Valid registration data
        When: User registers
        Then: Verification email is sent and token stored in Redis
        """
        registration_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "name": "New User"
        }

        response = await client.post(
            "/api/auth/register",
            json=registration_data
        )

        assert response.status_code == 201
        data = await response.get_json()
        assert "verify your email" in data["message"].lower()
        assert data["user"]["email_verified"] is False

        # Verify user created with email_verified=False
        result = await db_session.execute(
            select(User).where(User.email == "newuser@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email_verified is False

    @pytest.mark.asyncio
    async def test_verify_email_with_valid_token(
        self, client, test_user_unverified, db_session
    ):
        """
        Test email verification with valid token.

        Given: A user with unverified email and valid verification token
        When: User submits verification token
        Then: Email is marked as verified
        """
        # Create and store verification token
        token = AuthService.generate_verification_token()
        await AuthService.store_verification_token(
            test_user_unverified.email,
            token
        )

        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert "verified successfully" in data["message"].lower()
        assert data["user"]["email_verified"] is True

        # Verify in database
        await db_session.refresh(test_user_unverified)
        assert test_user_unverified.email_verified is True

    @pytest.mark.asyncio
    async def test_verify_email_with_invalid_token(
        self, client
    ):
        """
        Test email verification with invalid token.

        Given: An invalid or non-existent verification token
        When: User submits the token
        Then: Request is rejected with 400 error
        """
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": "invalid_token_12345"}
        )

        assert response.status_code == 400
        data = await response.get_json()
        assert "invalid" in data["error"].lower() or "expired" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_verify_email_with_expired_token(
        self, client, test_user_unverified
    ):
        """
        Test email verification with expired token.

        Given: A verification token that has expired
        When: User submits the token
        Then: Request is rejected with 400 error
        """
        # Create and store verification token with very short expiration
        token = AuthService.generate_verification_token()
        redis = get_redis()
        await redis.setex(
            f"verify_email:{test_user_unverified.email}",
            1,  # 1 second expiration
            token
        )

        # Wait for token to expire
        import asyncio
        await asyncio.sleep(2)

        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token}
        )

        assert response.status_code == 400
        data = await response.get_json()
        assert "expired" in data["error"].lower() or "invalid" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_verify_already_verified_email(
        self, client, test_user
    ):
        """
        Test verifying an already verified email (idempotent).

        Given: A user with already verified email
        When: User submits verification token
        Then: Returns success (idempotent operation)
        """
        # Create and store verification token
        token = AuthService.generate_verification_token()
        await AuthService.store_verification_token(
            test_user.email,
            token
        )

        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert "already verified" in data["message"].lower() or "verified successfully" in data["message"].lower()


class TestResendVerificationEmail:
    """Test the resend verification email functionality."""

    @pytest.mark.asyncio
    async def test_resend_verification_email_success(
        self, client, test_user_unverified
    ):
        """
        Test resending verification email for unverified user.

        Given: A user with unverified email
        When: User requests to resend verification email
        Then: New verification email is sent
        """
        response = await client.post(
            "/api/auth/resend-verification",
            json={"email": test_user_unverified.email}
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert "verification email sent" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_resend_verification_for_already_verified(
        self, client, test_user
    ):
        """
        Test resending verification email for already verified user.

        Given: A user with already verified email
        When: User requests to resend verification email
        Then: Returns appropriate message (email already verified)
        """
        response = await client.post(
            "/api/auth/resend-verification",
            json={"email": test_user.email}
        )

        # Should still return 200 to prevent email enumeration
        assert response.status_code == 200
        data = await response.get_json()
        # Message should be generic or indicate already verified
        assert "already verified" in data["message"].lower() or "verification email sent" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_resend_verification_for_nonexistent_user(
        self, client
    ):
        """
        Test resending verification email for non-existent user.

        Given: An email address not in the system
        When: Request to resend verification email
        Then: Returns generic success message (prevent email enumeration)
        """
        response = await client.post(
            "/api/auth/resend-verification",
            json={"email": "nonexistent@example.com"}
        )

        # Should return 200 to prevent email enumeration
        assert response.status_code == 200
        data = await response.get_json()
        assert "verification email sent" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_resend_verification_rate_limiting(
        self, client, test_user_unverified
    ):
        """
        Test rate limiting on resend verification email.

        Given: Multiple rapid requests to resend verification
        When: User exceeds rate limit
        Then: Subsequent requests are rate limited
        """
        # Make multiple requests
        for i in range(6):  # Assuming rate limit is 5 per minute
            response = await client.post(
                "/api/auth/resend-verification",
                json={"email": test_user_unverified.email}
            )

            if i < 5:
                assert response.status_code == 200
            else:
                # 6th request should be rate limited
                assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_resend_verification_missing_email(
        self, client
    ):
        """
        Test resend verification with missing email parameter.

        Given: Request without email parameter
        When: User requests to resend verification
        Then: Returns 400 validation error
        """
        response = await client.post(
            "/api/auth/resend-verification",
            json={}
        )

        assert response.status_code == 400
        data = await response.get_json()
        assert "email" in data["error"].lower()


class TestProtectedRoutes:
    """Test that appropriate routes require email verification."""

    @pytest.mark.asyncio
    async def test_daily_exercise_requires_verification(
        self, client, test_user_unverified, auth_headers_unverified,
        mock_jwt_auth_factory, patched_get_session
    ):
        """
        Test that daily exercise endpoint requires email verification.

        Route: GET /api/exercises/daily
        """
        with mock_jwt_auth_factory(test_user_unverified):
            response = await client.get(
                "/api/exercises/daily",
                headers=auth_headers_unverified
            )

            assert response.status_code == 403
            data = await response.get_json()
            assert "email verification" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_submit_exercise_requires_verification(
        self, client, test_user_unverified, auth_headers_unverified,
        mock_jwt_auth_factory, patched_get_session
    ):
        """
        Test that submit exercise endpoint requires email verification.

        Route: POST /api/exercises/{exercise_id}/submit
        """
        with mock_jwt_auth_factory(test_user_unverified):
            response = await client.post(
                "/api/exercises/1/submit",
                headers=auth_headers_unverified,
                json={"code": "print('hello')"}
            )

            assert response.status_code == 403
            data = await response.get_json()
            assert "email verification" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_chat_requires_verification(
        self, client, test_user_unverified, auth_headers_unverified,
        mock_jwt_auth_factory, patched_get_session
    ):
        """
        Test that chat endpoints require email verification.

        Route: POST /api/chat/conversations/{conversation_id}/messages
        """
        with mock_jwt_auth_factory(test_user_unverified):
            response = await client.post(
                "/api/chat/conversations/1/messages",
                headers=auth_headers_unverified,
                json={"content": "Hello"}
            )

            assert response.status_code == 403
            data = await response.get_json()
            assert "email verification" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_profile_update_requires_verification(
        self, client, test_user_unverified, auth_headers_unverified,
        mock_jwt_auth_factory, patched_get_session
    ):
        """
        Test that profile update endpoint requires email verification.

        Route: PUT /api/users/profile
        """
        with mock_jwt_auth_factory(test_user_unverified):
            response = await client.put(
                "/api/users/profile",
                headers=auth_headers_unverified,
                json={"name": "Updated Name"}
            )

            assert response.status_code == 403
            data = await response.get_json()
            assert "email verification" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_public_routes_do_not_require_verification(
        self, client
    ):
        """
        Test that public routes do not require email verification.

        Routes that should be accessible without verification:
        - /api/auth/register
        - /api/auth/login
        - /api/auth/verify-email
        - /api/auth/resend-verification
        """
        # These should all return non-403 status codes
        # (may be 400 for validation, but not 403 for email verification)

        # Register
        response = await client.post(
            "/api/auth/register",
            json={"email": "test@example.com", "password": "Test123!", "name": "Test"}
        )
        assert response.status_code in [200, 201, 400, 409]  # Not 403

        # Login (will fail, but not due to email verification)
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": "wrong"}
        )
        assert response.status_code in [200, 201, 400, 401]  # Not 403

        # Verify email
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": "fake_token"}
        )
        assert response.status_code in [200, 400]  # Not 403


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_verification_after_user_deletion(
        self, client, db_session
    ):
        """
        Test verification attempt after user is deleted.

        Given: A verification token for a user that was deleted
        When: Token is submitted
        Then: Returns appropriate error
        """
        # Create user
        user_email = "deleted_user@example.com"
        token = AuthService.generate_verification_token()
        await AuthService.store_verification_token(user_email, token)

        # Try to verify (user doesn't exist)
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token}
        )

        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_multiple_verification_tokens(
        self, client, test_user_unverified, db_session
    ):
        """
        Test that new verification token invalidates old one.

        Given: User requests verification email multiple times
        When: Old token is used
        Then: Old token should not work (only latest token valid)
        """
        # Create first token
        token1 = AuthService.generate_verification_token()
        await AuthService.store_verification_token(
            test_user_unverified.email,
            token1
        )

        # Create second token (should invalidate first)
        token2 = AuthService.generate_verification_token()
        await AuthService.store_verification_token(
            test_user_unverified.email,
            token2
        )

        # Try to use first token
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token1}
        )

        # First token should not work
        assert response.status_code in [400, 404]

        # Second token should work
        response = await client.post(
            "/api/auth/verify-email",
            json={"token": token2}
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_concurrent_verification_attempts(
        self, client, test_user_unverified, db_session
    ):
        """
        Test concurrent verification attempts (race condition).

        Given: Multiple simultaneous verification requests
        When: All requests use same valid token
        Then: All succeed or only first succeeds (idempotent)
        """
        token = AuthService.generate_verification_token()
        await AuthService.store_verification_token(
            test_user_unverified.email,
            token
        )

        # Make concurrent requests
        import asyncio
        responses = await asyncio.gather(
            client.post("/api/auth/verify-email", json={"token": token}),
            client.post("/api/auth/verify-email", json={"token": token}),
            client.post("/api/auth/verify-email", json={"token": token}),
        )

        # All should succeed (idempotent) or at least one should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 1


# Pytest fixtures for test data

@pytest.fixture
async def test_user_unverified(db_session):
    """Create a test user with unverified email."""
    user = User(
        email=f"unverified-{uuid.uuid4()}@example.com",
        password_hash=AuthService.hash_password("SecurePass123!"),
        name="Unverified User",
        role=UserRole.STUDENT,
        email_verified=False,
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_unverified(test_user_unverified):
    """Create auth headers for unverified user."""
    # Just return a dummy token - tests will use mock_jwt_auth_factory
    # to properly mock the authentication
    return {"Authorization": "Bearer test_token_unverified"}


@pytest.fixture
async def test_user_oauth(db_session):
    """Create a test user from OAuth (auto-verified)."""
    user = User(
        email=f"oauth-{uuid.uuid4()}@example.com",
        name="OAuth User",
        role=UserRole.STUDENT,
        email_verified=True,  # OAuth users are auto-verified
        is_active=True,
        oauth_provider="github",
        github_id="12345"
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_oauth(test_user_oauth):
    """Create auth headers for OAuth user."""
    # Just return a dummy token - tests will use mock_jwt_auth_factory
    # to properly mock the authentication
    return {"Authorization": "Bearer test_token_oauth"}

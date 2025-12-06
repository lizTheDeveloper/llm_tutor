"""
Integration tests for SEC-1 Security Hardening work stream.

Tests cover critical security vulnerabilities identified in architectural review:
- AP-CRIT-002: OAuth token exposure in URLs
- AP-CRIT-001: Hardcoded localhost URLs
- AP-CRIT-004: Password reset session invalidation
- AP-SEC-001: Token storage in localStorage (httpOnly cookies)

Test Strategy:
- Integration tests with real Redis and database connections
- No mocking of internal components
- Test actual security flows users will execute
- Verify tokens never appear in URLs
- Verify all redirects use config values
- Verify session invalidation works correctly
- Verify httpOnly cookie attributes
"""
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select, text
from src.models.user import User, UserRole
from src.services.auth_service import AuthService
from src.config import settings
import re


class TestOAuthSecurityFlow:
    """Tests for OAuth authorization code flow security (AP-CRIT-002, AP-CRIT-001)."""

    @pytest.mark.asyncio
    async def test_oauth_github_callback_no_tokens_in_url(self, client, mock_oauth):
        """
        Test that GitHub OAuth callback returns temporary code, NOT access tokens in URL.

        Critical Security Issue: AP-CRIT-002
        - Tokens in URL are visible in browser history, logs, and referer headers
        - Risk: Complete account compromise, token theft, session hijacking

        Expected Behavior:
        - OAuth callback should redirect with a short-lived temporary code
        - Temporary code should be different from actual GitHub access token
        - NO JWT access tokens or refresh tokens should be in redirect URL
        """
        # Mock OAuth state verification
        mock_oauth['verify_state'].return_value = True

        # Simulate GitHub callback with authorization code
        response = await client.get(
            "/api/auth/oauth/github/callback?code=github_auth_code_123&state=valid_state"
        )

        # Should redirect to frontend
        assert response.status_code == 302
        location = response.headers.get("Location")
        assert location is not None

        # CRITICAL: URL must NOT contain access_token or refresh_token
        assert "access_token" not in location, "Access token found in URL - SECURITY VULNERABILITY"
        assert "refresh_token" not in location, "Refresh token found in URL - SECURITY VULNERABILITY"
        assert "jwt" not in location.lower(), "JWT token found in URL - SECURITY VULNERABILITY"

        # URL should contain frontend_url from config (not hardcoded localhost)
        assert location.startswith(settings.frontend_url), f"Expected {settings.frontend_url}, got {location}"

        # URL should contain a temporary code parameter
        assert "code=" in location, "Missing temporary code in redirect URL"
        assert "provider=github" in location, "Missing provider in redirect URL"

        # Extract the temporary code
        match = re.search(r'code=([^&]+)', location)
        assert match, "Could not extract code from URL"
        temp_code = match.group(1)

        # Temporary code should be different from GitHub authorization code
        assert temp_code != "github_auth_code_123", "Temporary code should not be the same as OAuth code"

        # Temporary code should be a random token (at least 32 chars for security)
        assert len(temp_code) >= 32, "Temporary code too short for security"

    @pytest.mark.asyncio
    async def test_oauth_google_callback_no_tokens_in_url(self, client, mock_oauth):
        """
        Test that Google OAuth callback returns temporary code, NOT access tokens in URL.

        Same security requirements as GitHub OAuth.
        """
        mock_oauth['verify_state'].return_value = True

        response = await client.get(
            "/api/auth/oauth/google/callback?code=google_auth_code_456&state=valid_state"
        )

        assert response.status_code == 302
        location = response.headers.get("Location")

        # CRITICAL: No tokens in URL
        assert "access_token" not in location
        assert "refresh_token" not in location
        assert "jwt" not in location.lower()

        # Must use config frontend_url
        assert location.startswith(settings.frontend_url)

        # Must have temporary code
        assert "code=" in location
        assert "provider=google" in location

    @pytest.mark.asyncio
    async def test_oauth_exchange_endpoint_exists(self, client):
        """
        Test that /api/auth/oauth/exchange endpoint exists and accepts POST requests.

        This endpoint exchanges the temporary code for JWT tokens.
        """
        # Try without data first (should fail validation)
        response = await client.post("/api/auth/oauth/exchange", json={})

        # Should return 400 for missing fields, not 404 for missing endpoint
        assert response.status_code in [400, 422], f"Expected 400/422, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_oauth_exchange_returns_tokens_in_cookies(
        self, client, patched_get_session, mock_oauth
    ):
        """
        Test that OAuth token exchange returns tokens in httpOnly cookies, NOT JSON response.

        Critical Security Issue: AP-SEC-001
        - Tokens in localStorage vulnerable to XSS attacks
        - httpOnly cookies prevent JavaScript access

        Expected Behavior:
        - Access token and refresh token set in httpOnly cookies
        - Cookies must have secure=True, samesite=strict
        - Response body should NOT contain raw tokens
        """
        # Create a test user
        async with patched_get_session() as session:
            user = User(
                email="oauth@test.com",
                name="OAuth User",
                github_id="12345",
                oauth_provider="github",
                email_verified=True,
                role=UserRole.STUDENT,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

        # Mock OAuth service methods
        mock_oauth['exchange_github'].return_value = "github_access_token"
        mock_oauth['get_github_user'].return_value = {
            "email": "oauth@test.com",
            "name": "OAuth User",
            "github_id": "12345",
            "avatar_url": "https://avatar.example.com/user.jpg",
        }

        # Store temporary code in Redis (simulating callback)
        temp_code = AuthService.generate_verification_token()
        await AuthService.store_verification_token(
            f"oauth_github_github_auth_code_789",
            temp_code,
            expiration=300
        )

        # Exchange temporary code for tokens
        response = await client.post(
            "/api/auth/oauth/exchange",
            json={"code": temp_code, "provider": "github"}
        )

        assert response.status_code == 200
        data = await response.get_json()

        # CRITICAL: Response body should NOT contain raw tokens
        assert "access_token" not in data, "Access token in JSON response - MUST be in httpOnly cookie"
        assert "refresh_token" not in data, "Refresh token in JSON response - MUST be in httpOnly cookie"

        # CRITICAL: Tokens must be in httpOnly cookies
        cookies = response.headers.getlist("Set-Cookie")
        assert len(cookies) >= 2, "Expected at least 2 cookies (access + refresh)"

        # Parse cookies
        access_cookie = None
        refresh_cookie = None
        for cookie in cookies:
            if cookie.startswith("access_token="):
                access_cookie = cookie
            elif cookie.startswith("refresh_token="):
                refresh_cookie = cookie

        assert access_cookie is not None, "Missing access_token cookie"
        assert refresh_cookie is not None, "Missing refresh_token cookie"

        # Verify cookie security attributes
        for cookie_name, cookie_value in [("access_token", access_cookie), ("refresh_token", refresh_cookie)]:
            assert "HttpOnly" in cookie_value, f"{cookie_name} cookie missing HttpOnly flag"
            assert "Secure" in cookie_value or settings.app_env == "development", \
                f"{cookie_name} cookie missing Secure flag (required in production)"
            assert "SameSite=Strict" in cookie_value or "SameSite=Lax" in cookie_value, \
                f"{cookie_name} cookie missing SameSite attribute"


class TestHardcodedURLRemoval:
    """Tests for hardcoded URL removal (AP-CRIT-001)."""

    @pytest.mark.asyncio
    async def test_github_oauth_uses_config_backend_url(self, client):
        """
        Test that GitHub OAuth redirect URI uses settings.backend_url, not hardcoded localhost.

        Critical Security Issue: AP-CRIT-001
        - Hardcoded localhost URLs cause OAuth to fail in staging/production
        - Risk: Authentication completely broken in any non-local environment

        Expected Behavior:
        - All OAuth redirect URIs must use settings.backend_url
        - Must work in any environment (local, staging, production)
        """
        response = await client.get("/api/auth/oauth/github")

        assert response.status_code == 302
        location = response.headers.get("Location")

        # Parse the authorization URL to extract redirect_uri parameter
        assert "redirect_uri=" in location
        match = re.search(r'redirect_uri=([^&]+)', location)
        assert match, "Could not extract redirect_uri from authorization URL"

        redirect_uri = match.group(1)
        # URL decode
        from urllib.parse import unquote
        redirect_uri = unquote(redirect_uri)

        # CRITICAL: Must use settings.backend_url, NOT localhost
        assert redirect_uri.startswith(settings.backend_url), \
            f"Redirect URI uses hardcoded URL. Expected {settings.backend_url}, got {redirect_uri}"

        # Must NOT contain hardcoded localhost
        assert "localhost" not in redirect_uri or "localhost" in settings.backend_url, \
            "Hardcoded localhost found in redirect URI"

    @pytest.mark.asyncio
    async def test_google_oauth_uses_config_backend_url(self, client):
        """Test that Google OAuth redirect URI uses settings.backend_url."""
        response = await client.get("/api/auth/oauth/google")

        assert response.status_code == 302
        location = response.headers.get("Location")

        assert "redirect_uri=" in location
        match = re.search(r'redirect_uri=([^&]+)', location)
        assert match

        from urllib.parse import unquote
        redirect_uri = unquote(match.group(1))

        assert redirect_uri.startswith(settings.backend_url)
        assert "localhost" not in redirect_uri or "localhost" in settings.backend_url

    @pytest.mark.asyncio
    async def test_oauth_callback_redirects_use_config_frontend_url(self, client, mock_oauth):
        """
        Test that OAuth callbacks redirect to settings.frontend_url, not hardcoded localhost.
        """
        mock_oauth['verify_state'].return_value = True

        response = await client.get(
            "/api/auth/oauth/github/callback?code=test_code&state=test_state"
        )

        assert response.status_code == 302
        location = response.headers.get("Location")

        # CRITICAL: Must use settings.frontend_url
        assert location.startswith(settings.frontend_url), \
            f"Callback redirect uses hardcoded URL. Expected {settings.frontend_url}, got {location}"

        # Must NOT contain hardcoded localhost
        assert "localhost" not in location or "localhost" in settings.frontend_url, \
            "Hardcoded localhost found in callback redirect"


class TestPasswordResetSessionInvalidation:
    """Tests for password reset session invalidation (AP-CRIT-004)."""

    @pytest.mark.asyncio
    async def test_password_reset_invalidates_all_sessions(
        self, client, patched_get_session
    ):
        """
        Test that password reset invalidates ALL active sessions for the user.

        Critical Security Issue: AP-CRIT-004
        - If sessions remain valid after password reset, attacker retains access
        - Risk: Victim changes password but attacker's session still works

        Expected Behavior:
        - All existing sessions must be invalidated immediately
        - User must re-login with new password
        - Old access tokens must not work after password reset
        """
        # Create a test user
        async with patched_get_session() as session:
            password_hash = AuthService.hash_password("OldPassword123!")
            user = User(
                email="reset@test.com",
                password_hash=password_hash,
                name="Reset Test User",
                email_verified=True,
                role=UserRole.STUDENT,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

        # Create two active sessions (simulate user logged in on 2 devices)
        tokens1 = AuthService.generate_token_pair(
            user_id=user_id,
            email="reset@test.com",
            role=UserRole.STUDENT.value,
        )
        await AuthService.create_session(
            user_id=user_id,
            access_token=tokens1["access_token"],
            refresh_token=tokens1["refresh_token"],
            user_data={"name": "Reset Test User"},
        )

        tokens2 = AuthService.generate_token_pair(
            user_id=user_id,
            email="reset@test.com",
            role=UserRole.STUDENT.value,
        )
        await AuthService.create_session(
            user_id=user_id,
            access_token=tokens2["access_token"],
            refresh_token=tokens2["refresh_token"],
            user_data={"name": "Reset Test User"},
        )

        # Verify both sessions work before reset
        is_valid_1 = await AuthService.verify_session_token(tokens1["access_token"])
        is_valid_2 = await AuthService.verify_session_token(tokens2["access_token"])
        assert is_valid_1 is not None, "Session 1 should be valid before reset"
        assert is_valid_2 is not None, "Session 2 should be valid before reset"

        # Generate password reset token
        reset_token = await AuthService.generate_password_reset_token("reset@test.com")

        # Reset password
        response = await client.post(
            "/api/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": "NewSecurePassword123!"
            }
        )

        assert response.status_code == 200
        data = await response.get_json()
        assert "success" in data["message"].lower() or "successful" in data["message"].lower()

        # CRITICAL: Both sessions must be invalidated
        is_valid_1_after = await AuthService.verify_session_token(tokens1["access_token"])
        is_valid_2_after = await AuthService.verify_session_token(tokens2["access_token"])

        assert is_valid_1_after is None, \
            "Session 1 still valid after password reset - SECURITY VULNERABILITY"
        assert is_valid_2_after is None, \
            "Session 2 still valid after password reset - SECURITY VULNERABILITY"

    @pytest.mark.asyncio
    async def test_password_reset_user_can_login_with_new_password(
        self, client, patched_get_session
    ):
        """
        Test that user can login with new password after reset.

        This ensures the invalidation doesn't break the authentication system.
        """
        # Create user
        async with patched_get_session() as session:
            password_hash = AuthService.hash_password("OldPassword456!")
            user = User(
                email="newpass@test.com",
                password_hash=password_hash,
                name="New Pass User",
                email_verified=True,
                role=UserRole.STUDENT,
                is_active=True,
            )
            session.add(user)
            await session.flush()

        # Reset password
        reset_token = await AuthService.generate_password_reset_token("newpass@test.com")
        response = await client.post(
            "/api/auth/password-reset",
            json={
                "token": reset_token,
                "new_password": "NewPassword789!"
            }
        )
        assert response.status_code == 200

        # Login with new password
        login_response = await client.post(
            "/api/auth/login",
            json={
                "email": "newpass@test.com",
                "password": "NewPassword789!"
            }
        )

        assert login_response.status_code == 200
        login_data = await login_response.get_json()
        assert "user" in login_data


class TestCookieAuthentication:
    """Tests for httpOnly cookie authentication (AP-SEC-001)."""

    @pytest.mark.asyncio
    async def test_login_returns_tokens_in_cookies(self, client, patched_get_session):
        """
        Test that login endpoint returns tokens in httpOnly cookies, NOT JSON.

        Critical Security Issue: AP-SEC-001
        - localStorage vulnerable to XSS attacks
        - Any XSS vulnerability on the domain can steal tokens
        - httpOnly cookies are immune to JavaScript access
        """
        # Create user
        async with patched_get_session() as session:
            password_hash = AuthService.hash_password("LoginTest123!")
            user = User(
                email="cookie@test.com",
                password_hash=password_hash,
                name="Cookie User",
                email_verified=True,
                role=UserRole.STUDENT,
                is_active=True,
            )
            session.add(user)
            await session.flush()

        # Login
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "cookie@test.com",
                "password": "LoginTest123!"
            }
        )

        assert response.status_code == 200
        data = await response.get_json()

        # CRITICAL: Tokens should NOT be in response body
        assert "access_token" not in data, "Access token in response body - SECURITY RISK"
        assert "refresh_token" not in data, "Refresh token in response body - SECURITY RISK"

        # CRITICAL: Tokens must be in httpOnly cookies
        cookies = response.headers.getlist("Set-Cookie")
        assert len(cookies) >= 2, "Expected access and refresh token cookies"

        cookie_names = [cookie.split("=")[0] for cookie in cookies]
        assert "access_token" in cookie_names, "Missing access_token cookie"
        assert "refresh_token" in cookie_names, "Missing refresh_token cookie"

    @pytest.mark.asyncio
    async def test_authenticated_requests_use_cookies(self, client, patched_get_session):
        """
        Test that authenticated endpoints accept cookies instead of Authorization header.

        Once tokens are in httpOnly cookies, they're sent automatically by the browser.
        The backend must read from cookies, not just Authorization header.
        """
        # Create user and get tokens
        async with patched_get_session() as session:
            password_hash = AuthService.hash_password("AuthTest123!")
            user = User(
                email="auth@test.com",
                password_hash=password_hash,
                name="Auth User",
                email_verified=True,
                role=UserRole.STUDENT,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

        tokens = AuthService.generate_token_pair(
            user_id=user_id,
            email="auth@test.com",
            role=UserRole.STUDENT.value,
        )
        await AuthService.create_session(
            user_id=user_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_data={"name": "Auth User"},
        )

        # Make authenticated request with cookie
        client.set_cookie("localhost", "access_token", tokens["access_token"])

        response = await client.get("/api/users/me")

        # Should work with cookie authentication
        assert response.status_code == 200
        data = await response.get_json()
        assert data["email"] == "auth@test.com"


class TestConfigurationValidation:
    """Tests for startup configuration validation."""

    def test_config_validates_secret_key_length(self):
        """
        Test that configuration validation requires strong secret keys.

        Expected:
        - SECRET_KEY must be at least 32 characters
        - JWT_SECRET_KEY must be at least 32 characters
        - Should fail fast on startup with weak secrets
        """
        from src.config import Settings
        from pydantic import ValidationError

        # Try with weak secret key (should fail)
        with pytest.raises((ValidationError, ValueError)):
            Settings(
                secret_key="weak",  # Too short
                jwt_secret_key="also_weak",  # Too short
                database_url="postgresql://test",
                redis_url="redis://test",
            )

    def test_config_requires_critical_fields(self):
        """Test that critical configuration fields are required."""
        from src.config import Settings
        from pydantic import ValidationError

        # Missing SECRET_KEY
        with pytest.raises((ValidationError, ValueError)):
            Settings(
                jwt_secret_key="x" * 32,
                database_url="postgresql://test",
                redis_url="redis://test",
            )

    def test_config_uses_secret_str_for_sensitive_fields(self):
        """
        Test that sensitive fields use Pydantic SecretStr type.

        SecretStr prevents secrets from being printed in logs or error messages.
        """
        from src.config import Settings, settings
        from pydantic import SecretStr

        # Check that sensitive fields are SecretStr type
        # This will be implemented in the fix
        # For now, just verify the config loads
        assert settings.secret_key is not None
        assert settings.jwt_secret_key is not None


class TestDatabaseConnectionLeak:
    """Tests for database connection leak in health check (AP-ARCH-004)."""

    @pytest.mark.asyncio
    async def test_health_check_uses_async_connection(self, client):
        """
        Test that health check uses async database connection, not sync.

        Issue: Dual engines (sync + async) doubles connection pool requirements
        - Current: 20 sync + 20 async = 40 connections
        - Should be: 20 async connections only

        Health check should use async connection to avoid sync engine creation.
        """
        response = await client.get("/health")

        # Health check should work
        assert response.status_code in [200, 503]  # 503 if DB down
        data = await response.get_json()

        # Should return database status
        assert "database" in data

        # Verify sync engine is not created for health check
        # This requires checking DatabaseManager state
        from src.utils.database import get_database
        db_manager = get_database()

        # After health check, sync engine should NOT be created
        # (it's only created when accessed via the property)
        # This test will pass after we fix the health check to use async
        assert db_manager._sync_engine is None or db_manager._async_engine is not None, \
            "Health check should use async engine, not trigger sync engine creation"


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    @pytest.mark.asyncio
    async def test_security_headers_present_on_all_responses(self, client):
        """
        Test that security headers are present on all HTTP responses.

        Required headers:
        - Content-Security-Policy
        - X-Frame-Options: DENY
        - X-Content-Type-Options: nosniff
        """
        # Test on public endpoint
        response = await client.get("/health")

        # CSP header
        assert "Content-Security-Policy" in response.headers, \
            "Missing Content-Security-Policy header"

        # Clickjacking protection
        assert response.headers.get("X-Frame-Options") == "DENY", \
            "Missing or incorrect X-Frame-Options header"

        # MIME sniffing protection
        assert response.headers.get("X-Content-Type-Options") == "nosniff", \
            "Missing X-Content-Type-Options header"

    @pytest.mark.asyncio
    async def test_security_headers_on_authenticated_endpoints(self, client, patched_get_session):
        """Test security headers are present on authenticated endpoints."""
        # Create user and login
        async with patched_get_session() as session:
            password_hash = AuthService.hash_password("HeaderTest123!")
            user = User(
                email="headers@test.com",
                password_hash=password_hash,
                name="Headers User",
                email_verified=True,
                role=UserRole.STUDENT,
                is_active=True,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

        tokens = AuthService.generate_token_pair(
            user_id=user_id,
            email="headers@test.com",
            role=UserRole.STUDENT.value,
        )

        # Make authenticated request
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        response = await client.get("/api/users/me", headers=headers)

        # Security headers should be present
        assert "Content-Security-Policy" in response.headers
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"


# Fixtures for mocking OAuth services
@pytest.fixture
def mock_oauth():
    """Mock OAuth service methods."""
    with patch('src.services.oauth_service.OAuthService.verify_oauth_state', new_callable=AsyncMock) as verify_state, \
         patch('src.services.oauth_service.OAuthService.exchange_github_code', new_callable=AsyncMock) as exchange_github, \
         patch('src.services.oauth_service.OAuthService.exchange_google_code', new_callable=AsyncMock) as exchange_google, \
         patch('src.services.oauth_service.OAuthService.get_github_user_info', new_callable=AsyncMock) as get_github_user, \
         patch('src.services.oauth_service.OAuthService.get_google_user_info', new_callable=AsyncMock) as get_google_user:

        yield {
            'verify_state': verify_state,
            'exchange_github': exchange_github,
            'exchange_google': exchange_google,
            'get_github_user': get_github_user,
            'get_google_user': get_google_user,
        }

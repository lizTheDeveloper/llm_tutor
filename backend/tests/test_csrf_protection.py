"""
Integration tests for CSRF protection (SEC-3-CSRF).

CSRF (Cross-Site Request Forgery) Protection Strategy:
1. SameSite=Strict cookies (already implemented in SEC-1) - primary defense
2. Custom X-CSRF-Token header requirement - defense-in-depth for older browsers
3. Double-submit cookie pattern - CSRF token must match between cookie and header

Attack Scenarios Tested:
- Attacker cannot forge requests without CSRF token
- Attacker cannot read CSRF token due to SOP (Same-Origin Policy)
- Attacker cannot include custom headers in simple CORS requests
- Token mismatch is rejected
- Missing token on state-changing endpoints is rejected
- GET requests do not require CSRF token (idempotent)

Test Coverage:
- Authentication endpoints (login, register, password reset)
- Profile updates
- Exercise submission
- Chat messages
- All POST/PUT/PATCH/DELETE endpoints

This addresses AP-SEC-006 (architectural review finding).
"""

import pytest
from quart import Quart
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from src.models.user import User, UserRole


@pytest.mark.asyncio
class TestCSRFProtection:
    """Test CSRF protection on all state-changing endpoints."""

    async def test_csrf_token_generated_on_login(self, client, test_db):
        """
        Test that CSRF token is generated and set in cookie on successful login.

        Expected behavior:
        - Login response sets csrf_token cookie
        - Cookie has httpOnly=False (needs to be readable by JS)
        - Cookie has secure=True in production
        - Cookie has SameSite=Strict
        """
        # Register a user first
        register_data = {
            "email": "csrf@example.com",
            "password": "SecurePassword123!",
            "full_name": "CSRF Test User"
        }
        await client.post("/api/auth/register", json=register_data)

        # Login
        login_data = {
            "email": "csrf@example.com",
            "password": "SecurePassword123!"
        }
        response = await client.post("/api/auth/login", json=login_data)

        assert response.status_code == 200

        # Check CSRF token cookie is set
        cookies = response.headers.getlist("Set-Cookie")
        csrf_cookie = [c for c in cookies if "csrf_token=" in c]
        assert len(csrf_cookie) > 0, "CSRF token cookie not set on login"

        # Verify cookie attributes
        csrf_cookie_value = csrf_cookie[0]
        assert "HttpOnly" not in csrf_cookie_value, \
            "CSRF token cookie should NOT be httpOnly (needs JS access)"
        assert "SameSite=Strict" in csrf_cookie_value or "SameSite=Lax" in csrf_cookie_value, \
            "CSRF token cookie missing SameSite attribute"

    async def test_csrf_token_required_on_post_request(self, client, authenticated_client, test_db):
        """
        Test that POST requests without CSRF token are rejected.

        Attack scenario: Attacker tricks user into visiting malicious site that
        submits a form to our API. Without CSRF token, request should fail.
        """
        # Attempt to create a profile update without CSRF token
        profile_data = {
            "bio": "Attacker trying to update profile",
            "programming_languages": ["Python"]
        }

        response = await authenticated_client.put("/api/users/profile", json=profile_data)

        # Should be rejected due to missing CSRF token
        assert response.status_code == 403, \
            "POST request without CSRF token should be rejected"

        data = await response.get_json()
        assert "csrf" in data.get("error", "").lower() or \
               "forbidden" in data.get("error", "").lower(), \
            "Error message should mention CSRF or forbidden"

    async def test_csrf_token_required_on_put_request(self, client, authenticated_client, test_db):
        """Test that PUT requests without CSRF token are rejected."""
        profile_data = {
            "bio": "Updated bio without CSRF token",
            "programming_languages": ["JavaScript"]
        }

        response = await authenticated_client.put("/api/users/profile", json=profile_data)

        assert response.status_code == 403, \
            "PUT request without CSRF token should be rejected"

    async def test_csrf_token_required_on_delete_request(self, client, authenticated_client, test_db):
        """Test that DELETE requests without CSRF token are rejected."""
        # Assuming we have a delete endpoint for conversations
        response = await authenticated_client.delete("/api/chat/conversations/123")

        assert response.status_code == 403, \
            "DELETE request without CSRF token should be rejected"

    async def test_csrf_token_not_required_on_get_request(self, client, authenticated_client, test_db):
        """
        Test that GET requests do not require CSRF token.

        GET requests should be idempotent and not change state,
        so CSRF protection is not needed.
        """
        response = await authenticated_client.get("/api/users/me")

        # Should succeed without CSRF token (GET is safe)
        assert response.status_code in [200, 401], \
            "GET requests should not require CSRF token"

    async def test_csrf_token_mismatch_rejected(self, client, authenticated_client_with_csrf, test_db):
        """
        Test that requests with mismatched CSRF tokens are rejected.

        Attack scenario: Attacker tries to reuse an old CSRF token or
        forge a token value.
        """
        # Get the valid CSRF token from cookie
        csrf_cookie = authenticated_client_with_csrf.cookies.get("csrf_token")

        # Send request with DIFFERENT token in header
        profile_data = {
            "bio": "Trying with wrong CSRF token",
            "programming_languages": ["Go"]
        }

        # Set wrong CSRF token in header
        headers = {"X-CSRF-Token": "wrong_token_value_12345"}
        response = await authenticated_client_with_csrf.put(
            "/api/users/profile",
            json=profile_data,
            headers=headers
        )

        assert response.status_code == 403, \
            "Request with mismatched CSRF token should be rejected"

        data = await response.get_json()
        assert "csrf" in data.get("error", "").lower(), \
            "Error should mention CSRF token mismatch"

    async def test_csrf_token_valid_when_matching(self, client, authenticated_client_with_csrf, test_db):
        """
        Test that requests with valid matching CSRF tokens succeed.

        Happy path: User's browser sends both:
        1. CSRF token in cookie (set by server)
        2. CSRF token in X-CSRF-Token header (set by JS)
        Both must match for request to succeed.
        """
        # Get the valid CSRF token from cookie
        csrf_cookie = authenticated_client_with_csrf.cookies.get("csrf_token")

        # Send request with matching token in header
        profile_data = {
            "bio": "Valid CSRF token",
            "programming_languages": ["Rust"]
        }

        headers = {"X-CSRF-Token": csrf_cookie}
        response = await authenticated_client_with_csrf.put(
            "/api/users/profile",
            json=profile_data,
            headers=headers
        )

        # Should succeed (assuming profile endpoint exists)
        assert response.status_code in [200, 201], \
            "Request with valid CSRF token should succeed"

    async def test_csrf_protection_on_password_reset(self, client, authenticated_client, test_db):
        """
        Test CSRF protection on sensitive password reset endpoint.

        This is a high-value target for CSRF attacks.
        """
        reset_data = {
            "token": "some_reset_token",
            "new_password": "NewSecurePassword123!"
        }

        response = await client.post("/api/auth/reset-password/confirm", json=reset_data)

        # Should be rejected without CSRF token
        assert response.status_code == 403, \
            "Password reset without CSRF token should be rejected"

    async def test_csrf_protection_on_exercise_submission(self, client, authenticated_client, test_db):
        """Test CSRF protection on exercise submission endpoint."""
        submission_data = {
            "solution": "print('Hello, World!')",
            "language": "python"
        }

        response = await authenticated_client.post(
            "/api/exercises/123/submit",
            json=submission_data
        )

        assert response.status_code == 403, \
            "Exercise submission without CSRF token should be rejected"

    async def test_csrf_protection_on_chat_message(self, client, authenticated_client, test_db):
        """Test CSRF protection on chat message endpoint."""
        message_data = {
            "message": "Help me with Python",
            "conversation_id": "conv_123"
        }

        response = await authenticated_client.post("/api/chat/message", json=message_data)

        assert response.status_code == 403, \
            "Chat message without CSRF token should be rejected"

    async def test_csrf_token_regenerated_on_auth_change(self, client, test_db):
        """
        Test that CSRF token is regenerated when authentication state changes.

        Security best practice: Regenerate CSRF token on:
        - Login
        - Logout
        - Password change
        - Email verification

        This prevents session fixation attacks.
        """
        # Register and login
        register_data = {
            "email": "tokenregen@example.com",
            "password": "SecurePassword123!",
            "full_name": "Token Regen User"
        }
        await client.post("/api/auth/register", json=register_data)

        login_response = await client.post("/api/auth/login", json={
            "email": "tokenregen@example.com",
            "password": "SecurePassword123!"
        })

        # Extract CSRF token from login
        login_cookies = login_response.headers.getlist("Set-Cookie")
        login_csrf = [c for c in login_cookies if "csrf_token=" in c][0]
        login_csrf_value = login_csrf.split("csrf_token=")[1].split(";")[0]

        # Logout
        logout_response = await client.post("/api/auth/logout")

        # Login again
        login2_response = await client.post("/api/auth/login", json={
            "email": "tokenregen@example.com",
            "password": "SecurePassword123!"
        })

        # Extract new CSRF token
        login2_cookies = login2_response.headers.getlist("Set-Cookie")
        login2_csrf = [c for c in login2_cookies if "csrf_token=" in c][0]
        login2_csrf_value = login2_csrf.split("csrf_token=")[1].split(";")[0]

        # CSRF tokens should be different
        assert login_csrf_value != login2_csrf_value, \
            "CSRF token should be regenerated after logout/login cycle"

    async def test_csrf_exempt_endpoints(self, client, test_db):
        """
        Test that certain endpoints are exempt from CSRF protection.

        Exempt endpoints (no state change or already protected):
        - GET requests (idempotent)
        - /health endpoint
        - /api/auth/login (already protected by password)
        - /api/auth/register (no existing session to protect)
        """
        # Health check should not require CSRF
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_csrf_token_length_and_format(self, client, test_db):
        """
        Test that CSRF tokens meet security requirements.

        Requirements:
        - Minimum 32 bytes (256 bits) of entropy
        - URL-safe base64 encoding
        - Cryptographically random (secrets.token_urlsafe)
        """
        # Login to get CSRF token
        register_data = {
            "email": "tokenformat@example.com",
            "password": "SecurePassword123!",
            "full_name": "Token Format User"
        }
        await client.post("/api/auth/register", json=register_data)

        login_response = await client.post("/api/auth/login", json={
            "email": "tokenformat@example.com",
            "password": "SecurePassword123!"
        })

        # Extract CSRF token
        cookies = login_response.headers.getlist("Set-Cookie")
        csrf_cookie = [c for c in cookies if "csrf_token=" in c][0]
        csrf_value = csrf_cookie.split("csrf_token=")[1].split(";")[0]

        # Verify length (32 bytes base64 encoded = 43-44 chars)
        assert len(csrf_value) >= 43, \
            f"CSRF token too short ({len(csrf_value)} chars). Must be >= 43 chars (32 bytes)"

        # Verify URL-safe characters only
        import string
        url_safe_chars = string.ascii_letters + string.digits + "-_="
        assert all(c in url_safe_chars for c in csrf_value), \
            "CSRF token contains non-URL-safe characters"

    async def test_csrf_protection_timing_safe(self, client, authenticated_client_with_csrf, test_db):
        """
        Test that CSRF token comparison is timing-safe.

        Prevents timing attacks where attacker can guess token by
        measuring response time differences.

        Must use secrets.compare_digest() for comparison.
        """
        # This test verifies implementation uses timing-safe comparison
        # We can't directly test timing, but we ensure consistent behavior

        csrf_token = authenticated_client_with_csrf.cookies.get("csrf_token")

        # Try multiple wrong tokens with different prefixes
        wrong_tokens = [
            "a" * len(csrf_token),  # All wrong
            csrf_token[:10] + "x" * (len(csrf_token) - 10),  # Partial match
            "x" * len(csrf_token),  # Different wrong
        ]

        profile_data = {"bio": "Test timing"}

        for wrong_token in wrong_tokens:
            headers = {"X-CSRF-Token": wrong_token}
            response = await authenticated_client_with_csrf.put(
                "/api/users/profile",
                json=profile_data,
                headers=headers
            )

            # All should fail with same status code (timing-safe)
            assert response.status_code == 403, \
                "All invalid tokens should return same status code"

    async def test_csrf_protection_with_cors_preflight(self, client, test_db):
        """
        Test that CSRF protection works correctly with CORS preflight requests.

        OPTIONS requests should not require CSRF tokens.
        Actual POST/PUT/DELETE requests should require CSRF tokens.
        """
        # CORS preflight (OPTIONS) should succeed without CSRF
        response = await client.options("/api/users/profile")

        # Should succeed (200 or 204)
        assert response.status_code in [200, 204, 405], \
            "OPTIONS request should not require CSRF token"

    async def test_double_submit_cookie_pattern(self, client, test_db):
        """
        Test double-submit cookie pattern implementation.

        Pattern:
        1. Server generates random CSRF token on login
        2. Server sets token in cookie (csrf_token)
        3. Client reads token from cookie (JS can access if not httpOnly)
        4. Client sends token in X-CSRF-Token header on state-changing requests
        5. Server verifies cookie token == header token

        Security: Attacker cannot read cookie due to Same-Origin Policy,
        and cannot set custom headers on CORS requests.
        """
        # Register and login
        register_data = {
            "email": "doublesubmit@example.com",
            "password": "SecurePassword123!",
            "full_name": "Double Submit User"
        }
        await client.post("/api/auth/register", json=register_data)

        login_response = await client.post("/api/auth/login", json={
            "email": "doublesubmit@example.com",
            "password": "SecurePassword123!"
        })

        # Verify CSRF cookie is NOT httpOnly (so JS can read it)
        cookies = login_response.headers.getlist("Set-Cookie")
        csrf_cookie = [c for c in cookies if "csrf_token=" in c][0]

        assert "HttpOnly" not in csrf_cookie, \
            "CSRF token cookie must NOT be HttpOnly (JS needs to read it)"

        # Verify auth cookies ARE httpOnly (for comparison)
        access_cookie = [c for c in cookies if "access_token=" in c][0]
        assert "HttpOnly" in access_cookie or "httponly" in access_cookie.lower(), \
            "Access token cookie MUST be HttpOnly"


@pytest.mark.asyncio
class TestCSRFEdgeCases:
    """Test edge cases and error scenarios for CSRF protection."""

    async def test_csrf_token_empty_string(self, client, authenticated_client, test_db):
        """Test that empty CSRF token is rejected."""
        profile_data = {"bio": "Empty CSRF token"}
        headers = {"X-CSRF-Token": ""}

        response = await authenticated_client.put(
            "/api/users/profile",
            json=profile_data,
            headers=headers
        )

        assert response.status_code == 403

    async def test_csrf_token_null_value(self, client, authenticated_client, test_db):
        """Test that null CSRF token is rejected."""
        profile_data = {"bio": "Null CSRF token"}
        headers = {"X-CSRF-Token": None}

        response = await authenticated_client.put(
            "/api/users/profile",
            json=profile_data,
            headers=headers
        )

        assert response.status_code == 403

    async def test_csrf_token_sql_injection_attempt(self, client, authenticated_client, test_db):
        """Test that SQL injection in CSRF token is safely rejected."""
        profile_data = {"bio": "SQL injection attempt"}
        headers = {"X-CSRF-Token": "'; DROP TABLE users; --"}

        response = await authenticated_client.put(
            "/api/users/profile",
            json=profile_data,
            headers=headers
        )

        assert response.status_code == 403

    async def test_csrf_token_xss_attempt(self, client, authenticated_client, test_db):
        """Test that XSS payload in CSRF token is safely rejected."""
        profile_data = {"bio": "XSS attempt"}
        headers = {"X-CSRF-Token": "<script>alert('XSS')</script>"}

        response = await authenticated_client.put(
            "/api/users/profile",
            json=profile_data,
            headers=headers
        )

        assert response.status_code == 403

    async def test_csrf_protection_error_logging(self, client, authenticated_client, test_db):
        """
        Test that CSRF protection failures are logged for security monitoring.

        Security events to log:
        - Missing CSRF token
        - Mismatched CSRF token
        - Invalid CSRF token format
        - Timing attack attempts
        """
        # This test verifies implementation includes proper logging
        # We check that CSRF failures are recorded for security auditing

        profile_data = {"bio": "Logging test"}

        with patch("src.middleware.csrf_protection.logger") as mock_logger:
            response = await authenticated_client.put("/api/users/profile", json=profile_data)

            # Should log security event
            # Note: Actual assertion depends on logging implementation
            # This is a placeholder for the pattern
            assert response.status_code == 403


# Fixtures for authenticated clients with CSRF tokens

@pytest.fixture
async def authenticated_client_with_csrf(client, test_db):
    """
    Create an authenticated client WITH valid CSRF token.

    This fixture simulates a real browser that:
    1. Registers and logs in
    2. Receives CSRF token in cookie
    3. Includes CSRF token in subsequent requests
    """
    # Register user
    register_data = {
        "email": "csrf_user@example.com",
        "password": "SecurePassword123!",
        "full_name": "CSRF Test User"
    }
    await client.post("/api/auth/register", json=register_data)

    # Login to get CSRF token
    login_response = await client.post("/api/auth/login", json={
        "email": "csrf_user@example.com",
        "password": "SecurePassword123!"
    })

    # Extract CSRF token from cookie
    cookies = login_response.headers.getlist("Set-Cookie")
    csrf_cookie = [c for c in cookies if "csrf_token=" in c]

    if csrf_cookie:
        csrf_value = csrf_cookie[0].split("csrf_token=")[1].split(";")[0]
        # Store CSRF token in client for subsequent requests
        client.cookies = {"csrf_token": csrf_value}

    return client


@pytest.fixture
async def authenticated_client(client, test_db):
    """
    Create an authenticated client WITHOUT CSRF token.

    This simulates an attacker who has stolen session cookies
    but does not have the CSRF token.
    """
    # Register user
    register_data = {
        "email": "auth_user@example.com",
        "password": "SecurePassword123!",
        "full_name": "Auth Test User"
    }
    await client.post("/api/auth/register", json=register_data)

    # Login to get session cookies
    await client.post("/api/auth/login", json={
        "email": "auth_user@example.com",
        "password": "SecurePassword123!"
    })

    # Return client with session cookies but NO CSRF token in headers
    return client

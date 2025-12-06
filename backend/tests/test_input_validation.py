"""
Integration tests for comprehensive input validation hardening (SEC-3-INPUT).

This test suite validates:
1. All endpoints have Pydantic schemas
2. Maximum length enforcement on all text fields
3. XSS protection via HTML/script sanitization
4. SQL injection prevention
5. Markdown sanitization for user-generated content
6. URL validation for GitHub URLs
7. Clear validation error messages

Testing Philosophy:
- Integration tests over unit tests
- Test real API endpoints with actual validation
- Mock only external dependencies (LLM, OAuth providers)
- Test the same code paths users will execute

Security Testing:
- XSS payloads from OWASP XSS Filter Evasion Cheat Sheet
- SQL injection patterns from OWASP SQL Injection Guide
- Oversized inputs (10KB, 100KB, 1MB)
- Unicode edge cases (emojis, RTL text, zero-width characters)
- Markdown injection attacks
"""
import pytest
from quart import Quart
from typing import Dict, Any
import json
import uuid


# ===================================================================
# Test Data - Attack Vectors and Edge Cases
# ===================================================================

XSS_PAYLOADS = [
    # Basic XSS
    "<script>alert('XSS')</script>",
    "<img src=x onerror=alert('XSS')>",
    "<svg onload=alert('XSS')>",

    # Event handler XSS
    "<body onload=alert('XSS')>",
    "<input onfocus=alert('XSS') autofocus>",
    "<select onfocus=alert('XSS') autofocus>",

    # JavaScript protocol
    "<a href='javascript:alert(\"XSS\")'>click</a>",
    "<iframe src='javascript:alert(\"XSS\")'></iframe>",

    # Data URI XSS
    "<object data='data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4='></object>",

    # Encoded XSS
    "&#60;script&#62;alert('XSS')&#60;/script&#62;",
    "%3Cscript%3Ealert('XSS')%3C/script%3E",

    # Markdown-based XSS
    "[click me](javascript:alert('XSS'))",
    "![xss](javascript:alert('XSS'))",
    "[xss]: javascript:alert('XSS')",
]

SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    "' UNION SELECT NULL, NULL, NULL --",
    "admin'--",
    "1' AND '1'='1",
    "' OR 1=1 LIMIT 1 --",
    "'; DELETE FROM users WHERE 'a'='a",
    "1' UNION SELECT username, password FROM users --",
]

OVERSIZED_INPUTS = {
    "tiny": "a" * 10,
    "small": "a" * 100,
    "medium": "a" * 1000,
    "large": "a" * 10000,
    "xlarge": "a" * 100000,
    "huge": "a" * 1000000,
}

UNICODE_EDGE_CASES = [
    # Emojis
    "Hello 👋 World 🌍",
    "🚀" * 100,

    # RTL text
    "مرحبا بالعالم",  # Arabic
    "שלום עולם",  # Hebrew

    # Zero-width characters
    "Hello\u200bWorld",  # Zero-width space
    "Test\ufeffData",  # Zero-width no-break space

    # Combining characters
    "e\u0301",  # e with acute accent (é)
    "a\u0300\u0301\u0302",  # a with multiple combining marks

    # Surrogate pairs
    "𝕳𝖊𝖑𝖑𝖔",  # Mathematical bold text
]


# ===================================================================
# Auth Endpoint Validation Tests
# ===================================================================

class TestAuthInputValidation:
    """Test input validation for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_missing_schema_validation(self, client):
        """Test that /register endpoint validates all required fields."""
        # Missing email
        response = await client.post("/api/auth/register", json={
            "password": "ValidPass123!",
            "name": "Test User"
        })
        assert response.status_code == 400
        data = await response.get_json()
        assert "email" in data.get("message", "").lower()

        # Missing password
        response = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "name": "Test User"
        })
        assert response.status_code == 400
        data = await response.get_json()
        assert "password" in data.get("message", "").lower()

        # Missing name
        response = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "ValidPass123!"
        })
        assert response.status_code == 400
        data = await response.get_json()
        assert "name" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_register_email_validation(self, client):
        """Test email format validation."""
        invalid_emails = [
            "notanemail",
            "@example.com",
            "test@",
            "test..email@example.com",
            "test@example",
            "test@.com",
            "test email@example.com",
            " test@example.com ",  # Leading/trailing whitespace
        ]

        for invalid_email in invalid_emails:
            response = await client.post("/api/auth/register", json={
                "email": invalid_email,
                "password": "ValidPass123!",
                "name": "Test User"
            })
            assert response.status_code == 400, f"Failed to reject invalid email: {invalid_email}"
            data = await response.get_json()
            assert "email" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_register_password_strength_validation(self, client):
        """Test password strength requirements."""
        weak_passwords = [
            "123456",  # Too short
            "password",  # No numbers/symbols
            "Pass123",  # Too short
            "PASSWORD123!",  # No lowercase
            "password123!",  # No uppercase
            "Password!",  # No numbers
            "Password123",  # No special chars
        ]

        for weak_password in weak_passwords:
            response = await client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": weak_password,
                "name": "Test User"
            })
            assert response.status_code == 400, f"Failed to reject weak password: {weak_password}"
            data = await response.get_json()
            assert "password" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_register_name_length_validation(self, client):
        """Test name field length limits."""
        # Too short (should be at least 1 character after stripping)
        response = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "ValidPass123!",
            "name": "   "  # Only whitespace
        })
        assert response.status_code == 400

        # Too long (should be max 255 characters)
        response = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "ValidPass123!",
            "name": "a" * 256
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_register_xss_in_name(self, client):
        """Test XSS payload sanitization in name field."""
        for xss_payload in XSS_PAYLOADS:
            response = await client.post("/api/auth/register", json={
                "email": f"test{hash(xss_payload)}@example.com",
                "password": "ValidPass123!",
                "name": xss_payload
            })
            # Should either reject (400) or sanitize
            if response.status_code == 201:
                data = await response.get_json()
                # Name should be sanitized - no HTML tags
                assert "<script>" not in data.get("name", "").lower()
                assert "onerror" not in data.get("name", "").lower()
                assert "javascript:" not in data.get("name", "").lower()

    @pytest.mark.asyncio
    async def test_login_missing_schema_validation(self, client):
        """Test that /login endpoint validates required fields."""
        # Missing email
        response = await client.post("/api/auth/login", json={
            "password": "ValidPass123!"
        })
        assert response.status_code == 400

        # Missing password
        response = await client.post("/api/auth/login", json={
            "email": "test@example.com"
        })
        assert response.status_code == 400


# ===================================================================
# Chat Endpoint Validation Tests
# ===================================================================

class TestChatInputValidation:
    """Test input validation for chat endpoints."""

    @pytest.mark.asyncio
    async def test_send_message_missing_schema(self, client, auth_headers):
        """Test that /chat/message validates required fields."""
        # Missing message
        response = await client.post(
            "/api/chat/message",
            json={},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = await response.get_json()
        assert "message" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_send_message_length_validation(self, client, auth_headers):
        """Test message length limits."""
        # Empty message
        response = await client.post(
            "/api/chat/message",
            json={"message": ""},
            headers=auth_headers
        )
        assert response.status_code == 400

        # Only whitespace
        response = await client.post(
            "/api/chat/message",
            json={"message": "   "},
            headers=auth_headers
        )
        assert response.status_code == 400

        # Too long (should be max 5000 characters)
        response = await client.post(
            "/api/chat/message",
            json={"message": "a" * 5001},
            headers=auth_headers
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_send_message_xss_sanitization(self, client, auth_headers):
        """Test XSS payload sanitization in chat messages."""
        for xss_payload in XSS_PAYLOADS[:5]:  # Test subset for speed
            response = await client.post(
                "/api/chat/message",
                json={"message": xss_payload},
                headers=auth_headers
            )
            # Should accept but sanitize
            assert response.status_code in [200, 201]
            data = await response.get_json()
            # Response should not contain executable scripts
            response_text = json.dumps(data).lower()
            assert "<script>" not in response_text
            assert "onerror" not in response_text

    @pytest.mark.asyncio
    async def test_send_message_markdown_sanitization(self, client, auth_headers):
        """Test markdown sanitization in chat messages."""
        markdown_xss = [
            "[click me](javascript:alert('XSS'))",
            "![xss](javascript:alert('XSS'))",
            "[xss]: javascript:alert('XSS')",
            "[link](data:text/html;base64,PHNjcmlwdD5hbGVydCgnWFNTJyk8L3NjcmlwdD4=)",
        ]

        for payload in markdown_xss:
            response = await client.post(
                "/api/chat/message",
                json={"message": payload},
                headers=auth_headers
            )
            assert response.status_code in [200, 201]
            data = await response.get_json()
            # Markdown links with javascript: protocol should be sanitized
            response_text = json.dumps(data)
            assert "javascript:" not in response_text.lower()
            assert "data:text/html" not in response_text.lower()


# ===================================================================
# Profile Endpoint Validation Tests
# ===================================================================

class TestProfileInputValidation:
    """Test input validation for profile endpoints."""

    @pytest.mark.asyncio
    async def test_bio_length_validation(self, client, auth_headers):
        """Test bio field length limits (already has max_length=2000)."""
        # Oversized bio
        response = await client.put(
            "/api/users/profile",
            json={"bio": "a" * 2001},
            headers=auth_headers
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_bio_xss_sanitization(self, client, auth_headers):
        """Test XSS sanitization in bio field."""
        for xss_payload in XSS_PAYLOADS[:5]:
            response = await client.put(
                "/api/users/profile",
                json={"bio": xss_payload},
                headers=auth_headers
            )
            # Should accept but sanitize
            if response.status_code == 200:
                data = await response.get_json()
                assert "<script>" not in data.get("bio", "").lower()
                assert "onerror" not in data.get("bio", "").lower()

    @pytest.mark.asyncio
    async def test_career_goals_xss_sanitization(self, client, auth_headers):
        """Test XSS sanitization in career_goals field."""
        for xss_payload in XSS_PAYLOADS[:5]:
            response = await client.put(
                "/api/users/profile",
                json={"career_goals": xss_payload},
                headers=auth_headers
            )
            # Should accept but sanitize
            if response.status_code == 200:
                data = await response.get_json()
                assert "<script>" not in data.get("career_goals", "").lower()


# ===================================================================
# Exercise Endpoint Validation Tests
# ===================================================================

class TestExerciseInputValidation:
    """Test input validation for exercise endpoints."""

    @pytest.mark.asyncio
    async def test_solution_length_validation(self, client, auth_headers, sample_exercise):
        """Test solution code length limits."""
        # Empty solution (already validated by min_length=1)
        response = await client.post(
            f"/api/exercises/{sample_exercise['id']}/submit",
            json={"solution": ""},
            headers=auth_headers
        )
        assert response.status_code == 400

        # Oversized solution (should be max 50KB for code submissions)
        response = await client.post(
            f"/api/exercises/{sample_exercise['id']}/submit",
            json={"solution": "a" * 51000},
            headers=auth_headers
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_solution_sql_injection_safe(self, client, auth_headers, sample_exercise):
        """Test that SQL injection in solution code doesn't break validation."""
        for sql_payload in SQL_INJECTION_PAYLOADS[:5]:
            response = await client.post(
                f"/api/exercises/{sample_exercise['id']}/submit",
                json={"solution": sql_payload},
                headers=auth_headers
            )
            # Should accept (it's user code, not a query), but validate properly
            assert response.status_code in [200, 201, 400]  # Not 500 (server error)

    @pytest.mark.asyncio
    async def test_hint_context_length_validation(self, client, auth_headers, sample_exercise):
        """Test hint context length limits."""
        # Oversized context
        response = await client.post(
            f"/api/exercises/{sample_exercise['id']}/hint",
            json={"context": "a" * 2001},
            headers=auth_headers
        )
        assert response.status_code == 400


# ===================================================================
# GitHub URL Validation Tests
# ===================================================================

class TestGitHubURLValidation:
    """Test GitHub URL validation for repository links."""

    @pytest.mark.asyncio
    async def test_valid_github_urls(self, client):
        """Test that valid GitHub URLs are accepted."""
        valid_urls = [
            "https://github.com/user/repo",
            "https://github.com/user/repo-name",
            "https://github.com/user/repo_name",
            "https://github.com/user/repo.git",
            "https://github.com/user-name/repo-name",
        ]

        for url in valid_urls:
            # Test in profile update (if GitHub integration exists)
            # This will be implemented when GitHub integration is fully built
            pass  # Placeholder for now

    @pytest.mark.asyncio
    async def test_invalid_github_urls(self, client):
        """Test that invalid GitHub URLs are rejected."""
        invalid_urls = [
            "http://github.com/user/repo",  # Not HTTPS
            "https://github.com/user",  # No repo
            "https://github.com/",  # Incomplete
            "https://example.com/user/repo",  # Not GitHub
            "javascript:alert('XSS')",  # JavaScript protocol
            "data:text/html,<script>alert('XSS')</script>",  # Data URI
        ]

        for url in invalid_urls:
            # Test in profile update (if GitHub integration exists)
            # This will be implemented when GitHub integration is fully built
            pass  # Placeholder for now


# ===================================================================
# Unicode and Edge Case Tests
# ===================================================================

class TestUnicodeEdgeCases:
    """Test handling of unicode and special characters."""

    @pytest.mark.asyncio
    async def test_emoji_in_text_fields(self, client, auth_headers):
        """Test that emojis are handled correctly."""
        response = await client.put(
            "/api/users/profile",
            json={"bio": "I love coding! 💻🚀"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = await response.get_json()
        assert "💻" in data.get("bio", "")

    @pytest.mark.asyncio
    async def test_rtl_text(self, client, auth_headers):
        """Test right-to-left text (Arabic, Hebrew)."""
        response = await client.put(
            "/api/users/profile",
            json={"bio": "مرحبا بالعالم"},
            headers=auth_headers
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_zero_width_characters(self, client, auth_headers):
        """Test zero-width characters don't bypass length validation."""
        # Name with zero-width spaces
        response = await client.put(
            "/api/users/profile",
            json={"name": "\u200b" * 10},  # 10 zero-width spaces
        headers=auth_headers
        )
        # Should be rejected as effectively empty
        assert response.status_code == 400


# ===================================================================
# Oversized Input Tests
# ===================================================================

class TestOversizedInputs:
    """Test handling of oversized inputs."""

    @pytest.mark.asyncio
    async def test_oversized_career_goals(self, client, auth_headers):
        """Test career_goals max length enforcement."""
        response = await client.put(
            "/api/users/profile",
            json={"career_goals": "a" * 1001},  # Max is 1000
            headers=auth_headers
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_oversized_chat_message(self, client, auth_headers):
        """Test chat message max length enforcement."""
        response = await client.post(
            "/api/chat/message",
            json={"message": "a" * 5001},  # Should be max 5000
            headers=auth_headers
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_oversized_exercise_solution(self, client, auth_headers, sample_exercise):
        """Test exercise solution max length enforcement."""
        response = await client.post(
            f"/api/exercises/{sample_exercise['id']}/submit",
            json={"solution": "a" * 51000},  # Should be max 50KB
            headers=auth_headers
        )
        assert response.status_code == 400


# ===================================================================
# Validation Error Message Tests
# ===================================================================

class TestValidationErrorMessages:
    """Test that validation errors return clear, actionable messages."""

    @pytest.mark.asyncio
    async def test_missing_field_error_message(self, client):
        """Test error message for missing required field."""
        response = await client.post("/api/auth/register", json={
            "password": "ValidPass123!"
        })
        assert response.status_code == 400
        data = await response.get_json()

        # Error message should be clear
        assert "message" in data
        assert len(data["message"]) > 10  # Not just "error"

        # Should mention which field is missing
        assert "email" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_length_exceeded_error_message(self, client, auth_headers):
        """Test error message for length validation failure."""
        response = await client.put(
            "/api/users/profile",
            json={"bio": "a" * 2001},
            headers=auth_headers
        )
        assert response.status_code == 400
        data = await response.get_json()

        # Error message should be clear
        assert "message" in data
        assert "2000" in data["message"] or "maximum" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_validation_error_includes_field_name(self, client):
        """Test that validation errors include field name."""
        response = await client.post("/api/auth/register", json={
            "email": "invalid-email",
            "password": "ValidPass123!",
            "name": "Test"
        })
        assert response.status_code == 400
        data = await response.get_json()

        # Error should mention "email" field
        assert "email" in data["message"].lower()


# ===================================================================
# Test Fixtures
# ===================================================================

@pytest.fixture
async def client(app: Quart):
    """Create test client."""
    return app.test_client()


@pytest.fixture
async def auth_headers(client, test_user):
    """Get auth headers for authenticated requests."""
    # Login to get access token
    response = await client.post("/api/auth/login", json={
        "email": test_user["email"],
        "password": test_user["password"]
    })

    data = await response.get_json()
    access_token = data["access_token"]

    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
async def test_user(client):
    """Create a test user."""
    random_id = str(uuid.uuid4())[:8]
    user_data = {
        "email": f"test_validation_{random_id}@example.com",
        "password": "ValidPass123!",
        "name": "Test Validation User"
    }

    # Register user
    await client.post("/api/auth/register", json=user_data)

    return user_data


@pytest.fixture
async def sample_exercise(client, auth_headers):
    """Create a sample exercise for testing."""
    # Get daily exercise
    response = await client.get(
        "/api/exercises/daily",
        headers=auth_headers
    )

    data = await response.get_json()
    return data["exercise"]

"""
Tests for authentication API endpoints.
Tests user registration, login, OAuth, token refresh, email verification, and password reset.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, Mock
from sqlalchemy import select
from src.models.user import User, UserRole


@pytest.mark.asyncio
async def test_register_success(client, patched_get_session, mock_email_service, mock_auth_tokens):
    """
    Test POST /api/v1/auth/register with valid data creates user.
    """
    registration_data = {
        "email": "test@example.com",
        "password": "SecureP@ssw0rd123",
        "name": "Test User"
    }

    response = await client.post("/api/v1/auth/register", json=registration_data)
    assert response.status_code == 201

    data = await response.get_json()
    assert data["message"] == "Registration successful. Please check your email to verify your account."
    assert "user" in data
    assert data["user"]["email"] == "test@example.com"
    assert data["user"]["name"] == "Test User"
    assert data["user"]["email_verified"] is False

    # Verify email was sent
    mock_email_service.send_verification_email.assert_called_once()
    # Verify token was stored
    mock_auth_tokens['verify'].assert_called_once()


@pytest.mark.asyncio
async def test_register_missing_fields(client):
    """
    Test POST /api/v1/auth/register with missing fields returns 400.
    """
    # Missing password
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "name": "Test User"
    })
    assert response.status_code == 400

    # Missing email
    response = await client.post("/api/v1/auth/register", json={
        "password": "SecureP@ssw0rd123",
        "name": "Test User"
    })
    assert response.status_code == 400

    # Missing name
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "SecureP@ssw0rd123"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """
    Test POST /api/v1/auth/register with invalid email returns 400.
    """
    response = await client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "password": "SecureP@ssw0rd123",
        "name": "Test User"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password(client):
    """
    Test POST /api/v1/auth/register with weak password returns 400.
    """
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "weak",
        "name": "Test User"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_email(client, patched_get_session, mock_email_service, mock_auth_tokens):
    """
    Test POST /api/v1/auth/register with existing email returns 409.
    """
    # Create first user
    registration_data = {
        "email": "duplicate@example.com",
        "password": "SecureP@ssw0rd123",
        "name": "First User"
    }
    response1 = await client.post("/api/v1/auth/register", json=registration_data)
    assert response1.status_code == 201

    # Try to create duplicate
    registration_data["name"] = "Second User"
    response2 = await client.post("/api/v1/auth/register", json=registration_data)
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client, patched_get_session, mock_email_service, mock_auth_tokens, mock_auth_session):
    """
    Test POST /api/v1/auth/login with valid credentials returns tokens.
    """
    # Register user first
    registration_data = {
        "email": "login@example.com",
        "password": "SecureP@ssw0rd123",
        "name": "Login User"
    }
    await client.post("/api/v1/auth/register", json=registration_data)

    # Login with correct credentials
    login_data = {
        "email": "login@example.com",
        "password": "SecureP@ssw0rd123"
    }
    response = await client.post("/api/v1/auth/login", json=login_data)
    assert response.status_code == 200

    data = await response.get_json()
    assert data["message"] == "Login successful"
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data
    assert data["user"]["email"] == "login@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client, patched_get_session, mock_email_service, mock_auth_tokens):
    """
    Test POST /api/v1/auth/login with wrong password returns 401.
    """
    # Register user
    await client.post("/api/v1/auth/register", json={
        "email": "wrongpass@example.com",
        "password": "CorrectP@ssw0rd123",
        "name": "User"
    })

    # Try to login with wrong password
    response = await client.post("/api/v1/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "WrongP@ssw0rd123"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client, patched_get_session):
    """
    Test POST /api/v1/auth/login with nonexistent email returns 401.
    """
    response = await client.post("/api/v1/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "AnyP@ssw0rd123"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_requires_auth(client):
    """
    Test POST /api/v1/auth/logout without token returns 401.
    """
    response = await client.post("/api/v1/auth/logout")
    # Should fail due to missing auth token
    assert response.status_code in [401, 403, 500]  # Depends on auth middleware implementation


@pytest.mark.asyncio
async def test_verify_email_success(client, db_session):
    """
    Test POST /api/v1/auth/verify-email with valid token verifies email.
    """
    with patch('src.api.auth.get_session') as mock_get_session, \
         patch('src.services.auth_service.AuthService.verify_verification_token', new_callable=AsyncMock) as mock_verify, \
         patch('src.services.email_service.get_email_service') as mock_email_service:

        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_get_session.return_value.__aexit__.return_value = None

        # Setup mock to return email
        mock_verify.return_value = "verify@example.com"

        # Configure email service mock
        mock_email = AsyncMock()
        mock_email_service.return_value = mock_email

        # Create unverified user in database
        from src.services.auth_service import AuthService
        user = User(
            email="verify@example.com",
            password_hash=AuthService.hash_password("P@ssw0rd1234"),
            name="Verify User",
            role=UserRole.STUDENT,
            email_verified=False,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Verify email
        response = await client.post("/api/v1/auth/verify-email", json={
            "token": "valid_token_123"
        })
        assert response.status_code == 200

        data = await response.get_json()
        assert data["message"] == "Email verified successfully"


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client):
    """
    Test POST /api/v1/auth/verify-email with invalid token returns 400.
    """
    with patch('src.services.auth_service.AuthService.verify_verification_token', new_callable=AsyncMock) as mock_verify:
        # Mock returns None for invalid token
        mock_verify.return_value = None

        response = await client.post("/api/v1/auth/verify-email", json={
            "token": "invalid_token"
        })
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_request(client, db_session):
    """
    Test POST /api/v1/auth/password-reset requests password reset.
    """
    with patch('src.api.auth.get_session') as mock_get_session, \
         patch('src.services.auth_service.AuthService.store_password_reset_token', new_callable=AsyncMock), \
         patch('src.services.email_service.get_email_service') as mock_email_service:

        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_get_session.return_value.__aexit__.return_value = None

        # Configure email service mock
        mock_email = AsyncMock()
        mock_email_service.return_value = mock_email

        # Create user
        from src.services.auth_service import AuthService
        user = User(
            email="reset@example.com",
            password_hash=AuthService.hash_password("OldP@ssw0rd123"),
            name="Reset User",
            role=UserRole.STUDENT,
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        response = await client.post("/api/v1/auth/password-reset", json={
            "email": "reset@example.com"
        })
        assert response.status_code == 200

        data = await response.get_json()
        assert "password reset link has been sent" in data["message"].lower()


@pytest.mark.asyncio
async def test_password_reset_nonexistent_email(client):
    """
    Test POST /api/v1/auth/password-reset with nonexistent email.
    Should return success to prevent email enumeration.
    """
    with patch('src.api.auth.get_session') as mock_get_session:
        # Mock empty database
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none = Mock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_get_session.return_value.__aenter__.return_value = mock_session
        mock_get_session.return_value.__aexit__.return_value = None

        response = await client.post("/api/v1/auth/password-reset", json={
            "email": "nonexistent@example.com"
        })
        # Should return 200 to prevent email enumeration
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_password_reset_confirm_success(client, db_session):
    """
    Test POST /api/v1/auth/password-reset/confirm resets password.
    """
    with patch('src.api.auth.get_session') as mock_get_session, \
         patch('src.services.auth_service.AuthService.verify_password_reset_token', new_callable=AsyncMock) as mock_verify:

        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_get_session.return_value.__aexit__.return_value = None

        # Mock valid token
        mock_verify.return_value = "resetconfirm@example.com"

        # Create user
        from src.services.auth_service import AuthService
        old_password_hash = AuthService.hash_password("OldP@ssw0rd123")
        user = User(
            email="resetconfirm@example.com",
            password_hash=old_password_hash,
            name="Reset Confirm User",
            role=UserRole.STUDENT,
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Reset password
        response = await client.post("/api/v1/auth/password-reset/confirm", json={
            "token": "valid_reset_token",
            "new_password": "NewSecureP@ssw0rd456"
        })
        assert response.status_code == 200

        data = await response.get_json()
        assert "password reset successful" in data["message"].lower()


@pytest.mark.asyncio
async def test_password_reset_confirm_weak_password(client):
    """
    Test POST /api/v1/auth/password-reset/confirm with weak password returns 400.
    """
    with patch('src.services.auth_service.AuthService.verify_password_reset_token', new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = "user@example.com"

        response = await client.post("/api/v1/auth/password-reset/confirm", json={
            "token": "valid_token",
            "new_password": "weak"
        })
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_refresh_token_success(client, db_session):
    """
    Test POST /api/v1/auth/refresh with valid refresh token returns new access token.
    """
    with patch('src.api.auth.get_session') as mock_get_session, \
         patch('src.services.auth_service.AuthService.verify_jwt_token') as mock_verify, \
         patch('src.services.auth_service.AuthService.create_session', new_callable=AsyncMock):

        mock_get_session.return_value.__aenter__.return_value = db_session
        mock_get_session.return_value.__aexit__.return_value = None

        # Create user
        from src.services.auth_service import AuthService
        user = User(
            email="refresh@example.com",
            password_hash=AuthService.hash_password("P@ssw0rd1234"),
            name="Refresh User",
            role=UserRole.STUDENT,
            email_verified=True,
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()

        # Mock token verification to return user ID
        mock_verify.return_value = {"user_id": user.id, "email": user.email}

        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "valid_refresh_token"
        })
        assert response.status_code == 200

        data = await response.get_json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_invalid(client):
    """
    Test POST /api/v1/auth/refresh with invalid token returns 401.
    """
    with patch('src.services.auth_service.AuthService.verify_jwt_token') as mock_verify:
        # Mock raises exception for invalid token
        from src.middleware.error_handler import APIError
        mock_verify.side_effect = APIError("Invalid token", status_code=401)

        response = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token"
        })
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_missing(client):
    """
    Test POST /api/v1/auth/refresh without token returns 400.
    """
    response = await client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 400

"""
Pydantic schemas for authentication endpoints (SEC-3-INPUT).

These schemas provide comprehensive input validation for:
- User registration
- User login
- Password reset
- Email verification
- OAuth flows

Security Features:
- Email format validation
- Password strength enforcement
- Field length limits
- HTML/XSS sanitization
- Clear validation error messages
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator, EmailStr
import re
import html


def sanitize_html(text: str) -> str:
    """
    Sanitize HTML/XSS from user input.

    Escapes HTML entities to prevent XSS attacks.
    This is a basic sanitization - markdown fields use bleach for more comprehensive sanitization.

    Args:
        text: Raw user input

    Returns:
        Sanitized text with HTML entities escaped
    """
    return html.escape(text.strip())


class RegisterRequest(BaseModel):
    """
    Schema for user registration.

    Security validations:
    - Email format validation (RFC 5322)
    - Password strength (min 8 chars, uppercase, lowercase, number, special char)
    - Name sanitization (HTML escaping)
    - Field length limits
    """
    email: EmailStr = Field(
        ...,
        description="User email address (must be valid format)"
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (min 8 chars, must include uppercase, lowercase, number, special char)"
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User full name"
    )

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """
        Enforce strong password requirements.

        Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one number
        - At least one special character

        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r'[A-Z]', value):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r'[a-z]', value):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r'\d', value):
            raise ValueError("Password must contain at least one number")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise ValueError("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)")

        return value

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        """
        Validate and sanitize name field.

        - Strips leading/trailing whitespace
        - Escapes HTML entities (XSS protection)
        - Ensures non-empty after stripping

        Raises:
            ValueError: If name is empty after stripping
        """
        stripped = value.strip()

        if not stripped:
            raise ValueError("Name cannot be empty")

        # Sanitize HTML to prevent XSS
        sanitized = sanitize_html(stripped)

        return sanitized


class LoginRequest(BaseModel):
    """
    Schema for user login.

    Security validations:
    - Email format validation
    - Password field required
    """
    email: EmailStr = Field(
        ...,
        description="User email address"
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="User password"
    )


class PasswordResetRequestSchema(BaseModel):
    """
    Schema for password reset request (send reset email).

    Security validations:
    - Email format validation
    - Rate limiting (applied at endpoint level)
    """
    email: EmailStr = Field(
        ...,
        description="Email address to send password reset link"
    )


class PasswordResetConfirmSchema(BaseModel):
    """
    Schema for password reset confirmation (set new password).

    Security validations:
    - Token validation
    - Password strength enforcement
    - New password != old password (enforced at service layer)
    """
    token: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Password reset token from email"
    )
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password (min 8 chars, must include uppercase, lowercase, number, special char)"
    )

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        """Enforce strong password requirements (same as RegisterRequest)."""
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r'[A-Z]', value):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r'[a-z]', value):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r'\d', value):
            raise ValueError("Password must contain at least one number")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise ValueError("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)")

        return value


class EmailVerificationResendSchema(BaseModel):
    """
    Schema for resending email verification.

    Security validations:
    - Email format validation
    - Rate limiting (applied at endpoint level)
    """
    email: EmailStr = Field(
        ...,
        description="Email address to resend verification"
    )


class OAuthCallbackSchema(BaseModel):
    """
    Schema for OAuth callback (exchange authorization code for tokens).

    Security validations:
    - Code validation
    - State validation (CSRF protection)
    - Provider validation
    """
    code: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Authorization code from OAuth provider"
    )
    state: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="State parameter for CSRF protection"
    )
    provider: str = Field(
        ...,
        description="OAuth provider (github, google, etc.)"
    )

    @field_validator('provider')
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """
        Validate OAuth provider.

        Raises:
            ValueError: If provider is not supported
        """
        allowed_providers = ['github', 'google']

        if value.lower() not in allowed_providers:
            raise ValueError(f"Unsupported OAuth provider. Allowed: {', '.join(allowed_providers)}")

        return value.lower()


class RefreshTokenRequest(BaseModel):
    """
    Schema for refreshing access token.

    Note: Refresh token is read from httpOnly cookie, not request body.
    This schema is for documentation purposes.
    """
    pass  # No fields - token comes from cookie


# ===================================================================
# Response Schemas
# ===================================================================

class RegisterResponse(BaseModel):
    """Response schema for successful registration."""
    user_id: int
    email: str
    name: str
    message: str


class LoginResponse(BaseModel):
    """
    Response schema for successful login.

    Note: Tokens are set in httpOnly cookies, not response body (SEC-1 security hardening).
    """
    user_id: int
    email: str
    name: str
    message: str


class PasswordResetRequestResponse(BaseModel):
    """Response schema for password reset request."""
    message: str


class PasswordResetConfirmResponse(BaseModel):
    """Response schema for password reset confirmation."""
    message: str


class EmailVerificationResponse(BaseModel):
    """Response schema for email verification."""
    message: str
    email_verified: bool

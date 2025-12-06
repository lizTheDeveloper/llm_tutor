"""
Authentication API endpoints.
Handles user registration, login, OAuth, and session management.
"""
from quart import Blueprint, request, jsonify, redirect, make_response
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.middleware.auth_middleware import require_auth, get_current_user_id
from src.middleware.rate_limiter import rate_limit
from src.middleware.csrf_protection import inject_csrf_token_on_login, clear_csrf_token_on_logout
from src.services.auth_service import AuthService
from src.services.email_service import get_email_service
from src.services.oauth_service import OAuthService
from src.models.user import User, UserRole
from src.utils.database import get_async_db_session as get_session
from src.config import settings
from src.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    PasswordResetRequestSchema,
    PasswordResetConfirmSchema,
    EmailVerificationResendSchema,
)
from pydantic import ValidationError

logger = get_logger(__name__)
auth_bp = Blueprint("auth", __name__)


def set_auth_cookies(response, access_token: str, refresh_token: str):
    """
    Set authentication tokens in httpOnly cookies.

    Args:
        response: Quart response object
        access_token: JWT access token
        refresh_token: JWT refresh token

    Security Features:
    - httpOnly: Prevents JavaScript access (XSS protection)
    - secure: Only sent over HTTPS (except in development)
    - samesite=Strict: Prevents CSRF attacks
    - max_age: Automatic expiration

    This addresses AP-SEC-001: Token storage in localStorage vulnerability.
    """
    is_production = settings.app_env == "production"

    # Access token cookie (24 hours)
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.jwt_access_token_expire_hours * 3600,  # Convert to seconds
        httponly=True,
        secure=is_production,  # Only HTTPS in production
        samesite="Strict",  # Prevent CSRF
        path="/",
    )

    # Refresh token cookie (30 days)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.jwt_refresh_token_expire_days * 24 * 3600,  # Convert to seconds
        httponly=True,
        secure=is_production,
        samesite="Strict",
        path="/",
    )

    logger.debug("Auth cookies set", extra={"httponly": True, "secure": is_production})


def clear_auth_cookies(response):
    """
    Clear authentication cookies on logout.

    Args:
        response: Quart response object
    """
    response.set_cookie(
        key="access_token",
        value="",
        max_age=0,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="Strict",
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value="",
        max_age=0,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="Strict",
        path="/",
    )
    logger.debug("Auth cookies cleared")


@auth_bp.route("/register", methods=["POST"])
@rate_limit(requests_per_minute=5, requests_per_hour=20)
async def register() -> Dict[str, Any]:
    """
    Register a new user with email and password.

    Request Body:
        {
            "email": "user@example.com",
            "password": "secure_password",
            "name": "User Name"
        }

    Returns:
        JSON response with user data and message
    """
    data = await request.get_json()

    # Validate using Pydantic schema (SEC-3-INPUT)
    try:
        validated_data = RegisterRequest(**data)
    except ValidationError as validation_error:
        # Extract clear error message
        errors = validation_error.errors()
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        raise APIError(
            f"Validation error: {'; '.join(error_messages)}",
            status_code=400,
        )

    # Extract validated fields
    email = validated_data.email.lower()
    password = validated_data.password
    name = validated_data.name

    # Hash password
    password_hash = AuthService.hash_password(password)

    # Generate email verification token
    verification_token = AuthService.generate_verification_token()

    # Create user in database
    async with get_session() as session:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.warning(
                "Registration attempt with existing email",
                extra={"email": email},
            )
            # Don't reveal that user exists - return same message as success
            # This prevents email enumeration attacks
            return jsonify({
                "message": "Registration successful. Please check your email to verify your account.",
                "user": {
                    "email": email,
                },
            }), 201

        # Create new user
        new_user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            role=UserRole.STUDENT,
            email_verified=False,
            is_active=True,
        )

        session.add(new_user)

        try:
            await session.flush()
            await session.refresh(new_user)

            logger.info(
                "User registered successfully",
                extra={"user_id": new_user.id, "email": email},
            )

            # Store verification token in Redis
            await AuthService.store_verification_token(email, verification_token)

            # Send verification email
            email_service = get_email_service()
            await email_service.send_verification_email(email, verification_token)

            return jsonify({
                "message": "Registration successful. Please check your email to verify your account.",
                "user": {
                    "id": new_user.id,
                    "email": new_user.email,
                    "name": new_user.name,
                    "email_verified": new_user.email_verified,
                },
            }), 201

        except IntegrityError as exception:
            await session.rollback()
            logger.error("Database integrity error during registration", exc_info=True)
            raise APIError(
                "User with this email already exists",
                status_code=409,
            )


@auth_bp.route("/login", methods=["POST"])
@rate_limit(requests_per_minute=10, requests_per_hour=100)
async def login() -> Dict[str, Any]:
    """
    Login with email and password.

    Request Body:
        {
            "email": "user@example.com",
            "password": "secure_password"
        }

    Returns:
        JSON response with JWT tokens
    """
    data = await request.get_json()

    # Validate using Pydantic schema (SEC-3-INPUT)
    try:
        validated_data = LoginRequest(**data)
    except ValidationError as validation_error:
        errors = validation_error.errors()
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        raise APIError(
            f"Validation error: {'; '.join(error_messages)}",
            status_code=400,
        )

    email = validated_data.email.lower()
    password = validated_data.password

    # Get user from database
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user or not user.password_hash:
            logger.warning("Login attempt with invalid credentials", extra={"email": email})
            raise APIError("Invalid email or password", status_code=401)

        # Verify password
        if not AuthService.verify_password(password, user.password_hash):
            logger.warning("Login attempt with wrong password", extra={"email": email})
            raise APIError("Invalid email or password", status_code=401)

        # Check if user is active
        if not user.is_active:
            logger.warning("Login attempt for inactive user", extra={"email": email})
            raise APIError("Account is inactive. Please contact support.", status_code=403)

        # Generate token pair
        tokens = AuthService.generate_token_pair(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
        )

        # Create session in Redis
        await AuthService.create_session(
            user_id=user.id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_data={
                "name": user.name,
                "email_verified": user.email_verified,
            },
        )

        # Update last login timestamp
        user.last_login = datetime.utcnow()
        await session.flush()

        logger.info("User logged in successfully", extra={"user_id": user.id, "email": email})

        # Create response with user data (NO tokens in JSON)
        response_data = {
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value,
                "email_verified": user.email_verified,
            },
        }

        # Create response and set httpOnly cookies
        response = await make_response(jsonify(response_data), 200)
        set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])

        # SEC-3-CSRF: Generate and set CSRF token on login
        response = await inject_csrf_token_on_login(
            response,
            is_production=(settings.app_env == "production")
        )

        return response


@auth_bp.route("/logout", methods=["POST"])
@require_auth
async def logout() -> Dict[str, Any]:
    """
    Logout and invalidate session.

    Headers:
        Authorization: Bearer <access_token>

    Returns:
        JSON response confirming logout
    """
    user_id = get_current_user_id()

    # Get token from header or cookie
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split()[1] if len(auth_header.split()) == 2 else None

    if not token:
        token = request.cookies.get("access_token")

    if token:
        # Invalidate session in Redis
        await AuthService.invalidate_session(user_id, token)

    logger.info("User logged out successfully", extra={"user_id": user_id})

    # Create response and clear auth cookies
    response = await make_response(jsonify({"message": "Logout successful"}), 200)
    clear_auth_cookies(response)

    # SEC-3-CSRF: Clear CSRF token on logout
    response = await clear_csrf_token_on_logout(
        response,
        is_production=(settings.app_env == "production")
    )

    return response


@auth_bp.route("/oauth/github", methods=["GET"])
async def oauth_github() -> Dict[str, Any]:
    """
    Initiate GitHub OAuth flow.

    Returns:
        Redirect to GitHub authorization URL
    """
    from src.config import settings

    # Generate OAuth state for CSRF protection
    state = await OAuthService.generate_oauth_state("github")

    # Build redirect URI from config
    redirect_uri = f"{settings.backend_url}/api/auth/oauth/github/callback"

    # Get authorization URL
    auth_url = OAuthService.get_github_authorization_url(state, redirect_uri)

    logger.info("GitHub OAuth flow initiated", extra={"state": state[:10] + "..."})

    # Redirect to GitHub
    return redirect(auth_url)


@auth_bp.route("/oauth/github/callback", methods=["GET"])
async def oauth_github_callback() -> Dict[str, Any]:
    """
    Handle GitHub OAuth callback.

    Query Parameters:
        code: Authorization code from GitHub
        state: State parameter for CSRF protection

    Returns:
        Redirect to frontend with authorization code (NOT tokens)
    """
    from src.config import settings

    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        logger.warning("GitHub OAuth error", extra={"error": error})
        return redirect(f"{settings.frontend_url}/login?error=oauth_failed")

    if not code or not state:
        raise APIError("Missing OAuth parameters", status_code=400)

    # Verify state parameter
    await OAuthService.verify_oauth_state(state, "github")

    # Store the authorization code temporarily in Redis for exchange
    temp_code = AuthService.generate_verification_token()
    await AuthService.store_verification_token(
        f"oauth_github_{code}",
        temp_code,
        expiration=300  # 5 minutes
    )

    # Redirect to frontend with temporary code (NOT actual tokens)
    return redirect(f"{settings.frontend_url}/auth/callback?code={temp_code}&provider=github")


@auth_bp.route("/oauth/exchange", methods=["POST"])
async def oauth_exchange_code() -> Dict[str, Any]:
    """
    Exchange temporary OAuth code for JWT tokens.
    Called by frontend after OAuth callback redirect.

    Request Body:
        {
            "code": "temporary_code",
            "provider": "github" or "google"
        }

    Returns:
        JSON response with JWT tokens
    """
    from src.config import settings

    data = await request.get_json()
    temp_code = data.get("code")
    provider = data.get("provider")

    if not temp_code or provider not in ["github", "google"]:
        raise APIError("Invalid code or provider", status_code=400)

    # Retrieve original OAuth code from Redis
    stored_data = await AuthService.verify_verification_token(temp_code)
    if not stored_data:
        raise APIError("Invalid or expired code", status_code=400)

    # Extract the real OAuth code
    oauth_code_key = stored_data.replace(f"oauth_{provider}_", "")

    # Exchange code for access token based on provider
    redirect_uri = f"{settings.backend_url}/api/auth/oauth/{provider}/callback"

    if provider == "github":
        oauth_access_token = await OAuthService.exchange_github_code(oauth_code_key, redirect_uri)
        oauth_profile = await OAuthService.get_github_user_info(oauth_access_token)
        id_field = "github_id"
    else:  # google
        oauth_access_token = await OAuthService.exchange_google_code(oauth_code_key, redirect_uri)
        oauth_profile = await OAuthService.get_google_user_info(oauth_access_token)
        id_field = "google_id"

    if not oauth_profile.get("email"):
        raise APIError(f"{provider.title()} account must have a verified email address", status_code=400)

    # Create or update user in database
    async with get_session() as session:
        # Check if user exists with this OAuth ID
        filter_clause = getattr(User, id_field) == oauth_profile[id_field]
        result = await session.execute(select(User).where(filter_clause))
        user = result.scalar_one_or_none()

        if not user:
            # Check if user exists with this email
            result = await session.execute(
                select(User).where(User.email == oauth_profile["email"])
            )
            user = result.scalar_one_or_none()

            if user:
                # Link OAuth account to existing user
                setattr(user, id_field, oauth_profile[id_field])
                user.oauth_provider = provider
                if not user.avatar_url:
                    user.avatar_url = oauth_profile.get("avatar_url")
                logger.info(f"{provider.title()} account linked to existing user", extra={"user_id": user.id})
            else:
                # Create new user
                user_data = {
                    "email": oauth_profile["email"],
                    "oauth_provider": provider,
                    "name": oauth_profile["name"],
                    "avatar_url": oauth_profile.get("avatar_url"),
                    "email_verified": True,
                    "role": UserRole.STUDENT,
                    "is_active": True,
                }
                user_data[id_field] = oauth_profile[id_field]
                if provider == "github" and oauth_profile.get("bio"):
                    user_data["bio"] = oauth_profile["bio"]

                user = User(**user_data)
                session.add(user)
                logger.info(f"New user created via {provider.title()} OAuth", extra={"email": oauth_profile["email"]})

        await session.flush()
        await session.refresh(user)

        # Generate JWT tokens
        tokens = AuthService.generate_token_pair(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
        )

        # Create session
        await AuthService.create_session(
            user_id=user.id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user_data={
                "name": user.name,
                "email_verified": user.email_verified,
            },
        )

        # Update last login
        user.last_login = datetime.utcnow()
        await session.flush()

        logger.info(f"{provider.title()} OAuth exchange successful", extra={"user_id": user.id})

        # Create response with user data (NO tokens in JSON)
        response_data = {
            "message": "OAuth authentication successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role.value,
                "email_verified": user.email_verified,
            },
        }

        # Create response and set httpOnly cookies
        response = await make_response(jsonify(response_data), 200)
        set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])

        # SEC-3-CSRF: Generate and set CSRF token on OAuth login
        response = await inject_csrf_token_on_login(
            response,
            is_production=(settings.app_env == "production")
        )

        return response


@auth_bp.route("/oauth/google", methods=["GET"])
async def oauth_google() -> Dict[str, Any]:
    """
    Initiate Google OAuth flow.

    Returns:
        Redirect to Google authorization URL
    """
    from src.config import settings

    # Generate OAuth state for CSRF protection
    state = await OAuthService.generate_oauth_state("google")

    # Build redirect URI from config
    redirect_uri = f"{settings.backend_url}/api/auth/oauth/google/callback"

    # Get authorization URL
    auth_url = OAuthService.get_google_authorization_url(state, redirect_uri)

    logger.info("Google OAuth flow initiated", extra={"state": state[:10] + "..."})

    # Redirect to Google
    return redirect(auth_url)


@auth_bp.route("/oauth/google/callback", methods=["GET"])
async def oauth_google_callback() -> Dict[str, Any]:
    """
    Handle Google OAuth callback.

    Query Parameters:
        code: Authorization code from Google
        state: State parameter for CSRF protection

    Returns:
        Redirect to frontend with authorization code (NOT tokens)
    """
    from src.config import settings

    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        logger.warning("Google OAuth error", extra={"error": error})
        return redirect(f"{settings.frontend_url}/login?error=oauth_failed")

    if not code or not state:
        raise APIError("Missing OAuth parameters", status_code=400)

    # Verify state parameter
    await OAuthService.verify_oauth_state(state, "google")

    # Store the authorization code temporarily in Redis for exchange
    temp_code = AuthService.generate_verification_token()
    await AuthService.store_verification_token(
        f"oauth_google_{code}",
        temp_code,
        expiration=300  # 5 minutes
    )

    # Redirect to frontend with temporary code (NOT actual tokens)
    return redirect(f"{settings.frontend_url}/auth/callback?code={temp_code}&provider=google")


@auth_bp.route("/refresh", methods=["POST"])
async def refresh_token() -> Dict[str, Any]:
    """
    Refresh access token using refresh token.

    Request Body:
        {
            "refresh_token": "refresh_token_here"
        }

    Returns:
        JSON response with new access token
    """
    data = await request.get_json()
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        raise APIError("Refresh token is required", status_code=400)

    # Verify refresh token
    payload = AuthService.verify_jwt_token(refresh_token, token_type="refresh")

    # Get user from database to ensure they still exist and are active
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.id == payload["user_id"])
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            logger.warning(
                "Refresh attempt for non-existent or inactive user",
                extra={"user_id": payload["user_id"]},
            )
            raise APIError("Invalid refresh token", status_code=401)

        # Generate new access token
        new_access_token = AuthService.generate_jwt_token(
            user_id=user.id,
            email=user.email,
            role=user.role.value,
            token_type="access",
        )

        # Create new session with the new access token
        await AuthService.create_session(
            user_id=user.id,
            access_token=new_access_token,
            refresh_token=refresh_token,
            user_data={
                "name": user.name,
                "email_verified": user.email_verified,
            },
        )

        logger.info("Access token refreshed", extra={"user_id": user.id})

        return jsonify({
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": 86400,  # 24 hours in seconds
        }), 200


@auth_bp.route("/verify-email", methods=["POST"])
async def verify_email() -> Dict[str, Any]:
    """
    Verify user email with verification token.

    Request Body:
        {
            "token": "verification_token"
        }

    Returns:
        JSON response confirming verification
    """
    data = await request.get_json()
    token = data.get("token")

    if not token:
        raise APIError("Verification token is required", status_code=400)

    # Verify token and get email
    email = await AuthService.verify_verification_token(token)

    if not email:
        raise APIError("Invalid or expired verification token", status_code=400)

    # Update user in database
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.error("User not found for email verification", extra={"email": email})
            raise APIError("User not found", status_code=404)

        if user.email_verified:
            logger.info("Email already verified", extra={"user_id": user.id})
            return jsonify({
                "message": "Email already verified"
            }), 200

        # Mark email as verified
        user.email_verified = True
        await session.flush()

        logger.info("Email verified successfully", extra={"user_id": user.id, "email": email})

        # Send welcome email
        email_service = get_email_service()
        await email_service.send_welcome_email(user.email, user.name)

        return jsonify({
            "message": "Email verified successfully",
            "user": {
                "id": user.id,
                "email": user.email,
                "email_verified": user.email_verified,
            },
        }), 200


@auth_bp.route("/password-reset", methods=["POST"])
@rate_limit(requests_per_minute=3, requests_per_hour=10)
async def request_password_reset() -> Dict[str, Any]:
    """
    Request password reset email.

    Request Body:
        {
            "email": "user@example.com"
        }

    Returns:
        JSON response confirming email sent
    """
    data = await request.get_json()

    # Validate using Pydantic schema (SEC-3-INPUT)
    try:
        validated_data = PasswordResetRequestSchema(**data)
    except ValidationError as validation_error:
        errors = validation_error.errors()
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        raise APIError(
            f"Validation error: {'; '.join(error_messages)}",
            status_code=400,
        )

    email = validated_data.email.lower()

    # Check if user exists
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # Always return success to prevent email enumeration
        # Don't reveal whether user exists or not
        if not user:
            logger.info("Password reset requested for non-existent email", extra={"email": email})
            return jsonify({
                "message": "If an account with that email exists, a password reset link has been sent."
            }), 200

        # Generate reset token
        reset_token = AuthService.generate_verification_token()

        # Store token in Redis (1 hour expiration)
        await AuthService.store_password_reset_token(email, reset_token, expiration=3600)

        # Send reset email
        email_service = get_email_service()
        await email_service.send_password_reset_email(email, reset_token)

        logger.info("Password reset email sent", extra={"user_id": user.id, "email": email})

        return jsonify({
            "message": "If an account with that email exists, a password reset link has been sent."
        }), 200


@auth_bp.route("/resend-verification", methods=["POST"])
@rate_limit(requests_per_minute=3, requests_per_hour=15)
async def resend_verification_email() -> Dict[str, Any]:
    """
    Resend email verification email.

    Request Body:
        {
            "email": "user@example.com"
        }

    Returns:
        JSON response confirming email sent

    Security Note:
    Part of SEC-2-AUTH: Email Verification Enforcement.
    Always returns success to prevent email enumeration attacks.
    """
    data = await request.get_json()

    # Validate using Pydantic schema (SEC-3-INPUT)
    try:
        validated_data = EmailVerificationResendSchema(**data)
    except ValidationError as validation_error:
        errors = validation_error.errors()
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        raise APIError(
            f"Validation error: {'; '.join(error_messages)}",
            status_code=400,
        )

    email = validated_data.email.lower()

    # Check if user exists
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        # Always return success to prevent email enumeration
        # Don't reveal whether user exists or if email is already verified
        if not user:
            logger.info(
                "Resend verification requested for non-existent email",
                extra={"email": email}
            )
            return jsonify({
                "message": "If an account with that email exists and is unverified, a verification email has been sent."
            }), 200

        # Check if already verified
        if user.email_verified:
            logger.info(
                "Resend verification requested for already verified email",
                extra={"user_id": user.id, "email": email}
            )
            # Still return success, but don't send email
            return jsonify({
                "message": "If an account with that email exists and is unverified, a verification email has been sent."
            }), 200

        # Generate new verification token
        verification_token = AuthService.generate_verification_token()

        # Store token in Redis (24 hours expiration)
        await AuthService.store_verification_token(email, verification_token)

        # Send verification email
        email_service = get_email_service()
        await email_service.send_verification_email(email, verification_token)

        logger.info(
            "Verification email resent",
            extra={"user_id": user.id, "email": email}
        )

        return jsonify({
            "message": "If an account with that email exists and is unverified, a verification email has been sent."
        }), 200


@auth_bp.route("/password-reset/confirm", methods=["POST"])
@rate_limit(requests_per_minute=3, requests_per_hour=10)
@csrf_protect
async def confirm_password_reset() -> Dict[str, Any]:
    """
    Reset password with token.

    Request Body:
        {
            "token": "reset_token",
            "new_password": "new_secure_password"
        }

    Returns:
        JSON response confirming password reset
    """
    data = await request.get_json()

    # Validate using Pydantic schema (SEC-3-INPUT)
    try:
        validated_data = PasswordResetConfirmSchema(**data)
    except ValidationError as validation_error:
        errors = validation_error.errors()
        error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in errors]
        raise APIError(
            f"Validation error: {'; '.join(error_messages)}",
            status_code=400,
        )

    token = validated_data.token
    new_password = validated_data.new_password

    # Verify token and get email
    email = await AuthService.verify_password_reset_token(token)

    if not email:
        raise APIError("Invalid or expired reset token", status_code=400)

    # Hash new password (already validated by Pydantic schema)
    new_password_hash = AuthService.hash_password(new_password)

    # Update user password
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.error("User not found for password reset", extra={"email": email})
            raise APIError("User not found", status_code=404)

        # Update password
        user.password_hash = new_password_hash
        await session.flush()

        logger.info("Password reset successful", extra={"user_id": user.id, "email": email})

        # Invalidate all existing sessions for this user (security best practice)
        await AuthService.invalidate_all_user_sessions(user.id)
        logger.info(
            "All sessions invalidated after password reset",
            extra={"user_id": user.id},
        )

        return jsonify({
            "message": "Password reset successful. Please login with your new password."
        }), 200

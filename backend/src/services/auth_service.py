"""
Authentication service for handling JWT tokens, password hashing, and session management.
Provides core authentication functionality for the CodeMentor platform.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import re
import secrets
import jwt
import bcrypt
from src.config import settings
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.utils.redis_client import get_redis

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""

    # Email validation regex (RFC 5322 simplified)
    EMAIL_REGEX = re.compile(
        r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
    )

    # Password validation regex
    PASSWORD_REGEX = re.compile(
        r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{12,}$"
    )

    @staticmethod
    def validate_email(email: str) -> bool:
        """
        Validate email address format.

        Args:
            email: Email address to validate

        Returns:
            True if email is valid

        Raises:
            APIError: If email format is invalid
        """
        if not email or not isinstance(email, str):
            raise APIError("Email is required", status_code=400)

        if not AuthService.EMAIL_REGEX.match(email):
            raise APIError("Invalid email format", status_code=400)

        return True

    @staticmethod
    def validate_password(password: str) -> bool:
        """
        Validate password meets security requirements.
        Requirements: minimum 12 chars, mixed case, numbers, special characters

        Args:
            password: Password to validate

        Returns:
            True if password is valid

        Raises:
            APIError: If password doesn't meet requirements
        """
        if not password or not isinstance(password, str):
            raise APIError("Password is required", status_code=400)

        if len(password) < settings.password_min_length:
            raise APIError(
                f"Password must be at least {settings.password_min_length} characters",
                status_code=400,
            )

        if not AuthService.PASSWORD_REGEX.match(password):
            raise APIError(
                "Password must contain uppercase, lowercase, number, and special character",
                status_code=400,
            )

        return True

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        AuthService.validate_password(password)

        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)

        logger.info("Password hashed successfully")
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password
            hashed_password: Hashed password to compare

        Returns:
            True if password matches hash
        """
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception as exception:
            logger.error("Password verification failed", exc_info=True)
            return False

    @staticmethod
    def generate_jwt_token(
        user_id: int,
        email: str,
        role: str,
        token_type: str = "access",
    ) -> str:
        """
        Generate JWT token for user.

        Args:
            user_id: User ID
            email: User email
            role: User role (student, mentor, admin)
            token_type: Type of token (access or refresh)

        Returns:
            JWT token string
        """
        now = datetime.utcnow()

        # Set expiration based on token type
        if token_type == "access":
            expires_delta = timedelta(hours=settings.jwt_access_token_expire_hours)
        else:  # refresh
            expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "type": token_type,
            "iat": now,
            "exp": now + expires_delta,
            "jti": secrets.token_urlsafe(32),  # JWT ID for token tracking
        }

        token = jwt.encode(
            payload,
            settings.jwt_secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )

        logger.info(
            "JWT token generated",
            extra={
                "user_id": user_id,
                "type": token_type,
                "expires_in": expires_delta.total_seconds(),
            },
        )

        return token

    @staticmethod
    def verify_jwt_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token to verify
            token_type: Expected token type (access or refresh)

        Returns:
            Decoded token payload

        Raises:
            APIError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )

            # Verify token type matches expected
            if payload.get("type") != token_type:
                raise APIError(
                    f"Invalid token type. Expected {token_type}",
                    status_code=401,
                )

            logger.debug(
                "JWT token verified",
                extra={"user_id": payload.get("user_id"), "type": token_type},
            )

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            raise APIError("Token has expired", status_code=401)
        except jwt.InvalidTokenError as exception:
            logger.warning("Invalid JWT token", exc_info=True)
            raise APIError("Invalid token", status_code=401)

    @staticmethod
    def generate_token_pair(user_id: int, email: str, role: str) -> Dict[str, str]:
        """
        Generate access and refresh token pair.

        Args:
            user_id: User ID
            email: User email
            role: User role

        Returns:
            Dictionary with access_token and refresh_token
        """
        access_token = AuthService.generate_jwt_token(
            user_id, email, role, token_type="access"
        )
        refresh_token = AuthService.generate_jwt_token(
            user_id, email, role, token_type="refresh"
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_hours * 3600,
        }

    @staticmethod
    async def create_session(
        user_id: int,
        access_token: str,
        refresh_token: str,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Create user session in Redis.

        Args:
            user_id: User ID
            access_token: Access token
            refresh_token: Refresh token
            user_data: Optional additional user data

        Returns:
            True if session created successfully
        """
        try:
            redis_manager = get_redis()

            # Decode tokens to get JTI and expiration
            access_payload = jwt.decode(
                access_token,
                settings.jwt_secret_key.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )
            refresh_payload = jwt.decode(
                refresh_token,
                settings.jwt_secret_key.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )

            session_data = {
                "user_id": user_id,
                "access_jti": access_payload["jti"],
                "refresh_jti": refresh_payload["jti"],
                "created_at": datetime.utcnow().isoformat(),
                "user_data": user_data or {},
            }

            # Store session with refresh token expiration
            session_key = f"session:{user_id}:{refresh_payload['jti']}"
            expiration = settings.jwt_refresh_token_expire_days * 24 * 3600

            await redis_manager.set_cache(session_key, session_data, expiration)

            # Track this session in user's session set
            user_sessions_key = f"user_sessions:{user_id}"
            await redis_manager.async_client.sadd(user_sessions_key, refresh_payload["jti"])
            await redis_manager.async_client.expire(user_sessions_key, expiration)

            # Also store access token JTI for quick validation
            access_key = f"access_token:{access_payload['jti']}"
            await redis_manager.set_cache(
                access_key,
                {"user_id": user_id, "valid": True},
                settings.jwt_access_token_expire_hours * 3600,
            )

            logger.info(
                "Session created",
                extra={"user_id": user_id, "session_key": session_key},
            )

            return True

        except Exception as exception:
            logger.error("Failed to create session", exc_info=True)
            return False

    @staticmethod
    async def validate_session(token: str) -> bool:
        """
        Validate if token's session exists in Redis.

        Args:
            token: Access token to validate

        Returns:
            True if session is valid
        """
        try:
            redis_manager = get_redis()

            # Decode token to get JTI
            payload = jwt.decode(
                token,
                settings.jwt_secret_key.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )

            # Check if token is valid in Redis
            access_key = f"access_token:{payload['jti']}"
            token_data = await redis_manager.get_cache(access_key)

            if not token_data or not token_data.get("valid"):
                logger.warning(
                    "Invalid session",
                    extra={"user_id": payload.get("user_id")},
                )
                return False

            return True

        except Exception as exception:
            logger.error("Session validation failed", exc_info=True)
            return False

    @staticmethod
    async def invalidate_session(user_id: int, token: str) -> bool:
        """
        Invalidate user session in Redis.

        Args:
            user_id: User ID
            token: Access or refresh token

        Returns:
            True if session invalidated
        """
        try:
            redis_manager = get_redis()

            # Decode token to get JTI
            payload = jwt.decode(
                token,
                settings.jwt_secret_key.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )

            # Invalidate access token
            access_key = f"access_token:{payload['jti']}"
            await redis_manager.delete_cache(access_key)

            # If it's a refresh token, delete the session
            if payload.get("type") == "refresh":
                session_key = f"session:{user_id}:{payload['jti']}"
                await redis_manager.delete_cache(session_key)

                # Remove from user's session set
                user_sessions_key = f"user_sessions:{user_id}"
                await redis_manager.async_client.srem(user_sessions_key, payload["jti"])

            logger.info(
                "Session invalidated",
                extra={"user_id": user_id, "token_type": payload.get("type")},
            )

            return True

        except Exception as exception:
            logger.error("Failed to invalidate session", exc_info=True)
            return False

    @staticmethod
    async def invalidate_all_user_sessions(user_id: int) -> bool:
        """
        Invalidate all sessions for a user.
        Used when password is reset or account security is compromised.

        Args:
            user_id: User ID

        Returns:
            True if all sessions invalidated successfully
        """
        try:
            redis_manager = get_redis()

            # Get all session JTIs for this user
            user_sessions_key = f"user_sessions:{user_id}"
            session_jtis = await redis_manager.async_client.smembers(user_sessions_key)

            if not session_jtis:
                logger.info(
                    "No active sessions to invalidate",
                    extra={"user_id": user_id},
                )
                return True

            # Delete all sessions and tokens
            for jti in session_jtis:
                session_key = f"session:{user_id}:{jti}"
                access_key = f"access_token:{jti}"

                await redis_manager.delete_cache(session_key)
                await redis_manager.delete_cache(access_key)

            # Clear the user sessions set
            await redis_manager.async_client.delete(user_sessions_key)

            logger.info(
                "All user sessions invalidated",
                extra={
                    "user_id": user_id,
                    "sessions_count": len(session_jtis),
                },
            )

            return True

        except Exception as exception:
            logger.error(
                "Failed to invalidate all user sessions",
                exc_info=True,
                extra={"user_id": user_id, "exception": str(exception)},
            )
            return False

    @staticmethod
    def generate_verification_token() -> str:
        """
        Generate email verification token.

        Returns:
            Secure random token
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    async def store_verification_token(
        email: str,
        token: str,
        expiration: int = 86400,  # 24 hours
    ) -> bool:
        """
        Store email verification token in Redis.

        Args:
            email: User email
            token: Verification token
            expiration: Token expiration in seconds (default 24 hours)

        Returns:
            True if stored successfully
        """
        try:
            redis_manager = get_redis()
            key = f"email_verification:{token}"
            await redis_manager.set_cache(key, {"email": email}, expiration)

            logger.info(
                "Verification token stored",
                extra={"email": email, "expires_in": expiration},
            )

            return True

        except Exception as exception:
            logger.error("Failed to store verification token", exc_info=True)
            return False

    @staticmethod
    async def verify_verification_token(token: str) -> Optional[str]:
        """
        Verify email verification token and return associated email.

        Args:
            token: Verification token

        Returns:
            Email address if token is valid, None otherwise
        """
        try:
            redis_manager = get_redis()
            key = f"email_verification:{token}"
            data = await redis_manager.get_cache(key)

            if not data:
                logger.warning("Verification token not found or expired")
                return None

            # Delete token after use (one-time use)
            await redis_manager.delete_cache(key)

            email = data.get("email")
            logger.info("Verification token validated", extra={"email": email})

            return email

        except Exception as exception:
            logger.error("Failed to verify token", exc_info=True)
            return None

    @staticmethod
    async def store_password_reset_token(
        email: str,
        token: str,
        expiration: int = 3600,  # 1 hour
    ) -> bool:
        """
        Store password reset token in Redis.

        Args:
            email: User email
            token: Reset token
            expiration: Token expiration in seconds (default 1 hour)

        Returns:
            True if stored successfully
        """
        try:
            redis_manager = get_redis()
            key = f"password_reset:{token}"
            await redis_manager.set_cache(key, {"email": email}, expiration)

            logger.info(
                "Password reset token stored",
                extra={"email": email, "expires_in": expiration},
            )

            return True

        except Exception as exception:
            logger.error("Failed to store password reset token", exc_info=True)
            return False

    @staticmethod
    async def verify_password_reset_token(token: str) -> Optional[str]:
        """
        Verify password reset token and return associated email.

        Args:
            token: Reset token

        Returns:
            Email address if token is valid, None otherwise
        """
        try:
            redis_manager = get_redis()
            key = f"password_reset:{token}"
            data = await redis_manager.get_cache(key)

            if not data:
                logger.warning("Password reset token not found or expired")
                return None

            # Delete token after use (one-time use)
            await redis_manager.delete_cache(key)

            email = data.get("email")
            logger.info("Password reset token validated", extra={"email": email})

            return email

        except Exception as exception:
            logger.error("Failed to verify password reset token", exc_info=True)
            return None

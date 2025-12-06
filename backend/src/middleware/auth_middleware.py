"""
Authentication and authorization middleware.
Provides JWT token validation, RBAC, and route protection.
"""
from functools import wraps
from typing import Callable, List, Optional
from quart import request, g
from src.logging_config import get_logger
from src.middleware.error_handler import APIError
from src.services.auth_service import AuthService
from src.models.user import UserRole

logger = get_logger(__name__)


def get_token_from_header() -> Optional[str]:
    """
    Extract JWT token from Authorization header.

    Returns:
        JWT token or None if not found

    Raises:
        APIError: If Authorization header is malformed
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return None

    # Check for Bearer token format
    parts = auth_header.split()

    if len(parts) != 2:
        raise APIError(
            "Invalid Authorization header format. Expected: Bearer <token>",
            status_code=401,
        )

    if parts[0].lower() != "bearer":
        raise APIError(
            "Invalid Authorization header format. Expected: Bearer <token>",
            status_code=401,
        )

    return parts[1]


def get_token_from_request() -> Optional[str]:
    """
    Extract JWT token from httpOnly cookie or Authorization header.

    Priority:
    1. Authorization header (for backward compatibility and API clients)
    2. access_token cookie (for browser clients with httpOnly cookies)

    Returns:
        JWT token or None if not found

    Raises:
        APIError: If Authorization header is malformed

    Security Note:
    This addresses AP-SEC-001: Token storage in localStorage vulnerability.
    Cookies are httpOnly, preventing XSS attacks from stealing tokens.
    """
    # Try to get token from Authorization header first (backward compatibility)
    try:
        token = get_token_from_header()
        if token:
            logger.debug("Token found in Authorization header")
            return token
    except APIError:
        # If Authorization header is malformed, raise the error
        raise

    # Try to get token from httpOnly cookie
    token = request.cookies.get("access_token")
    if token:
        logger.debug("Token found in httpOnly cookie")
        return token

    return None


def require_auth(function: Callable) -> Callable:
    """
    Decorator to require authentication for route.
    Validates JWT token and adds user info to request context.

    Usage:
        @require_auth
        async def protected_route():
            user_id = g.user_id
            # ... route logic

    Raises:
        APIError: If token is missing, invalid, or expired
    """

    @wraps(function)
    async def wrapper(*args, **kwargs):
        # Get token from cookie or header
        token = get_token_from_request()

        if not token:
            logger.warning("Missing authentication token")
            raise APIError("Authentication required", status_code=401)

        try:
            # Verify token
            payload = AuthService.verify_jwt_token(token, token_type="access")

            # Validate session exists in Redis
            session_valid = await AuthService.validate_session(token)
            if not session_valid:
                logger.warning(
                    "Invalid session",
                    extra={"user_id": payload.get("user_id")},
                )
                raise APIError("Session expired or invalid", status_code=401)

            # Add user info to request context
            g.user_id = payload["user_id"]
            g.user_email = payload["email"]
            g.user_role = payload["role"]
            g.token_jti = payload["jti"]

            logger.debug(
                "Request authenticated",
                extra={
                    "user_id": g.user_id,
                    "role": g.user_role,
                    "path": request.path,
                },
            )

            # Call the wrapped function
            return await function(*args, **kwargs)

        except APIError:
            raise
        except Exception as exception:
            logger.error("Authentication failed", exc_info=True)
            raise APIError("Authentication failed", status_code=401)

    return wrapper


def require_roles(*allowed_roles: UserRole) -> Callable:
    """
    Decorator to require specific roles for route access.
    Must be used with @require_auth decorator.

    Usage:
        @require_auth
        @require_roles(UserRole.ADMIN, UserRole.MODERATOR)
        async def admin_route():
            # ... route logic

    Args:
        allowed_roles: One or more UserRole values that are allowed

    Raises:
        APIError: If user doesn't have required role
    """

    def decorator(function: Callable) -> Callable:
        @wraps(function)
        async def wrapper(*args, **kwargs):
            # Check if user is authenticated (require_auth should be applied first)
            if not hasattr(g, "user_role"):
                logger.error("require_roles used without require_auth")
                raise APIError(
                    "Authentication required",
                    status_code=401,
                )

            # Convert role string to UserRole enum for comparison
            try:
                user_role = UserRole(g.user_role)
            except ValueError:
                logger.error(
                    "Invalid user role",
                    extra={"role": g.user_role, "user_id": g.user_id},
                )
                raise APIError("Invalid user role", status_code=403)

            # Check if user has required role
            if user_role not in allowed_roles:
                logger.warning(
                    "Insufficient permissions",
                    extra={
                        "user_id": g.user_id,
                        "user_role": user_role.value,
                        "required_roles": [r.value for r in allowed_roles],
                        "path": request.path,
                    },
                )
                raise APIError(
                    "Insufficient permissions",
                    status_code=403,
                )

            logger.debug(
                "Authorization check passed",
                extra={
                    "user_id": g.user_id,
                    "role": user_role.value,
                    "path": request.path,
                },
            )

            # Call the wrapped function
            return await function(*args, **kwargs)

        return wrapper

    return decorator


def require_verified_email(function: Callable) -> Callable:
    """
    Decorator to require verified email for route access.
    Must be used with @require_auth decorator.

    Usage:
        @require_auth
        @require_verified_email
        async def email_required_route():
            # ... route logic

    Raises:
        APIError: If user's email is not verified
    """

    @wraps(function)
    async def wrapper(*args, **kwargs):
        # Check if user is authenticated
        if not hasattr(g, "user_id"):
            logger.error("require_verified_email used without require_auth")
            raise APIError("Authentication required", status_code=401)

        # In a full implementation, we would fetch user from database to check
        # email_verified status. For now, we'll document this requirement.
        # The actual check should be implemented when integrating with database queries.

        logger.debug(
            "Email verification check (placeholder)",
            extra={"user_id": g.user_id},
        )

        # Call the wrapped function
        return await function(*args, **kwargs)

    return wrapper


def optional_auth(function: Callable) -> Callable:
    """
    Decorator for routes that optionally accept authentication.
    If token is present and valid, user info is added to context.
    If token is missing or invalid, continues without authentication.

    Usage:
        @optional_auth
        async def public_route():
            if hasattr(g, 'user_id'):
                # User is authenticated
                user_id = g.user_id
            else:
                # Anonymous user

    """

    @wraps(function)
    async def wrapper(*args, **kwargs):
        try:
            # Try to get token from cookie or header
            token = get_token_from_request()

            if token:
                # Verify token
                payload = AuthService.verify_jwt_token(token, token_type="access")

                # Validate session
                session_valid = await AuthService.validate_session(token)

                if session_valid:
                    # Add user info to request context
                    g.user_id = payload["user_id"]
                    g.user_email = payload["email"]
                    g.user_role = payload["role"]
                    g.token_jti = payload["jti"]

                    logger.debug(
                        "Optional auth: user authenticated",
                        extra={"user_id": g.user_id},
                    )
                else:
                    logger.debug("Optional auth: invalid session")

        except Exception as exception:
            # If authentication fails, continue without auth
            logger.debug(
                "Optional auth: authentication failed, continuing as anonymous",
                extra={"exception": str(exception)},
            )

        # Call the wrapped function regardless of auth status
        return await function(*args, **kwargs)

    return wrapper


def get_current_user_id() -> Optional[int]:
    """
    Get current authenticated user ID from request context.

    Returns:
        User ID if authenticated, None otherwise
    """
    return getattr(g, "user_id", None)


def get_current_user_role() -> Optional[str]:
    """
    Get current authenticated user role from request context.

    Returns:
        User role if authenticated, None otherwise
    """
    return getattr(g, "user_role", None)


def get_current_user_email() -> Optional[str]:
    """
    Get current authenticated user email from request context.

    Returns:
        User email if authenticated, None otherwise
    """
    return getattr(g, "user_email", None)

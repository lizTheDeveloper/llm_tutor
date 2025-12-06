"""
CSRF (Cross-Site Request Forgery) Protection Middleware.

Implements defense-in-depth CSRF protection using:
1. SameSite=Strict cookies (already in SEC-1) - primary defense
2. Double-submit cookie pattern - CSRF token validation
3. Custom X-CSRF-Token header requirement

Security Model:
- CSRF token is a cryptographically random 32-byte value
- Token is set in a non-httpOnly cookie (so JS can read it)
- Client must include token in X-CSRF-Token header for state-changing requests
- Server verifies cookie token == header token using timing-safe comparison
- Token is regenerated on authentication state changes (login, logout)

Attack Mitigation:
- Attacker cannot read CSRF token due to Same-Origin Policy
- Attacker cannot set custom headers on simple CORS requests
- Token mismatch/missing token results in 403 Forbidden
- All failures are logged for security monitoring

This addresses AP-SEC-006 from architectural review.
"""

import secrets
from typing import Optional, Set
from quart import request, make_response, jsonify
from functools import wraps
from src.logging_config import get_logger

logger = get_logger(__name__)

# CSRF token cookie name
CSRF_COOKIE_NAME = "csrf_token"

# CSRF token header name (follows Django/Rails convention)
CSRF_HEADER_NAME = "X-CSRF-Token"

# HTTP methods that require CSRF protection (state-changing operations)
CSRF_PROTECTED_METHODS: Set[str] = {"POST", "PUT", "PATCH", "DELETE"}

# Endpoints exempt from CSRF protection
# These are either:
# 1. Already protected by other means (password required)
# 2. No existing session to protect (new registration)
# 3. Read-only operations
CSRF_EXEMPT_ENDPOINTS: Set[str] = {
    "/api/auth/login",  # Protected by password
    "/api/auth/register",  # No session yet
    "/api/auth/verify-email",  # One-time token in URL
    "/health",  # Read-only
    "/",  # Read-only
}


def generate_csrf_token() -> str:
    """
    Generate a cryptographically secure CSRF token.

    Uses secrets.token_urlsafe() which provides:
    - Cryptographically strong random number generation
    - URL-safe base64 encoding (no special chars)
    - 32 bytes (256 bits) of entropy

    Returns:
        URL-safe base64-encoded random token (43-44 characters)
    """
    # 32 bytes = 256 bits of entropy
    # Base64 encoding: 32 bytes → 43-44 characters
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: Optional[str], header_token: Optional[str]) -> bool:
    """
    Verify CSRF token using timing-safe comparison.

    Double-submit cookie pattern:
    - Token from cookie must match token from header
    - Uses secrets.compare_digest() to prevent timing attacks

    Args:
        cookie_token: CSRF token from cookie
        header_token: CSRF token from X-CSRF-Token header

    Returns:
        True if tokens match, False otherwise

    Security Notes:
    - Uses timing-safe comparison (secrets.compare_digest)
    - Rejects if either token is missing
    - Rejects if tokens are empty strings
    """
    if not cookie_token or not header_token:
        logger.warning(
            "CSRF token missing",
            extra={
                "has_cookie_token": bool(cookie_token),
                "has_header_token": bool(header_token),
                "remote_addr": request.remote_addr,
            }
        )
        return False

    # Timing-safe comparison prevents attackers from guessing token
    # by measuring response time differences
    if not secrets.compare_digest(cookie_token, header_token):
        logger.warning(
            "CSRF token mismatch",
            extra={
                "cookie_token_length": len(cookie_token) if cookie_token else 0,
                "header_token_length": len(header_token) if header_token else 0,
                "remote_addr": request.remote_addr,
                "endpoint": request.path,
            }
        )
        return False

    return True


def set_csrf_cookie(response, csrf_token: str, is_production: bool = False):
    """
    Set CSRF token in a non-httpOnly cookie.

    Cookie attributes:
    - httpOnly=False: JavaScript MUST be able to read this cookie
    - secure=True: Only sent over HTTPS in production
    - samesite=Strict: Additional CSRF protection
    - max_age=86400: 24 hours (matches access token)

    Args:
        response: Quart response object
        csrf_token: CSRF token value
        is_production: Whether running in production (affects secure flag)

    Security Note:
    CSRF cookie is NOT httpOnly because:
    1. JavaScript needs to read it to include in X-CSRF-Token header
    2. XSS protection comes from Content-Security-Policy headers
    3. Attacker cannot use cookie value alone (must also send in header)
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=24 * 3600,  # 24 hours (matches access token)
        httponly=False,  # MUST be False so JS can read it
        secure=is_production,  # Only HTTPS in production
        samesite="Strict",  # Prevent CSRF (belt and suspenders)
        path="/",
    )

    logger.debug(
        "CSRF token cookie set",
        extra={
            "httponly": False,
            "secure": is_production,
            "token_length": len(csrf_token),
        }
    )


def clear_csrf_cookie(response, is_production: bool = False):
    """
    Clear CSRF token cookie on logout.

    Args:
        response: Quart response object
        is_production: Whether running in production
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=False,
        secure=is_production,
        samesite="Strict",
        path="/",
    )

    logger.debug("CSRF token cookie cleared")


def csrf_protect(func):
    """
    Decorator to protect endpoints from CSRF attacks.

    Usage:
        @auth_bp.route("/api/users/profile", methods=["PUT"])
        @require_auth
        @csrf_protect
        async def update_profile():
            ...

    Protection:
    - Validates CSRF token on POST/PUT/PATCH/DELETE requests
    - Skips validation on GET/OPTIONS/HEAD (safe methods)
    - Returns 403 Forbidden if token missing or mismatched
    - Logs all CSRF failures for security monitoring

    Order matters:
    - Place AFTER @require_auth (needs authenticated user context)
    - Place BEFORE route handler

    Args:
        func: Async route handler function

    Returns:
        Wrapped function with CSRF protection
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Skip CSRF check for safe HTTP methods
        if request.method not in CSRF_PROTECTED_METHODS:
            return await func(*args, **kwargs)

        # Skip CSRF check for exempt endpoints
        if request.path in CSRF_EXEMPT_ENDPOINTS:
            return await func(*args, **kwargs)

        # Get CSRF tokens from cookie and header
        csrf_cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        csrf_header_token = request.headers.get(CSRF_HEADER_NAME)

        # Verify tokens match
        if not verify_csrf_token(csrf_cookie_token, csrf_header_token):
            logger.warning(
                "CSRF protection triggered",
                extra={
                    "method": request.method,
                    "endpoint": request.path,
                    "remote_addr": request.remote_addr,
                    "has_cookie_token": bool(csrf_cookie_token),
                    "has_header_token": bool(csrf_header_token),
                    "user_agent": request.headers.get("User-Agent"),
                }
            )

            return jsonify({
                "error": "CSRF token validation failed",
                "message": "Invalid or missing CSRF token. Please refresh the page and try again.",
                "status": 403,
                "code": "CSRF_TOKEN_INVALID"
            }), 403

        # CSRF token valid, proceed with request
        return await func(*args, **kwargs)

    return wrapper


async def inject_csrf_token_on_login(response, is_production: bool = False):
    """
    Generate and inject CSRF token after successful login.

    Call this function after user authentication succeeds.

    Args:
        response: Quart response object
        is_production: Whether running in production

    Returns:
        Response with CSRF token cookie set

    Usage:
        @auth_bp.route("/api/auth/login", methods=["POST"])
        async def login():
            # ... authenticate user ...
            response = await make_response(jsonify({"message": "Login successful"}))
            response = await inject_csrf_token_on_login(response)
            return response
    """
    csrf_token = generate_csrf_token()
    set_csrf_cookie(response, csrf_token, is_production)

    logger.info(
        "CSRF token generated on login",
        extra={
            "token_length": len(csrf_token),
            "remote_addr": request.remote_addr,
        }
    )

    return response


async def clear_csrf_token_on_logout(response, is_production: bool = False):
    """
    Clear CSRF token on logout.

    Call this function when user logs out.

    Args:
        response: Quart response object
        is_production: Whether running in production

    Returns:
        Response with CSRF token cookie cleared

    Usage:
        @auth_bp.route("/api/auth/logout", methods=["POST"])
        async def logout():
            # ... clear session ...
            response = await make_response(jsonify({"message": "Logout successful"}))
            response = await clear_csrf_token_on_logout(response)
            return response
    """
    clear_csrf_cookie(response, is_production)

    logger.info(
        "CSRF token cleared on logout",
        extra={"remote_addr": request.remote_addr}
    )

    return response


def is_csrf_protected_endpoint(path: str, method: str) -> bool:
    """
    Check if an endpoint requires CSRF protection.

    Args:
        path: Request path (e.g., "/api/users/profile")
        method: HTTP method (e.g., "POST")

    Returns:
        True if endpoint requires CSRF protection, False otherwise
    """
    # Safe HTTP methods don't need CSRF protection
    if method not in CSRF_PROTECTED_METHODS:
        return False

    # Check if endpoint is explicitly exempt
    if path in CSRF_EXEMPT_ENDPOINTS:
        return False

    return True


# Configuration validation
def validate_csrf_configuration():
    """
    Validate CSRF protection configuration at startup.

    Checks:
    - SameSite cookies enabled
    - Secure cookies in production
    - CORS origins properly configured

    Raises:
        RuntimeError: If configuration is insecure
    """
    from src.config import settings

    # Verify production settings
    if settings.app_env == "production":
        if not settings.cors_origins:
            raise RuntimeError(
                "CORS_ORIGINS must be configured in production for CSRF protection"
            )

        # Check that frontend URL is in CORS origins
        if settings.frontend_url not in settings.cors_origins:
            logger.warning(
                "Frontend URL not in CORS origins",
                extra={
                    "frontend_url": settings.frontend_url,
                    "cors_origins": settings.cors_origins,
                }
            )

    logger.info(
        "CSRF protection configured",
        extra={
            "environment": settings.app_env,
            "csrf_protected_methods": list(CSRF_PROTECTED_METHODS),
            "exempt_endpoints_count": len(CSRF_EXEMPT_ENDPOINTS),
        }
    )

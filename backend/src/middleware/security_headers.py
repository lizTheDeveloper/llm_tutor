"""
Security headers middleware.
Adds security-related HTTP headers to all responses.
"""
from quart import Quart
from src.logging_config import get_logger

logger = get_logger(__name__)


def add_security_headers(app: Quart) -> None:
    """
    Add security headers middleware to the application.

    Args:
        app: Quart application instance
    """

    @app.after_request
    async def set_security_headers(response):
        """Add security headers to every response."""

        # Content Security Policy - Restrict resource loading
        # Adjust this based on your needs (especially for development vs production)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer Policy - Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions Policy - Control browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        # Strict Transport Security - Force HTTPS (only in production)
        # Uncomment and configure for production with HTTPS
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # Remove server identification
        response.headers.pop("Server", None)

        return response

    logger.info("Security headers middleware registered")


def add_request_size_limit(app: Quart, max_size: int = 16 * 1024 * 1024) -> None:
    """
    Add request size limit to prevent DoS attacks.

    Args:
        app: Quart application instance
        max_size: Maximum request size in bytes (default: 16MB)
    """
    app.config["MAX_CONTENT_LENGTH"] = max_size
    logger.info(f"Request size limit set to {max_size / (1024 * 1024):.0f}MB")

"""
Quart application factory for CodeMentor backend.
Creates and configures the async Flask application instance.
"""
from typing import Optional
from quart import Quart, jsonify
from quart_cors import cors
import structlog

from .config import settings
from .utils.logger import setup_logging, get_logger, log_request
from .utils.database import init_database, get_database
from .utils.redis_client import init_redis, get_redis


def create_app(config_override: Optional[dict] = None) -> Quart:
    """
    Application factory pattern for creating Quart app instances.

    Args:
        config_override: Optional dictionary to override default configuration

    Returns:
        Configured Quart application instance
    """
    # Initialize logging
    setup_logging(
        log_level=settings.log_level,
        log_format=settings.log_format,
        app_name=settings.app_name,
    )
    logger = get_logger(__name__)
    logger.info(
        "Creating Quart application",
        extra={
            "app_name": settings.app_name,
            "app_env": settings.app_env,
        },
    )

    # Create Quart app
    # Workaround: Set Flask default config for PROVIDE_AUTOMATIC_OPTIONS
    # This must be set before Quart initialization as it's checked during __init__
    from flask.config import Config as FlaskConfig
    original_init = FlaskConfig.__init__
    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.setdefault("PROVIDE_AUTOMATIC_OPTIONS", True)

    FlaskConfig.__init__ = patched_init

    try:
        app = Quart(__name__)
    finally:
        # Restore original init
        FlaskConfig.__init__ = original_init

    # Apply configuration
    app.config.update(
        {
            "SECRET_KEY": settings.secret_key.get_secret_value(),
            "DEBUG": settings.debug,
            "TESTING": False,
        }
    )

    if config_override:
        app.config.update(config_override)

    # Enable CORS
    app = cors(
        app,
        allow_origin=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        allow_credentials=True,
    )

    # Initialize database
    init_database(
        database_url=settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )

    # Initialize Redis
    init_redis(
        redis_url=settings.redis_url,
        session_db=settings.redis_session_db,
    )

    # Register request/response hooks
    @app.before_request
    async def before_request():
        """Log incoming requests."""
        from quart import request
        log_request(request)

    @app.after_request
    async def after_request(response):
        """Log outgoing responses."""
        from quart import request
        log_request(request, response)
        return response

    # Register error handlers
    @app.errorhandler(404)
    async def not_found(error):
        """Handle 404 errors."""
        return jsonify(
            {
                "error": "Not Found",
                "message": "The requested resource was not found",
                "status": 404,
            }
        ), 404

    @app.errorhandler(500)
    async def internal_server_error(error):
        """Handle 500 errors."""
        logger.error(
            "Internal server error",
            exc_info=True,
            extra={"error": str(error)},
        )
        return jsonify(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "status": 500,
            }
        ), 500

    @app.errorhandler(Exception)
    async def handle_exception(error):
        """Handle uncaught exceptions."""
        logger.error(
            "Uncaught exception",
            exc_info=True,
            extra={"error": str(error)},
        )
        return jsonify(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "status": 500,
            }
        ), 500

    # Health check endpoint
    @app.route("/health", methods=["GET"])
    async def health_check():
        """
        Health check endpoint for monitoring.

        Returns:
            JSON response with system health status
        """
        health_status = {
            "status": "healthy",
            "app_name": settings.app_name,
            "environment": settings.app_env,
        }

        # Check database connectivity (using async engine to avoid dual-engine overhead)
        try:
            from sqlalchemy import text

            db_manager = get_database()
            # Use async engine to avoid creating unnecessary sync engine
            # This addresses AP-ARCH-004: Dual database engines
            async with db_manager.async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            health_status["database"] = "connected"
        except Exception as exception:
            logger.error(
                "Database health check failed",
                exc_info=True,
                extra={"exception": str(exception)},
            )
            health_status["database"] = "error"
            health_status["status"] = "unhealthy"

        # Check Redis connectivity
        try:
            redis_manager = get_redis()
            redis_healthy = redis_manager.ping()
            health_status["redis"] = "connected" if redis_healthy else "disconnected"
        except Exception as exception:
            logger.error(
                "Redis health check failed",
                exc_info=True,
                extra={"exception": str(exception)},
            )
            health_status["redis"] = "error"
            health_status["status"] = "unhealthy"

        status_code = 200 if health_status["status"] == "healthy" else 503
        return jsonify(health_status), status_code

    # Root endpoint
    @app.route("/", methods=["GET"])
    async def root():
        """
        Root endpoint with API information.

        Returns:
            JSON response with API metadata
        """
        return jsonify(
            {
                "name": settings.app_name,
                "version": "0.1.0",
                "status": "running",
                "environment": settings.app_env,
                "endpoints": {
                    "health": "/health",
                    "api": "/api/v1",
                    "docs": "/docs",
                },
            }
        )

    # Register security headers middleware
    from .middleware.security_headers import add_security_headers, add_request_size_limit
    add_security_headers(app)
    add_request_size_limit(app, max_size=16 * 1024 * 1024)  # 16MB limit

    # Register error handlers
    from .middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    # Register blueprints (routes)
    from .api import register_blueprints
    register_blueprints(app)

    logger.info(
        "Quart application created successfully",
        extra={
            "debug": app.config["DEBUG"],
            "cors_origins": len(settings.cors_origins),
        },
    )

    return app


async def shutdown_app(app: Quart):
    """
    Cleanup function to gracefully shutdown application resources.

    Args:
        app: Quart application instance
    """
    logger = get_logger(__name__)
    logger.info("Shutting down application")

    # Close database connections
    try:
        db_manager = get_database()
        await db_manager.close()
        logger.info("Database connections closed")
    except Exception as exception:
        logger.error(
            "Error closing database",
            exc_info=True,
            extra={"exception": str(exception)},
        )

    # Close Redis connections
    try:
        redis_manager = get_redis()
        await redis_manager.close()
        logger.info("Redis connections closed")
    except Exception as exception:
        logger.error(
            "Error closing Redis",
            exc_info=True,
            extra={"exception": str(exception)},
        )

    logger.info("Application shutdown complete")

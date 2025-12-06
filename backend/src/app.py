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
from .services.monitoring_service import init_monitoring_service, get_monitoring_service
from .services.metrics_collector import init_metrics_collector, get_metrics_collector


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
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
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

    # Initialize monitoring (OPS-1)
    init_monitoring_service(
        sentry_dsn=settings.sentry_dsn if settings.sentry_enabled else None,
        environment=settings.app_env
    )
    init_metrics_collector()

    logger.info(
        "Monitoring initialized",
        extra={
            "sentry_enabled": settings.sentry_enabled,
            "metrics_enabled": settings.metrics_enabled
        }
    )

    # Register request/response hooks
    @app.before_request
    async def before_request():
        """Log incoming requests and start timing."""
        from quart import request, g
        import time

        log_request(request)

        # Start request timer for metrics (OPS-1)
        g.request_start_time = time.time()

    @app.after_request
    async def after_request(response):
        """Log outgoing responses and record metrics."""
        from quart import request, g
        import time

        log_request(request, response)

        # Record request metrics (OPS-1)
        if settings.metrics_enabled and hasattr(g, 'request_start_time'):
            duration = time.time() - g.request_start_time
            metrics_collector = get_metrics_collector()

            metrics_collector.record_request_latency(
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                duration_seconds=duration
            )

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

        # Capture in Sentry (OPS-1)
        monitoring_service = get_monitoring_service()
        monitoring_service.capture_exception(error)

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

        # Capture in Sentry (OPS-1)
        monitoring_service = get_monitoring_service()
        monitoring_service.capture_exception(error)

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

        # Check monitoring status (OPS-1)
        try:
            monitoring_service = get_monitoring_service()
            health_status["monitoring"] = {
                "sentry": "enabled" if monitoring_service.sentry_enabled else "disabled",
                "metrics": "enabled" if settings.metrics_enabled else "disabled"
            }
        except Exception as exception:
            logger.error(
                "Monitoring health check failed",
                exc_info=True,
                extra={"exception": str(exception)},
            )
            health_status["monitoring"] = {"status": "error"}

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
                    "metrics": "/metrics",
                    "api": "/api/v1",
                    "docs": "/docs",
                },
            }
        )

    # Prometheus metrics endpoint (OPS-1)
    @app.route("/metrics", methods=["GET"])
    async def metrics():
        """
        Prometheus metrics endpoint.

        Exposes application metrics in Prometheus text format:
        - HTTP request latency and counts
        - LLM API costs and usage
        - Database query performance
        - Active users
        - Business metrics

        Returns:
            Prometheus text format metrics
        """
        if not settings.metrics_enabled:
            return jsonify({"error": "Metrics disabled"}), 404

        try:
            metrics_collector = get_metrics_collector()
            prometheus_data = metrics_collector.generate_prometheus_metrics()

            from quart import Response
            return Response(
                prometheus_data,
                mimetype=metrics_collector.get_content_type()
            )
        except Exception as exception:
            logger.error(
                "Metrics endpoint error",
                exc_info=True,
                extra={"exception": str(exception)}
            )
            return jsonify({"error": "Metrics generation failed"}), 500

    # Register security headers middleware
    from .middleware.security_headers import add_security_headers, add_request_size_limit
    add_security_headers(app)
    add_request_size_limit(app, max_size=16 * 1024 * 1024)  # 16MB limit

    # Initialize CSRF protection (SEC-3-CSRF)
    from .middleware.csrf_protection import validate_csrf_configuration
    validate_csrf_configuration()
    logger.info("CSRF protection initialized")

    # Register error handlers
    from .middleware.error_handler import register_error_handlers
    register_error_handlers(app)

    # Register blueprints (routes)
    from .api import register_blueprints
    register_blueprints(app)

    # Add OpenAPI documentation routes (DOC-1)
    from .utils.openapi_integration import add_openapi_routes
    add_openapi_routes(app)
    logger.info("OpenAPI documentation routes registered at /openapi.json and /docs")

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


# Create application instance for ASGI servers
app = create_app()

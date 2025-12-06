"""
API Blueprint Registration
Registers all API route blueprints with the application.
"""
from quart import Quart
from src.logging_config import get_logger

# Import blueprints (will be created in following files)
from src.api.health import health_bp
from src.api.auth import auth_bp
from src.api.users import users_bp
from src.api.exercises import exercises_bp
from src.api.chat import chat_bp
from src.api.github import github_bp

logger = get_logger(__name__)


def register_blueprints(app: Quart) -> None:
    """
    Register all API blueprints with the application.

    Args:
        app: Quart application instance
    """
    # API prefix (no versioning for now)
    api_prefix = "/api"

    # Register blueprints
    app.register_blueprint(health_bp, url_prefix=f"{api_prefix}/health")
    app.register_blueprint(auth_bp, url_prefix=f"{api_prefix}/auth")
    app.register_blueprint(users_bp, url_prefix=f"{api_prefix}/users")
    app.register_blueprint(exercises_bp, url_prefix=f"{api_prefix}/exercises")
    app.register_blueprint(chat_bp, url_prefix=f"{api_prefix}/chat")
    app.register_blueprint(github_bp, url_prefix=f"{api_prefix}/github")

    logger.info(
        "API blueprints registered",
        blueprints=["health", "auth", "users", "exercises", "chat", "github"]
    )

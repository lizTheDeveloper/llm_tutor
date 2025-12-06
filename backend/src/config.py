"""
Configuration management for CodeMentor backend.
Loads settings from environment variables and provides typed configuration objects.
"""
import os
from typing import Optional, List
from pydantic import validator, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""

    # Application
    app_name: str = Field(default="CodeMentor", env="APP_NAME")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: str = Field(..., env="SECRET_KEY")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=5000, env="PORT")

    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")

    # Redis
    redis_url: str = Field(..., env="REDIS_URL")
    redis_session_db: int = Field(default=1, env="REDIS_SESSION_DB")

    # JWT
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_hours: int = Field(default=24, env="JWT_ACCESS_TOKEN_EXPIRE_HOURS")
    jwt_refresh_token_expire_days: int = Field(default=30, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # OAuth
    github_client_id: Optional[str] = Field(None, env="GITHUB_CLIENT_ID")
    github_client_secret: Optional[str] = Field(None, env="GITHUB_CLIENT_SECRET")
    google_client_id: Optional[str] = Field(None, env="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(None, env="GOOGLE_CLIENT_SECRET")

    # LLM
    groq_api_key: Optional[str] = Field(None, env="GROQ_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    llm_primary_provider: str = Field(default="groq", env="LLM_PRIMARY_PROVIDER")
    llm_fallback_provider: str = Field(default="openai", env="LLM_FALLBACK_PROVIDER")
    llm_max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")

    # GROQ-specific settings
    groq_model: str = Field(default="llama-3.3-70b-versatile", env="GROQ_MODEL")
    groq_compound_model: str = Field(default="groq/compound", env="GROQ_COMPOUND_MODEL")
    groq_rate_limit_rpm: int = Field(default=30, env="GROQ_RATE_LIMIT_RPM")  # requests per minute
    groq_rate_limit_rpd: int = Field(default=14400, env="GROQ_RATE_LIMIT_RPD")  # requests per day
    groq_max_retries: int = Field(default=3, env="GROQ_MAX_RETRIES")
    groq_timeout: int = Field(default=30, env="GROQ_TIMEOUT")  # seconds

    # Email
    email_provider: str = Field(default="sendgrid", env="EMAIL_PROVIDER")
    sendgrid_api_key: Optional[str] = Field(None, env="SENDGRID_API_KEY")
    email_from: str = Field(default="noreply@codementor.io", env="EMAIL_FROM")

    # Matrix
    matrix_homeserver: str = Field(default="https://matrix.org", env="MATRIX_HOMESERVER")
    matrix_access_token: Optional[str] = Field(None, env="MATRIX_ACCESS_TOKEN")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000", env="CORS_ORIGINS")

    # URLs
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    backend_url: str = Field(default="http://localhost:5000", env="BACKEND_URL")

    # Security
    bcrypt_rounds: int = Field(default=12, env="BCRYPT_ROUNDS")
    password_min_length: int = Field(default=12, env="PASSWORD_MIN_LENGTH")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_burst: int = Field(default=10, env="RATE_LIMIT_BURST")

    @validator("cors_origins")
    def parse_cors_origins(cls, value) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",")]
        return value

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


def get_settings() -> Settings:
    """Get application settings singleton."""
    settings = Settings()

    # Validate critical settings at startup
    critical_fields = {
        "secret_key": "SECRET_KEY",
        "jwt_secret_key": "JWT_SECRET_KEY",
        "database_url": "DATABASE_URL",
        "redis_url": "REDIS_URL",
    }

    missing = []
    for field, env_var in critical_fields.items():
        value = getattr(settings, field, None)
        if not value or (isinstance(value, str) and value.strip() == ""):
            missing.append(env_var)

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return settings


# Global settings instance
settings = get_settings()

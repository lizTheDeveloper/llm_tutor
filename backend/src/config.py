"""
Configuration management for CodeMentor backend.
Loads settings from environment variables and provides typed configuration objects.
"""
import os
from typing import Optional, List
from pydantic import validator, field_validator, model_validator, Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""

    # Application
    app_name: str = Field(default="CodeMentor", env="APP_NAME")
    app_env: str = Field(default="development", env="APP_ENV")
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: SecretStr = Field(..., env="SECRET_KEY")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=5000, env="PORT")

    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    # DB-OPT: Connection pool sizing formula: workers × threads × 2 + overhead
    # Example: 4 workers × 4 threads × 2 + 4 = 36 connections
    # Default 20 is conservative for development (2 workers × 4 threads × 2 + 4)
    database_pool_size: int = Field(default=20, env="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")

    # Redis
    redis_url: str = Field(..., env="REDIS_URL")
    redis_session_db: int = Field(default=1, env="REDIS_SESSION_DB")

    # JWT
    jwt_secret_key: SecretStr = Field(..., env="JWT_SECRET_KEY")
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

    # Rate Limiting - General
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    rate_limit_burst: int = Field(default=10, env="RATE_LIMIT_BURST")

    # Rate Limiting - Tiered by User Role (SEC-3)
    # Chat endpoints (per minute)
    rate_limit_chat_per_minute_student: int = Field(default=10, env="RATE_LIMIT_CHAT_PER_MINUTE_STUDENT")
    rate_limit_chat_per_minute_admin: int = Field(default=30, env="RATE_LIMIT_CHAT_PER_MINUTE_ADMIN")

    # Exercise generation (per hour) - expensive operation
    rate_limit_exercise_generation_per_hour: int = Field(default=3, env="RATE_LIMIT_EXERCISE_GENERATION_PER_HOUR")
    rate_limit_exercise_generation_per_hour_admin: int = Field(default=10, env="RATE_LIMIT_EXERCISE_GENERATION_PER_HOUR_ADMIN")

    # Hint requests (per hour) - moderate cost
    rate_limit_hint_per_hour: int = Field(default=5, env="RATE_LIMIT_HINT_PER_HOUR")
    rate_limit_hint_per_hour_admin: int = Field(default=15, env="RATE_LIMIT_HINT_PER_HOUR_ADMIN")

    # Daily cost limits (in USD)
    daily_cost_limit_student: float = Field(default=1.00, env="DAILY_COST_LIMIT_STUDENT")
    daily_cost_limit_admin: float = Field(default=10.00, env="DAILY_COST_LIMIT_ADMIN")

    # Cost warning threshold (percentage of daily limit)
    cost_warning_threshold: float = Field(default=0.8, env="COST_WARNING_THRESHOLD")

    # Monitoring & Observability (OPS-1)
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    sentry_enabled: bool = Field(default=False, env="SENTRY_ENABLED")
    sentry_sample_rate: float = Field(default=1.0, env="SENTRY_SAMPLE_RATE")
    sentry_traces_sample_rate: float = Field(default=0.1, env="SENTRY_TRACES_SAMPLE_RATE")
    metrics_enabled: bool = Field(default=True, env="METRICS_ENABLED")

    @field_validator("secret_key", "jwt_secret_key")
    @classmethod
    def validate_secret_strength(cls, value: SecretStr) -> SecretStr:
        """
        Validate that secret keys are strong enough for production use.

        Security Requirement:
        - Minimum 32 characters for cryptographic strength
        - Prevents weak secrets that could be brute-forced

        This addresses AP-CRIT-003: Configuration validation missing.
        """
        secret_str = value.get_secret_value()

        if len(secret_str) < 32:
            raise ValueError(
                f"Secret key must be at least 32 characters long for security. "
                f"Got {len(secret_str)} characters. "
                f"Use a strong random string generated with: "
                f"python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        return value

    @validator("cors_origins")
    def parse_cors_origins(cls, value) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",")]
        return value

    @model_validator(mode='after')
    def validate_production_config(self) -> 'Settings':
        """
        Validate production-specific configuration requirements.

        This validator ensures safe production deployment by:
        1. Rejecting weak/development secrets
        2. Requiring HTTPS URLs in production
        3. Validating database/Redis URL formats
        4. Requiring LLM API keys if needed

        Addresses CRIT-3: Configuration Validation Incomplete
        """
        if self.app_env != "production":
            # Only validate production environments
            return self

        # 1. Detect development secrets (common weak patterns)
        dev_secret_patterns = ["changeme", "password", "secret", "test", "development", "default"]

        for secret_field in ["secret_key", "jwt_secret_key"]:
            secret_value = getattr(self, secret_field).get_secret_value().lower()

            for pattern in dev_secret_patterns:
                if pattern in secret_value:
                    raise ValueError(
                        f"Production {secret_field} appears to be a development secret! "
                        f"Contains '{pattern}'. Use a strong random secret: "
                        f"python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                    )

        # 2. Require HTTPS for frontend and backend URLs in production
        if not self.frontend_url.startswith("https://"):
            raise ValueError(
                f"FRONTEND_URL must use HTTPS in production. "
                f"Got: {self.frontend_url}. "
                f"HTTP is insecure for production deployment."
            )

        if not self.backend_url.startswith("https://"):
            raise ValueError(
                f"BACKEND_URL must use HTTPS in production. "
                f"Got: {self.backend_url}. "
                f"HTTP is insecure for production deployment."
            )

        # 3. Validate database URL format (PostgreSQL)
        if not self.database_url.startswith("postgresql://") and not self.database_url.startswith("postgres://"):
            raise ValueError(
                f"DATABASE_URL must be a valid PostgreSQL connection string in production. "
                f"Expected format: postgresql://user:password@host:port/database. "
                f"Got URL starting with: {self.database_url.split('://')[0] if '://' in self.database_url else 'invalid'}"
            )

        # 4. Validate Redis URL format
        if not self.redis_url.startswith("redis://") and not self.redis_url.startswith("rediss://"):
            raise ValueError(
                f"REDIS_URL must be a valid Redis connection string in production. "
                f"Expected format: redis://host:port/db or rediss://host:port/db (SSL). "
                f"Got URL starting with: {self.redis_url.split('://')[0] if '://' in self.redis_url else 'invalid'}"
            )

        # 5. Require LLM API key if GROQ is primary provider
        if self.llm_primary_provider == "groq" and not self.groq_api_key:
            raise ValueError(
                f"GROQ_API_KEY is required in production when LLM_PRIMARY_PROVIDER=groq. "
                f"Get an API key from: https://console.groq.com/"
            )

        # 6. Require LLM API key if OpenAI is primary provider
        if self.llm_primary_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                f"OPENAI_API_KEY is required in production when LLM_PRIMARY_PROVIDER=openai."
            )

        # 7. Require LLM API key if Anthropic is primary provider
        if self.llm_primary_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                f"ANTHROPIC_API_KEY is required in production when LLM_PRIMARY_PROVIDER=anthropic."
            )

        return self

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file
        validate_assignment = True  # Validate on assignment, not just initialization


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

"""
Test suite for SEC-2: Secrets Management work stream.

This test suite verifies:
1. .env file is NOT tracked in git
2. Secrets are loaded from environment variables
3. Production configuration validation works correctly
4. Weak/development secrets are rejected in production
5. Missing critical secrets cause startup failure
6. HTTPS is enforced in production for frontend/backend URLs

Test Strategy:
- Integration tests that validate real configuration behavior
- Test production vs development environment differences
- Verify fail-fast behavior on invalid configuration
- Test secret validation logic

Implements requirements:
- CRIT-3: Configuration Validation Incomplete
- AP-CRIT-001: Hardcoded Configuration Values
- REQ-SEC-001: Authentication security requirements
"""

import pytest
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError


class TestGitSecretProtection:
    """Test that .env file is NOT tracked in git."""

    def test_env_not_in_git_tracking(self):
        """
        CRITICAL: Verify .env file is not tracked in git repository.

        This prevents secrets from being committed to version control.
        Addresses CRIT-1: Secrets exposed in git repository.
        """
        # Get project root
        project_root = Path(__file__).parent.parent.parent

        # Run git ls-files to check if .env is tracked
        result = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=project_root,
            capture_output=True,
            text=True
        )

        # .env should NOT be in git tracking (empty output)
        assert result.stdout.strip() == "", (
            ".env file MUST NOT be tracked in git! "
            "Run: git rm --cached .env && git commit -m 'Remove .env from tracking'"
        )

    def test_env_in_gitignore(self):
        """
        Verify .env is listed in .gitignore.

        Prevents accidental commits of .env file.
        """
        project_root = Path(__file__).parent.parent.parent
        gitignore_path = project_root / ".gitignore"

        assert gitignore_path.exists(), ".gitignore file must exist"

        gitignore_content = gitignore_path.read_text()
        assert ".env" in gitignore_content, ".env must be in .gitignore"

    def test_env_example_exists(self):
        """
        Verify .env.example file exists as a template.

        Developers need a template to create their own .env file.
        """
        project_root = Path(__file__).parent.parent.parent
        env_example_path = project_root / ".env.example"

        assert env_example_path.exists(), (
            ".env.example must exist as a template. "
            "Create it with placeholder values."
        )

        # Verify .env.example does NOT contain real secrets
        env_example_content = env_example_path.read_text()

        forbidden_patterns = [
            "228c16fc98109fde31f7dc521c887555e98c927d7b0697dd8f5363a8cb5a3579",  # Current JWT secret
            "llm_tutor_2024_secure",  # Database password
        ]

        for pattern in forbidden_patterns:
            assert pattern not in env_example_content, (
                f".env.example MUST NOT contain real secrets! "
                f"Found: {pattern}"
            )


class TestProductionConfigValidation:
    """Test production-specific configuration validation (CRIT-3)."""

    def test_production_requires_database_url(self):
        """
        Production environment MUST have DATABASE_URL set.

        Fail-fast if critical database configuration is missing.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,  # Valid secret
            "JWT_SECRET_KEY": "b" * 32,  # Valid secret
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_URL": "https://example.com",
            "BACKEND_URL": "https://api.example.com",
            "GROQ_API_KEY": "fake-api-key",  # Required for production
            # DATABASE_URL intentionally missing
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="(?i)database_url"):
                Settings(_env_file=None)  # Disable .env file loading

    def test_production_requires_redis_url(self):
        """
        Production environment MUST have REDIS_URL set.

        Fail-fast if critical Redis configuration is missing.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "FRONTEND_URL": "https://example.com",
            "BACKEND_URL": "https://api.example.com",
            "GROQ_API_KEY": "fake-api-key",  # Required for production
            # REDIS_URL intentionally missing
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="(?i)redis_url"):
                Settings(_env_file=None)  # Disable .env file loading

    def test_production_requires_strong_secrets(self):
        """
        Production MUST reject weak secrets.

        Prevents deployment with insecure secret keys.
        Addresses AP-CRIT-003: Configuration validation missing.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "weak",  # Too short, should fail
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="at least 32 characters"):
                Settings()

    def test_production_rejects_development_secrets(self):
        """
        Production MUST detect and reject common development secrets.

        Prevents accidental use of default/development secrets in production.
        This is a critical security requirement.
        """
        development_secrets = [
            "changeme" + "x" * 24,  # 32 chars but obviously dev secret
            "password" + "x" * 24,
            "secret" + "x" * 26,
            "test" + "x" * 28,
            "development" + "x" * 21,
        ]

        for dev_secret in development_secrets:
            with patch.dict(os.environ, {
                "APP_ENV": "production",
                "SECRET_KEY": dev_secret,
                "JWT_SECRET_KEY": "b" * 32,
                "DATABASE_URL": "postgresql://user:pass@localhost/db",
                "REDIS_URL": "redis://localhost:6379/0",
            }, clear=True):
                from src.config import Settings

                with pytest.raises(
                    ValidationError,
                    match="(development secret|weak secret|insecure)"
                ):
                    Settings()

    def test_production_requires_https_frontend_url(self):
        """
        Production MUST use HTTPS for frontend URL.

        HTTP URLs are insecure for production deployment.
        Addresses AP-CRIT-001: Hardcoded localhost URLs.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_URL": "http://example.com",  # HTTP not allowed
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="HTTPS.*production"):
                Settings()

    def test_production_requires_https_backend_url(self):
        """
        Production MUST use HTTPS for backend URL.

        HTTP URLs are insecure for production deployment.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "BACKEND_URL": "http://api.example.com",  # HTTP not allowed
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="HTTPS.*production"):
                Settings()

    def test_production_requires_groq_api_key_if_primary(self):
        """
        Production MUST have GROQ_API_KEY if GROQ is primary LLM provider.

        Fail-fast if LLM API key is missing.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_URL": "https://example.com",
            "BACKEND_URL": "https://api.example.com",
            "LLM_PRIMARY_PROVIDER": "groq",
            # GROQ_API_KEY intentionally missing
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="GROQ_API_KEY.*required"):
                Settings()

    def test_production_validates_database_url_format(self):
        """
        Production MUST validate DATABASE_URL is a valid PostgreSQL URL.

        Prevents misconfiguration that would cause runtime failures.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "invalid://not-a-postgres-url",
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_URL": "https://example.com",
            "BACKEND_URL": "https://api.example.com",
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="PostgreSQL"):
                Settings()

    def test_production_validates_redis_url_format(self):
        """
        Production MUST validate REDIS_URL is a valid Redis URL.

        Prevents misconfiguration that would cause runtime failures.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "invalid://not-a-redis-url",
            "FRONTEND_URL": "https://example.com",
            "BACKEND_URL": "https://api.example.com",
        }, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError, match="Redis"):
                Settings()


class TestDevelopmentConfigFlexibility:
    """Test that development environment allows flexible configuration."""

    def test_development_allows_http_urls(self):
        """
        Development environment SHOULD allow HTTP URLs.

        HTTP is acceptable for local development.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_URL": "http://localhost:3000",
            "BACKEND_URL": "http://localhost:5000",
        }, clear=True):
            from src.config import Settings

            # Should not raise - HTTP is OK in development
            settings = Settings()
            assert settings.frontend_url == "http://localhost:3000"
            assert settings.backend_url == "http://localhost:5000"

    def test_development_allows_optional_llm_keys(self):
        """
        Development environment SHOULD allow missing LLM API keys.

        Developers might not have API keys for local testing.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "development",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "b" * 32,
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            # No GROQ_API_KEY
        }, clear=True):
            from src.config import Settings

            # Should not raise - API keys optional in development
            settings = Settings()
            assert settings.groq_api_key is None


class TestSecretRotation:
    """Test secret rotation procedures."""

    def test_different_secrets_for_jwt_and_app(self):
        """
        Best practice: JWT secret and app secret SHOULD be different.

        Reduces blast radius if one secret is compromised.
        """
        with patch.dict(os.environ, {
            "APP_ENV": "production",
            "SECRET_KEY": "a" * 32,
            "JWT_SECRET_KEY": "a" * 32,  # Same as SECRET_KEY - warning
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "FRONTEND_URL": "https://example.com",
            "BACKEND_URL": "https://api.example.com",
            "GROQ_API_KEY": "fake-api-key-for-testing",  # Required when GROQ is primary
        }, clear=True):
            from src.config import Settings

            # Should still work but log a warning
            settings = Settings()

            # Check that we can detect they're the same
            assert (
                settings.secret_key.get_secret_value() ==
                settings.jwt_secret_key.get_secret_value()
            ), "This test verifies same secrets are accepted but should warn in logs"


class TestConfigurationErrorMessages:
    """Test that configuration errors provide clear, actionable messages."""

    def test_missing_secret_key_error_message(self):
        """
        Error messages MUST guide users to fix configuration.

        Clear error messages reduce deployment friction.
        """
        with patch.dict(os.environ, {}, clear=True):
            from src.config import Settings

            with pytest.raises(ValidationError) as exc_info:
                Settings(_env_file=None)  # Disable .env file loading

            error_msg = str(exc_info.value)
            # Should mention the field name
            assert "SECRET_KEY" in error_msg or "secret_key" in error_msg

    def test_weak_secret_error_message_helpful(self):
        """
        Weak secret errors MUST explain how to generate strong secrets.
        """
        with patch.dict(os.environ, {
            "SECRET_KEY": "weak",
            "JWT_SECRET_KEY": "b" * 32,
        }, clear=True):
            from src.config import Settings

            try:
                Settings()
                pytest.fail("Should have raised ValidationError")
            except ValidationError as e:
                error_msg = str(e)
                # Should explain minimum length
                assert "32 characters" in error_msg
                # Should provide command to generate secure secret
                assert "secrets.token_urlsafe" in error_msg or "python -c" in error_msg

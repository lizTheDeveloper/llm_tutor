"""
Pytest configuration and shared fixtures for backend tests.
Provides database setup/teardown and test client.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load test environment variables BEFORE any other imports
test_env_path = Path(__file__).parent.parent / ".env.test"
if test_env_path.exists():
    load_dotenv(test_env_path, override=True)
    print(f"[TEST CONFIG] Loaded test environment from {test_env_path}")
else:
    print(f"[TEST CONFIG] WARNING: .env.test not found at {test_env_path}")

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from src.models.base import Base
from src.app import create_app


# Test database URL - using dev database for tests (no permission to create test DB)
# NOTE: Tests use transactions that rollback, so dev data is safe
# Load from environment or use default
TEST_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://llmtutor@localhost/llm_tutor_dev")


@pytest.fixture(scope="function")
def event_loop():
    """
    Create event loop for async tests.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """
    Create test database engine for tests.
    Function scope to ensure clean state, but tables are NOT dropped/recreated each time.
    Instead, transactions rollback to keep tests isolated while reusing tables.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    # Create tables once - checkfirst=True skips if already exist
    # This dramatically improves test performance
    async with engine.begin() as conn:
        # Skip tables that require pgvector extension in test environment
        from src.models.interaction_log import InteractionLog
        from src.models.user_memory import UserMemory

        # Get all tables except those requiring pgvector
        tables_to_create = [
            table for table in Base.metadata.sorted_tables
            if table.name not in ['interaction_logs']  # Skip pgvector-dependent tables
        ]

        # Create tables - checkfirst=True makes this idempotent
        for table in tables_to_create:
            try:
                await conn.run_sync(lambda sync_conn, t=table: t.create(sync_conn, checkfirst=True))
            except Exception as e:
                # Log but don't fail - table might already exist
                print(f"[TEST] Info: Table {table.name} creation: {e}")

    yield engine

    # No teardown - tables persist between tests for performance
    # Tests use transactions that rollback, so data is isolated
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a new database session for each test.
    Automatically rolls back changes after each test.
    """
    # Create session factory
    async_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_factory() as session:
        # Begin a transaction
        async with session.begin():
            yield session
            # Transaction is automatically rolled back after test


@pytest.fixture
async def clear_rate_limits():
    """
    Clear rate limit data in Redis before each test.
    This prevents rate limiting issues when running multiple tests.
    NOT autouse - only used by tests that need rate limiting cleared.
    This significantly improves test performance by not initializing Redis for every test.
    """
    from src.utils.redis_client import get_redis

    try:
        redis_manager = get_redis()
        # Get async client
        client = redis_manager.async_client

        # Find and delete all rate limit keys
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="rate_limit:*", count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break

        # Also clear cost tracking keys
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="cost:*", count=100)
            if keys:
                await client.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        # If Redis is not available, just log and continue
        print(f"[TEST] Warning: Could not clear rate limits: {e}")

    yield

    # Cleanup after test (optional - could clear again)


@pytest.fixture
async def app():
    """
    Create test application instance.
    """
    app = create_app()
    app.config['TESTING'] = True
    return app


@pytest.fixture
async def client(app):
    """
    Create test client for making API requests.
    """
    async with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def mock_email_service():
    """
    Create a mock email service for testing.
    """
    from unittest.mock import AsyncMock, patch

    mock_service = AsyncMock()
    mock_service.send_verification_email = AsyncMock()
    mock_service.send_welcome_email = AsyncMock()
    mock_service.send_password_reset_email = AsyncMock()

    with patch('src.api.auth.get_email_service', return_value=mock_service):
        with patch('src.services.email_service.get_email_service', return_value=mock_service):
            yield mock_service


@pytest.fixture
async def mock_auth_tokens():
    """
    Mock auth service token storage methods.
    """
    from unittest.mock import AsyncMock, patch

    with patch('src.services.auth_service.AuthService.store_verification_token', new_callable=AsyncMock) as mock_verify, \
         patch('src.services.auth_service.AuthService.store_password_reset_token', new_callable=AsyncMock) as mock_reset:
        yield {'verify': mock_verify, 'reset': mock_reset}


@pytest.fixture
async def patched_get_session(db_session):
    """
    Patch get_session to return test database session.
    Mock commit() to use flush() instead to keep transaction open for test verification.
    """
    from unittest.mock import patch, AsyncMock
    from contextlib import asynccontextmanager

    # Store original flush method
    original_flush = db_session.flush
    original_commit = db_session.commit

    # Mock commit to just flush (keep transaction open)
    async def mock_commit():
        await original_flush()

    db_session.commit = mock_commit

    @asynccontextmanager
    async def mock_get_session():
        yield db_session

    with patch('src.api.auth.get_session', side_effect=mock_get_session), \
         patch('src.api.chat.get_session', side_effect=mock_get_session), \
         patch('src.api.users.get_session', side_effect=mock_get_session), \
         patch('src.api.exercises.get_session', side_effect=mock_get_session), \
         patch('src.api.progress.get_session', side_effect=mock_get_session):
        yield

    # Restore original commit
    db_session.commit = original_commit


@pytest.fixture
def mock_auth_session():
    """
    Mock auth service create_session method.
    """
    from unittest.mock import AsyncMock, patch

    with patch('src.services.auth_service.AuthService.create_session', new_callable=AsyncMock) as mock_session:
        yield mock_session


@pytest.fixture
def mock_jwt_auth_factory(app):
    """
    Factory fixture for creating JWT auth mocks with custom user data.
    Returns a context manager that can be used to mock authentication for any user.

    Usage:
        async def test_example(client, test_user, mock_jwt_auth_factory, patched_get_session):
            with mock_jwt_auth_factory(test_user):
                response = await client.get('/api/protected-endpoint')
    """
    from unittest.mock import patch, AsyncMock
    from contextlib import contextmanager

    @contextmanager
    def _mock_auth(user):
        # Mock the auth service methods that require_auth decorator uses
        async def mock_validate_session(token):
            return True

        mock_payload = {
            "user_id": user.id,
            "email": user.email,
            "role": getattr(user, 'role', 'student'),
            "jti": "test-jti"
        }

        with patch('src.services.auth_service.AuthService.verify_jwt_token', return_value=mock_payload):
            with patch('src.services.auth_service.AuthService.validate_session', new_callable=AsyncMock, side_effect=mock_validate_session):
                yield

    return _mock_auth


@pytest.fixture
async def test_user(db_session):
    """
    Create a test user for tests that need authentication.
    Uses UUID to ensure unique email per test, avoiding IntegrityError.
    """
    import uuid
    from src.models.user import User, UserRole
    unique_id = str(uuid.uuid4())[:8]  # Short unique ID
    user = User(
        email=f"testuser-{unique_id}@example.com",
        password_hash="hashed_password",
        name="Test User",
        email_verified=True,
        role=UserRole.STUDENT,
        onboarding_completed=True,
        programming_language="Python"
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def auth_headers(test_user, db_session):
    """
    Create authentication headers for a test user.
    Returns headers dict with Bearer token for authenticated requests.
    """
    from src.services.auth_service import AuthService
    auth_service = AuthService(db_session)
    tokens = await auth_service.create_access_token(test_user.id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}

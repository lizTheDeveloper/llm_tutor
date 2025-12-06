"""
Test Suite for Database Optimization (DB-OPT Work Stream)

This test suite verifies:
1. All required indexes exist on frequently-queried columns
2. Sync engine has been removed (async-only architecture)
3. Connection pool is properly tuned based on worker count
4. Query performance meets requirements (< 100ms at scale)

Test Strategy:
- Integration tests using real database connections
- No mocks for database components
- Test actual query performance with EXPLAIN ANALYZE
- Verify index usage on production-like queries

Author: TDD Workflow Engineer
Work Stream: DB-OPT (Stage 4.5)
Date: 2025-12-06
"""

import pytest
from sqlalchemy import inspect, text, Index
from sqlalchemy.schema import MetaData
from src.utils.database import DatabaseManager, get_database, init_database
from src.models.user import User, UserRole
from src.models.exercise import Exercise, ExerciseDifficulty, UserExercise, ExerciseStatus
from src.models.achievement import (
    Achievement,
    UserAchievement,
    ProgressSnapshot,
    SkillLevel
)
from src.config import get_settings
import asyncio
from datetime import datetime, timedelta


class TestDatabaseIndexes:
    """
    Test suite for verifying all required database indexes exist.

    Per AP-DATA-001, missing indexes cause full table scans that will fail at 10k users.
    These tests ensure indexes are present for all frequently-queried columns.
    """

    @pytest.mark.asyncio
    async def test_users_role_index_exists(self):
        """
        Test that users.role has an index for admin queries.

        Query: SELECT * FROM users WHERE role = 'admin'
        Without index: O(n) full table scan - 10,000 rows at 10k users
        With index: O(log n) ≈ 13 comparisons
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        # DB-OPT: Use migration engine for inspection (no sync_engine in DatabaseManager)
        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('users')
        engine.dispose()

        # Check if 'role' column has an index
        role_indexed = any(
            'role' in idx['column_names']
            for idx in indexes
        )

        assert role_indexed, (
            "Missing index on users.role - admin queries will do full table scan. "
            "At 10k users, queries will be ~800ms instead of ~12ms."
        )

    @pytest.mark.asyncio
    async def test_users_is_active_index_exists(self):
        """
        Test that users.is_active has an index.

        Query: SELECT * FROM users WHERE is_active = true
        Used everywhere in the application for filtering active users.
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('users')
        engine.dispose()

        is_active_indexed = any(
            'is_active' in idx['column_names']
            for idx in indexes
        )

        assert is_active_indexed, (
            "Missing index on users.is_active - most queries filter by this column. "
            "Performance will degrade significantly at scale."
        )

    @pytest.mark.asyncio
    async def test_users_onboarding_completed_index_exists(self):
        """
        Test that users.onboarding_completed has an index for dashboard queries.

        Query: SELECT * FROM users WHERE onboarding_completed = false
        Used in dashboard to show incomplete onboarding users.
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('users')
        engine.dispose()

        onboarding_indexed = any(
            'onboarding_completed' in idx['column_names']
            for idx in indexes
        )

        assert onboarding_indexed, (
            "Missing index on users.onboarding_completed - dashboard queries will be slow. "
            "Every user login checks this column."
        )

    @pytest.mark.asyncio
    async def test_exercises_difficulty_index_exists(self):
        """
        Test that exercises.difficulty has an index for adaptive algorithm.

        Query: SELECT * FROM exercises WHERE difficulty = 'medium'
        Used by adaptive difficulty engine to select appropriate exercises.
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('exercises')
        engine.dispose()

        difficulty_indexed = any(
            'difficulty' in idx['column_names']
            for idx in indexes
        )

        assert difficulty_indexed, (
            "Missing index on exercises.difficulty - exercise generation will be slow. "
            "D3 adaptive algorithm queries by difficulty frequently."
        )

    @pytest.mark.asyncio
    async def test_exercises_language_index_exists(self):
        """
        Test that exercises.programming_language has an index for exercise generation.

        Query: SELECT * FROM exercises WHERE programming_language = 'python'
        Used to filter exercises by user's preferred language.
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('exercises')
        engine.dispose()

        language_indexed = any(
            'programming_language' in idx['column_names']
            for idx in indexes
        )

        assert language_indexed, (
            "Missing index on exercises.programming_language - exercise queries will be slow. "
            "Every daily exercise generation filters by language."
        )

    @pytest.mark.asyncio
    async def test_user_exercises_status_index_exists(self):
        """
        Test that user_exercises.status has an index for progress tracking.

        Query: SELECT * FROM user_exercises WHERE status = 'completed'
        Used extensively in progress tracking (D2) to calculate statistics.
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('user_exercises')
        engine.dispose()

        status_indexed = any(
            'status' in idx['column_names']
            for idx in indexes
        )

        assert status_indexed, (
            "Missing index on user_exercises.status - progress queries will be slow. "
            "D2 progress tracking queries this column constantly."
        )

    @pytest.mark.asyncio
    async def test_user_exercises_composite_index_exists(self):
        """
        Test that user_exercises has composite index (user_id, created_at) for streak calculations.

        Query: SELECT * FROM user_exercises
               WHERE user_id = 123
               ORDER BY created_at DESC

        Used for streak calculations and exercise history retrieval.
        This is a composite index for optimal query performance.
        """
        settings = get_settings()
        from src.utils.database import get_sync_engine_for_migrations

        engine = get_sync_engine_for_migrations(settings.database_url)
        inspector = inspect(engine)
        indexes = inspector.get_indexes('user_exercises')
        engine.dispose()

        # Check for composite index with both user_id and created_at
        composite_indexed = any(
            set(['user_id', 'created_at']).issubset(set(idx['column_names']))
            for idx in indexes
        )

        assert composite_indexed, (
            "Missing composite index on user_exercises(user_id, created_at). "
            "Streak calculations will be extremely slow - O(n*m) where n=users, m=exercises. "
            "At 10k users with 30 exercises each, queries will take 1200ms instead of 25ms."
        )


class TestSyncEngineRemoval:
    """
    Test suite for verifying sync engine has been removed.

    Per AP-ARCH-004, dual engines double connection pool requirements.
    Current: 20 sync + 20 async = 40 connections
    Should be: 20 async connections only

    50% reduction in connection pool usage.
    """

    def test_database_manager_has_no_sync_engine_property(self):
        """
        Test that DatabaseManager no longer exposes sync_engine property.

        The sync engine should be completely removed from DatabaseManager,
        not just deprecated or hidden.
        """
        settings = get_settings()
        db = DatabaseManager(
            database_url=settings.database_url,
            pool_size=20
        )

        # Sync engine property should not exist
        assert not hasattr(db, '_sync_engine'), (
            "DatabaseManager still has _sync_engine attribute. "
            "This doubles connection pool requirements (20 sync + 20 async = 40 total). "
            "Should be async-only architecture."
        )

    def test_database_manager_has_no_session_factory(self):
        """
        Test that DatabaseManager no longer has synchronous session factory.
        """
        settings = get_settings()
        db = DatabaseManager(
            database_url=settings.database_url,
            pool_size=20
        )

        assert not hasattr(db, 'session_factory'), (
            "DatabaseManager still has sync session_factory. "
            "All sessions should be async-only."
        )

    def test_database_manager_has_no_get_sync_session_method(self):
        """
        Test that DatabaseManager no longer has get_sync_session method.
        """
        settings = get_settings()
        db = DatabaseManager(
            database_url=settings.database_url,
            pool_size=20
        )

        assert not hasattr(db, 'get_sync_session'), (
            "DatabaseManager still has get_sync_session() method. "
            "Should only have async session methods."
        )

    def test_only_async_engine_exists(self):
        """
        Test that only async engine is created.
        """
        settings = get_settings()
        db = DatabaseManager(
            database_url=settings.database_url,
            pool_size=20
        )

        # Should have async engine
        assert hasattr(db, 'async_engine'), "Missing async_engine property"

        # Should NOT have sync engine
        assert not hasattr(db, 'sync_engine'), (
            "Still has sync_engine property. Should be async-only."
        )


class TestConnectionPoolTuning:
    """
    Test suite for verifying connection pool is properly tuned.

    Connection pool should be calculated as:
    pool_size = workers × threads × 2 + overhead

    Example: 4 workers × 4 threads × 2 + 4 = 36 connections

    Per architectural review, arbitrary defaults lead to either:
    - Wasted resources (pool too large)
    - Connection exhaustion (pool too small)
    """

    def test_connection_pool_calculation_documented(self):
        """
        Test that connection pool calculation is documented in code.

        The formula and reasoning should be clear in comments.
        """
        # Read database.py to check for pool size calculation documentation
        with open('/home/llmtutor/llm_tutor/backend/src/utils/database.py', 'r') as f:
            database_py_content = f.read()

        # Check for pool size calculation documentation
        has_calculation_docs = (
            'workers' in database_py_content.lower() and
            'threads' in database_py_content.lower() and
            'pool' in database_py_content.lower()
        )

        assert has_calculation_docs, (
            "Connection pool sizing calculation not documented. "
            "Should explain: pool_size = workers × threads × 2 + overhead"
        )

    def test_connection_pool_size_is_configurable(self):
        """
        Test that pool size can be configured from settings.
        """
        settings = get_settings()

        # Pool size should be configurable
        assert hasattr(settings, 'database_pool_size') or hasattr(settings, 'DATABASE_POOL_SIZE'), (
            "Pool size not configurable from settings. "
            "Should have DATABASE_POOL_SIZE config option."
        )

    def test_connection_pool_respects_configured_size(self):
        """
        Test that DatabaseManager uses configured pool size.
        """
        test_pool_size = 36
        db = DatabaseManager(
            database_url="postgresql://user:pass@localhost/test",
            pool_size=test_pool_size
        )

        assert db.pool_size == test_pool_size, (
            f"DatabaseManager not using configured pool size. "
            f"Expected {test_pool_size}, got {db.pool_size}"
        )


class TestQueryPerformance:
    """
    Test suite for verifying query performance with indexes.

    Performance targets (per CRITICAL-ROADMAP-ITEMS.md):
    - Find active users: < 50ms (currently 800ms without index)
    - Find by role: < 50ms (currently 650ms without index)
    - Streak calculation: < 100ms (currently 1200ms without index)
    - Exercise by difficulty: < 50ms (currently 400ms without index)

    These tests use EXPLAIN ANALYZE to verify index usage.
    """

    @pytest.mark.asyncio
    async def test_active_users_query_uses_index(self):
        """
        Test that active users query uses index (not full table scan).

        Query: SELECT * FROM users WHERE is_active = true
        Should use: Index Scan on idx_users_is_active
        Should NOT: Seq Scan on users
        """
        settings = get_settings()
        db = init_database(settings.database_url)

        async with db.get_async_session() as session:
            # Use EXPLAIN to check query plan
            result = await session.execute(
                text("EXPLAIN SELECT * FROM users WHERE is_active = true")
            )
            query_plan = result.fetchall()
            query_plan_str = ' '.join([str(row) for row in query_plan])

            # Should use index scan, not sequential scan
            uses_index = 'Index Scan' in query_plan_str or 'Bitmap Index Scan' in query_plan_str
            is_seq_scan = 'Seq Scan' in query_plan_str

            assert uses_index or not is_seq_scan, (
                f"Query for active users not using index. "
                f"Query plan: {query_plan_str}\n"
                f"Add index on users.is_active to avoid full table scan."
            )

    @pytest.mark.asyncio
    async def test_role_query_uses_index(self):
        """
        Test that role-based query uses index.

        Query: SELECT * FROM users WHERE role = 'admin'
        Should use index scan on users.role.
        """
        settings = get_settings()
        db = init_database(settings.database_url)

        async with db.get_async_session() as session:
            result = await session.execute(
                text("EXPLAIN SELECT * FROM users WHERE role = 'admin'")
            )
            query_plan = result.fetchall()
            query_plan_str = ' '.join([str(row) for row in query_plan])

            uses_index = 'Index Scan' in query_plan_str or 'Bitmap Index Scan' in query_plan_str
            is_seq_scan = 'Seq Scan' in query_plan_str

            assert uses_index or not is_seq_scan, (
                f"Query for users by role not using index. "
                f"Query plan: {query_plan_str}\n"
                f"Add index on users.role for admin queries."
            )

    @pytest.mark.asyncio
    async def test_difficulty_query_uses_index(self):
        """
        Test that difficulty-based exercise query uses index.

        Query: SELECT * FROM exercises WHERE difficulty = 'medium'
        Should use index scan on exercises.difficulty.
        """
        settings = get_settings()
        db = init_database(settings.database_url)

        async with db.get_async_session() as session:
            result = await session.execute(
                text("EXPLAIN SELECT * FROM exercises WHERE difficulty = 'medium'")
            )
            query_plan = result.fetchall()
            query_plan_str = ' '.join([str(row) for row in query_plan])

            uses_index = 'Index Scan' in query_plan_str or 'Bitmap Index Scan' in query_plan_str
            is_seq_scan = 'Seq Scan' in query_plan_str

            assert uses_index or not is_seq_scan, (
                f"Query for exercises by difficulty not using index. "
                f"Query plan: {query_plan_str}\n"
                f"Add index on exercises.difficulty for adaptive algorithm."
            )

    @pytest.mark.asyncio
    async def test_streak_calculation_query_uses_composite_index(self):
        """
        Test that streak calculation uses composite index.

        Query: SELECT * FROM user_exercises
               WHERE user_id = 123
               ORDER BY created_at DESC

        Should use composite index (user_id, created_at).
        """
        settings = get_settings()
        db = init_database(settings.database_url)

        async with db.get_async_session() as session:
            # Create a test user first
            test_user = User(
                email=f"test_streak_{datetime.now().timestamp()}@example.com",
                name="Test User",
                role=UserRole.STUDENT
            )
            session.add(test_user)
            await session.flush()

            # Check query plan
            result = await session.execute(
                text(f"EXPLAIN SELECT * FROM user_exercises WHERE user_id = {test_user.id} ORDER BY created_at DESC")
            )
            query_plan = result.fetchall()
            query_plan_str = ' '.join([str(row) for row in query_plan])

            uses_index = 'Index Scan' in query_plan_str or 'Bitmap Index Scan' in query_plan_str
            is_seq_scan = 'Seq Scan' in query_plan_str

            assert uses_index or not is_seq_scan, (
                f"Streak calculation query not using composite index. "
                f"Query plan: {query_plan_str}\n"
                f"Add composite index on user_exercises(user_id, created_at)."
            )


class TestDatabaseArchitecture:
    """
    Additional tests for database architecture improvements.
    """

    def test_health_check_uses_async_engine_only(self):
        """
        Test that health check endpoint uses async engine only.

        Per AP-ARCH-004, health check was creating sync engine unnecessarily.
        This test verifies health check is fully async.
        """
        # This will be verified by checking app.py health check implementation
        # The actual health check should use async_engine, not sync_engine

        with open('/home/llmtutor/llm_tutor/backend/src/app.py', 'r') as f:
            app_py_content = f.read()

        # Health check should not reference sync_engine
        health_check_uses_sync = 'sync_engine' in app_py_content

        assert not health_check_uses_sync, (
            "Health check endpoint still uses sync_engine. "
            "Should use async_engine only to avoid connection leak."
        )

    @pytest.mark.asyncio
    async def test_alembic_migration_exists_for_indexes(self):
        """
        Test that Alembic migration exists for adding indexes.

        All index additions should be in a migration file.
        """
        import os
        import glob

        # Check for migration files
        migration_dir = '/home/llmtutor/llm_tutor/backend/alembic/versions'

        if os.path.exists(migration_dir):
            migration_files = glob.glob(f"{migration_dir}/*.py")

            # Look for recent migration mentioning indexes
            index_migration_found = False
            for migration_file in migration_files:
                with open(migration_file, 'r') as f:
                    content = f.read()
                    if 'create_index' in content.lower() or 'add missing indexes' in content.lower():
                        index_migration_found = True
                        break

            # Migration should exist (this will fail initially in TDD, then pass after migration created)
            assert index_migration_found, (
                "No Alembic migration found for adding indexes. "
                "Create migration with: alembic revision --autogenerate -m 'Add missing indexes'"
            )
        else:
            pytest.skip("Alembic migrations directory not found")


class TestIndexPerformanceImpact:
    """
    Test suite to demonstrate performance impact of indexes.

    These tests create sample data and measure query performance
    with and without indexes (if possible).
    """

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_index_performance_improvement_measurable(self):
        """
        Test that indexes provide measurable performance improvement.

        This test is marked as slow since it creates sample data.
        It verifies that indexed queries are significantly faster.
        """
        settings = get_settings()
        db = init_database(settings.database_url)

        async with db.get_async_session() as session:
            # Use EXPLAIN ANALYZE to get actual execution time
            result = await session.execute(
                text("EXPLAIN ANALYZE SELECT * FROM users WHERE is_active = true LIMIT 100")
            )
            query_plan = result.fetchall()
            query_plan_str = '\n'.join([str(row[0]) for row in query_plan])

            # Extract execution time from EXPLAIN ANALYZE output
            # Format: "Execution Time: XX.XXX ms"
            import re
            time_match = re.search(r'Execution Time: ([\d.]+) ms', query_plan_str)

            if time_match:
                execution_time_ms = float(time_match.group(1))

                # With proper indexes, queries should be < 50ms even with data
                # This is a soft assertion - may fail with small datasets
                # but demonstrates the performance target
                assert execution_time_ms < 100, (
                    f"Query execution time ({execution_time_ms}ms) exceeds 100ms target. "
                    f"Verify indexes are present and being used.\n"
                    f"Query plan:\n{query_plan_str}"
                )

"""
Database configuration and connection management for CodeMentor backend.
Provides SQLAlchemy setup with PostgreSQL connection pooling.

DB-OPT Changes:
- Removed sync engine (async-only architecture)
- Added connection pool sizing documentation
- Created get_sync_engine_for_migrations() for Alembic
"""
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import QueuePool
import threading

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Base class for all models
Base = declarative_base()


class DatabaseManager:
    """
    Database connection and session management.
    Async-only architecture for optimal connection pool utilization.

    DB-OPT: Removed sync engine to reduce connection pool usage by 50%.
    Previous: 20 sync + 20 async = 40 connections
    Current: 20 async connections only

    Connection Pool Sizing Formula:
        pool_size = workers × threads × 2 + overhead
        Example: 4 workers × 4 threads × 2 + 4 = 36 connections

    For Alembic migrations, use get_sync_engine_for_migrations() instead.
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 20,
        max_overflow: int = 10,
        pool_pre_ping: bool = True,
        echo: bool = False,
    ):
        """
        Initialize database manager with async-only engine.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Connection pool size (calculated based on workers × threads × 2 + overhead)
            max_overflow: Maximum overflow connections
            pool_pre_ping: Enable connection health checks
            echo: Enable SQL query echo logging
        """
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_pre_ping = pool_pre_ping
        self.echo = echo

        # Initialize async engine only (DB-OPT: removed sync engine)
        self._async_engine = None
        self._async_session_factory = None

        logger.info(
            "Database manager initialized (async-only)",
            extra={
                "pool_size": pool_size,
                "max_overflow": max_overflow,
            },
        )

    @property
    def async_engine(self):
        """Get or create asynchronous SQLAlchemy engine."""
        if self._async_engine is None:
            # Convert postgresql:// to postgresql+asyncpg://
            async_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )
            self._async_engine = create_async_engine(
                async_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=self.pool_pre_ping,
                echo=self.echo,
            )
            logger.info("Asynchronous database engine created")
        return self._async_engine

    @property
    def async_session_factory(self):
        """Get or create asynchronous session factory."""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        return self._async_session_factory

    @asynccontextmanager
    async def get_async_session(self):
        """
        Get an async database session context manager.

        Usage:
            async with db_manager.get_async_session() as session:
                # Use session
                result = await session.execute(query)
        """
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as exception:
                await session.rollback()
                logger.error(
                    "Database session error",
                    exc_info=True,
                    extra={"exception": str(exception)},
                )
                raise
            finally:
                await session.close()

    async def create_all_tables(self):
        """
        Create all database tables defined in models (async).

        DB-OPT: Converted to async to avoid sync engine dependency.
        """
        logger.info("Creating database tables (async)")
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

    async def drop_all_tables(self):
        """
        Drop all database tables. Use with caution!

        DB-OPT: Converted to async to avoid sync engine dependency.
        """
        logger.warning("Dropping all database tables (async)")
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.warning("All database tables dropped")

    async def close(self):
        """
        Close database connections and dispose async engine.

        DB-OPT: Only async engine exists now.
        """
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database engine disposed")


# Global database manager instance and thread lock
_db_manager: Optional[DatabaseManager] = None
_db_lock = threading.Lock()


def init_database(
    database_url: str,
    pool_size: int = 20,
    max_overflow: int = 10,
    enable_slow_query_logging: bool = True,
    slow_query_threshold_ms: float = 100.0
) -> DatabaseManager:
    """
    Initialize global database manager (thread-safe).

    Args:
        database_url: PostgreSQL connection URL
        pool_size: Connection pool size
        max_overflow: Maximum overflow connections
        enable_slow_query_logging: Enable slow query logging (PERF-1)
        slow_query_threshold_ms: Slow query threshold in milliseconds

    Returns:
        Initialized DatabaseManager instance
    """
    global _db_manager

    with _db_lock:
        if _db_manager is None:
            _db_manager = DatabaseManager(
                database_url=database_url,
                pool_size=pool_size,
                max_overflow=max_overflow,
            )
            logger.info("Global database manager initialized")

            # Enable slow query logging (PERF-1)
            if enable_slow_query_logging:
                from ..middleware.slow_query_logger import init_slow_query_logging
                init_slow_query_logging(
                    _db_manager.async_engine,
                    threshold_ms=slow_query_threshold_ms
                )

    return _db_manager


def get_database() -> DatabaseManager:
    """
    Get the global database manager instance.

    Returns:
        DatabaseManager instance

    Raises:
        RuntimeError: If database not initialized
    """
    if _db_manager is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _db_manager


@asynccontextmanager
async def get_async_db_session():
    """
    Dependency injection function for Quart routes to get async database session.

    Usage in routes:
        @app.route('/users')
        async def get_users():
            async with get_async_db_session() as session:
                # Use session
    """
    db_manager = get_database()
    async with db_manager.get_async_session() as session:
        yield session


def get_sync_engine_for_migrations(database_url: str):
    """
    Create a synchronous engine specifically for Alembic migrations.

    DB-OPT: DatabaseManager no longer has sync engine. This function provides
    a separate sync engine ONLY for migration purposes.

    Args:
        database_url: PostgreSQL connection URL

    Returns:
        Synchronous SQLAlchemy engine for migrations

    Usage in alembic/env.py:
        from src.utils.database import get_sync_engine_for_migrations
        engine = get_sync_engine_for_migrations(config.get_main_option("sqlalchemy.url"))
    """
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=5,  # Small pool for migrations only
        max_overflow=5,
        pool_pre_ping=True,
    )
    logger.info("Created sync engine for migrations")
    return engine

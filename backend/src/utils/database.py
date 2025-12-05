"""
Database configuration and connection management for CodeMentor backend.
Provides SQLAlchemy setup with PostgreSQL connection pooling.
"""
from typing import Optional
from contextlib import asynccontextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import QueuePool
import time

from ..utils.logger import get_logger, log_database_query

logger = get_logger(__name__)

# Base class for all models
Base = declarative_base()


class DatabaseManager:
    """
    Database connection and session management.
    Handles both sync and async SQLAlchemy engines.
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
        Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Connection pool size
            max_overflow: Maximum overflow connections
            pool_pre_ping: Enable connection health checks
            echo: Enable SQL query echo logging
        """
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_pre_ping = pool_pre_ping
        self.echo = echo

        # Initialize engines
        self._sync_engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None

        logger.info(
            "Database manager initialized",
            extra={
                "pool_size": pool_size,
                "max_overflow": max_overflow,
            },
        )

    @property
    def sync_engine(self):
        """Get or create synchronous SQLAlchemy engine."""
        if self._sync_engine is None:
            self._sync_engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_pre_ping=self.pool_pre_ping,
                echo=self.echo,
            )
            self._setup_event_listeners(self._sync_engine)
            logger.info("Synchronous database engine created")
        return self._sync_engine

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
    def session_factory(self):
        """Get or create synchronous session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.sync_engine,
                class_=Session,
                expire_on_commit=False,
            )
        return self._session_factory

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

    def _setup_event_listeners(self, engine):
        """Set up SQLAlchemy event listeners for query logging."""

        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Record query start time."""
            conn.info.setdefault("query_start_time", []).append(time.time())

        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Log query execution time."""
            total_time = time.time() - conn.info["query_start_time"].pop()
            log_database_query(
                query=statement,
                duration_ms=total_time * 1000,
                success=True,
            )

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

    def get_sync_session(self) -> Session:
        """
        Get a synchronous database session.

        Returns:
            SQLAlchemy Session instance

        Note: Caller is responsible for closing the session.
        """
        return self.session_factory()

    def create_all_tables(self):
        """Create all database tables defined in models."""
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=self.sync_engine)
        logger.info("Database tables created successfully")

    def drop_all_tables(self):
        """Drop all database tables. Use with caution!"""
        logger.warning("Dropping all database tables")
        Base.metadata.drop_all(bind=self.sync_engine)
        logger.warning("All database tables dropped")

    async def close(self):
        """Close database connections and dispose engines."""
        if self._async_engine:
            await self._async_engine.dispose()
            logger.info("Async database engine disposed")
        if self._sync_engine:
            self._sync_engine.dispose()
            logger.info("Sync database engine disposed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def init_database(
    database_url: str,
    pool_size: int = 20,
    max_overflow: int = 10,
) -> DatabaseManager:
    """
    Initialize global database manager.

    Args:
        database_url: PostgreSQL connection URL
        pool_size: Connection pool size
        max_overflow: Maximum overflow connections

    Returns:
        Initialized DatabaseManager instance
    """
    global _db_manager
    _db_manager = DatabaseManager(
        database_url=database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )
    logger.info("Global database manager initialized")
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

"""
Slow Query Logger Middleware (PERF-1).

This middleware uses SQLAlchemy events to log queries that exceed a threshold.

Features:
1. Logs queries exceeding threshold (default: 100ms)
2. Includes query text, parameters, and execution time
3. Helps identify performance bottlenecks in production
4. Integrates with monitoring service for alerting

Usage:
    from src.middleware.slow_query_logger import init_slow_query_logging
    init_slow_query_logging(engine, threshold_ms=100)
"""
import time
from typing import Any
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from src.logging_config import get_logger

logger = get_logger(__name__)


class SlowQueryLogger:
    """
    SQLAlchemy event listener for slow query detection.

    Tracks query execution time and logs queries exceeding threshold.
    """

    def __init__(self, threshold_ms: float = 100.0):
        """
        Initialize slow query logger.

        Args:
            threshold_ms: Query duration threshold in milliseconds
        """
        self.threshold_ms = threshold_ms
        self.query_start_times = {}

    def before_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        """
        SQLAlchemy event: called before query execution.

        Stores start time for this query.
        """
        conn_id = id(conn)
        self.query_start_times[conn_id] = time.time()

    def after_cursor_execute(
        self,
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany
    ):
        """
        SQLAlchemy event: called after query execution.

        Calculates execution time and logs if exceeds threshold.
        """
        conn_id = id(conn)
        start_time = self.query_start_times.pop(conn_id, None)

        if start_time is None:
            return

        execution_time_ms = (time.time() - start_time) * 1000

        if execution_time_ms >= self.threshold_ms:
            # Extract first 200 chars of query for logging
            query_preview = statement[:200] if len(statement) > 200 else statement

            logger.warning(
                "SLOW QUERY DETECTED",
                extra={
                    "execution_time_ms": round(execution_time_ms, 2),
                    "threshold_ms": self.threshold_ms,
                    "query_preview": query_preview,
                    "has_parameters": parameters is not None and len(parameters) > 0,
                    "executemany": executemany,
                    "performance_issue": "slow_query"
                }
            )

            # Log full query at debug level
            logger.debug(
                "Full slow query",
                extra={
                    "query": statement,
                    "parameters": str(parameters) if parameters else None,
                    "execution_time_ms": round(execution_time_ms, 2)
                }
            )


def init_slow_query_logging(
    engine: Any,
    threshold_ms: float = 100.0
) -> None:
    """
    Initialize slow query logging for a SQLAlchemy engine.

    Registers event listeners to track query performance.

    Args:
        engine: SQLAlchemy engine (sync or async)
        threshold_ms: Query duration threshold in milliseconds (default: 100ms)

    Usage:
        # In app.py or database.py
        from src.middleware.slow_query_logger import init_slow_query_logging

        async_engine = create_async_engine(DATABASE_URL)
        init_slow_query_logging(async_engine, threshold_ms=100)
    """
    slow_query_logger = SlowQueryLogger(threshold_ms=threshold_ms)

    # For async engines, we need to listen on the sync_engine
    if isinstance(engine, AsyncEngine):
        sync_engine = engine.sync_engine
    else:
        sync_engine = engine

    # Register event listeners
    event.listen(
        sync_engine,
        "before_cursor_execute",
        slow_query_logger.before_cursor_execute
    )

    event.listen(
        sync_engine,
        "after_cursor_execute",
        slow_query_logger.after_cursor_execute
    )

    logger.info(
        "Slow query logging initialized",
        extra={
            "threshold_ms": threshold_ms,
            "engine_type": "async" if isinstance(engine, AsyncEngine) else "sync"
        }
    )


# =============================================================================
# QUERY PERFORMANCE STATISTICS
# =============================================================================

class QueryPerformanceTracker:
    """
    Track query performance statistics for monitoring.

    Collects metrics:
    - Total queries executed
    - Average query time
    - Slow query count
    - P50, P95, P99 query times
    """

    def __init__(self):
        """Initialize performance tracker."""
        self.query_times = []
        self.slow_query_count = 0
        self.total_queries = 0
        self.threshold_ms = 100.0

    def record_query(self, execution_time_ms: float):
        """
        Record query execution time.

        Args:
            execution_time_ms: Query execution time in milliseconds
        """
        self.query_times.append(execution_time_ms)
        self.total_queries += 1

        if execution_time_ms >= self.threshold_ms:
            self.slow_query_count += 1

    def get_statistics(self) -> dict:
        """
        Get query performance statistics.

        Returns:
            Dict with performance metrics
        """
        if not self.query_times:
            return {
                "total_queries": 0,
                "slow_queries": 0,
                "avg_time_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0
            }

        sorted_times = sorted(self.query_times)
        count = len(sorted_times)

        return {
            "total_queries": self.total_queries,
            "slow_queries": self.slow_query_count,
            "slow_query_rate": (self.slow_query_count / self.total_queries) * 100,
            "avg_time_ms": sum(self.query_times) / count,
            "min_time_ms": sorted_times[0],
            "max_time_ms": sorted_times[-1],
            "p50_ms": sorted_times[int(count * 0.50)],
            "p95_ms": sorted_times[int(count * 0.95)],
            "p99_ms": sorted_times[int(count * 0.99)]
        }

    def reset(self):
        """Reset all statistics."""
        self.query_times = []
        self.slow_query_count = 0
        self.total_queries = 0


# Global performance tracker instance
_performance_tracker = None


def get_performance_tracker() -> QueryPerformanceTracker:
    """
    Get global query performance tracker.

    Returns:
        QueryPerformanceTracker instance
    """
    global _performance_tracker

    if _performance_tracker is None:
        _performance_tracker = QueryPerformanceTracker()

    return _performance_tracker

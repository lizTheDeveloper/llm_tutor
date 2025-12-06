"""
Custom metrics collection service for application monitoring.

This service collects and exposes custom application metrics:
- HTTP request latency and counts
- LLM API costs per user
- Database query performance
- Active user counts
- Business metrics

Integrates with Prometheus for metrics export.

OPS-1 Work Stream: Production Monitoring Setup
"""

import time
from typing import Dict, Any, List, Optional
from collections import defaultdict, deque
from datetime import datetime, timedelta
import statistics

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST
)

from src.config import settings
from src.utils.logger import get_logger


logger = get_logger(__name__)


class MetricsCollector:
    """
    Custom metrics collector using Prometheus client.

    Metrics Categories:
    1. HTTP Requests (latency, count, status codes)
    2. LLM API (cost, tokens, calls)
    3. Database (query time, pool metrics)
    4. Business (active users, exercises completed)

    All metrics are exposed via Prometheus text format at /metrics endpoint.
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.

        Args:
            registry: Prometheus collector registry (uses default if None)
        """
        self.registry = registry or CollectorRegistry()

        # HTTP Request Metrics
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request latency in seconds',
            ['method', 'endpoint', 'status'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],  # Buckets in seconds
            registry=self.registry
        )

        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status'],
            registry=self.registry
        )

        # LLM API Metrics
        self.llm_cost_usd_total = Counter(
            'llm_cost_usd_total',
            'Total LLM API cost in USD',
            ['user_id', 'provider', 'model'],
            registry=self.registry
        )

        self.llm_tokens_used_total = Counter(
            'llm_tokens_used_total',
            'Total tokens used in LLM API calls',
            ['user_id', 'provider', 'model'],
            registry=self.registry
        )

        self.llm_api_calls_total = Counter(
            'llm_api_calls_total',
            'Total LLM API calls',
            ['provider', 'model', 'status'],
            registry=self.registry
        )

        # Database Metrics
        self.database_query_duration = Histogram(
            'database_query_duration_seconds',
            'Database query execution time',
            ['query_type'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )

        self.database_pool_size = Gauge(
            'database_pool_size',
            'Database connection pool size',
            registry=self.registry
        )

        self.database_active_connections = Gauge(
            'database_active_connections',
            'Number of active database connections',
            registry=self.registry
        )

        # Business Metrics
        self.active_users = Gauge(
            'active_users',
            'Number of active users in last hour',
            registry=self.registry
        )

        self.exercises_completed_total = Counter(
            'exercises_completed_total',
            'Total exercises completed',
            ['programming_language', 'difficulty'],
            registry=self.registry
        )

        # Internal tracking for calculations
        self.user_daily_costs = defaultdict(lambda: defaultdict(float))  # {user_id: {date: cost}}
        self.user_activity_timestamps = defaultdict(list)  # {user_id: [timestamps]}
        self.slow_queries = deque(maxlen=100)  # Keep last 100 slow queries

        logger.info("Metrics collector initialized with Prometheus client")

    def record_request_latency(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_seconds: float
    ):
        """
        Record HTTP request latency.

        Args:
            endpoint: API endpoint path (e.g., "/api/exercises/daily")
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code (200, 404, etc.)
            duration_seconds: Request duration in seconds
        """
        # Record histogram
        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).observe(duration_seconds)

        # Increment counter
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=str(status_code)
        ).inc()

        logger.debug(
            "Request latency recorded",
            extra={
                "endpoint": endpoint,
                "method": method,
                "status": status_code,
                "duration_ms": duration_seconds * 1000
            }
        )

    def record_llm_cost(
        self,
        user_id: int,
        provider: str,
        model: str,
        cost_usd: float,
        tokens_used: int
    ):
        """
        Record LLM API cost and usage.

        Args:
            user_id: User ID
            provider: LLM provider (groq, openai, anthropic)
            model: Model name
            cost_usd: Cost in USD
            tokens_used: Number of tokens used
        """
        # Record cost
        self.llm_cost_usd_total.labels(
            user_id=str(user_id),
            provider=provider,
            model=model
        ).inc(cost_usd)

        # Record tokens
        self.llm_tokens_used_total.labels(
            user_id=str(user_id),
            provider=provider,
            model=model
        ).inc(tokens_used)

        # Increment API call counter
        self.llm_api_calls_total.labels(
            provider=provider,
            model=model,
            status="success"
        ).inc()

        # Track daily cost internally
        today = datetime.now().date().isoformat()
        self.user_daily_costs[user_id][today] += cost_usd

        logger.debug(
            "LLM cost recorded",
            extra={
                "user_id": user_id,
                "provider": provider,
                "cost_usd": cost_usd,
                "tokens": tokens_used
            }
        )

    def record_database_query(
        self,
        query_type: str,
        duration_seconds: float,
        is_slow: bool = False
    ):
        """
        Record database query performance.

        Args:
            query_type: Type of query (SELECT, INSERT, UPDATE, etc.)
            duration_seconds: Query execution time in seconds
            is_slow: Whether this query exceeded slow query threshold
        """
        self.database_query_duration.labels(
            query_type=query_type
        ).observe(duration_seconds)

        if is_slow:
            self.slow_queries.append({
                "query_type": query_type,
                "duration": duration_seconds,
                "timestamp": time.time()
            })

        logger.debug(
            "Database query recorded",
            extra={
                "query_type": query_type,
                "duration_ms": duration_seconds * 1000,
                "slow": is_slow
            }
        )

    def record_connection_pool_metrics(
        self,
        pool_size: int,
        active_connections: int,
        idle_connections: int,
        checkout_time_seconds: float
    ):
        """
        Record database connection pool metrics.

        Args:
            pool_size: Total pool size
            active_connections: Number of active connections
            idle_connections: Number of idle connections
            checkout_time_seconds: Time to checkout connection
        """
        self.database_pool_size.set(pool_size)
        self.database_active_connections.set(active_connections)

        logger.debug(
            "Connection pool metrics recorded",
            extra={
                "pool_size": pool_size,
                "active": active_connections,
                "idle": idle_connections
            }
        )

    def record_user_activity(
        self,
        user_id: int,
        activity_type: str
    ):
        """
        Record user activity for active user tracking.

        Args:
            user_id: User ID
            activity_type: Type of activity (login, exercise_completion, etc.)
        """
        timestamp = time.time()
        self.user_activity_timestamps[user_id].append(timestamp)

        # Update active users count
        self._update_active_users_count()

        logger.debug(
            "User activity recorded",
            extra={"user_id": user_id, "activity_type": activity_type}
        )

    def record_exercise_completion(
        self,
        programming_language: str,
        difficulty: str
    ):
        """
        Record exercise completion for business metrics.

        Args:
            programming_language: Programming language (python, javascript, etc.)
            difficulty: Difficulty level (easy, medium, hard)
        """
        self.exercises_completed_total.labels(
            programming_language=programming_language,
            difficulty=difficulty
        ).inc()

        logger.debug(
            "Exercise completion recorded",
            extra={"language": programming_language, "difficulty": difficulty}
        )

    def get_user_daily_cost(self, user_id: int) -> float:
        """
        Get total LLM cost for a user today.

        Args:
            user_id: User ID

        Returns:
            Total cost in USD for today
        """
        today = datetime.now().date().isoformat()
        return self.user_daily_costs[user_id].get(today, 0.0)

    def get_user_cost_history(self, user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get cost history for a user.

        Args:
            user_id: User ID
            days: Number of days to retrieve

        Returns:
            List of {date, cost} dictionaries
        """
        history = []
        for i in range(days):
            date = (datetime.now().date() - timedelta(days=i)).isoformat()
            cost = self.user_daily_costs[user_id].get(date, 0.0)
            history.append({"date": date, "cost": cost})

        return history

    def get_active_users_count(self, time_window_minutes: int = 60) -> int:
        """
        Get count of active users in time window.

        Args:
            time_window_minutes: Time window in minutes

        Returns:
            Number of active users
        """
        cutoff_time = time.time() - (time_window_minutes * 60)

        active_users = set()
        for user_id, timestamps in self.user_activity_timestamps.items():
            # Check if user has any activity in time window
            if any(ts >= cutoff_time for ts in timestamps):
                active_users.add(user_id)

        return len(active_users)

    def get_slow_queries(self) -> List[Dict[str, Any]]:
        """
        Get recent slow queries.

        Returns:
            List of slow query dictionaries
        """
        return list(self.slow_queries)

    def get_latency_histogram(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """
        Get latency histogram for an endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Histogram data or None if no data
        """
        # This would return actual histogram data from Prometheus
        # For now, return placeholder
        return {"endpoint": endpoint, "histogram": "data"}

    def get_latency_percentiles(self, endpoint: str) -> Dict[str, float]:
        """
        Calculate latency percentiles for an endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Dictionary with p50, p95, p99 percentiles
        """
        # In production, this would query Prometheus
        # For now, return placeholder
        return {
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.

        Returns:
            Dictionary of metric names to values
        """
        # Return metric names that have been registered
        return {
            "http_request_duration_seconds": "histogram",
            "http_requests_total": "counter",
            "llm_cost_usd_total": "counter",
            "database_query_duration_seconds": "histogram",
            "database_pool_size": "gauge",
            "database_active_connections": "gauge",
            "active_users": "gauge",
            "exercises_completed_total": "counter"
        }

    def reset(self):
        """Reset all metrics (for testing)."""
        # Clear internal tracking
        self.user_daily_costs.clear()
        self.user_activity_timestamps.clear()
        self.slow_queries.clear()

        logger.debug("Metrics collector reset")

    def reset_daily_metrics(self):
        """
        Reset daily metrics (called at midnight).

        This keeps historical data but resets daily counters.
        """
        # Remove old daily cost data (keep last 7 days)
        cutoff_date = (datetime.now().date() - timedelta(days=7)).isoformat()

        for user_id in list(self.user_daily_costs.keys()):
            dates_to_remove = [
                date for date in self.user_daily_costs[user_id]
                if date < cutoff_date
            ]
            for date in dates_to_remove:
                del self.user_daily_costs[user_id][date]

        logger.info("Daily metrics reset")

    def _update_active_users_count(self):
        """Update the active users gauge metric."""
        active_count = self.get_active_users_count(time_window_minutes=60)
        self.active_users.set(active_count)

    def generate_prometheus_metrics(self) -> bytes:
        """
        Generate Prometheus metrics in text format.

        Returns:
            Metrics in Prometheus text format
        """
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """
        Get Prometheus content type header.

        Returns:
            Content-Type header value for Prometheus metrics
        """
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.

    Returns:
        MetricsCollector singleton instance
    """
    global _metrics_collector

    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()

    return _metrics_collector


def init_metrics_collector(registry: Optional[CollectorRegistry] = None) -> MetricsCollector:
    """
    Initialize the global metrics collector.

    Args:
        registry: Prometheus collector registry

    Returns:
        Initialized MetricsCollector instance
    """
    global _metrics_collector

    _metrics_collector = MetricsCollector(registry=registry)

    return _metrics_collector

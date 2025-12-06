"""
Production monitoring service integrating error tracking and metrics collection.

This service provides:
- Error tracking with Sentry
- Custom application metrics
- Alert threshold monitoring
- Integration with Prometheus metrics

Architecture:
- Singleton pattern for global monitoring instance
- Async-compatible for Quart integration
- Configurable alert thresholds
- Production-ready error handling

OPS-1 Work Stream: Production Monitoring Setup
"""

import time
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
import asyncio

import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from src.config import settings
from src.utils.logger import get_logger


logger = get_logger(__name__)


class MonitoringService:
    """
    Central monitoring service for error tracking and alerting.

    Features:
    - Sentry integration for error tracking
    - Exception capture with context
    - Message capture for important events
    - Alert threshold monitoring
    - Health status reporting

    Usage:
        monitoring = MonitoringService()
        monitoring.capture_exception(error, context={...})
        monitoring.capture_message("Important event", level="warning")
    """

    def __init__(
        self,
        sentry_dsn: Optional[str] = None,
        environment: Optional[str] = None,
        sample_rate: float = 1.0,
        enable_performance: bool = True
    ):
        """
        Initialize monitoring service.

        Args:
            sentry_dsn: Sentry Data Source Name (DSN) for error tracking
            environment: Environment name (production, staging, development)
            sample_rate: Percentage of events to capture (0.0 to 1.0)
            enable_performance: Whether to enable performance monitoring
        """
        self.environment = environment or settings.app_env
        self.sentry_enabled = sentry_dsn is not None or self._should_enable_sentry()

        # Error tracking for alert thresholds
        self.error_counts = defaultdict(lambda: deque(maxlen=100))
        self.request_latencies = defaultdict(lambda: deque(maxlen=1000))

        # Alert thresholds
        self.alert_thresholds = {
            "error_rate_per_minute": 5,  # 5 errors per minute
            "p95_latency_seconds": 2.0,  # 2 seconds
            "cost_warning_threshold": 0.8,  # 80% of daily limit
        }

        if self.sentry_enabled:
            self._initialize_sentry(sentry_dsn, sample_rate, enable_performance)
            logger.info(
                "Monitoring service initialized with Sentry",
                extra={"environment": self.environment}
            )
        else:
            logger.info(
                "Monitoring service initialized without Sentry (development mode)",
                extra={"environment": self.environment}
            )

    def _should_enable_sentry(self) -> bool:
        """
        Determine if Sentry should be enabled based on environment.

        Returns:
            True if Sentry should be enabled, False otherwise
        """
        # Enable Sentry in production and staging, disable in development/testing
        return self.environment in ["production", "staging"]

    def _initialize_sentry(
        self,
        sentry_dsn: Optional[str],
        sample_rate: float,
        enable_performance: bool
    ):
        """
        Initialize Sentry SDK with appropriate integrations.

        Args:
            sentry_dsn: Sentry DSN from configuration
            sample_rate: Percentage of events to capture
            enable_performance: Whether to enable performance monitoring
        """
        # Get DSN from config if not provided
        dsn = sentry_dsn or getattr(settings, 'sentry_dsn', None)

        if not dsn:
            logger.warning("Sentry DSN not configured, error tracking disabled")
            self.sentry_enabled = False
            return

        # Configure integrations
        integrations = [
            # AsyncioIntegration for proper async support
            AsyncioIntegration(),

            # LoggingIntegration to capture log messages
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above
                event_level=logging.ERROR  # Send errors as events
            ),
        ]

        # Initialize Sentry
        sentry_sdk.init(
            dsn=dsn,
            environment=self.environment,
            traces_sample_rate=sample_rate if enable_performance else 0.0,
            profiles_sample_rate=0.1 if enable_performance else 0.0,
            integrations=integrations,
            send_default_pii=False,  # Don't send PII by default (SEC compliance)
            attach_stacktrace=True,  # Always attach stack traces
            max_breadcrumbs=50,  # Keep last 50 breadcrumbs
            before_send=self._before_send_sentry_event,
        )

        logger.info("Sentry initialized successfully", extra={"dsn": dsn[:20] + "..."})

    def _before_send_sentry_event(
        self,
        event: Dict[str, Any],
        hint: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Filter and modify events before sending to Sentry.

        This hook allows us to:
        - Remove sensitive data (PII, secrets)
        - Add additional context
        - Filter out noise (expected errors)

        Args:
            event: Sentry event dictionary
            hint: Additional context about the event

        Returns:
            Modified event or None to drop the event
        """
        # Add application metadata
        event.setdefault("tags", {})
        event["tags"]["app_name"] = settings.app_name

        # Filter out expected errors that shouldn't alert
        if "exc_info" in hint:
            exc_type, exc_value, tb = hint["exc_info"]
            # Don't send certain expected exceptions
            if exc_type.__name__ in ["ValidationError", "NotFound"]:
                return None

        return event

    def capture_exception(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None
    ):
        """
        Capture an exception with optional context.

        Args:
            exception: The exception to capture
            context: Additional context dictionary
            request_context: HTTP request context (method, URL, user, etc.)
        """
        if not self.sentry_enabled:
            # In development, just log the exception
            logger.error(
                "Exception captured (Sentry disabled)",
                exc_info=exception,
                extra={"context": context}
            )
            return

        # Set context if provided
        if context:
            sentry_sdk.set_context("custom", context)

        if request_context:
            sentry_sdk.set_context("request", request_context)

        # Capture the exception
        sentry_sdk.capture_exception(exception)

        # Track for alert thresholds
        self.error_counts[type(exception).__name__].append(time.time())

        logger.debug(
            "Exception captured by Sentry",
            extra={
                "exception_type": type(exception).__name__,
                "context": context is not None
            }
        )

    def capture_message(
        self,
        message: str,
        level: str = "info",
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Capture a log message with Sentry.

        Useful for important events that aren't exceptions:
        - Security events
        - Business logic events
        - Audit trail

        Args:
            message: Message to capture
            level: Severity level (debug, info, warning, error, critical)
            context: Additional context dictionary
        """
        if not self.sentry_enabled:
            logger.log(
                getattr(logging, level.upper(), logging.INFO),
                message,
                extra={"context": context}
            )
            return

        # Set context if provided
        if context:
            sentry_sdk.set_context("custom", context)

        # Capture message
        sentry_sdk.capture_message(message, level=level)

        logger.debug(
            "Message captured by Sentry",
            extra={"level": level, "message": message[:50]}
        )

    def record_error(
        self,
        error_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Record an error for alert threshold monitoring.

        Args:
            error_type: Type/category of error (e.g., "DATABASE_CONNECTION")
            message: Error message
            context: Additional context
        """
        self.error_counts[error_type].append(time.time())

        logger.warning(
            f"Error recorded: {error_type}",
            extra={"message": message, "context": context}
        )

    def record_request_latency(
        self,
        endpoint: str,
        latency_seconds: float
    ):
        """
        Record request latency for monitoring.

        Args:
            endpoint: API endpoint path
            latency_seconds: Request duration in seconds
        """
        self.request_latencies[endpoint].append({
            "timestamp": time.time(),
            "latency": latency_seconds
        })

    def record_llm_cost(
        self,
        user_id: int,
        cost_usd: float
    ):
        """
        Record LLM API cost for a user.

        Args:
            user_id: User ID
            cost_usd: Cost in USD
        """
        # This would integrate with MetricsCollector in production
        # For now, just log it
        logger.info(
            "LLM cost recorded",
            extra={"user_id": user_id, "cost_usd": cost_usd}
        )

    def check_alert_thresholds(self):
        """
        Check if any alert thresholds have been exceeded.

        This method should be called periodically (e.g., every minute)
        to check for alert conditions.
        """
        current_time = time.time()
        one_minute_ago = current_time - 60

        # Check error rate
        for error_type, timestamps in self.error_counts.items():
            # Count errors in last minute
            recent_errors = sum(1 for ts in timestamps if ts >= one_minute_ago)

            if recent_errors >= self.alert_thresholds["error_rate_per_minute"]:
                self.send_alert({
                    "type": "high_error_rate",
                    "error_type": error_type,
                    "error_count": recent_errors,
                    "threshold": self.alert_thresholds["error_rate_per_minute"],
                    "severity": "warning"
                })

        # Check P95 latency
        for endpoint, latencies in self.request_latencies.items():
            if len(latencies) < 20:  # Need enough samples
                continue

            # Calculate P95
            sorted_latencies = sorted([l["latency"] for l in latencies])
            p95_index = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[p95_index]

            if p95_latency >= self.alert_thresholds["p95_latency_seconds"]:
                self.send_alert({
                    "type": "high_latency",
                    "endpoint": endpoint,
                    "p95_latency": p95_latency,
                    "threshold": self.alert_thresholds["p95_latency_seconds"],
                    "severity": "warning"
                })

    def send_alert(self, alert_data: Dict[str, Any]):
        """
        Send an alert (placeholder for actual alerting system).

        In production, this would integrate with:
        - PagerDuty
        - Slack
        - Email
        - SMS

        Args:
            alert_data: Alert information
        """
        logger.warning(
            f"ALERT: {alert_data['type']}",
            extra=alert_data
        )

        # In production, send to actual alerting system
        if self.sentry_enabled:
            self.capture_message(
                f"Alert: {alert_data['type']}",
                level="warning",
                context=alert_data
            )

    def is_healthy(self) -> bool:
        """
        Check if monitoring service is healthy.

        Returns:
            True if monitoring is operational, False otherwise
        """
        if not self.sentry_enabled:
            return True  # Development mode, always healthy

        # In production, could check Sentry connectivity
        # For now, assume healthy if initialized
        return True

    def shutdown(self):
        """Gracefully shutdown monitoring service."""
        if self.sentry_enabled:
            # Flush any pending events to Sentry
            client = sentry_sdk.Hub.current.client
            if client:
                client.flush(timeout=2.0)

        logger.info("Monitoring service shutdown complete")


# Global monitoring service instance
_monitoring_service: Optional[MonitoringService] = None


def get_monitoring_service() -> MonitoringService:
    """
    Get the global monitoring service instance.

    Returns:
        MonitoringService singleton instance
    """
    global _monitoring_service

    if _monitoring_service is None:
        _monitoring_service = MonitoringService()

    return _monitoring_service


def init_monitoring_service(
    sentry_dsn: Optional[str] = None,
    environment: Optional[str] = None
) -> MonitoringService:
    """
    Initialize the global monitoring service.

    Args:
        sentry_dsn: Sentry DSN for error tracking
        environment: Environment name

    Returns:
        Initialized MonitoringService instance
    """
    global _monitoring_service

    _monitoring_service = MonitoringService(
        sentry_dsn=sentry_dsn,
        environment=environment
    )

    return _monitoring_service

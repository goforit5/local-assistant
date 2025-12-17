"""
Distributed Tracing with OpenTelemetry
Provides span management for tracking request flows
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional, AsyncIterator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode, Span
import structlog

logger = structlog.get_logger(__name__)


class TraceManager:
    """
    Manages distributed tracing with OpenTelemetry.

    Features:
    - Span creation and management
    - Event tracking within spans
    - Automatic error recording
    - Jaeger export support
    """

    def __init__(
        self,
        service_name: str = "local-assistant",
        jaeger_endpoint: Optional[str] = None,
        console_export: bool = False,
    ):
        """
        Initialize trace manager.

        Args:
            service_name: Name of the service
            jaeger_endpoint: Jaeger collector endpoint (e.g., localhost:14268)
            console_export: Whether to export spans to console
        """
        self.service_name = service_name

        # Create resource
        resource = Resource(attributes={SERVICE_NAME: service_name})

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add span processors
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split(":")[0],
                agent_port=int(jaeger_endpoint.split(":")[1]) if ":" in jaeger_endpoint else 6831,
            )
            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            logger.info("jaeger_exporter_enabled", endpoint=jaeger_endpoint)

        if console_export:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("console_exporter_enabled")

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer
        self.tracer = trace.get_tracer(__name__)

        logger.info("trace_manager_initialized", service=service_name)

    @asynccontextmanager
    async def start_span(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Optional[Span] = None,
    ) -> AsyncIterator[Span]:
        """
        Create and manage a span as async context manager.

        Args:
            name: Span name
            attributes: Span attributes
            parent: Parent span

        Yields:
            Span object

        Example:
            async with trace_manager.start_span("api_request", {"model": "gpt-4o"}) as span:
                response = await make_request()
                span.set_attribute("tokens", response.tokens)
        """
        context = trace.set_span_in_context(parent) if parent else None

        with self.tracer.start_as_current_span(name, context=context) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))

            span.set_attribute("start_time", datetime.now().isoformat())

            logger.debug("span_started", span_name=name, span_id=format(span.get_span_context().span_id, '016x'))

            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.error(
                    "span_error",
                    span_name=name,
                    error=str(e),
                    span_id=format(span.get_span_context().span_id, '016x'),
                )
                raise
            finally:
                span.set_attribute("end_time", datetime.now().isoformat())
                logger.debug("span_ended", span_name=name, span_id=format(span.get_span_context().span_id, '016x'))

    def add_event(
        self,
        span: Span,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an event to a span.

        Args:
            span: Span to add event to
            name: Event name
            attributes: Event attributes
        """
        event_attrs = attributes or {}
        event_attrs["timestamp"] = datetime.now().isoformat()
        span.add_event(name, event_attrs)

        logger.debug(
            "span_event",
            event_name=name,
            span_id=format(span.get_span_context().span_id, '016x'),
        )

    def set_attributes(
        self,
        span: Span,
        attributes: Dict[str, Any],
    ) -> None:
        """
        Set multiple attributes on a span.

        Args:
            span: Span to set attributes on
            attributes: Attributes to set
        """
        for key, value in attributes.items():
            span.set_attribute(key, str(value))

    def record_error(
        self,
        span: Span,
        error: Exception,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record an error on a span.

        Args:
            span: Span to record error on
            error: Exception that occurred
            attributes: Additional error attributes
        """
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error, attributes=attributes)

        logger.error(
            "span_error_recorded",
            error_type=type(error).__name__,
            error_message=str(error),
            span_id=format(span.get_span_context().span_id, '016x'),
        )

    def end_span(self, span: Span, status: Optional[StatusCode] = None) -> None:
        """
        Explicitly end a span.

        Args:
            span: Span to end
            status: Status code (defaults to OK)
        """
        if status:
            span.set_status(Status(status))
        span.end()

    def get_current_span(self) -> Optional[Span]:
        """Get the current active span"""
        return trace.get_current_span()

    def create_child_span(
        self,
        parent: Span,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """
        Create a child span.

        Args:
            parent: Parent span
            name: Child span name
            attributes: Child span attributes

        Returns:
            Child span
        """
        context = trace.set_span_in_context(parent)
        span = self.tracer.start_span(name, context=context)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

        return span


# Global instance
_trace_manager: Optional[TraceManager] = None


def get_trace_manager(
    service_name: str = "local-assistant",
    jaeger_endpoint: Optional[str] = None,
    console_export: bool = False,
) -> TraceManager:
    """Get or create global trace manager instance"""
    global _trace_manager
    if _trace_manager is None:
        _trace_manager = TraceManager(service_name, jaeger_endpoint, console_export)
    return _trace_manager


# Convenience decorators
def traced(span_name: Optional[str] = None):
    """
    Decorator to automatically trace async functions.

    Example:
        @traced("process_request")
        async def process_request(data):
            return await process(data)
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            name = span_name or func.__name__
            manager = get_trace_manager()

            async with manager.start_span(name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    manager.record_error(span, e)
                    raise

        return wrapper
    return decorator

"""
Prometheus Metrics Collection
Exports metrics for requests, tokens, latency, costs, and errors
"""

from typing import Dict, Optional, List
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
import structlog

logger = structlog.get_logger(__name__)


class MetricsCollector:
    """
    Collects and exports Prometheus metrics for the local assistant.

    Metrics:
    - request_count: Total API requests by model/provider/status
    - latency_seconds: Request latency distribution
    - token_usage: Token consumption by model/type
    - cost_dollars: API costs by model/window
    - error_rate: Error counts by type/model
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize metrics collector.

        Args:
            registry: Prometheus registry (creates new if None)
        """
        self.registry = registry or CollectorRegistry()

        # Request metrics
        self.request_count = Counter(
            "local_assistant_requests_total",
            "Total number of API requests",
            labelnames=["model", "provider", "status", "capability"],
            registry=self.registry,
        )

        self.request_latency = Histogram(
            "local_assistant_request_latency_seconds",
            "Request latency in seconds",
            labelnames=["model", "provider", "capability"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
            registry=self.registry,
        )

        # Token usage metrics
        self.input_tokens = Counter(
            "local_assistant_input_tokens_total",
            "Total input tokens consumed",
            labelnames=["model", "provider"],
            registry=self.registry,
        )

        self.output_tokens = Counter(
            "local_assistant_output_tokens_total",
            "Total output tokens generated",
            labelnames=["model", "provider"],
            registry=self.registry,
        )

        self.token_rate = Gauge(
            "local_assistant_tokens_per_second",
            "Token generation rate",
            labelnames=["model"],
            registry=self.registry,
        )

        # Cost metrics
        self.cost_total = Counter(
            "local_assistant_cost_dollars_total",
            "Total API costs in dollars",
            labelnames=["model", "provider", "window"],
            registry=self.registry,
        )

        self.cost_hourly = Gauge(
            "local_assistant_cost_hourly_dollars",
            "Hourly API costs in dollars",
            labelnames=["model", "provider"],
            registry=self.registry,
        )

        self.cost_daily = Gauge(
            "local_assistant_cost_daily_dollars",
            "Daily API costs in dollars",
            labelnames=["model", "provider"],
            registry=self.registry,
        )

        # Error metrics
        self.error_count = Counter(
            "local_assistant_errors_total",
            "Total number of errors",
            labelnames=["error_type", "model", "provider"],
            registry=self.registry,
        )

        self.error_rate = Gauge(
            "local_assistant_error_rate",
            "Error rate (errors per request)",
            labelnames=["model"],
            registry=self.registry,
        )

        # Rate limit metrics
        self.rate_limit_hits = Counter(
            "local_assistant_rate_limit_hits_total",
            "Number of rate limit hits",
            labelnames=["model", "provider", "limit_type"],
            registry=self.registry,
        )

        # Cache metrics
        self.cache_hits = Counter(
            "local_assistant_cache_hits_total",
            "Number of cache hits",
            labelnames=["cache_type"],
            registry=self.registry,
        )

        self.cache_misses = Counter(
            "local_assistant_cache_misses_total",
            "Number of cache misses",
            labelnames=["cache_type"],
            registry=self.registry,
        )

        # Active requests gauge
        self.active_requests = Gauge(
            "local_assistant_active_requests",
            "Number of currently active requests",
            labelnames=["model", "provider"],
            registry=self.registry,
        )

        # HTTP-level metrics (for API middleware integration)
        self.http_request_size = Histogram(
            "local_assistant_http_request_size_bytes",
            "HTTP request size in bytes",
            labelnames=["endpoint", "method"],
            buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
            registry=self.registry,
        )

        self.http_response_size = Histogram(
            "local_assistant_http_response_size_bytes",
            "HTTP response size in bytes",
            labelnames=["endpoint", "method", "status_code"],
            buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
            registry=self.registry,
        )

        logger.info("metrics_collector_initialized")

    def track_request(
        self,
        model: str,
        provider: str,
        status: str,
        capability: str,
        latency: float,
        input_tokens: int,
        output_tokens: int,
        cost: float,
    ) -> None:
        """
        Track a completed API request.

        Args:
            model: Model name
            provider: Provider name (openai, anthropic, google)
            status: Request status (success, error, timeout)
            capability: Capability used (chat, vision, reasoning, etc)
            latency: Request latency in seconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Request cost in dollars
        """
        # Request count
        self.request_count.labels(
            model=model,
            provider=provider,
            status=status,
            capability=capability,
        ).inc()

        # Latency
        self.request_latency.labels(
            model=model,
            provider=provider,
            capability=capability,
        ).observe(latency)

        # Tokens
        if input_tokens > 0:
            self.input_tokens.labels(model=model, provider=provider).inc(input_tokens)
        if output_tokens > 0:
            self.output_tokens.labels(model=model, provider=provider).inc(output_tokens)

        # Token rate
        if latency > 0 and output_tokens > 0:
            tokens_per_second = output_tokens / latency
            self.token_rate.labels(model=model).set(tokens_per_second)

        # Cost
        if cost > 0:
            self.cost_total.labels(
                model=model,
                provider=provider,
                window="per_request",
            ).inc(cost)

        logger.debug(
            "request_tracked",
            model=model,
            provider=provider,
            status=status,
            latency=f"{latency:.2f}s",
            tokens=input_tokens + output_tokens,
            cost=f"${cost:.4f}",
        )

    def track_tokens(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Track token usage.

        Args:
            model: Model name
            provider: Provider name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if input_tokens > 0:
            self.input_tokens.labels(model=model, provider=provider).inc(input_tokens)
        if output_tokens > 0:
            self.output_tokens.labels(model=model, provider=provider).inc(output_tokens)

    def track_latency(
        self,
        model: str,
        provider: str,
        capability: str,
        latency: float,
    ) -> None:
        """
        Track request latency.

        Args:
            model: Model name
            provider: Provider name
            capability: Capability used
            latency: Request latency in seconds
        """
        self.request_latency.labels(
            model=model,
            provider=provider,
            capability=capability,
        ).observe(latency)

    def track_cost(
        self,
        model: str,
        provider: str,
        cost: float,
        window: str = "per_request",
    ) -> None:
        """
        Track API cost.

        Args:
            model: Model name
            provider: Provider name
            cost: Cost in dollars
            window: Time window (per_request, per_hour, per_day)
        """
        self.cost_total.labels(
            model=model,
            provider=provider,
            window=window,
        ).inc(cost)

    def track_error(
        self,
        error_type: str,
        model: str,
        provider: str,
    ) -> None:
        """
        Track an error.

        Args:
            error_type: Type of error (timeout, rate_limit, api_error, etc)
            model: Model name
            provider: Provider name
        """
        self.error_count.labels(
            error_type=error_type,
            model=model,
            provider=provider,
        ).inc()

        logger.warning(
            "error_tracked",
            error_type=error_type,
            model=model,
            provider=provider,
        )

    def track_rate_limit(
        self,
        model: str,
        provider: str,
        limit_type: str = "requests",
    ) -> None:
        """
        Track rate limit hit.

        Args:
            model: Model name
            provider: Provider name
            limit_type: Type of limit (requests, tokens)
        """
        self.rate_limit_hits.labels(
            model=model,
            provider=provider,
            limit_type=limit_type,
        ).inc()

    def track_cache(self, cache_type: str, hit: bool) -> None:
        """
        Track cache hit/miss.

        Args:
            cache_type: Type of cache (response, embedding, etc)
            hit: Whether it was a hit (True) or miss (False)
        """
        if hit:
            self.cache_hits.labels(cache_type=cache_type).inc()
        else:
            self.cache_misses.labels(cache_type=cache_type).inc()

    def set_active_requests(self, model: str, provider: str, count: int) -> None:
        """
        Set number of active requests.

        Args:
            model: Model name
            provider: Provider name
            count: Number of active requests
        """
        self.active_requests.labels(model=model, provider=provider).set(count)

    def update_hourly_cost(self, model: str, provider: str, cost: float) -> None:
        """Update hourly cost gauge"""
        self.cost_hourly.labels(model=model, provider=provider).set(cost)

    def update_daily_cost(self, model: str, provider: str, cost: float) -> None:
        """Update daily cost gauge"""
        self.cost_daily.labels(model=model, provider=provider).set(cost)

    def track_http_request_size(
        self, endpoint: str, method: str, size_bytes: int
    ) -> None:
        """
        Track HTTP request size.

        Args:
            endpoint: Endpoint path
            method: HTTP method
            size_bytes: Request size in bytes
        """
        self.http_request_size.labels(endpoint=endpoint, method=method).observe(
            size_bytes
        )

    def track_http_response_size(
        self, endpoint: str, method: str, status_code: str, size_bytes: int
    ) -> None:
        """
        Track HTTP response size.

        Args:
            endpoint: Endpoint path
            method: HTTP method
            status_code: HTTP status code
            size_bytes: Response size in bytes
        """
        self.http_response_size.labels(
            endpoint=endpoint, method=method, status_code=status_code
        ).observe(size_bytes)

    def export_metrics(self) -> bytes:
        """
        Export metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        return generate_latest(self.registry)

    def get_content_type(self) -> str:
        """Get content type for metrics endpoint"""
        return CONTENT_TYPE_LATEST


# Global instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector(
    registry: Optional[CollectorRegistry] = None,
) -> MetricsCollector:
    """Get or create global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector(registry)
    return _metrics_collector

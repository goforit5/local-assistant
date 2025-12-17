"""
Life Graph Metrics Extension
Prometheus metrics specific to Life Graph document intelligence pipeline
"""

from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
import structlog

logger = structlog.get_logger(__name__)


class LifeGraphMetrics:
    """
    Life Graph specific Prometheus metrics.

    Tracks:
    - Document processing (uploads, types, deduplication)
    - Vendor resolution (matches, creates, confidence)
    - Commitment creation (priority distribution, domains)
    - Extraction performance (latency, costs, models)
    - Entity relationships (links created)
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize Life Graph metrics.

        Args:
            registry: Prometheus registry (creates new if None)
        """
        self.registry = registry or CollectorRegistry()

        # Document metrics
        self.documents_processed_total = Counter(
            "lifegraph_documents_processed_total",
            "Total documents processed",
            labelnames=["extraction_type", "status"],
            registry=self.registry,
        )

        self.documents_deduplicated_total = Counter(
            "lifegraph_documents_deduplicated_total",
            "Total documents deduplicated (SHA-256 match)",
            labelnames=["extraction_type"],
            registry=self.registry,
        )

        self.extraction_duration_seconds = Histogram(
            "lifegraph_extraction_duration_seconds",
            "Document extraction latency in seconds",
            labelnames=["extraction_type", "model"],
            buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0],
            registry=self.registry,
        )

        self.extraction_cost_dollars = Counter(
            "lifegraph_extraction_cost_dollars_total",
            "Total extraction costs in dollars",
            labelnames=["model", "extraction_type"],
            registry=self.registry,
        )

        # Vendor resolution metrics
        self.vendor_resolutions_total = Counter(
            "lifegraph_vendor_resolutions_total",
            "Total vendor resolution attempts",
            labelnames=["matched", "confidence_tier"],
            registry=self.registry,
        )

        self.vendor_deduplication_rate = Gauge(
            "lifegraph_vendor_deduplication_rate",
            "Percentage of vendors matched vs created (0-100)",
            registry=self.registry,
        )

        self.vendor_match_confidence = Histogram(
            "lifegraph_vendor_match_confidence",
            "Vendor match confidence distribution",
            buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],
            registry=self.registry,
        )

        # Commitment metrics
        self.commitments_created_total = Counter(
            "lifegraph_commitments_created_total",
            "Total commitments created",
            labelnames=["domain", "commitment_type"],
            registry=self.registry,
        )

        self.commitments_fulfilled_total = Counter(
            "lifegraph_commitments_fulfilled_total",
            "Total commitments fulfilled",
            labelnames=["domain"],
            registry=self.registry,
        )

        self.active_commitments_count = Gauge(
            "lifegraph_active_commitments_count",
            "Number of active commitments",
            labelnames=["domain", "priority_tier"],
            registry=self.registry,
        )

        self.commitment_priority_distribution = Histogram(
            "lifegraph_commitment_priority_distribution",
            "Commitment priority score distribution (0-100)",
            buckets=[0, 10, 25, 50, 60, 70, 75, 80, 85, 90, 95, 100],
            registry=self.registry,
        )

        self.commitment_priority_calculation_seconds = Histogram(
            "lifegraph_commitment_priority_calculation_seconds",
            "Priority calculation duration",
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
            registry=self.registry,
        )

        # Entity relationship metrics
        self.document_links_created_total = Counter(
            "lifegraph_document_links_created_total",
            "Total document links created",
            labelnames=["entity_type"],
            registry=self.registry,
        )

        # Pipeline metrics
        self.pipeline_duration_seconds = Histogram(
            "lifegraph_pipeline_duration_seconds",
            "Full pipeline end-to-end duration",
            labelnames=["extraction_type"],
            buckets=[1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
            registry=self.registry,
        )

        self.pipeline_errors_total = Counter(
            "lifegraph_pipeline_errors_total",
            "Total pipeline errors",
            labelnames=["stage", "error_type"],
            registry=self.registry,
        )

        logger.info("lifegraph_metrics_initialized")

    def track_document_processed(
        self,
        extraction_type: str,
        status: str,
        deduplicated: bool = False,
    ) -> None:
        """
        Track a processed document.

        Args:
            extraction_type: Type (invoice, receipt, contract, etc)
            status: Processing status (success, error)
            deduplicated: Whether document was deduplicated
        """
        self.documents_processed_total.labels(
            extraction_type=extraction_type,
            status=status,
        ).inc()

        if deduplicated:
            self.documents_deduplicated_total.labels(
                extraction_type=extraction_type,
            ).inc()

    def track_extraction(
        self,
        extraction_type: str,
        model: str,
        duration: float,
        cost: float,
    ) -> None:
        """
        Track document extraction.

        Args:
            extraction_type: Type of extraction
            model: Model used (gpt-4o, claude-3-5-sonnet, etc)
            duration: Extraction duration in seconds
            cost: Extraction cost in dollars
        """
        self.extraction_duration_seconds.labels(
            extraction_type=extraction_type,
            model=model,
        ).observe(duration)

        self.extraction_cost_dollars.labels(
            model=model,
            extraction_type=extraction_type,
        ).inc(cost)

    def track_vendor_resolution(
        self,
        matched: bool,
        confidence: float,
    ) -> None:
        """
        Track vendor resolution.

        Args:
            matched: Whether vendor was matched (True) or created (False)
            confidence: Match confidence score (0.0-1.0)
        """
        # Determine confidence tier
        if confidence >= 0.9:
            tier = "high"
        elif confidence >= 0.75:
            tier = "medium"
        else:
            tier = "low"

        self.vendor_resolutions_total.labels(
            matched=str(matched).lower(),
            confidence_tier=tier,
        ).inc()

        self.vendor_match_confidence.observe(confidence)

    def update_vendor_deduplication_rate(self, rate: float) -> None:
        """
        Update vendor deduplication rate gauge.

        Args:
            rate: Deduplication rate (0-100 percentage)
        """
        self.vendor_deduplication_rate.set(rate)

    def track_commitment_created(
        self,
        domain: str,
        commitment_type: str,
        priority: int,
    ) -> None:
        """
        Track commitment creation.

        Args:
            domain: Commitment domain (finance, legal, health, etc)
            commitment_type: Type (obligation, goal, routine, etc)
            priority: Priority score (0-100)
        """
        self.commitments_created_total.labels(
            domain=domain,
            commitment_type=commitment_type,
        ).inc()

        self.commitment_priority_distribution.observe(priority)

    def track_commitment_fulfilled(self, domain: str) -> None:
        """
        Track commitment fulfillment.

        Args:
            domain: Commitment domain
        """
        self.commitments_fulfilled_total.labels(domain=domain).inc()

    def update_active_commitments(
        self,
        domain: str,
        priority_tier: str,
        count: int,
    ) -> None:
        """
        Update active commitments count.

        Args:
            domain: Commitment domain
            priority_tier: Priority tier (high: 75+, medium: 50-74, low: <50)
            count: Number of active commitments
        """
        self.active_commitments_count.labels(
            domain=domain,
            priority_tier=priority_tier,
        ).set(count)

    def track_priority_calculation(self, duration: float) -> None:
        """
        Track priority calculation performance.

        Args:
            duration: Calculation duration in seconds
        """
        self.commitment_priority_calculation_seconds.observe(duration)

    def track_document_link(self, entity_type: str) -> None:
        """
        Track document link creation.

        Args:
            entity_type: Type of entity linked (signal, party, commitment, etc)
        """
        self.document_links_created_total.labels(entity_type=entity_type).inc()

    def track_pipeline(
        self,
        extraction_type: str,
        duration: float,
    ) -> None:
        """
        Track full pipeline execution.

        Args:
            extraction_type: Type of extraction
            duration: Total pipeline duration in seconds
        """
        self.pipeline_duration_seconds.labels(
            extraction_type=extraction_type,
        ).observe(duration)

    def track_pipeline_error(
        self,
        stage: str,
        error_type: str,
    ) -> None:
        """
        Track pipeline error.

        Args:
            stage: Pipeline stage (storage, extraction, resolution, etc)
            error_type: Type of error (timeout, api_error, validation_error, etc)
        """
        self.pipeline_errors_total.labels(
            stage=stage,
            error_type=error_type,
        ).inc()


# Global instance
_lifegraph_metrics: Optional[LifeGraphMetrics] = None


def get_lifegraph_metrics(
    registry: Optional[CollectorRegistry] = None,
) -> LifeGraphMetrics:
    """Get or create global Life Graph metrics instance"""
    global _lifegraph_metrics
    if _lifegraph_metrics is None:
        _lifegraph_metrics = LifeGraphMetrics(registry)
    return _lifegraph_metrics

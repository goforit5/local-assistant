"""
Life Graph Logging Helper
Structured logging events for Life Graph document intelligence pipeline
"""

from typing import Optional, Dict, Any
from uuid import UUID
import structlog

logger = structlog.get_logger(__name__)


class LifeGraphLogger:
    """
    Helper class for Life Graph structured logging.

    Provides convenience methods for logging Life Graph specific events
    with consistent structure and fields.
    """

    @staticmethod
    def document_uploaded(
        document_id: UUID,
        filename: str,
        sha256: str,
        size_bytes: int,
        extraction_type: str,
        deduplicated: bool,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log document upload event.

        Args:
            document_id: Document UUID
            filename: Original filename
            sha256: SHA-256 hash
            size_bytes: File size in bytes
            extraction_type: Type of extraction
            deduplicated: Whether file was deduplicated
            trace_id: Optional trace ID
        """
        logger.info(
            "document_uploaded",
            document_id=str(document_id),
            filename=filename,
            sha256=sha256,
            size_bytes=size_bytes,
            size_mb=round(size_bytes / 1_000_000, 2),
            extraction_type=extraction_type,
            deduplicated=deduplicated,
            trace_id=trace_id,
        )

    @staticmethod
    def vendor_resolved(
        vendor_id: UUID,
        vendor_name: str,
        matched: bool,
        confidence: float,
        match_method: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log vendor resolution event.

        Args:
            vendor_id: Vendor UUID
            vendor_name: Vendor name
            matched: Whether vendor was matched existing (True) or created (False)
            confidence: Match confidence (0.0-1.0)
            match_method: Method used (exact_tax_id, fuzzy_name, etc)
            trace_id: Optional trace ID
        """
        logger.info(
            "vendor_resolved",
            vendor_id=str(vendor_id),
            vendor_name=vendor_name,
            matched=matched,
            confidence=round(confidence, 3),
            confidence_percent=f"{confidence * 100:.1f}%",
            match_method=match_method,
            trace_id=trace_id,
        )

    @staticmethod
    def commitment_created(
        commitment_id: UUID,
        title: str,
        priority: int,
        priority_reason: str,
        domain: str,
        commitment_type: str,
        due_date: Optional[str] = None,
        amount: Optional[float] = None,
        vendor_id: Optional[UUID] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log commitment creation event.

        Args:
            commitment_id: Commitment UUID
            title: Commitment title
            priority: Priority score (0-100)
            priority_reason: Explainable reason for priority
            domain: Domain (finance, legal, health, etc)
            commitment_type: Type (obligation, goal, routine, etc)
            due_date: Optional due date
            amount: Optional amount in dollars
            vendor_id: Optional vendor UUID
            trace_id: Optional trace ID
        """
        log_data: Dict[str, Any] = {
            "commitment_id": str(commitment_id),
            "title": title,
            "priority": priority,
            "priority_tier": (
                "high" if priority >= 75 else "medium" if priority >= 50 else "low"
            ),
            "priority_reason": priority_reason,
            "domain": domain,
            "commitment_type": commitment_type,
            "trace_id": trace_id,
        }

        if due_date:
            log_data["due_date"] = due_date
        if amount is not None:
            log_data["amount"] = round(amount, 2)
            log_data["amount_formatted"] = f"${amount:,.2f}"
        if vendor_id:
            log_data["vendor_id"] = str(vendor_id)

        logger.info("commitment_created", **log_data)

    @staticmethod
    def entity_linked(
        document_id: UUID,
        entity_type: str,
        entity_id: UUID,
        link_type: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log entity linkage event.

        Args:
            document_id: Document UUID
            entity_type: Type of entity (signal, party, commitment, etc)
            entity_id: Entity UUID
            link_type: Link type (source, extracted_from, etc)
            trace_id: Optional trace ID
        """
        logger.info(
            "entity_linked",
            document_id=str(document_id),
            entity_type=entity_type,
            entity_id=str(entity_id),
            link_type=link_type,
            trace_id=trace_id,
        )

    @staticmethod
    def priority_calculated(
        commitment_id: UUID,
        priority: int,
        factors: Dict[str, Any],
        duration_ms: Optional[float] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log priority calculation event.

        Args:
            commitment_id: Commitment UUID
            priority: Calculated priority score (0-100)
            factors: Priority factors breakdown
            duration_ms: Calculation duration in milliseconds
            trace_id: Optional trace ID
        """
        logger.info(
            "priority_calculated",
            commitment_id=str(commitment_id),
            priority=priority,
            factors=factors,
            duration_ms=round(duration_ms, 2) if duration_ms else None,
            trace_id=trace_id,
        )

    @staticmethod
    def extraction_completed(
        document_id: UUID,
        extraction_type: str,
        model: str,
        cost: float,
        duration_seconds: float,
        pages: Optional[int] = None,
        success: bool = True,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log extraction completion event.

        Args:
            document_id: Document UUID
            extraction_type: Type of extraction
            model: Model used
            cost: Extraction cost in dollars
            duration_seconds: Extraction duration
            pages: Number of pages processed
            success: Whether extraction succeeded
            trace_id: Optional trace ID
        """
        logger.info(
            "extraction_completed",
            document_id=str(document_id),
            extraction_type=extraction_type,
            model=model,
            cost=round(cost, 6),
            cost_formatted=f"${cost:.4f}",
            duration_seconds=round(duration_seconds, 2),
            pages=pages,
            success=success,
            trace_id=trace_id,
        )

    @staticmethod
    def pipeline_started(
        document_id: Optional[UUID] = None,
        extraction_type: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log pipeline start event.

        Args:
            document_id: Document UUID (if known)
            extraction_type: Type of extraction
            trace_id: Trace ID for following the pipeline
        """
        logger.info(
            "pipeline_started",
            document_id=str(document_id) if document_id else None,
            extraction_type=extraction_type,
            trace_id=trace_id,
        )

    @staticmethod
    def pipeline_completed(
        document_id: UUID,
        extraction_type: str,
        duration_seconds: float,
        entities_created: Dict[str, int],
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log pipeline completion event.

        Args:
            document_id: Document UUID
            extraction_type: Type of extraction
            duration_seconds: Total pipeline duration
            entities_created: Count of entities created (vendors, commitments, etc)
            trace_id: Optional trace ID
        """
        logger.info(
            "pipeline_completed",
            document_id=str(document_id),
            extraction_type=extraction_type,
            duration_seconds=round(duration_seconds, 2),
            entities_created=entities_created,
            trace_id=trace_id,
        )

    @staticmethod
    def pipeline_error(
        stage: str,
        error_type: str,
        error_message: str,
        document_id: Optional[UUID] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log pipeline error event.

        Args:
            stage: Pipeline stage where error occurred
            error_type: Type of error
            error_message: Error message
            document_id: Optional document UUID
            trace_id: Optional trace ID
        """
        logger.error(
            "pipeline_error",
            stage=stage,
            error_type=error_type,
            error_message=error_message,
            document_id=str(document_id) if document_id else None,
            trace_id=trace_id,
        )

    @staticmethod
    def interaction_logged(
        interaction_id: UUID,
        interaction_type: str,
        entity_type: str,
        entity_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """
        Log interaction logging event (meta!).

        Args:
            interaction_id: Interaction UUID
            interaction_type: Type of interaction
            entity_type: Entity type
            entity_id: Entity UUID
            metadata: Optional metadata
            trace_id: Optional trace ID
        """
        logger.debug(
            "interaction_logged",
            interaction_id=str(interaction_id),
            interaction_type=interaction_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            metadata=metadata,
            trace_id=trace_id,
        )


# Convenience singleton
lifegraph_log = LifeGraphLogger()

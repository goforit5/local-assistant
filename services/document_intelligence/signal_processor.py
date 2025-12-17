"""
Signal processor for handling document upload signals.

Creates Signal records in the database with idempotency checks to prevent
duplicate processing of the same document.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from memory.models import Signal
from services.document_intelligence.classifiers import DocumentClassifier, DocumentType


class SignalProcessor:
    """Processes document upload signals with idempotency.

    Signals represent raw inputs (uploaded PDFs, emails, API calls) that
    need to be processed and attached to entities. The signal processor:
    1. Creates Signal records in the database
    2. Checks for duplicates using dedupe_key (idempotency)
    3. Classifies documents to determine processing strategy
    4. Tracks signal lifecycle (new → processing → attached → complete)

    Example:
        processor = SignalProcessor()
        signal = await processor.create_signal(
            db=db_session,
            source="vision_upload",
            payload={"filename": "invoice.pdf", "size": 1024000},
            dedupe_key=file_sha256
        )
        print(f"Signal ID: {signal.id}, Status: {signal.status}")
    """

    def __init__(self):
        """Initialize signal processor."""
        self.classifier = DocumentClassifier()

    async def create_signal(
        self,
        db: AsyncSession,
        source: str,
        payload: Dict[str, Any],
        dedupe_key: str
    ) -> Signal:
        """Create a signal with idempotency check.

        If a signal with the same dedupe_key already exists, returns the
        existing signal instead of creating a new one.

        Args:
            db: Database session
            source: Signal source (e.g., "vision_upload", "email_inbox")
            payload: Signal payload (e.g., {"filename": "invoice.pdf"})
            dedupe_key: Unique key for idempotency (typically SHA-256 hash)

        Returns:
            Signal record (either newly created or existing)

        Example:
            signal = await processor.create_signal(
                db=db_session,
                source="vision_upload",
                payload={"filename": "invoice.pdf"},
                dedupe_key="a1b2c3d4..."
            )
        """
        # Check if signal already exists (idempotency)
        result = await db.execute(
            select(Signal).where(Signal.dedupe_key == dedupe_key)
        )
        existing_signal = result.scalar_one_or_none()

        if existing_signal:
            return existing_signal

        # Create new signal
        signal = Signal(
            source=source,
            payload=payload,
            dedupe_key=dedupe_key,
            status="new",
            created_at=datetime.utcnow()
        )

        db.add(signal)
        await db.flush()
        await db.refresh(signal)

        return signal

    async def update_signal_status(
        self,
        db: AsyncSession,
        signal_id: str,
        status: str,
        processed_at: Optional[datetime] = None
    ) -> Signal:
        """Update signal status.

        Signal lifecycle:
            new → processing → attached → error

        Args:
            db: Database session
            signal_id: Signal ID to update
            status: New status (e.g., "processing", "attached", "error")
            processed_at: Optional timestamp when signal was processed

        Returns:
            Updated Signal record

        Example:
            await processor.update_signal_status(
                db=db_session,
                signal_id=signal.id,
                status="processing",
                processed_at=datetime.utcnow()
            )
        """
        result = await db.execute(
            select(Signal).where(Signal.id == signal_id)
        )
        signal = result.scalar_one_or_none()

        if not signal:
            raise ValueError(f"Signal not found: {signal_id}")

        signal.status = status

        # Set processed_at if provided
        if processed_at:
            signal.processed_at = processed_at

        await db.flush()
        await db.refresh(signal)

        return signal

    def classify_document(
        self,
        filename: str,
        mime_type: Optional[str] = None,
        content_preview: Optional[str] = None
    ) -> tuple[DocumentType, float]:
        """Classify a document using the document classifier.

        Args:
            filename: Name of the file
            mime_type: MIME type (e.g., "application/pdf")
            content_preview: First few lines of text content (optional)

        Returns:
            Tuple of (DocumentType, confidence_score)

        Example:
            doc_type, confidence = processor.classify_document(
                filename="Invoice_240470.pdf",
                mime_type="application/pdf"
            )
        """
        return self.classifier.classify(filename, mime_type, content_preview)

    def get_extraction_type(self, doc_type: DocumentType) -> str:
        """Get the extraction type for a document type.

        Args:
            doc_type: Classified document type

        Returns:
            Extraction type string for Vision API

        Example:
            extraction_type = processor.get_extraction_type(DocumentType.INVOICE)
            # Returns: "invoice"
        """
        return self.classifier.get_suggested_extraction_type(doc_type)

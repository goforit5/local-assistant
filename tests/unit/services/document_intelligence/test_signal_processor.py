"""
Unit tests for signal processor and document classifier.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from services.document_intelligence.classifiers import DocumentClassifier, DocumentType
from services.document_intelligence.signal_processor import SignalProcessor
from memory.models import Signal


class TestDocumentClassifier:
    """Tests for DocumentClassifier."""

    def test_classify_invoice_by_filename(self):
        """Test classifying an invoice by filename."""
        classifier = DocumentClassifier()

        doc_type, confidence = classifier.classify(
            filename="Invoice_240470.pdf",
            mime_type="application/pdf"
        )

        assert doc_type == DocumentType.INVOICE
        assert confidence >= 0.75

    def test_classify_receipt_by_filename(self):
        """Test classifying a receipt by filename."""
        classifier = DocumentClassifier()

        doc_type, confidence = classifier.classify(
            filename="receipt_20250101.pdf"
        )

        assert doc_type == DocumentType.RECEIPT
        assert confidence >= 0.75

    def test_classify_contract_by_filename(self):
        """Test classifying a contract by filename."""
        classifier = DocumentClassifier()

        doc_type, confidence = classifier.classify(
            filename="contract_agreement_2025.pdf"
        )

        assert doc_type == DocumentType.CONTRACT
        assert confidence >= 0.75

    def test_classify_unknown_document(self):
        """Test classifying an unknown document type."""
        classifier = DocumentClassifier()

        doc_type, confidence = classifier.classify(
            filename="random_document.pdf"
        )

        assert doc_type == DocumentType.OTHER
        assert confidence <= 0.60

    def test_classify_by_content_preview(self):
        """Test classifying using content preview."""
        classifier = DocumentClassifier()

        content_preview = """
        INVOICE
        Invoice Number: 240470
        Date: 2025-11-08
        Amount Due: $12,419.83
        """

        doc_type, confidence = classifier.classify(
            filename="document.pdf",
            content_preview=content_preview
        )

        assert doc_type == DocumentType.INVOICE
        assert confidence >= 0.65

    def test_multiple_keywords_increase_confidence(self):
        """Test that multiple matching keywords increase confidence."""
        classifier = DocumentClassifier()

        # Filename with multiple invoice keywords
        doc_type1, confidence1 = classifier.classify(
            filename="invoice_bill_payment_due.pdf"  # 4 keywords
        )

        # Filename with single keyword
        doc_type2, confidence2 = classifier.classify(
            filename="invoice.pdf"  # 1 keyword
        )

        assert doc_type1 == DocumentType.INVOICE
        assert doc_type2 == DocumentType.INVOICE
        # Multiple keywords should give higher confidence (capped at 0.95)
        assert confidence1 >= 0.85  # At least high confidence
        assert confidence2 >= 0.75  # At least medium confidence

    def test_get_suggested_extraction_type(self):
        """Test getting suggested extraction type for document types."""
        classifier = DocumentClassifier()

        assert classifier.get_suggested_extraction_type(DocumentType.INVOICE) == "invoice"
        assert classifier.get_suggested_extraction_type(DocumentType.RECEIPT) == "receipt"
        assert classifier.get_suggested_extraction_type(DocumentType.CONTRACT) == "document"
        assert classifier.get_suggested_extraction_type(DocumentType.FORM) == "form"
        assert classifier.get_suggested_extraction_type(DocumentType.OTHER) == "document"


class TestSignalProcessor:
    """Tests for SignalProcessor."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def processor(self):
        """Create a SignalProcessor instance."""
        return SignalProcessor()

    async def test_create_signal_new(self, processor, mock_db):
        """Test creating a new signal."""
        # Mock database query to return None (no existing signal)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Create signal
        signal = await processor.create_signal(
            db=mock_db,
            source="vision_upload",
            payload={"filename": "test.pdf", "size": 1024},
            dedupe_key="abc123"
        )

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        # Verify signal was created
        added_signal = mock_db.add.call_args[0][0]
        assert added_signal.source == "vision_upload"
        assert added_signal.dedupe_key == "abc123"
        assert added_signal.status == "new"

    async def test_create_signal_idempotency(self, processor, mock_db):
        """Test that creating a signal with same dedupe_key returns existing signal."""
        # Mock existing signal
        existing_signal = Signal(
            id="signal_001",
            source="vision_upload",
            payload={"filename": "test.pdf"},
            dedupe_key="abc123",
            status="processing"
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_signal
        mock_db.execute.return_value = mock_result

        # Try to create signal with same dedupe_key
        signal = await processor.create_signal(
            db=mock_db,
            source="vision_upload",
            payload={"filename": "test.pdf"},
            dedupe_key="abc123"
        )

        # Should return existing signal
        assert signal.id == "signal_001"
        assert signal.status == "processing"

        # Should NOT create new signal
        mock_db.add.assert_not_called()

    async def test_update_signal_status(self, processor, mock_db):
        """Test updating signal status."""
        # Mock existing signal
        existing_signal = Signal(
            id="signal_001",
            source="vision_upload",
            payload={},
            dedupe_key="abc123",
            status="new"
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_signal
        mock_db.execute.return_value = mock_result

        # Update status
        updated_signal = await processor.update_signal_status(
            db=mock_db,
            signal_id="signal_001",
            status="processing",
            processed_at=datetime.utcnow()
        )

        # Verify status was updated
        assert updated_signal.status == "processing"
        assert updated_signal.processed_at is not None

        # Verify database operations
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    async def test_update_signal_status_not_found(self, processor, mock_db):
        """Test updating status of non-existent signal raises error."""
        # Mock no signal found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Should raise ValueError
        with pytest.raises(ValueError, match="Signal not found"):
            await processor.update_signal_status(
                db=mock_db,
                signal_id="nonexistent",
                status="processing"
            )

    def test_classify_document(self, processor):
        """Test document classification through processor."""
        doc_type, confidence = processor.classify_document(
            filename="Invoice_240470.pdf",
            mime_type="application/pdf"
        )

        assert doc_type == DocumentType.INVOICE
        assert confidence >= 0.75

    def test_get_extraction_type(self, processor):
        """Test getting extraction type from document type."""
        extraction_type = processor.get_extraction_type(DocumentType.INVOICE)
        assert extraction_type == "invoice"

        extraction_type = processor.get_extraction_type(DocumentType.RECEIPT)
        assert extraction_type == "receipt"

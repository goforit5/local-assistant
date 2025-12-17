"""
Unit tests for DocumentProcessingPipeline.

Tests the complete E2E pipeline with mocked dependencies.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, date
from decimal import Decimal
import uuid

from services.document_intelligence.pipeline import (
    DocumentProcessingPipeline,
    PipelineResult
)
from services.document_intelligence.storage import ContentAddressableStorage
from services.document_intelligence.signal_processor import SignalProcessor
from services.document_intelligence.entity_resolver import EntityResolver
from services.document_intelligence.commitment_manager import CommitmentManager
from services.document_intelligence.interaction_logger import InteractionLogger
from services.document_intelligence.backends.base import StorageResult
from services.vision.processor import VisionProcessor, VisionResult
from services.document_intelligence.classifiers import DocumentType
from services.document_intelligence.entity_resolver import ResolutionResult
from memory.models import Signal, Document, Party, Role, Commitment, Interaction


@pytest.fixture
def mock_storage():
    """Mock content-addressable storage."""
    storage = Mock(spec=ContentAddressableStorage)
    storage.store = AsyncMock(return_value=StorageResult(
        sha256="a" * 64,
        storage_path="/data/documents/aaa.pdf",
        file_size=1024,
        mime_type="application/pdf",
        deduplicated=False,
        created_at=datetime.utcnow(),
        original_filename="test.pdf"
    ))
    return storage


@pytest.fixture
def mock_signal_processor():
    """Mock signal processor."""
    processor = Mock(spec=SignalProcessor)

    # Create mock signal
    signal = Signal(
        id=uuid.uuid4(),
        source="vision_upload",
        dedupe_key="a" * 64,
        payload={"filename": "test.pdf"},
        status="new",
        created_at=datetime.utcnow()
    )

    processor.create_signal = AsyncMock(return_value=signal)
    processor.update_signal_status = AsyncMock(return_value=signal)
    processor.classify_document = Mock(return_value=(DocumentType.INVOICE, 0.95))
    processor.get_extraction_type = Mock(return_value="invoice")

    return processor


@pytest.fixture
def mock_vision_processor():
    """Mock vision processor."""
    processor = Mock(spec=VisionProcessor)
    processor.analyze_document = AsyncMock(return_value=VisionResult(
        content="Invoice #12345\nVendor: Acme Corp\nTotal: $1,234.56\nDue Date: 2025-01-15",
        pages_processed=1,
        cost=0.0234,
        provider="openai",
        model="gpt-4o",
        metadata={"usage": {"input_tokens": 100, "output_tokens": 50}},
        ocr_fallback_used=False
    ))
    return processor


@pytest.fixture
def mock_entity_resolver():
    """Mock entity resolver."""
    resolver = Mock(spec=EntityResolver)

    # Create mock party
    party = Party(
        id=uuid.uuid4(),
        kind="org",
        name="Acme Corp",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    # Create mock role
    role = Role(
        id=uuid.uuid4(),
        party_id=party.id,
        role_name="vendor",
        created_at=datetime.utcnow()
    )

    # Return ResolutionResult instead of tuple
    resolution_result = ResolutionResult(
        matched=False,  # New party created
        party=party,
        confidence=0.0,
        reason="No match found - created new org: 'Acme Corp'",
        tier=5
    )

    resolver.resolve_vendor = AsyncMock(return_value=resolution_result)
    resolver.get_or_create_role = AsyncMock(return_value=(role, True))

    return resolver


@pytest.fixture
def mock_commitment_manager():
    """Mock commitment manager."""
    manager = Mock(spec=CommitmentManager)

    # Create mock commitment
    commitment = Commitment(
        id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        title="Pay Invoice #12345 - Acme Corp",
        commitment_type="obligation",
        priority=85,
        reason="Due in 7 days, $1,234.56, from Acme Corp, financial obligation",
        state="pending",
        due_date=date(2025, 1, 15),
        amount=Decimal("1234.56"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    manager.create_invoice_commitment = AsyncMock(return_value=commitment)

    return manager


@pytest.fixture
def mock_interaction_logger():
    """Mock interaction logger."""
    logger = Mock(spec=InteractionLogger)

    def create_interaction(action, entity_type=None, entity_id=None):
        return Interaction(
            id=uuid.uuid4(),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            created_at=datetime.utcnow()
        )

    logger.log_upload = AsyncMock(return_value=create_interaction("upload", "document"))
    logger.log_extraction = AsyncMock(return_value=create_interaction("extraction", "document"))
    logger.log_entity_created = AsyncMock(return_value=create_interaction("entity_created"))
    logger.log_error = AsyncMock(return_value=create_interaction("error"))

    return logger


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def pipeline(
    mock_storage,
    mock_signal_processor,
    mock_vision_processor,
    mock_entity_resolver,
    mock_commitment_manager,
    mock_interaction_logger
):
    """Create pipeline with mocked dependencies."""
    return DocumentProcessingPipeline(
        storage=mock_storage,
        signal_processor=mock_signal_processor,
        vision_processor=mock_vision_processor,
        entity_resolver=mock_entity_resolver,
        commitment_manager=mock_commitment_manager,
        interaction_logger=mock_interaction_logger
    )


@pytest.mark.asyncio
async def test_happy_path_full_pipeline(pipeline, mock_db_session):
    """Test complete pipeline execution with all steps."""
    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify success
    assert result.success
    assert result.error is None
    assert result.document_id is not None
    assert result.signal_id is not None
    assert result.vendor_id is not None
    assert result.commitment_id is not None
    assert len(result.interaction_ids) >= 2  # Upload + extraction + entity created

    # Verify metrics
    assert "storage" in result.metrics
    assert "extraction" in result.metrics
    assert "classification" in result.metrics
    assert "vendor_resolution" in result.metrics
    assert "commitment" in result.metrics
    assert "links" in result.metrics
    assert "pipeline" in result.metrics

    # Verify storage was called
    pipeline.storage.store.assert_called_once()

    # Verify signal was created and updated
    pipeline.signal_processor.create_signal.assert_called_once()
    assert pipeline.signal_processor.update_signal_status.call_count == 2  # processing, then attached

    # Verify vision extraction
    pipeline.vision_processor.analyze_document.assert_called_once()

    # Verify vendor resolution
    pipeline.entity_resolver.resolve_vendor.assert_called_once()
    pipeline.entity_resolver.get_or_create_role.assert_called_once()

    # Verify commitment creation
    pipeline.commitment_manager.create_invoice_commitment.assert_called_once()

    # Verify interactions logged
    pipeline.interaction_logger.log_upload.assert_called_once()
    pipeline.interaction_logger.log_extraction.assert_called_once()


@pytest.mark.asyncio
async def test_idempotency_skip_already_processed(pipeline, mock_db_session, mock_signal_processor):
    """Test that already-processed documents are skipped."""
    # Mock signal as already processed
    processed_signal = Signal(
        id=uuid.uuid4(),
        source="vision_upload",
        dedupe_key="a" * 64,
        payload={"filename": "test.pdf"},
        status="attached",  # Already processed
        processed_at=datetime.utcnow(),
        created_at=datetime.utcnow()
    )
    mock_signal_processor.create_signal = AsyncMock(return_value=processed_signal)

    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    result = await pipeline.process_document_upload(
        db=mock_db_session,
        file_bytes=file_bytes,
        filename=filename,
        mime_type=mime_type
    )

    # Verify idempotent skip
    assert result.success
    assert result.signal_id == processed_signal.id
    assert result.metrics.get("idempotent_skip") is True

    # Verify vision processing was NOT called
    pipeline.vision_processor.analyze_document.assert_not_called()


@pytest.mark.asyncio
async def test_error_handling_vision_api_failure(pipeline, mock_db_session, mock_vision_processor):
    """Test error handling when Vision API fails."""
    # Mock vision API failure
    mock_vision_processor.analyze_document = AsyncMock(
        side_effect=Exception("Vision API timeout")
    )

    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify error was captured
    assert not result.success
    assert result.error is not None
    assert "Vision API timeout" in result.error

    # Verify error was logged
    pipeline.interaction_logger.log_error.assert_called_once()


@pytest.mark.asyncio
async def test_no_vendor_extracted(pipeline, mock_db_session, mock_vision_processor):
    """Test pipeline when no vendor is extracted from document."""
    # Mock vision result with no vendor info
    mock_vision_processor.analyze_document = AsyncMock(return_value=VisionResult(
        content="Some generic document content",
        pages_processed=1,
        cost=0.01,
        provider="openai",
        model="gpt-4o",
        metadata={},
        ocr_fallback_used=False
    ))

    file_bytes = b"fake pdf content"
    filename = "document.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify success even without vendor
    assert result.success
    assert result.vendor_id is None
    assert result.commitment_id is None  # No commitment without vendor

    # Verify vendor resolution was NOT called
    pipeline.entity_resolver.resolve_vendor.assert_not_called()


@pytest.mark.asyncio
async def test_document_links_created(pipeline, mock_db_session):
    """Test that document links are created correctly."""
    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify links were created
    assert "links" in result.metrics
    assert result.metrics["links"]["count"] == 3  # signal, vendor, commitment

    # Verify DocumentLink objects were added to session
    add_calls = [call[0][0] for call in mock_db_session.add.call_args_list]
    from memory.models import DocumentLink
    doc_links = [obj for obj in add_calls if isinstance(obj, DocumentLink)]
    assert len(doc_links) == 3


@pytest.mark.asyncio
async def test_signal_lifecycle_management(pipeline, mock_db_session, mock_signal_processor):
    """Test signal status transitions."""
    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify signal status updates
    assert mock_signal_processor.update_signal_status.call_count == 2

    # First call: new -> processing
    first_call = mock_signal_processor.update_signal_status.call_args_list[0]
    assert first_call[1]["status"] == "processing"

    # Second call: processing -> attached
    second_call = mock_signal_processor.update_signal_status.call_args_list[1]
    assert second_call[1]["status"] == "attached"
    assert second_call[1]["processed_at"] is not None


@pytest.mark.asyncio
async def test_interaction_audit_trail(pipeline, mock_db_session):
    """Test that all interactions are logged."""
    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify interactions logged
    assert len(result.interaction_ids) >= 4  # upload, extraction, vendor created, commitment created

    pipeline.interaction_logger.log_upload.assert_called_once()
    pipeline.interaction_logger.log_extraction.assert_called_once()
    # Entity created called for vendor and commitment
    assert pipeline.interaction_logger.log_entity_created.call_count >= 1


@pytest.mark.asyncio
async def test_metrics_collection(pipeline, mock_db_session):
    """Test that comprehensive metrics are collected."""
    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify all metric categories
    assert "storage" in result.metrics
    assert "extraction" in result.metrics
    assert "classification" in result.metrics
    assert "vendor_resolution" in result.metrics
    assert "commitment" in result.metrics
    assert "links" in result.metrics
    assert "pipeline" in result.metrics

    # Verify storage metrics
    assert "sha256" in result.metrics["storage"]
    assert "deduplicated" in result.metrics["storage"]

    # Verify extraction metrics
    assert "cost" in result.metrics["extraction"]
    assert "model" in result.metrics["extraction"]
    assert "duration_seconds" in result.metrics["extraction"]

    # Verify pipeline metrics
    assert "total_duration_seconds" in result.metrics["pipeline"]
    assert result.metrics["pipeline"]["success"] is True


@pytest.mark.asyncio
async def test_vision_result_parsing(pipeline, mock_db_session):
    """Test that vision results are parsed correctly."""
    file_bytes = b"fake pdf content"
    filename = "invoice.pdf"
    mime_type = "application/pdf"

    with patch('services.vision.document.DocumentHandler.load_from_bytes') as mock_doc:
        mock_doc.return_value = Mock(pages=[Mock()], total_pages=1)

        result = await pipeline.process_document_upload(
            db=mock_db_session,
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type
        )

    # Verify parsing was called (check Document was created with extraction_data)
    add_calls = [call[0][0] for call in mock_db_session.add.call_args_list]
    documents = [obj for obj in add_calls if isinstance(obj, Document)]
    assert len(documents) == 1

    doc = documents[0]
    assert doc.extraction_data is not None
    assert isinstance(doc.extraction_data, dict)

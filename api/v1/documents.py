"""Document API endpoints - Version 1."""

import logging
import os
import tempfile
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

from api.schemas.document_schemas import (
    DocumentUploadResponse,
    DocumentDetail,
    ErrorResponse,
    VendorSummary,
    CommitmentSummary,
    ExtractionSummary,
    LinksInfo,
)
from api.state import app_state
from memory.database import get_db
from memory.models import Document, DocumentLink, Party, Commitment, Signal
from services.document_intelligence import DocumentProcessingPipeline
from services.document_intelligence.storage import ContentAddressableStorage
from services.document_intelligence.signal_processor import SignalProcessor
from services.document_intelligence.entity_resolver import EntityResolver
from services.document_intelligence.commitment_manager import CommitmentManager
from services.document_intelligence.interaction_logger import InteractionLogger
from services.vision.processor import VisionProcessor
from services.vision.config import VisionConfig
from providers.openai_provider import OpenAIProvider
from providers.base import ProviderConfig

router = APIRouter()


def get_pipeline() -> DocumentProcessingPipeline:
    """Get or create document processing pipeline instance.

    This creates all necessary service dependencies and returns a configured pipeline.
    """
    # Get OpenAI provider for vision extraction
    openai_provider = app_state.get("openai")
    if not openai_provider:
        # Fail fast if provider not initialized in app_state
        raise RuntimeError(
            "OpenAI provider not initialized in app_state. "
            "Ensure providers are initialized on application startup."
        )

    # Create service instances
    storage = ContentAddressableStorage(base_path="./data/documents")
    signal_processor = SignalProcessor()
    vision_config = VisionConfig(model="gpt-4o")
    vision_processor = VisionProcessor(provider=openai_provider, config=vision_config)
    entity_resolver = EntityResolver()
    commitment_manager = CommitmentManager()
    interaction_logger = InteractionLogger()

    # Create and return pipeline
    return DocumentProcessingPipeline(
        storage=storage,
        signal_processor=signal_processor,
        vision_processor=vision_processor,
        entity_resolver=entity_resolver,
        commitment_manager=commitment_manager,
        interaction_logger=interaction_logger,
    )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file or parameters"},
        500: {"model": ErrorResponse, "description": "Processing failed"},
    },
    summary="Upload and process document",
    description="""
    Upload a document (PDF, image) for processing through the document intelligence pipeline.

    **Workflow**:
    1. Store file (content-addressable storage with SHA-256)
    2. Create signal (idempotency check)
    3. Extract via Vision API (GPT-4o)
    4. Classify document type
    5. Resolve vendor (fuzzy matching)
    6. Create commitment (if invoice)
    7. Link all entities
    8. Log interactions

    **Returns**:
    Complete entity graph including document, vendor, commitment, extraction details, and quick links.

    **Idempotency**:
    If the same file (SHA-256 hash) is uploaded twice, the second upload will return the existing result.
    """,
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload (PDF, PNG, JPG)"),
    extraction_type: str = Form(
        "invoice", description="Extraction type: invoice, receipt, contract, form"
    ),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload and process document through pipeline."""
    try:
        # Validate file type
        allowed_types = {"application/pdf", "image/png", "image/jpeg", "image/jpg"}
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Allowed: PDF, PNG, JPG",
            )

        # Read file bytes
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # Process through pipeline
        pipeline = get_pipeline()

        # Process document (uses db.flush() internally, we commit at the end)
        result = await pipeline.process_document_upload(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename or "unknown.pdf",
            mime_type=file.content_type or "application/pdf",
            user_id=None,  # Future: get from auth context
        )

        # Debug: Check document_id
        print(f"DEBUG: Pipeline result success={result.success}, document_id={result.document_id}, error={result.error}")

        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)

        # Commit transaction before building response
        await db.commit()

        # Build response
        vendor_summary = None
        if result.vendor_id:
            # Fetch vendor details
            vendor_query = select(Party).where(Party.id == result.vendor_id)
            vendor_result = await db.execute(vendor_query)
            vendor = vendor_result.scalar_one_or_none()

            if vendor:
                vendor_summary = VendorSummary(
                    id=vendor.id,
                    name=vendor.name,
                    matched=result.metrics.get("vendor_resolution", {}).get(
                        "created_new", False
                    )
                    is False,
                    confidence=result.metrics.get("vendor_resolution", {}).get(
                        "confidence"
                    ),
                    tier=result.metrics.get("vendor_resolution", {}).get("tier"),
                )

        commitment_summary = None
        if result.commitment_id:
            # Fetch commitment details
            commitment_query = select(Commitment).where(
                Commitment.id == result.commitment_id
            )
            commitment_result = await db.execute(commitment_query)
            commitment = commitment_result.scalar_one_or_none()

            if commitment:
                commitment_summary = CommitmentSummary(
                    id=commitment.id,
                    title=commitment.title,
                    priority=commitment.priority,
                    reason=commitment.reason,
                    due_date=commitment.due_date,
                    commitment_type=commitment.commitment_type,
                    state=commitment.state,
                )

        extraction_summary = ExtractionSummary(
            cost=result.metrics.get("extraction", {}).get("cost", 0.0),
            model=result.metrics.get("extraction", {}).get("model", "unknown"),
            pages_processed=result.metrics.get("extraction", {}).get(
                "pages_processed", 0
            ),
            duration_seconds=result.metrics.get("extraction", {}).get(
                "duration_seconds"
            ),
        )

        links = LinksInfo(
            timeline=f"/api/v1/interactions/timeline?entity_id={result.document_id}",
            vendor=f"/api/v1/vendors/{result.vendor_id}" if result.vendor_id else None,
            download=f"/api/v1/documents/{result.document_id}/download",
        )

        return DocumentUploadResponse(
            document_id=result.document_id,
            sha256=result.metrics.get("storage", {}).get("sha256", "unknown"),
            vendor=vendor_summary,
            commitment=commitment_summary,
            extraction=extraction_summary,
            links=links,
            metrics=result.metrics,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
    summary="Get document details",
    description="""
    Retrieve complete document details including all linked entities.

    **Returns**:
    - Document metadata (SHA-256, size, type)
    - Extraction details (cost, model, timestamp)
    - Linked vendor (if any)
    - Linked commitments (if any)
    - Signal ID
    - Extraction preview (first 1000 chars)
    """,
)
async def get_document(
    document_id: UUID, db: AsyncSession = Depends(get_db)
) -> DocumentDetail:
    """Get document by ID with all linked entities."""
    try:
        # Fetch document
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        # Fetch linked entities
        links_query = select(DocumentLink).where(DocumentLink.document_id == document_id)
        links_result = await db.execute(links_query)
        links = links_result.scalars().all()

        # Extract entity IDs by type
        vendor_id = None
        commitment_ids = []
        signal_id = None

        for link in links:
            if link.entity_type == "party" and link.link_type == "vendor":
                vendor_id = link.entity_id
            elif link.entity_type == "commitment":
                commitment_ids.append(link.entity_id)
            elif link.entity_type == "signal":
                signal_id = link.entity_id

        # Fetch vendor
        vendor_summary = None
        if vendor_id:
            vendor_query = select(Party).where(Party.id == vendor_id)
            vendor_result = await db.execute(vendor_query)
            vendor = vendor_result.scalar_one_or_none()

            if vendor:
                vendor_summary = VendorSummary(
                    id=vendor.id, name=vendor.name, matched=True
                )

        # Fetch commitments
        commitment_summaries = []
        if commitment_ids:
            commitments_query = select(Commitment).where(
                Commitment.id.in_(commitment_ids)
            )
            commitments_result = await db.execute(commitments_query)
            commitments = commitments_result.scalars().all()

            for commitment in commitments:
                commitment_summaries.append(
                    CommitmentSummary(
                        id=commitment.id,
                        title=commitment.title,
                        priority=commitment.priority,
                        reason=commitment.reason,
                        due_date=commitment.due_date,
                        commitment_type=commitment.commitment_type,
                        state=commitment.state,
                    )
                )

        # Build response
        return DocumentDetail(
            id=document.id,
            sha256=document.sha256,
            path=document.path,
            mime_type=document.mime_type,
            file_size=document.file_size,
            extraction_type=document.extraction_type,
            extraction_cost=document.extraction_cost,
            extracted_at=document.extracted_at,
            created_at=document.created_at,
            vendor=vendor_summary,
            commitments=commitment_summaries,
            signal_id=signal_id,
            extraction_preview=document.content[:1000] if document.content else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{document_id}/download",
    responses={
        404: {"description": "Document not found"},
        200: {
            "content": {"application/pdf": {}},
            "description": "Original document file",
        },
    },
    summary="Download original document",
    description="""
    Stream the original uploaded document file.

    **Returns**:
    File with appropriate Content-Type and Content-Disposition headers for download.
    """,
)
async def download_document(
    document_id: UUID, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    """Download original document file."""
    try:
        # Fetch document
        query = select(Document).where(Document.id == document_id)
        result = await db.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        # Check if file exists
        if not os.path.exists(document.path):
            raise HTTPException(
                status_code=404, detail=f"Document file not found: {document.path}"
            )

        # Extract original filename from path or use SHA-256
        filename = os.path.basename(document.path)

        # Return file response
        return FileResponse(
            path=document.path,
            media_type=document.mime_type,
            filename=filename,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

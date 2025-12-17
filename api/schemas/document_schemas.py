"""Document API schemas."""

from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


class VendorSummary(BaseModel):
    """Vendor summary embedded in document response."""

    id: UUID
    name: str
    matched: bool = Field(description="Whether vendor was matched (vs created new)")
    confidence: Optional[float] = Field(None, description="Match confidence score (0.0-1.0)")
    tier: Optional[str] = Field(None, description="Match tier (exact, fuzzy, created)")


class CommitmentSummary(BaseModel):
    """Commitment summary embedded in document response."""

    id: UUID
    title: str
    priority: int = Field(description="Priority score (0-100)")
    reason: Optional[str] = Field(None, description="Explainable priority reason")
    due_date: Optional[datetime] = None
    commitment_type: str
    state: str


class ExtractionSummary(BaseModel):
    """Extraction summary with cost and model info."""

    cost: float = Field(description="Extraction cost in USD")
    model: str = Field(description="Model used for extraction")
    pages_processed: int
    duration_seconds: Optional[float] = None


class LinksInfo(BaseModel):
    """Quick links for document navigation."""

    timeline: str = Field(description="URL to interaction timeline")
    vendor: Optional[str] = Field(None, description="URL to vendor details")
    download: str = Field(description="URL to download PDF")


class DocumentUploadResponse(BaseModel):
    """Response after successful document upload.

    Returns complete entity graph created during processing.
    """

    document_id: UUID
    sha256: str = Field(description="Content hash for deduplication")
    vendor: Optional[VendorSummary] = None
    commitment: Optional[CommitmentSummary] = None
    extraction: ExtractionSummary
    links: LinksInfo
    metrics: Dict[str, Any] = Field(description="Pipeline execution metrics")

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "550e8400-e29b-41d4-a716-446655440000",
                "sha256": "a1b2c3d4...",
                "vendor": {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "Clipboard Health",
                    "matched": True,
                    "confidence": 0.95,
                    "tier": "fuzzy"
                },
                "commitment": {
                    "id": "770e8400-e29b-41d4-a716-446655440002",
                    "title": "Pay Invoice #240470 - Clipboard Health",
                    "priority": 85,
                    "reason": "Due in 2 days, legal risk, $12,419.83",
                    "due_date": "2024-02-28T00:00:00",
                    "commitment_type": "obligation",
                    "state": "active"
                },
                "extraction": {
                    "cost": 0.0048675,
                    "model": "gpt-4o",
                    "pages_processed": 3
                },
                "links": {
                    "timeline": "/api/interactions/timeline?entity_id=550e8400-e29b-41d4-a716-446655440000",
                    "vendor": "/api/vendors/660e8400-e29b-41d4-a716-446655440001",
                    "download": "/api/documents/550e8400-e29b-41d4-a716-446655440000/download"
                },
                "metrics": {
                    "storage": {"sha256": "a1b2c3d4...", "deduplicated": False},
                    "extraction": {"cost": 0.0048675, "duration_seconds": 1.23}
                }
            }
        }


class DocumentDetail(BaseModel):
    """Detailed document information with all linked entities."""

    id: UUID
    sha256: str
    path: str
    mime_type: str
    file_size: int
    extraction_type: str
    extraction_cost: float
    extracted_at: datetime
    created_at: datetime

    # Linked entities
    vendor: Optional[VendorSummary] = None
    commitments: List[CommitmentSummary] = Field(default_factory=list)
    signal_id: Optional[UUID] = None

    # Extraction data preview
    extraction_preview: Optional[str] = Field(
        None,
        description="First 1000 chars of extraction content"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "sha256": "a1b2c3d4...",
                "path": "data/documents/a1b2c3d4.pdf",
                "mime_type": "application/pdf",
                "file_size": 524288,
                "extraction_type": "invoice",
                "extraction_cost": 0.0048675,
                "extracted_at": "2025-11-08T12:00:00",
                "created_at": "2025-11-08T12:00:00",
                "vendor": {
                    "id": "660e8400-e29b-41d4-a716-446655440001",
                    "name": "Clipboard Health",
                    "matched": True
                },
                "commitments": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "title": "Pay Invoice #240470",
                        "priority": 85,
                        "state": "active"
                    }
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(description="Error message")
    error_type: str = Field(description="Error type/category")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Document not found",
                "error_type": "NotFoundError",
                "details": {"document_id": "550e8400-e29b-41d4-a716-446655440000"}
            }
        }

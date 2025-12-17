"""Vendor API schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class VendorListItem(BaseModel):
    """Vendor list item for search results."""

    id: UUID
    name: str
    kind: str = Field(description="Party kind: person, org, group")
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime


class VendorStats(BaseModel):
    """Vendor statistics."""

    document_count: int = Field(description="Number of documents from vendor")
    commitment_count: int = Field(description="Number of commitments with vendor")
    total_amount: Optional[float] = Field(None, description="Total amount across all invoices")
    last_interaction: Optional[datetime] = Field(None, description="Last interaction timestamp")


class VendorDetail(BaseModel):
    """Detailed vendor information."""

    id: UUID
    name: str
    kind: str
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    contact_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Stats
    stats: VendorStats

    class Config:
        json_schema_extra = {
            "example": {
                "id": "660e8400-e29b-41d4-a716-446655440001",
                "name": "Clipboard Health",
                "kind": "org",
                "address": "P.O. Box 103125, Pasadena CA 91189",
                "email": "[email protected]",
                "phone": None,
                "tax_id": None,
                "contact_name": None,
                "notes": None,
                "created_at": "2025-11-08T12:00:00",
                "updated_at": "2025-11-08T12:00:00",
                "stats": {
                    "document_count": 5,
                    "commitment_count": 3,
                    "total_amount": 45678.90,
                    "last_interaction": "2025-11-08T12:00:00",
                },
            }
        }


class VendorListResponse(BaseModel):
    """Response for vendor list endpoint."""

    vendors: List[VendorListItem]
    total: int = Field(description="Total count (for pagination)")
    offset: int
    limit: int

    class Config:
        json_schema_extra = {
            "example": {
                "vendors": [
                    {
                        "id": "660e8400-e29b-41d4-a716-446655440001",
                        "name": "Clipboard Health",
                        "kind": "org",
                        "address": "P.O. Box 103125, Pasadena CA 91189",
                        "email": "[email protected]",
                        "created_at": "2025-11-08T12:00:00",
                    }
                ],
                "total": 1,
                "offset": 0,
                "limit": 50,
            }
        }


class DocumentSummary(BaseModel):
    """Document summary for vendor details."""

    id: UUID
    path: str
    extraction_type: str
    extracted_at: datetime
    extraction_cost: float


class VendorDocumentsResponse(BaseModel):
    """Response for vendor documents endpoint."""

    vendor_id: UUID
    vendor_name: str
    documents: List[DocumentSummary]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "vendor_id": "660e8400-e29b-41d4-a716-446655440001",
                "vendor_name": "Clipboard Health",
                "documents": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "path": "data/documents/a1b2c3d4.pdf",
                        "extraction_type": "invoice",
                        "extracted_at": "2025-11-08T12:00:00",
                        "extraction_cost": 0.0048675,
                    }
                ],
                "total": 1,
            }
        }

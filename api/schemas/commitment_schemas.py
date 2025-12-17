"""Commitment API schemas."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


class CommitmentListItem(BaseModel):
    """Commitment list item for filtered views."""

    id: UUID
    title: str
    commitment_type: str = Field(description="Type: obligation, goal, routine, appointment")
    state: str = Field(description="State: active, fulfilled, canceled, paused")
    priority: int = Field(description="Priority score (0-100)")
    reason: Optional[str] = Field(None, description="Explainable priority reason")
    due_date: Optional[datetime] = None
    domain: Optional[str] = Field(None, description="Domain: finance, legal, health, personal, work")
    created_at: datetime


class CommitmentDetail(BaseModel):
    """Detailed commitment information."""

    id: UUID
    title: str
    commitment_type: str
    state: str
    priority: int
    reason: Optional[str] = None
    due_date: Optional[datetime] = None
    domain: Optional[str] = None
    estimated_effort_hours: Optional[float] = None
    recurrence_rule: Optional[str] = None
    parent_commitment_id: Optional[UUID] = None
    description: Optional[str] = None
    metadata_: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    fulfilled_at: Optional[datetime] = None

    # Linked entities
    vendor_id: Optional[UUID] = None
    vendor_name: Optional[str] = None
    document_count: int = Field(default=0, description="Number of linked documents")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "title": "Pay Invoice #240470 - Clipboard Health",
                "commitment_type": "obligation",
                "state": "active",
                "priority": 85,
                "reason": "Due in 2 days, legal risk, $12,419.83",
                "due_date": "2024-02-28T00:00:00",
                "domain": "finance",
                "estimated_effort_hours": 0.5,
                "recurrence_rule": None,
                "parent_commitment_id": None,
                "description": "Pay invoice for staffing services",
                "metadata_": {"invoice_id": "240470", "amount": 12419.83},
                "created_at": "2025-11-08T12:00:00",
                "updated_at": "2025-11-08T12:00:00",
                "fulfilled_at": None,
                "vendor_id": "660e8400-e29b-41d4-a716-446655440001",
                "vendor_name": "Clipboard Health",
                "document_count": 1,
            }
        }


class CommitmentListResponse(BaseModel):
    """Response for commitment list endpoint."""

    commitments: List[CommitmentListItem]
    total: int = Field(description="Total count (for pagination)")
    offset: int
    limit: int

    class Config:
        json_schema_extra = {
            "example": {
                "commitments": [
                    {
                        "id": "770e8400-e29b-41d4-a716-446655440002",
                        "title": "Pay Invoice #240470 - Clipboard Health",
                        "commitment_type": "obligation",
                        "state": "active",
                        "priority": 85,
                        "reason": "Due in 2 days, legal risk, $12,419.83",
                        "due_date": "2024-02-28T00:00:00",
                        "domain": "finance",
                        "created_at": "2025-11-08T12:00:00",
                    }
                ],
                "total": 1,
                "offset": 0,
                "limit": 50,
            }
        }


class CommitmentUpdateRequest(BaseModel):
    """Request to update commitment fields."""

    title: Optional[str] = None
    state: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=100)
    due_date: Optional[datetime] = None
    domain: Optional[str] = None
    estimated_effort_hours: Optional[float] = Field(None, ge=0)
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "state": "fulfilled",
                "priority": 0,
            }
        }


class CommitmentFulfillResponse(BaseModel):
    """Response after fulfilling commitment."""

    id: UUID
    title: str
    state: str = Field(description="Should be 'fulfilled'")
    fulfilled_at: datetime
    message: str = Field(description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "770e8400-e29b-41d4-a716-446655440002",
                "title": "Pay Invoice #240470 - Clipboard Health",
                "state": "fulfilled",
                "fulfilled_at": "2025-11-08T14:30:00",
                "message": "Commitment marked as fulfilled",
            }
        }

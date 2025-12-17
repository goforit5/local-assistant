"""Interaction API schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class InteractionListItem(BaseModel):
    """Interaction list item for timeline view."""

    id: UUID
    interaction_type: str = Field(description="Type: upload, extraction, entity_created, error")
    entity_type: Optional[str] = Field(None, description="Entity type: document, party, commitment")
    entity_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    cost: Optional[float] = Field(None, description="Cost in USD")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    metadata_: Optional[Dict[str, Any]] = None
    created_at: datetime


class InteractionTimelineResponse(BaseModel):
    """Response for interaction timeline endpoint."""

    interactions: List[InteractionListItem]
    total: int = Field(description="Total count")
    offset: int
    limit: int

    class Config:
        json_schema_extra = {
            "example": {
                "interactions": [
                    {
                        "id": "880e8400-e29b-41d4-a716-446655440003",
                        "interaction_type": "upload",
                        "entity_type": "document",
                        "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": None,
                        "cost": None,
                        "duration": None,
                        "metadata_": {
                            "filename": "invoice.pdf",
                            "size": 524288,
                            "mime_type": "application/pdf",
                        },
                        "created_at": "2025-11-08T12:00:00",
                    },
                    {
                        "id": "990e8400-e29b-41d4-a716-446655440004",
                        "interaction_type": "extraction",
                        "entity_type": "document",
                        "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": None,
                        "cost": 0.0048675,
                        "duration": 1.23,
                        "metadata_": {
                            "model": "gpt-4o",
                            "pages_processed": 3,
                        },
                        "created_at": "2025-11-08T12:00:01",
                    },
                ],
                "total": 2,
                "offset": 0,
                "limit": 50,
            }
        }


class ExportFormat(str):
    """Supported export formats."""

    CSV = "csv"
    JSON = "json"

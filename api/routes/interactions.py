"""Interaction API endpoints."""

import csv
import io
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.schemas.interaction_schemas import (
    InteractionTimelineResponse,
    InteractionListItem,
    ExportFormat,
)
from api.schemas.document_schemas import ErrorResponse
from memory.database import get_db
from memory.models import Interaction

router = APIRouter()


@router.get(
    "/timeline",
    response_model=InteractionTimelineResponse,
    summary="Get interaction timeline",
    description="""
    Retrieve chronological timeline of interactions (audit trail).

    **Filters**:
    - entity_type: Filter by entity type (document, party, commitment, signal)
    - entity_id: Filter by specific entity UUID
    - interaction_type: Filter by type (upload, extraction, entity_created, error)
    - date_from: Start date
    - date_to: End date

    **Pagination**:
    - offset/limit supported

    **Returns**:
    Chronological list of interactions (newest first).
    """,
)
async def get_timeline(
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[UUID] = Query(None, description="Filter by entity ID"),
    interaction_type: Optional[str] = Query(None, description="Filter by interaction type"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> InteractionTimelineResponse:
    """Get interaction timeline with filters."""
    try:
        # Base query
        stmt = select(Interaction)

        # Apply filters
        if entity_type:
            stmt = stmt.where(Interaction.entity_type == entity_type)

        if entity_id:
            stmt = stmt.where(Interaction.entity_id == entity_id)

        if interaction_type:
            stmt = stmt.where(Interaction.interaction_type == interaction_type)

        if date_from:
            stmt = stmt.where(Interaction.created_at >= date_from)

        if date_to:
            stmt = stmt.where(Interaction.created_at <= date_to)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply sorting (newest first)
        stmt = stmt.order_by(Interaction.created_at.desc())

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute query
        result = await db.execute(stmt)
        interactions = result.scalars().all()

        # Build response
        interaction_items = [
            InteractionListItem(
                id=i.id,
                interaction_type=i.interaction_type,
                entity_type=i.entity_type,
                entity_id=i.entity_id,
                user_id=i.user_id,
                cost=i.cost,
                duration=i.duration,
                metadata_=i.metadata_,
                created_at=i.created_at,
            )
            for i in interactions
        ]

        return InteractionTimelineResponse(
            interactions=interaction_items,
            total=total,
            offset=offset,
            limit=limit,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/export",
    responses={
        200: {
            "content": {
                "text/csv": {},
                "application/json": {},
            },
            "description": "Exported interactions",
        },
    },
    summary="Export interactions",
    description="""
    Export interactions to CSV or JSON format.

    **Query Parameters**:
    - format: Export format (csv or json)
    - date_from: Start date
    - date_to: End date
    - interaction_type: Filter by type
    - entity_type: Filter by entity type

    **Returns**:
    File stream with appropriate Content-Type and Content-Disposition headers.

    **CSV Format**:
    Columns: id, interaction_type, entity_type, entity_id, user_id, cost, duration, created_at

    **JSON Format**:
    Array of interaction objects.
    """,
)
async def export_interactions(
    format: str = Query("csv", description="Export format: csv or json"),
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    interaction_type: Optional[str] = Query(None, description="Filter by type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export interactions to CSV or JSON."""
    try:
        # Validate format
        if format not in ["csv", "json"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format: {format}. Supported: csv, json",
            )

        # Base query
        stmt = select(Interaction)

        # Apply filters
        if date_from:
            stmt = stmt.where(Interaction.created_at >= date_from)

        if date_to:
            stmt = stmt.where(Interaction.created_at <= date_to)

        if interaction_type:
            stmt = stmt.where(Interaction.interaction_type == interaction_type)

        if entity_type:
            stmt = stmt.where(Interaction.entity_type == entity_type)

        # Order by created_at
        stmt = stmt.order_by(Interaction.created_at.desc())

        # Execute query
        result = await db.execute(stmt)
        interactions = result.scalars().all()

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"interactions_{timestamp}.{format}"

        if format == "csv":
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                "id",
                "interaction_type",
                "entity_type",
                "entity_id",
                "user_id",
                "cost",
                "duration",
                "created_at",
                "metadata",
            ])

            # Write rows
            for i in interactions:
                writer.writerow([
                    str(i.id),
                    i.interaction_type,
                    i.entity_type or "",
                    str(i.entity_id) if i.entity_id else "",
                    str(i.user_id) if i.user_id else "",
                    f"{i.cost:.6f}" if i.cost else "",
                    f"{i.duration:.2f}" if i.duration else "",
                    i.created_at.isoformat(),
                    json.dumps(i.metadata_) if i.metadata_ else "",
                ])

            # Create streaming response
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode("utf-8")),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                },
            )

        else:  # json
            # Generate JSON
            data = [
                {
                    "id": str(i.id),
                    "interaction_type": i.interaction_type,
                    "entity_type": i.entity_type,
                    "entity_id": str(i.entity_id) if i.entity_id else None,
                    "user_id": str(i.user_id) if i.user_id else None,
                    "cost": float(i.cost) if i.cost else None,
                    "duration": float(i.duration) if i.duration else None,
                    "metadata": i.metadata_,
                    "created_at": i.created_at.isoformat(),
                }
                for i in interactions
            ]

            json_str = json.dumps(data, indent=2)

            # Create streaming response
            return StreamingResponse(
                io.BytesIO(json_str.encode("utf-8")),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

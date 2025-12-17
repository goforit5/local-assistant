"""Commitment API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.schemas.commitment_schemas import (
    CommitmentListResponse,
    CommitmentDetail,
    CommitmentListItem,
    CommitmentUpdateRequest,
    CommitmentFulfillResponse,
)
from api.schemas.document_schemas import ErrorResponse
from memory.database import get_db
from memory.models import Commitment, Role, Party, DocumentLink

router = APIRouter()


@router.get(
    "",
    response_model=CommitmentListResponse,
    summary="List commitments",
    description="""
    List commitments with flexible filtering and sorting.

    **Filters**:
    - state: Filter by state (active, fulfilled, canceled, paused)
    - domain: Filter by domain (finance, legal, health, personal, work)
    - priority_min: Minimum priority score (0-100)
    - due_before: Due date before this timestamp

    **Sorting**:
    - By priority (desc) then due_date

    **Pagination**:
    - offset/limit supported

    **Returns**:
    List of commitments matching filters.
    """,
)
async def list_commitments(
    state: Optional[str] = Query(None, description="Filter by state"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    priority_min: Optional[int] = Query(None, ge=0, le=100, description="Minimum priority"),
    due_before: Optional[datetime] = Query(None, description="Due before date"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> CommitmentListResponse:
    """List commitments with filters."""
    try:
        # Base query
        stmt = select(Commitment)

        # Apply filters
        if state:
            stmt = stmt.where(Commitment.state == state)

        if domain:
            stmt = stmt.where(Commitment.domain == domain)

        if priority_min is not None:
            stmt = stmt.where(Commitment.priority >= priority_min)

        if due_before:
            stmt = stmt.where(Commitment.due_date <= due_before)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply sorting
        stmt = stmt.order_by(
            Commitment.priority.desc(),
            Commitment.due_date.nullslast(),
        )

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute query
        result = await db.execute(stmt)
        commitments = result.scalars().all()

        # Build response
        commitment_items = [
            CommitmentListItem(
                id=c.id,
                title=c.title,
                commitment_type=c.commitment_type,
                state=c.state,
                priority=c.priority,
                reason=c.reason,
                due_date=c.due_date,
                domain=c.domain,
                created_at=c.created_at,
            )
            for c in commitments
        ]

        return CommitmentListResponse(
            commitments=commitment_items,
            total=total,
            offset=offset,
            limit=limit,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{commitment_id}",
    response_model=CommitmentDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Commitment not found"},
    },
    summary="Get commitment details",
    description="""
    Get complete commitment information including linked vendor and document count.

    **Returns**:
    - Commitment details (title, priority, reason, due_date, etc.)
    - Linked vendor info (if any)
    - Document count
    """,
)
async def get_commitment(
    commitment_id: UUID, db: AsyncSession = Depends(get_db)
) -> CommitmentDetail:
    """Get commitment by ID with linked entities."""
    try:
        # Fetch commitment
        stmt = select(Commitment).where(Commitment.id == commitment_id)
        result = await db.execute(stmt)
        commitment = result.scalar_one_or_none()

        if not commitment:
            raise HTTPException(
                status_code=404, detail=f"Commitment not found: {commitment_id}"
            )

        # Fetch linked vendor (through role)
        vendor_id = None
        vendor_name = None

        if commitment.role_id:
            role_stmt = select(Role).where(Role.id == commitment.role_id)
            role_result = await db.execute(role_stmt)
            role = role_result.scalar_one_or_none()

            if role and role.party_id:
                party_stmt = select(Party).where(Party.id == role.party_id)
                party_result = await db.execute(party_stmt)
                party = party_result.scalar_one_or_none()

                if party:
                    vendor_id = party.id
                    vendor_name = party.name

        # Count linked documents
        doc_count_stmt = (
            select(func.count(DocumentLink.id))
            .where(
                DocumentLink.entity_type == "commitment",
                DocumentLink.entity_id == commitment_id,
            )
        )
        doc_count_result = await db.execute(doc_count_stmt)
        document_count = doc_count_result.scalar_one()

        # Build response
        return CommitmentDetail(
            id=commitment.id,
            title=commitment.title,
            commitment_type=commitment.commitment_type,
            state=commitment.state,
            priority=commitment.priority,
            reason=commitment.reason,
            due_date=commitment.due_date,
            domain=commitment.domain,
            estimated_effort_hours=commitment.estimated_effort_hours,
            recurrence_rule=commitment.recurrence_rule,
            parent_commitment_id=commitment.parent_commitment_id,
            description=commitment.description,
            metadata_=commitment.metadata_,
            created_at=commitment.created_at,
            updated_at=commitment.updated_at,
            fulfilled_at=commitment.fulfilled_at,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            document_count=document_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{commitment_id}/fulfill",
    response_model=CommitmentFulfillResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Commitment not found"},
    },
    summary="Mark commitment as fulfilled",
    description="""
    Mark a commitment as fulfilled.

    **Actions**:
    - Sets state to 'fulfilled'
    - Sets fulfilled_at timestamp
    - Reduces priority to 0

    **Returns**:
    Updated commitment with fulfilled status.
    """,
)
async def fulfill_commitment(
    commitment_id: UUID, db: AsyncSession = Depends(get_db)
) -> CommitmentFulfillResponse:
    """Mark commitment as fulfilled."""
    try:
        # Fetch commitment
        stmt = select(Commitment).where(Commitment.id == commitment_id)
        result = await db.execute(stmt)
        commitment = result.scalar_one_or_none()

        if not commitment:
            raise HTTPException(
                status_code=404, detail=f"Commitment not found: {commitment_id}"
            )

        # Update commitment
        commitment.state = "fulfilled"
        commitment.fulfilled_at = datetime.utcnow()
        commitment.priority = 0  # Reduce priority after fulfillment
        commitment.updated_at = datetime.utcnow()

        # Commit changes
        await db.commit()
        await db.refresh(commitment)

        return CommitmentFulfillResponse(
            id=commitment.id,
            title=commitment.title,
            state=commitment.state,
            fulfilled_at=commitment.fulfilled_at,
            message="Commitment marked as fulfilled",
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/{commitment_id}",
    response_model=CommitmentDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Commitment not found"},
        400: {"model": ErrorResponse, "description": "Invalid update data"},
    },
    summary="Update commitment",
    description="""
    Update commitment fields.

    **Updatable Fields**:
    - title
    - state
    - priority (0-100)
    - due_date
    - domain
    - estimated_effort_hours
    - description

    **Returns**:
    Updated commitment details.
    """,
)
async def update_commitment(
    commitment_id: UUID,
    update_data: CommitmentUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> CommitmentDetail:
    """Update commitment fields."""
    try:
        # Fetch commitment
        stmt = select(Commitment).where(Commitment.id == commitment_id)
        result = await db.execute(stmt)
        commitment = result.scalar_one_or_none()

        if not commitment:
            raise HTTPException(
                status_code=404, detail=f"Commitment not found: {commitment_id}"
            )

        # Apply updates
        update_dict = update_data.model_dump(exclude_unset=True)

        for field, value in update_dict.items():
            if hasattr(commitment, field):
                setattr(commitment, field, value)

        # Update timestamp
        commitment.updated_at = datetime.utcnow()

        # Commit changes
        await db.commit()
        await db.refresh(commitment)

        # Fetch linked vendor for response
        vendor_id = None
        vendor_name = None

        if commitment.role_id:
            role_stmt = select(Role).where(Role.id == commitment.role_id)
            role_result = await db.execute(role_stmt)
            role = role_result.scalar_one_or_none()

            if role and role.party_id:
                party_stmt = select(Party).where(Party.id == role.party_id)
                party_result = await db.execute(party_stmt)
                party = party_result.scalar_one_or_none()

                if party:
                    vendor_id = party.id
                    vendor_name = party.name

        # Count documents
        doc_count_stmt = (
            select(func.count(DocumentLink.id))
            .where(
                DocumentLink.entity_type == "commitment",
                DocumentLink.entity_id == commitment_id,
            )
        )
        doc_count_result = await db.execute(doc_count_stmt)
        document_count = doc_count_result.scalar_one()

        # Build response
        return CommitmentDetail(
            id=commitment.id,
            title=commitment.title,
            commitment_type=commitment.commitment_type,
            state=commitment.state,
            priority=commitment.priority,
            reason=commitment.reason,
            due_date=commitment.due_date,
            domain=commitment.domain,
            estimated_effort_hours=commitment.estimated_effort_hours,
            recurrence_rule=commitment.recurrence_rule,
            parent_commitment_id=commitment.parent_commitment_id,
            description=commitment.description,
            metadata_=commitment.metadata_,
            created_at=commitment.created_at,
            updated_at=commitment.updated_at,
            fulfilled_at=commitment.fulfilled_at,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            document_count=document_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

"""Vendor API endpoints."""

from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from api.schemas.vendor_schemas import (
    VendorListResponse,
    VendorDetail,
    VendorListItem,
    VendorStats,
    VendorDocumentsResponse,
    DocumentSummary,
)
from api.schemas.document_schemas import ErrorResponse
from api.schemas.commitment_schemas import (
    CommitmentListResponse,
    CommitmentListItem,
)
from memory.database import get_db
from memory.models import Party, Document, DocumentLink, Commitment, Role

router = APIRouter()


@router.get(
    "",
    response_model=VendorListResponse,
    summary="List vendors",
    description="""
    List all vendors with optional fuzzy search by name.

    **Query Parameters**:
    - query: Fuzzy search by vendor name (uses PostgreSQL pg_trgm)
    - offset: Pagination offset
    - limit: Page size (max 100)

    **Returns**:
    List of vendors with basic info.
    """,
)
async def list_vendors(
    query: Optional[str] = Query(None, description="Fuzzy search by name"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> VendorListResponse:
    """List vendors with optional search."""
    try:
        # Base query
        stmt = select(Party).where(Party.kind == "org")

        # Add fuzzy search if query provided
        if query:
            # Use ILIKE for simple search (can be upgraded to pg_trgm similarity)
            stmt = stmt.where(Party.name.ilike(f"%{query}%"))

        # Order by name
        stmt = stmt.order_by(Party.name)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await db.execute(count_stmt)
        total = count_result.scalar_one()

        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)

        # Execute query
        result = await db.execute(stmt)
        vendors = result.scalars().all()

        # Build response
        vendor_items = [
            VendorListItem(
                id=vendor.id,
                name=vendor.name,
                kind=vendor.kind,
                address=vendor.address,
                email=vendor.email,
                phone=vendor.phone,
                created_at=vendor.created_at,
            )
            for vendor in vendors
        ]

        return VendorListResponse(
            vendors=vendor_items, total=total, offset=offset, limit=limit
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{vendor_id}",
    response_model=VendorDetail,
    responses={
        404: {"model": ErrorResponse, "description": "Vendor not found"},
    },
    summary="Get vendor details",
    description="""
    Get complete vendor information including statistics.

    **Returns**:
    - Vendor details (name, contact, tax_id, etc.)
    - Statistics (document count, commitment count, total amount)
    """,
)
async def get_vendor(
    vendor_id: UUID, db: AsyncSession = Depends(get_db)
) -> VendorDetail:
    """Get vendor by ID with statistics."""
    try:
        # Fetch vendor
        stmt = select(Party).where(Party.id == vendor_id)
        result = await db.execute(stmt)
        vendor = result.scalar_one_or_none()

        if not vendor:
            raise HTTPException(status_code=404, detail=f"Vendor not found: {vendor_id}")

        # Calculate stats
        # Document count
        doc_count_stmt = (
            select(func.count(Document.id))
            .select_from(DocumentLink)
            .join(Document, DocumentLink.document_id == Document.id)
            .where(
                DocumentLink.entity_type == "party",
                DocumentLink.entity_id == vendor_id,
                DocumentLink.link_type == "vendor",
            )
        )
        doc_count_result = await db.execute(doc_count_stmt)
        document_count = doc_count_result.scalar_one()

        # Commitment count (through roles)
        commitment_count_stmt = (
            select(func.count(Commitment.id))
            .select_from(Role)
            .join(Commitment, Role.id == Commitment.role_id)
            .where(Role.party_id == vendor_id)
        )
        commitment_count_result = await db.execute(commitment_count_stmt)
        commitment_count = commitment_count_result.scalar_one()

        # Build stats
        stats = VendorStats(
            document_count=document_count,
            commitment_count=commitment_count,
            total_amount=None,  # Future: sum from invoice extraction data
            last_interaction=None,  # Future: max from interactions table
        )

        # Build response
        return VendorDetail(
            id=vendor.id,
            name=vendor.name,
            kind=vendor.kind,
            address=vendor.address,
            email=vendor.email,
            phone=vendor.phone,
            tax_id=vendor.tax_id,
            contact_name=vendor.contact_name,
            notes=vendor.notes,
            created_at=vendor.created_at,
            updated_at=vendor.updated_at,
            stats=stats,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{vendor_id}/documents",
    response_model=VendorDocumentsResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Vendor not found"},
    },
    summary="Get vendor documents",
    description="""
    Get all documents linked to a vendor.

    **Returns**:
    List of documents with extraction details.
    """,
)
async def get_vendor_documents(
    vendor_id: UUID, db: AsyncSession = Depends(get_db)
) -> VendorDocumentsResponse:
    """Get all documents for a vendor."""
    try:
        # Fetch vendor
        vendor_stmt = select(Party).where(Party.id == vendor_id)
        vendor_result = await db.execute(vendor_stmt)
        vendor = vendor_result.scalar_one_or_none()

        if not vendor:
            raise HTTPException(status_code=404, detail=f"Vendor not found: {vendor_id}")

        # Fetch documents
        docs_stmt = (
            select(Document)
            .join(DocumentLink, Document.id == DocumentLink.document_id)
            .where(
                DocumentLink.entity_type == "party",
                DocumentLink.entity_id == vendor_id,
                DocumentLink.link_type == "vendor",
            )
            .order_by(Document.extracted_at.desc())
        )

        docs_result = await db.execute(docs_stmt)
        documents = docs_result.scalars().all()

        # Build response
        doc_summaries = [
            DocumentSummary(
                id=doc.id,
                path=doc.path,
                extraction_type=doc.extraction_type,
                extracted_at=doc.extracted_at,
                extraction_cost=doc.extraction_cost,
            )
            for doc in documents
        ]

        return VendorDocumentsResponse(
            vendor_id=vendor.id,
            vendor_name=vendor.name,
            documents=doc_summaries,
            total=len(doc_summaries),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{vendor_id}/commitments",
    response_model=CommitmentListResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Vendor not found"},
    },
    summary="Get vendor commitments",
    description="""
    Get all commitments linked to a vendor (through roles).

    **Returns**:
    List of commitments with priority and status.
    """,
)
async def get_vendor_commitments(
    vendor_id: UUID, db: AsyncSession = Depends(get_db)
) -> CommitmentListResponse:
    """Get all commitments for a vendor."""
    try:
        # Fetch vendor
        vendor_stmt = select(Party).where(Party.id == vendor_id)
        vendor_result = await db.execute(vendor_stmt)
        vendor = vendor_result.scalar_one_or_none()

        if not vendor:
            raise HTTPException(status_code=404, detail=f"Vendor not found: {vendor_id}")

        # Fetch commitments (through roles)
        commitments_stmt = (
            select(Commitment)
            .join(Role, Commitment.role_id == Role.id)
            .where(Role.party_id == vendor_id)
            .order_by(Commitment.priority.desc(), Commitment.due_date)
        )

        commitments_result = await db.execute(commitments_stmt)
        commitments = commitments_result.scalars().all()

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
            total=len(commitment_items),
            offset=0,
            limit=len(commitment_items),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

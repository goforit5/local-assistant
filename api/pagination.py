"""Pagination utilities for FastAPI endpoints.

This module provides reusable pagination components following RFC 5988 (Web Linking)
for consistent pagination across all list endpoints.

Features:
- Query parameter validation (PaginationParams)
- Generic paginated response wrapper (PaginatedResponse[T])
- Link header builder for REST HATEOAS (RFC 5988)
- Integration with memory/queries.py paginate_query()

Usage Example:
    from api.pagination import PaginationParams, paginate_response, build_link_header
    from fastapi import Depends, Response

    @router.get("/vendors", response_model=PaginatedResponse[VendorListItem])
    async def list_vendors(
        pagination: PaginationParams = Depends(),
        response: Response,
        db: AsyncSession = Depends(get_db),
    ):
        # Build base query
        stmt = select(Party).where(Party.kind == "org").order_by(Party.name)

        # Paginate using helper
        items, total = await paginate_query(
            db, stmt, page=pagination.page, page_size=pagination.size
        )

        # Build response with metadata
        result = paginate_response(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.size,
        )

        # Add Link headers (RFC 5988)
        link_header = build_link_header(
            base_url="/api/v1/vendors",
            page=pagination.page,
            page_size=pagination.size,
            total=total,
        )
        if link_header:
            response.headers["Link"] = link_header

        return result
"""

from typing import Generic, TypeVar, Optional, List
from urllib.parse import urlencode
from math import ceil

from pydantic import BaseModel, Field
from fastapi import Query


# Default pagination settings
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class PaginationParams(BaseModel):
    """Reusable pagination query parameters.

    Attributes:
        page: Page number (1-indexed)
        size: Items per page (max 100, default 20)

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            items, total = await paginate_query(
                db, stmt, page=pagination.page, page_size=pagination.size
            )
    """

    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)",
    )
    size: int = Field(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description=f"Items per page (max {MAX_PAGE_SIZE})",
    )

    @classmethod
    def as_query_params(cls) -> "PaginationParams":
        """Factory for use with FastAPI Depends().

        Returns:
            PaginationParams configured as query parameters

        Usage:
            @router.get("/items")
            async def list_items(pagination: PaginationParams = Depends(PaginationParams.as_query_params)):
                ...
        """
        return cls(
            page=Query(default=1, ge=1, description="Page number (1-indexed)"),
            size=Query(
                default=DEFAULT_PAGE_SIZE,
                ge=1,
                le=MAX_PAGE_SIZE,
                description=f"Items per page (max {MAX_PAGE_SIZE})",
            ),
        )


class PageInfo(BaseModel):
    """Pagination metadata.

    Attributes:
        current_page: Current page number (1-indexed)
        page_size: Items per page
        total_items: Total number of items across all pages
        total_pages: Total number of pages
        has_next: Whether there is a next page
        has_prev: Whether there is a previous page
    """

    current_page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Items per page")
    total_items: int = Field(description="Total items across all pages")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper.

    Type Parameters:
        T: Type of items in the data list

    Attributes:
        data: List of items for current page
        page_info: Pagination metadata

    Usage:
        from api.schemas.vendor_schemas import VendorListItem

        @router.get("/vendors", response_model=PaginatedResponse[VendorListItem])
        async def list_vendors():
            return PaginatedResponse(
                data=[...],
                page_info=PageInfo(...)
            )
    """

    data: List[T]
    page_info: PageInfo


def paginate_response(
    items: List[T],
    total: int,
    page: int,
    page_size: int,
) -> PaginatedResponse[T]:
    """Build a paginated response with metadata.

    Args:
        items: List of items for current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Items per page

    Returns:
        PaginatedResponse with data and pagination metadata

    Example:
        items, total = await paginate_query(db, stmt, page=2, page_size=20)
        response = paginate_response(items, total, page=2, page_size=20)
        # response.page_info.total_pages = 5
        # response.page_info.has_next = True
    """
    total_pages = ceil(total / page_size) if page_size > 0 else 0

    page_info = PageInfo(
        current_page=page,
        page_size=page_size,
        total_items=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )

    return PaginatedResponse(data=items, page_info=page_info)


def build_link_header(
    base_url: str,
    page: int,
    page_size: int,
    total: int,
    query_params: Optional[dict] = None,
) -> Optional[str]:
    """Build RFC 5988 Link header for pagination.

    Link header format:
        Link: <url?page=2&size=20>; rel="next",
              <url?page=1&size=20>; rel="first",
              <url?page=10&size=20>; rel="last"

    Args:
        base_url: Base URL path (e.g., "/api/v1/vendors")
        page: Current page number (1-indexed)
        page_size: Items per page
        total: Total number of items
        query_params: Additional query parameters to preserve (e.g., {"query": "acme"})

    Returns:
        Link header string, or None if no links to include

    Example:
        link_header = build_link_header(
            base_url="/api/v1/vendors",
            page=2,
            page_size=20,
            total=100,
            query_params={"query": "acme"},
        )
        response.headers["Link"] = link_header
        # Link: </api/v1/vendors?page=1&size=20&query=acme>; rel="first", ...
    """
    total_pages = ceil(total / page_size) if page_size > 0 else 0

    if total_pages <= 1:
        return None  # No pagination needed

    # Build base query params
    params = query_params.copy() if query_params else {}
    params["size"] = page_size

    links = []

    # First page
    if page > 1:
        params["page"] = 1
        links.append(f'<{base_url}?{urlencode(params)}>; rel="first"')

    # Previous page
    if page > 1:
        params["page"] = page - 1
        links.append(f'<{base_url}?{urlencode(params)}>; rel="prev"')

    # Next page
    if page < total_pages:
        params["page"] = page + 1
        links.append(f'<{base_url}?{urlencode(params)}>; rel="next"')

    # Last page
    if page < total_pages:
        params["page"] = total_pages
        links.append(f'<{base_url}?{urlencode(params)}>; rel="last"')

    return ", ".join(links) if links else None


# ========== Integration Example (Comment Form) ==========

"""
# Full endpoint example with pagination:

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.pagination import PaginationParams, paginate_response, build_link_header
from api.schemas.vendor_schemas import VendorListItem
from api.schemas.pagination import PaginatedResponse
from memory.database import get_db
from memory.models import Party
from memory.queries import paginate_query

router = APIRouter()


@router.get(
    "/vendors",
    response_model=PaginatedResponse[VendorListItem],
    summary="List vendors with pagination",
)
async def list_vendors(
    query: Optional[str] = Query(None, description="Search by name"),
    pagination: PaginationParams = Depends(),
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    '''List vendors with pagination and Link headers.

    Returns:
        Paginated list of vendors with metadata and RFC 5988 Link headers.
    '''
    # Build base query
    stmt = select(Party).where(Party.kind == "org")

    if query:
        stmt = stmt.where(Party.name.ilike(f"%{query}%"))

    stmt = stmt.order_by(Party.name)

    # Paginate using memory/queries.py helper
    items, total = await paginate_query(
        db,
        stmt,
        page=pagination.page,
        page_size=pagination.size,
    )

    # Convert to response schemas
    vendor_items = [
        VendorListItem(
            id=v.id,
            name=v.name,
            kind=v.kind,
            address=v.address,
            email=v.email,
            phone=v.phone,
            created_at=v.created_at,
        )
        for v in items
    ]

    # Build paginated response
    result = paginate_response(
        items=vendor_items,
        total=total,
        page=pagination.page,
        page_size=pagination.size,
    )

    # Add Link headers (RFC 5988)
    link_header = build_link_header(
        base_url="/api/v1/vendors",
        page=pagination.page,
        page_size=pagination.size,
        total=total,
        query_params={"query": query} if query else None,
    )
    if link_header:
        response.headers["Link"] = link_header

    return result


# Example response:
# HTTP/1.1 200 OK
# Link: </api/v1/vendors?page=1&size=20>; rel="first",
#       </api/v1/vendors?page=2&size=20>; rel="next",
#       </api/v1/vendors?page=5&size=20>; rel="last"
# Content-Type: application/json
#
# {
#   "data": [
#     {
#       "id": "550e8400-e29b-41d4-a716-446655440000",
#       "name": "Acme Corp",
#       "kind": "org",
#       ...
#     }
#   ],
#   "page_info": {
#     "current_page": 1,
#     "page_size": 20,
#     "total_items": 87,
#     "total_pages": 5,
#     "has_next": true,
#     "has_prev": false
#   }
# }
"""

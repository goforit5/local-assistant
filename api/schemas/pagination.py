"""Pagination response schemas.

Reusable Pydantic models for paginated API responses.
These schemas work with api/pagination.py utilities.

Usage:
    from api.schemas.pagination import PaginatedResponse, PageInfo
    from api.schemas.vendor_schemas import VendorListItem

    @router.get("/vendors", response_model=PaginatedResponse[VendorListItem])
    async def list_vendors():
        return PaginatedResponse(
            data=[...],
            page_info=PageInfo(...)
        )
"""

from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field


class PageInfo(BaseModel):
    """Pagination metadata for list endpoints.

    This provides clients with all information needed to navigate
    through paginated results.

    Attributes:
        current_page: Current page number (1-indexed)
        page_size: Number of items per page
        total_items: Total number of items across all pages
        total_pages: Total number of pages
        has_next: Whether there is a next page available
        has_prev: Whether there is a previous page available
    """

    current_page: int = Field(
        description="Current page number (1-indexed)",
        ge=1,
    )
    page_size: int = Field(
        description="Number of items per page",
        ge=1,
    )
    total_items: int = Field(
        description="Total number of items across all pages",
        ge=0,
    )
    total_pages: int = Field(
        description="Total number of pages",
        ge=0,
    )
    has_next: bool = Field(
        description="Whether there is a next page available",
    )
    has_prev: bool = Field(
        description="Whether there is a previous page available",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "current_page": 2,
                "page_size": 20,
                "total_items": 87,
                "total_pages": 5,
                "has_next": True,
                "has_prev": True,
            }
        }


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper.

    This is a type-safe wrapper for any list endpoint response.
    The generic type parameter T should be the item schema.

    Type Parameters:
        T: Type of items in the data list

    Attributes:
        data: List of items for the current page
        page_info: Pagination metadata

    Usage:
        from api.schemas.vendor_schemas import VendorListItem
        from api.schemas.pagination import PaginatedResponse

        # In route definition
        @router.get("/vendors", response_model=PaginatedResponse[VendorListItem])
        async def list_vendors():
            return PaginatedResponse(
                data=[vendor1, vendor2, ...],
                page_info=PageInfo(
                    current_page=1,
                    page_size=20,
                    total_items=87,
                    total_pages=5,
                    has_next=True,
                    has_prev=False,
                )
            )

    Example Response:
        {
            "data": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Acme Corp",
                    ...
                }
            ],
            "page_info": {
                "current_page": 1,
                "page_size": 20,
                "total_items": 87,
                "total_pages": 5,
                "has_next": true,
                "has_prev": false
            }
        }
    """

    data: List[T] = Field(
        description="List of items for the current page",
    )
    page_info: PageInfo = Field(
        description="Pagination metadata",
    )

    class Config:
        # Allow arbitrary types for generic T
        arbitrary_types_allowed = True


# ========== Example Endpoint Integration ==========

"""
Complete example showing how to use these schemas with FastAPI:

from typing import Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.pagination import PaginationParams, paginate_response, build_link_header
from api.schemas.pagination import PaginatedResponse, PageInfo
from api.schemas.vendor_schemas import VendorListItem
from memory.database import get_db
from memory.models import Party
from memory.queries import paginate_query

router = APIRouter()


@router.get(
    "/vendors",
    response_model=PaginatedResponse[VendorListItem],
    summary="List vendors with pagination",
    description='''
    List all vendors with pagination support.

    **Pagination**:
    - Default page size: 20 items
    - Maximum page size: 100 items
    - Page numbers are 1-indexed
    - Link headers (RFC 5988) provided for navigation

    **Query Parameters**:
    - page: Page number (default: 1)
    - size: Items per page (default: 20, max: 100)
    - query: Search vendors by name (fuzzy match)

    **Response Headers**:
    - Link: Contains first, prev, next, last URLs (RFC 5988)

    **Example**:
        GET /api/v1/vendors?page=2&size=20&query=acme

        Response:
        Link: </api/v1/vendors?page=1&size=20&query=acme>; rel="first",
              </api/v1/vendors?page=1&size=20&query=acme>; rel="prev",
              </api/v1/vendors?page=3&size=20&query=acme>; rel="next",
              </api/v1/vendors?page=5&size=20&query=acme>; rel="last"

        {
          "data": [...],
          "page_info": {
            "current_page": 2,
            "page_size": 20,
            "total_items": 87,
            "total_pages": 5,
            "has_next": true,
            "has_prev": true
          }
        }
    ''',
)
async def list_vendors(
    query: Optional[str] = Query(None, description="Search by vendor name"),
    pagination: PaginationParams = Depends(),
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[VendorListItem]:
    '''List vendors with pagination.'''

    # Build query
    stmt = select(Party).where(Party.kind == "org")

    if query:
        stmt = stmt.where(Party.name.ilike(f"%{query}%"))

    stmt = stmt.order_by(Party.name)

    # Paginate using helper from memory/queries.py
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

    # Build paginated response with metadata
    result = paginate_response(
        items=vendor_items,
        total=total,
        page=pagination.page,
        page_size=pagination.size,
    )

    # Add RFC 5988 Link headers for navigation
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


# ========== Migration Strategy for Existing Endpoints ==========

# Current endpoint (api/v1/vendors.py):
# @router.get("", response_model=VendorListResponse)
# async def list_vendors(
#     query: Optional[str] = Query(None),
#     offset: int = Query(0, ge=0),
#     limit: int = Query(50, ge=1, le=100),
#     db: AsyncSession = Depends(get_db),
# ) -> VendorListResponse:
#     ...
#     return VendorListResponse(
#         vendors=vendor_items,
#         total=total,
#         offset=offset,
#         limit=limit,
#     )

# Updated endpoint with pagination:
# @router.get("", response_model=PaginatedResponse[VendorListItem])
# async def list_vendors(
#     query: Optional[str] = Query(None),
#     pagination: PaginationParams = Depends(),
#     response: Response,
#     db: AsyncSession = Depends(get_db),
# ) -> PaginatedResponse[VendorListItem]:
#     stmt = select(Party).where(Party.kind == "org")
#     if query:
#         stmt = stmt.where(Party.name.ilike(f"%{query}%"))
#     stmt = stmt.order_by(Party.name)
#
#     # Use paginate_query instead of manual offset/limit
#     items, total = await paginate_query(
#         db, stmt, page=pagination.page, page_size=pagination.size
#     )
#
#     vendor_items = [VendorListItem(...) for v in items]
#
#     result = paginate_response(
#         items=vendor_items,
#         total=total,
#         page=pagination.page,
#         page_size=pagination.size,
#     )
#
#     # Add Link headers
#     link_header = build_link_header(
#         base_url="/api/v1/vendors",
#         page=pagination.page,
#         page_size=pagination.size,
#         total=total,
#         query_params={"query": query} if query else None,
#     )
#     if link_header:
#         response.headers["Link"] = link_header
#
#     return result

# Benefits:
# 1. Consistent pagination across all endpoints
# 2. RFC 5988 Link headers for HATEOAS
# 3. Type-safe generic response wrapper
# 4. Better client experience (has_next, has_prev flags)
# 5. Automatic validation (max page size, positive page numbers)
# 6. Preserves query parameters in Link headers
"""

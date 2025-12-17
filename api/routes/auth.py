"""Authentication routes."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.jwt import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from api.schemas.auth import LoginRequest, TokenResponse, RefreshTokenRequest

router = APIRouter()


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    # db: AsyncSession = Depends(get_db)  # TODO: Add database session dependency
) -> TokenResponse:
    """
    Authenticate user and return JWT tokens.

    Args:
        request: Login credentials (username and password)

    Returns:
        TokenResponse with access and refresh tokens

    Raises:
        HTTPException: If authentication fails
    """
    # TODO: Uncomment when database session dependency is added
    # user = await authenticate_user(db, request.username, request.password)
    # if not user:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Incorrect username or password",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    # Placeholder for testing without database
    # In production, replace with actual user authentication
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Database session dependency not yet configured. Add get_db() dependency to enable authentication.",
    )

    # Generate tokens (uncomment when database is ready)
    # access_token = create_access_token(
    #     data={"sub": user.username, "user_id": user.id},
    #     expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # )
    # refresh_token = create_refresh_token(
    #     data={"sub": user.username, "user_id": user.id},
    #     expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    # )
    #
    # return TokenResponse(
    #     access_token=access_token,
    #     refresh_token=refresh_token,
    #     token_type="bearer",
    #     expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    # )


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: RefreshTokenRequest,
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    Args:
        request: Refresh token request

    Returns:
        TokenResponse with new access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    # Verify refresh token
    token_data = await verify_token(request.refresh_token, token_type="refresh")

    # Generate new tokens
    access_token = create_access_token(
        data={"sub": token_data.username, "user_id": token_data.user_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token(
        data={"sub": token_data.username, "user_id": token_data.user_id},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.get("/me")
async def get_current_user_info(
    current_user: Annotated[dict, Depends(get_current_user)]
):
    """
    Get current authenticated user information.

    Args:
        current_user: Current user from JWT token

    Returns:
        User information
    """
    return {
        "username": current_user.username,
        "user_id": current_user.user_id,
    }

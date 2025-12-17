"""
Microsoft Graph Base Client

Provides base HTTP client functionality for all Graph API interactions:
- Automatic authentication header injection
- Retry logic with exponential backoff
- Rate limit handling (throttling)
- Request batching (up to 20 requests per batch)
- Error handling and logging

Best Practices (from research):
- Respect throttling limits (10k requests / 10 minutes)
- Use batch requests for bulk operations
- Implement exponential backoff on 429/503
- Cache responses where appropriate
"""

import httpx
import asyncio
import structlog
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = structlog.get_logger(__name__)


class GraphRateLimitError(Exception):
    """Raised when Graph API rate limit is exceeded."""
    pass


class GraphBaseClient:
    """
    Base client for Microsoft Graph API interactions.

    Handles:
    - Authentication
    - Rate limiting
    - Retries
    - Batching
    - Error handling
    """

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    GRAPH_API_BETA = "https://graph.microsoft.com/beta"
    MAX_BATCH_SIZE = 20  # Microsoft Graph limit

    def __init__(
        self,
        authenticator,
        use_beta: bool = False,
        timeout: float = 30.0,
    ):
        """
        Initialize Graph base client.

        Args:
            authenticator: GraphAuthenticator instance
            use_beta: Use beta API endpoint instead of v1.0
            timeout: HTTP request timeout in seconds
        """
        self.authenticator = authenticator
        self.base_url = self.GRAPH_API_BETA if use_beta else self.GRAPH_API_BASE
        self.timeout = timeout

        # HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        # Rate limiting tracking
        self.request_count = 0
        self.window_start = datetime.now()
        self.rate_limit_window = timedelta(minutes=10)
        self.rate_limit_max = 10000

        logger.info(
            "graph_client_initialized",
            base_url=self.base_url,
            use_beta=use_beta,
        )

    async def _get_headers(self) -> Dict[str, str]:
        """Get headers including fresh access token."""
        token = self.authenticator.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _check_rate_limit(self) -> None:
        """
        Check if we're approaching rate limit and wait if needed.

        Microsoft Graph rate limit: ~10,000 requests per 10 minutes
        """
        now = datetime.now()

        # Reset window if expired
        if now - self.window_start > self.rate_limit_window:
            self.request_count = 0
            self.window_start = now

        # Check if approaching limit (leave 10% buffer)
        if self.request_count >= (self.rate_limit_max * 0.9):
            wait_seconds = (
                self.rate_limit_window - (now - self.window_start)
            ).total_seconds()
            if wait_seconds > 0:
                logger.warning(
                    "rate_limit_approaching",
                    count=self.request_count,
                    wait_seconds=wait_seconds,
                )
                raise GraphRateLimitError(
                    f"Rate limit approaching. Wait {wait_seconds:.0f}s"
                )

        self.request_count += 1

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make GET request to Graph API.

        Args:
            endpoint: API endpoint (e.g., "/me/planner/tasks")
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            httpx.HTTPStatusError: On HTTP error
            GraphRateLimitError: On rate limit
        """
        self._check_rate_limit()
        headers = await self._get_headers()

        logger.debug("graph_api_get", endpoint=endpoint, params=params)

        response = await self.client.get(
            endpoint,
            params=params,
            headers=headers,
        )

        # Handle throttling
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("throttled", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            return await self.get(endpoint, params)

        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def post(
        self,
        endpoint: str,
        json_data: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make POST request to Graph API.

        Args:
            endpoint: API endpoint
            json_data: Request body
            params: Query parameters

        Returns:
            Response JSON
        """
        self._check_rate_limit()
        headers = await self._get_headers()

        logger.debug("graph_api_post", endpoint=endpoint)

        response = await self.client.post(
            endpoint,
            json=json_data,
            params=params,
            headers=headers,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("throttled", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            return await self.post(endpoint, json_data, params)

        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def patch(
        self,
        endpoint: str,
        json_data: Dict[str, Any],
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make PATCH request to Graph API.

        Args:
            endpoint: API endpoint
            json_data: Request body (partial update)
            params: Query parameters

        Returns:
            Response JSON
        """
        self._check_rate_limit()
        headers = await self._get_headers()

        logger.debug("graph_api_patch", endpoint=endpoint)

        response = await self.client.patch(
            endpoint,
            json=json_data,
            params=params,
            headers=headers,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("throttled", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            return await self.patch(endpoint, json_data, params)

        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Make DELETE request to Graph API.

        Args:
            endpoint: API endpoint
            params: Query parameters
        """
        self._check_rate_limit()
        headers = await self._get_headers()

        logger.debug("graph_api_delete", endpoint=endpoint)

        response = await self.client.delete(
            endpoint,
            params=params,
            headers=headers,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("throttled", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            return await self.delete(endpoint, params)

        response.raise_for_status()

    async def batch(
        self,
        requests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Execute batch request (up to 20 requests).

        Batch requests are useful for:
        - Fetching task details for multiple tasks
        - Bulk updates
        - Reducing round trips

        Args:
            requests: List of request dicts with keys:
                - id: Request ID (for matching responses)
                - method: HTTP method (GET, POST, PATCH, DELETE)
                - url: Endpoint URL (relative to /v1.0 or /beta)
                - body: Request body (for POST/PATCH)
                - headers: Additional headers

        Returns:
            List of response dicts

        Example:
            >>> requests = [
            >>>     {
            >>>         "id": "1",
            >>>         "method": "GET",
            >>>         "url": "/planner/tasks/{task1_id}/details"
            >>>     },
            >>>     {
            >>>         "id": "2",
            >>>         "method": "GET",
            >>>         "url": "/planner/tasks/{task2_id}/details"
            >>>     }
            >>> ]
            >>> responses = await client.batch(requests)
        """
        if len(requests) > self.MAX_BATCH_SIZE:
            logger.warning(
                "batch_too_large",
                size=len(requests),
                max=self.MAX_BATCH_SIZE,
            )
            # Split into multiple batches
            results = []
            for i in range(0, len(requests), self.MAX_BATCH_SIZE):
                batch = requests[i:i + self.MAX_BATCH_SIZE]
                batch_results = await self.batch(batch)
                results.extend(batch_results)
            return results

        self._check_rate_limit()
        headers = await self._get_headers()

        logger.debug("graph_api_batch", count=len(requests))

        # Batch endpoint
        response = await self.client.post(
            "/$batch",
            json={"requests": requests},
            headers=headers,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("throttled", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            return await self.batch(requests)

        response.raise_for_status()
        result = response.json()

        return result.get("responses", [])

    async def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all pages of a paginated response.

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_pages: Maximum number of pages to fetch (None = all)

        Returns:
            List of all items across all pages
        """
        all_items = []
        page_count = 0
        next_link = endpoint

        while next_link:
            if max_pages and page_count >= max_pages:
                break

            # If it's a full URL (from @odata.nextLink), extract path
            if next_link.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(next_link)
                next_link = parsed.path + ("?" + parsed.query if parsed.query else "")

            response = await self.get(next_link, params if page_count == 0 else None)

            # Extract items
            items = response.get("value", [])
            all_items.extend(items)

            # Get next link
            next_link = response.get("@odata.nextLink")
            page_count += 1

            logger.debug(
                "pagination",
                page=page_count,
                items_count=len(items),
                total=len(all_items),
                has_more=bool(next_link),
            )

        return all_items

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("graph_client_closed")

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

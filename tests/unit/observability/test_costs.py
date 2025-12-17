"""Unit tests for cost tracking."""

import pytest
import asyncio
from datetime import datetime, timedelta

from observability.costs import CostTracker, CostLimitExceeded, CostWindow


class TestCostTracker:
    """Test CostTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create cost tracker."""
        return CostTracker(
            per_request_warn=0.50,
            per_request_max=1.00,
            per_hour_warn=5.00,
            per_hour_max=10.00,
            per_day_warn=20.00,
            per_day_max=50.00
        )

    @pytest.mark.asyncio
    async def test_add_cost(self, tracker):
        """Test adding cost."""
        await tracker.add_cost(0.25, "anthropic", "claude-sonnet-4-20250514")

        total = await tracker.get_total(CostWindow.PER_REQUEST)
        assert total == 0.25

    @pytest.mark.asyncio
    async def test_hourly_window(self, tracker):
        """Test hourly cost tracking."""
        # Add costs
        await tracker.add_cost(1.00, "anthropic", "claude-sonnet-4-20250514")
        await tracker.add_cost(2.00, "openai", "gpt-4o")

        total = await tracker.get_total(CostWindow.HOURLY)
        assert total == 3.00

    @pytest.mark.asyncio
    async def test_cost_limit_warning(self, tracker):
        """Test cost limit warning."""
        # Below warn threshold
        exceeded = await tracker.check_limit(0.30, CostWindow.PER_REQUEST)
        assert not exceeded

        # At warn threshold
        exceeded = await tracker.check_limit(0.50, CostWindow.PER_REQUEST)
        assert exceeded == "warn"

    @pytest.mark.asyncio
    async def test_cost_limit_exceeded(self, tracker):
        """Test cost limit max."""
        exceeded = await tracker.check_limit(1.50, CostWindow.PER_REQUEST)
        assert exceeded == "max"

    @pytest.mark.asyncio
    async def test_alert_if_exceeded(self, tracker):
        """Test alert on exceeded limit."""
        # Should not raise on warn
        await tracker.alert_if_exceeded(0.60, CostWindow.PER_REQUEST)

        # Should raise on max
        with pytest.raises(CostLimitExceeded):
            await tracker.alert_if_exceeded(1.50, CostWindow.PER_REQUEST)

    @pytest.mark.asyncio
    async def test_cost_breakdown_by_provider(self, tracker):
        """Test cost breakdown."""
        await tracker.add_cost(1.00, "anthropic", "claude-sonnet-4-20250514")
        await tracker.add_cost(2.00, "openai", "gpt-4o")
        await tracker.add_cost(0.50, "google", "gemini-2.5-flash-latest")

        breakdown = await tracker.get_breakdown_by_provider(CostWindow.DAILY)
        assert breakdown["anthropic"] == 1.00
        assert breakdown["openai"] == 2.00
        assert breakdown["google"] == 0.50

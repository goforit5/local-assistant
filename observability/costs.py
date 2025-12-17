"""
Cost Tracking and Enforcement
Monitors API costs and enforces per_request, hourly, and daily limits
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple
import json
import structlog

logger = structlog.get_logger(__name__)


class CostWindow(str, Enum):
    """Time windows for cost tracking"""
    PER_REQUEST = "per_request"
    HOURLY = "per_hour"
    DAILY = "per_day"


class CostLimitExceeded(Exception):
    """Raised when a cost limit is exceeded"""
    def __init__(self, window: CostWindow, amount: float, limit: float):
        self.window = window
        self.amount = amount
        self.limit = limit
        super().__init__(
            f"Cost limit exceeded for {window.value}: ${amount:.4f} > ${limit:.4f}"
        )


class CostTracker:
    """
    Tracks API costs across multiple time windows and enforces limits.

    Features:
    - Per-request, hourly, and daily tracking
    - Warn and max thresholds
    - Persistent storage
    - Thread-safe operations
    """

    def __init__(
        self,
        limits: Dict[str, Dict[str, float]],
        storage_path: Optional[Path] = None,
    ):
        """
        Initialize cost tracker.

        Args:
            limits: Cost limits from config (per_request, per_hour, per_day)
            storage_path: Path to persist cost data
        """
        self.limits = limits
        self.storage_path = storage_path or Path("data/costs.json")
        self._lock = asyncio.Lock()

        # In-memory storage: {window: [(timestamp, cost), ...]}
        self._costs: Dict[CostWindow, list[Tuple[datetime, float]]] = {
            CostWindow.PER_REQUEST: [],
            CostWindow.HOURLY: [],
            CostWindow.DAILY: [],
        }

        # Load persisted data
        self._load()

    def _load(self) -> None:
        """Load cost data from persistent storage"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for window_str, entries in data.items():
                    window = CostWindow(window_str)
                    self._costs[window] = [
                        (datetime.fromisoformat(ts), cost)
                        for ts, cost in entries
                    ]
            logger.info("cost_data_loaded", path=str(self.storage_path))
        except Exception as e:
            logger.error("cost_data_load_failed", error=str(e))

    async def _save(self) -> None:
        """Save cost data to persistent storage"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                window.value: [
                    (ts.isoformat(), cost)
                    for ts, cost in entries
                ]
                for window, entries in self._costs.items()
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("cost_data_save_failed", error=str(e))

    def _cleanup_old_entries(self, window: CostWindow) -> None:
        """Remove entries outside the tracking window"""
        now = datetime.now()
        cutoff = now - timedelta(hours=1 if window == CostWindow.HOURLY else 24)

        if window == CostWindow.PER_REQUEST:
            return  # Keep all per-request entries

        self._costs[window] = [
            (ts, cost) for ts, cost in self._costs[window]
            if ts >= cutoff
        ]

    async def add_cost(
        self,
        amount: float,
        model: str,
        input_tokens: int,
        output_tokens: int,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Add a cost entry and check limits.

        Args:
            amount: Cost in dollars
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            metadata: Additional metadata

        Raises:
            CostLimitExceeded: If a max limit is exceeded
        """
        async with self._lock:
            now = datetime.now()

            # Check per-request limit first
            await self._check_limit(CostWindow.PER_REQUEST, amount)

            # Add to all windows
            for window in CostWindow:
                self._costs[window].append((now, amount))
                self._cleanup_old_entries(window)

            # Check hourly and daily limits
            await self._check_limit(CostWindow.HOURLY, self.get_total(CostWindow.HOURLY))
            await self._check_limit(CostWindow.DAILY, self.get_total(CostWindow.DAILY))

            # Log the cost
            logger.info(
                "cost_tracked",
                amount=f"${amount:.4f}",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                hourly_total=f"${self.get_total(CostWindow.HOURLY):.4f}",
                daily_total=f"${self.get_total(CostWindow.DAILY):.4f}",
                **(metadata or {}),
            )

            # Save to disk
            await self._save()

    async def _check_limit(self, window: CostWindow, amount: float) -> None:
        """
        Check if amount exceeds limits for window.

        Args:
            window: Time window to check
            amount: Amount to check

        Raises:
            CostLimitExceeded: If max limit is exceeded
        """
        limits = self.limits.get(window.value, {})
        warn_limit = limits.get("warn")
        max_limit = limits.get("max")

        if warn_limit and amount >= warn_limit:
            logger.warning(
                "cost_limit_warning",
                window=window.value,
                amount=f"${amount:.4f}",
                warn_limit=f"${warn_limit:.4f}",
            )

        if max_limit and amount >= max_limit:
            logger.error(
                "cost_limit_exceeded",
                window=window.value,
                amount=f"${amount:.4f}",
                max_limit=f"${max_limit:.4f}",
            )
            raise CostLimitExceeded(window, amount, max_limit)

    def get_total(self, window: CostWindow) -> float:
        """
        Get total cost for a time window.

        Args:
            window: Time window

        Returns:
            Total cost in dollars
        """
        return sum(cost for _, cost in self._costs[window])

    def get_summary(self) -> Dict[str, float]:
        """
        Get cost summary for all windows.

        Returns:
            Dict mapping window to total cost
        """
        return {
            window.value: self.get_total(window)
            for window in CostWindow
        }

    async def alert_if_exceeded(self) -> None:
        """Check all limits and log warnings/errors"""
        for window in [CostWindow.HOURLY, CostWindow.DAILY]:
            total = self.get_total(window)
            limits = self.limits.get(window.value, {})

            warn_limit = limits.get("warn")
            max_limit = limits.get("max")

            if max_limit and total >= max_limit:
                logger.error(
                    "cost_limit_alert",
                    window=window.value,
                    total=f"${total:.4f}",
                    max_limit=f"${max_limit:.4f}",
                    action="blocking",
                )
            elif warn_limit and total >= warn_limit:
                logger.warning(
                    "cost_limit_alert",
                    window=window.value,
                    total=f"${total:.4f}",
                    warn_limit=f"${warn_limit:.4f}",
                    action="warning",
                )


# Global instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker(
    limits: Optional[Dict[str, Dict[str, float]]] = None,
    storage_path: Optional[Path] = None,
) -> CostTracker:
    """Get or create global cost tracker instance"""
    global _cost_tracker
    if _cost_tracker is None:
        if limits is None:
            raise ValueError("limits must be provided on first call")
        _cost_tracker = CostTracker(limits, storage_path)
    return _cost_tracker

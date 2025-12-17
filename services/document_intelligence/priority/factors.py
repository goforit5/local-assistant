"""
Priority calculation factors for commitments.

Each factor returns a score (0-100) and an explanation string.
Factors are weighted and combined by the PriorityCalculator.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from lib.shared.local_assistant_shared.utils.date_utils import (
    calculate_days_until,
    format_relative_date,
)


@dataclass
class FactorResult:
    """Result from a single priority factor calculation.

    Attributes:
        score: Factor score (0-100)
        explanation: Human-readable explanation of score
        metadata: Additional context data
    """
    score: float
    explanation: str
    metadata: dict


class TimeFactor:
    """Time pressure based on days until due date (30% weight).

    Uses exponential decay: recent deadlines score higher.

    Scoring:
    - Overdue: 100
    - Due today: 95-100
    - Due in 1 week: 70
    - Due in 1 month: 30
    - Due in 3+ months: <10
    """

    WEIGHT = 0.30

    @staticmethod
    def calculate(
        due_date: Optional[datetime],
        reference_date: Optional[datetime] = None
    ) -> FactorResult:
        """Calculate time pressure score.

        Args:
            due_date: When commitment is due (None = no deadline)
            reference_date: Reference date for calculation (default: now)

        Returns:
            FactorResult with score and explanation
        """
        if due_date is None:
            return FactorResult(
                score=0.0,
                explanation="No due date",
                metadata={"has_due_date": False}
            )

        if reference_date is None:
            from datetime import timezone
            reference_date = datetime.now(timezone.utc)

        days_until = calculate_days_until(due_date, reference_date)

        # Exponential decay formula: 100 * exp(-days / 30)
        if days_until < 0:
            score = 100.0  # Overdue = maximum urgency
            explanation = f"Overdue by {abs(days_until)} days"
        else:
            score = 100.0 * math.exp(-days_until / 30.0)
            relative = format_relative_date(due_date, reference_date)
            explanation = f"Due {relative}"

        return FactorResult(
            score=round(score, 1),
            explanation=explanation,
            metadata={"days_until": days_until}
        )


class SeverityFactor:
    """Domain-based severity/risk scoring (25% weight).

    Different commitment domains have different risk profiles.

    Scoring (0-100 scale):
    - Legal/Compliance: 100 (highest risk)
    - Health: 90
    - Finance: 80
    - Customer: 60
    - Internal: 50
    - Maintenance: 40
    - Enhancement: 30
    - Personal: 10
    """

    WEIGHT = 0.25

    DOMAIN_SCORES = {
        "legal": 100,
        "compliance": 100,
        "health": 90,
        "finance": 80,
        "customer": 60,
        "internal": 50,
        "maintenance": 40,
        "enhancement": 30,
        "research": 20,
        "personal": 10,
    }

    @staticmethod
    def calculate(
        severity: Optional[int] = None,
        domain: Optional[str] = None
    ) -> FactorResult:
        """Calculate severity score.

        Args:
            severity: Manual severity rating 0-100 (overrides domain)
            domain: Domain category (legal, finance, health, etc.)

        Returns:
            FactorResult with score and explanation
        """
        if severity is not None:
            score = max(0.0, min(100.0, float(severity)))
            explanation = f"Manual severity: {score}/100"
            metadata = {"source": "manual", "severity": severity}
        elif domain:
            domain_lower = domain.lower()
            score = SeverityFactor.DOMAIN_SCORES.get(domain_lower, 50.0)
            explanation = f"{domain.title()} domain risk"
            metadata = {"source": "domain", "domain": domain}
        else:
            score = 50.0  # Default medium severity
            explanation = "Default severity (no domain specified)"
            metadata = {"source": "default"}

        return FactorResult(
            score=score,
            explanation=explanation,
            metadata=metadata
        )


class AmountFactor:
    """Financial impact scoring using logarithmic scale (15% weight).

    Prioritizes higher dollar amounts, with diminishing returns.

    Scoring:
    - $0-$100: 0-20
    - $100-$1,000: 20-50
    - $1,000-$10,000: 50-80
    - $10,000-$100,000: 80-100
    - $100,000+: 100
    """

    WEIGHT = 0.15

    @staticmethod
    def calculate(amount: Optional[float] = None) -> FactorResult:
        """Calculate financial impact score.

        Args:
            amount: Dollar amount (None = not applicable)

        Returns:
            FactorResult with score and explanation
        """
        if amount is None or amount <= 0:
            return FactorResult(
                score=0.0,
                explanation="No financial amount",
                metadata={"amount": None}
            )

        # Logarithmic scale: 100 * (log10(amount) / 5.0)
        # $1 = 0, $100 = 40, $1,000 = 60, $10,000 = 80, $100,000 = 100
        score = 100.0 * (math.log10(amount) / 5.0)
        score = max(0.0, min(100.0, score))

        # Format amount with commas
        if isinstance(amount, Decimal):
            amount_str = f"${amount:,.2f}"
        else:
            amount_str = f"${amount:,.2f}"

        return FactorResult(
            score=round(score, 1),
            explanation=f"Financial impact: {amount_str}",
            metadata={"amount_usd": float(amount)}
        )


class EffortFactor:
    """Effort-based scoring - prioritizes quick wins (15% weight).

    Lower effort commitments score higher (can be completed quickly).

    Scoring (inverted):
    - 0-1 hour: 100 (quick win)
    - 1-4 hours: 70-90
    - 4-8 hours: 50-70
    - 8-40 hours: 20-50
    - 40+ hours: 0-20
    """

    WEIGHT = 0.15

    @staticmethod
    def calculate(effort_hours: Optional[float] = None) -> FactorResult:
        """Calculate effort score (inverted - less effort = higher score).

        Args:
            effort_hours: Estimated hours to complete (None = unknown)

        Returns:
            FactorResult with score and explanation
        """
        if effort_hours is None or effort_hours <= 0:
            return FactorResult(
                score=50.0,  # Unknown effort = medium priority
                explanation="Effort unknown",
                metadata={"effort_hours": None}
            )

        # Inverted logarithmic: 100 * (1 - log10(hours) / 2.0)
        score = 100.0 * (1.0 - (math.log10(max(effort_hours, 0.1)) / 2.0))
        score = max(0.0, min(100.0, score))

        # Format effort
        if effort_hours < 1:
            minutes = int(effort_hours * 60)
            effort_str = f"{minutes}min"
        else:
            effort_str = f"{effort_hours:.1f}h"

        return FactorResult(
            score=round(score, 1),
            explanation=f"Quick win: {effort_str} effort",
            metadata={"effort_hours": effort_hours}
        )


class DependencyFactor:
    """Dependency-based scoring (10% weight).

    Commitments blocked by others score lower.
    Commitments blocking others score higher.

    Scoring:
    - Blocks others: 100
    - No dependencies: 50
    - Blocked by others: 0
    """

    WEIGHT = 0.10

    @staticmethod
    def calculate(
        is_blocked: bool = False,
        blocks_count: int = 0
    ) -> FactorResult:
        """Calculate dependency score.

        Args:
            is_blocked: True if blocked by other commitments
            blocks_count: Number of commitments this blocks

        Returns:
            FactorResult with score and explanation
        """
        if blocks_count > 0:
            score = 100.0
            explanation = f"Blocks {blocks_count} other commitment(s)"
            metadata = {"is_blocked": is_blocked, "blocks_count": blocks_count}
        elif is_blocked:
            score = 0.0
            explanation = "Blocked by dependencies"
            metadata = {"is_blocked": True, "blocks_count": 0}
        else:
            score = 50.0  # No dependencies = neutral
            explanation = "No dependencies"
            metadata = {"is_blocked": False, "blocks_count": 0}

        return FactorResult(
            score=score,
            explanation=explanation,
            metadata=metadata
        )


class PreferenceFactor:
    """User preference/manual boost (5% weight).

    Allows manual prioritization overrides.

    Scoring:
    - User flagged: 100
    - Default: 0
    """

    WEIGHT = 0.05

    @staticmethod
    def calculate(user_boost: bool = False) -> FactorResult:
        """Calculate user preference score.

        Args:
            user_boost: True if user manually flagged as high priority

        Returns:
            FactorResult with score and explanation
        """
        if user_boost:
            score = 100.0
            explanation = "User-flagged high priority"
            metadata = {"user_boost": True}
        else:
            score = 0.0
            explanation = ""
            metadata = {"user_boost": False}

        return FactorResult(
            score=score,
            explanation=explanation,
            metadata=metadata
        )

"""
Priority calculator for commitments using weighted multi-factor analysis.

Integrates 6 priority factors with configurable weights to produce
a final priority score (0-100) with explainable reasoning.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import yaml

from lib.shared.local_assistant_shared.utils.priority_calculator import (
    PriorityResult as SharedPriorityResult,
    calculate_priority as calculate_priority_shared,
)
from services.document_intelligence.priority.factors import (
    AmountFactor,
    DependencyFactor,
    EffortFactor,
    PreferenceFactor,
    SeverityFactor,
    TimeFactor,
)


@dataclass
class PriorityResult:
    """Result of priority calculation with explainability.

    Attributes:
        score: Final priority score (0-100, higher = more urgent)
        reason: Human-readable explanation
        factors: Dictionary of factor scores (0-100 scale)
        metadata: Additional context data
    """
    score: int
    reason: str
    factors: dict[str, float]
    metadata: dict


class PriorityCalculator:
    """Calculate commitment priority using weighted multi-factor analysis.

    Factors:
    1. Time Pressure (30%): Exponential decay based on due date
    2. Severity (25%): Domain-based risk scoring
    3. Amount (15%): Logarithmic financial impact
    4. Effort (15%): Quick wins prioritized (inverted)
    5. Dependency (10%): Blocked/blocking commitments
    6. User Preference (5%): Manual priority boost

    Example:
        >>> from datetime import datetime, timedelta, timezone
        >>> calculator = PriorityCalculator()
        >>> now = datetime.now(timezone.utc)
        >>> due_date = now + timedelta(days=2)
        >>> result = calculator.calculate(
        ...     due_date=due_date,
        ...     amount=12419.83,
        ...     domain="finance",
        ...     effort_hours=0.5
        ... )
        >>> result.score >= 80  # High priority
        True
        >>> "Due in 2 days" in result.reason or "in 2 days" in result.reason
        True
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize calculator with optional config file.

        Args:
            config_path: Path to YAML config file (default: auto-detect)
        """
        self.config = self._load_config(config_path)
        self.weights = self._extract_weights()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from YAML file.

        Args:
            config_path: Path to config file or None for default

        Returns:
            Configuration dictionary
        """
        if config_path is None:
            # Auto-detect config path
            import os
            project_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))
                    )
                )
            )
            config_path = os.path.join(
                project_root, "config", "commitment_priority_config.yaml"
            )

        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # Fall back to default weights
            return {
                "priority_weights": {
                    "time_pressure": 0.30,
                    "severity": 0.25,
                    "amount": 0.15,
                    "effort": 0.15,
                    "dependency": 0.10,
                    "user_preference": 0.05,
                }
            }

    def _extract_weights(self) -> dict:
        """Extract weights from config.

        Returns:
            Dictionary of factor weights
        """
        return self.config.get("priority_weights", {
            "time_pressure": 0.30,
            "severity": 0.25,
            "amount": 0.15,
            "effort": 0.15,
            "dependency": 0.10,
            "user_preference": 0.05,
        })

    def calculate(
        self,
        due_date: Optional[datetime] = None,
        amount: Optional[float] = None,
        severity: Optional[int] = None,
        domain: Optional[str] = None,
        effort_hours: Optional[float] = None,
        is_blocked: bool = False,
        blocks_count: int = 0,
        user_boost: bool = False,
        reference_date: Optional[datetime] = None,
    ) -> PriorityResult:
        """Calculate weighted priority score for a commitment.

        Args:
            due_date: When commitment is due (None = no deadline)
            amount: Financial amount in USD (None = not applicable)
            severity: Manual severity rating 0-100 (overrides domain)
            domain: Domain category (legal, finance, health, etc.)
            effort_hours: Estimated hours to complete (None = unknown)
            is_blocked: True if blocked by other commitments
            blocks_count: Number of commitments this blocks
            user_boost: True if user manually flagged as high priority
            reference_date: Reference date for time calculations (default: now)

        Returns:
            PriorityResult with score, reason, and factor breakdown

        Example:
            >>> from datetime import datetime, timedelta, timezone
            >>> calc = PriorityCalculator()
            >>> now = datetime.now(timezone.utc)
            >>> result = calc.calculate(
            ...     due_date=now + timedelta(days=2),
            ...     amount=12419.83,
            ...     domain="finance"
            ... )
            >>> result.score > 50
            True
        """
        # Calculate individual factor scores
        time_result = TimeFactor.calculate(due_date, reference_date)
        severity_result = SeverityFactor.calculate(severity, domain)
        amount_result = AmountFactor.calculate(amount)
        effort_result = EffortFactor.calculate(effort_hours)
        dependency_result = DependencyFactor.calculate(is_blocked, blocks_count)
        preference_result = PreferenceFactor.calculate(user_boost)

        # Calculate weighted score
        weighted_score = (
            time_result.score * self.weights["time_pressure"] +
            severity_result.score * self.weights["severity"] +
            amount_result.score * self.weights["amount"] +
            effort_result.score * self.weights["effort"] +
            dependency_result.score * self.weights["dependency"] +
            preference_result.score * self.weights["user_preference"]
        )

        # Round to integer (0-100 scale)
        final_score = int(round(weighted_score))

        # Build reason string from non-empty explanations
        reason_parts = []
        for result in [
            time_result,
            severity_result,
            amount_result,
            effort_result,
            dependency_result,
            preference_result,
        ]:
            if result.explanation:
                reason_parts.append(result.explanation)

        reason = ", ".join(reason_parts) if reason_parts else "No priority factors"

        # Collect factor scores
        factors = {
            "time_pressure": time_result.score,
            "severity": severity_result.score,
            "amount": amount_result.score,
            "effort": effort_result.score,
            "dependency": dependency_result.score,
            "user_preference": preference_result.score,
        }

        # Collect metadata
        metadata = {
            "time": time_result.metadata,
            "severity": severity_result.metadata,
            "amount": amount_result.metadata,
            "effort": effort_result.metadata,
            "dependency": dependency_result.metadata,
            "preference": preference_result.metadata,
            "weights": self.weights,
        }

        return PriorityResult(
            score=final_score,
            reason=reason,
            factors=factors,
            metadata=metadata,
        )

    def calculate_from_shared(
        self,
        due_date: Optional[datetime] = None,
        amount: Optional[float] = None,
        severity: Optional[int] = None,
        domain: Optional[str] = None,
        effort_hours: Optional[float] = None,
        is_blocked: bool = False,
        user_boost: bool = False,
        reference_date: Optional[datetime] = None,
    ) -> PriorityResult:
        """Calculate priority using shared utility function.

        This method uses the shared priority calculator from
        lib/shared/local_assistant_shared/utils/priority_calculator.py
        and converts the result to our PriorityResult format.

        Args:
            due_date: When commitment is due
            amount: Financial amount in USD
            severity: Manual severity rating 1-10
            domain: Domain category
            effort_hours: Estimated hours to complete
            is_blocked: True if blocked by dependencies
            user_boost: True if user-flagged
            reference_date: Reference date for calculations

        Returns:
            PriorityResult with score and reason
        """
        shared_result = calculate_priority_shared(
            due_date=due_date,
            amount=amount,
            severity=severity,
            domain=domain,
            effort_hours=effort_hours,
            is_blocked=is_blocked,
            user_boost=user_boost,
            reference_date=reference_date,
        )

        # Convert shared result to our format
        return PriorityResult(
            score=int(round(shared_result.score)),
            reason=shared_result.reason,
            factors=shared_result.factors,
            metadata=shared_result.normalized_factors,
        )

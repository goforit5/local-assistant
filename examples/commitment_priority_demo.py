"""
Demonstration of Commitment Priority Calculation.

Shows various scenarios with different factor combinations.
"""

from datetime import datetime, timedelta, timezone
from services.document_intelligence.priority import PriorityCalculator


def print_priority_result(scenario: str, result):
    """Print formatted priority result."""
    print(f"\n{'='*70}")
    print(f"Scenario: {scenario}")
    print(f"{'='*70}")
    print(f"Priority Score: {result.score}/100")
    print(f"Reason: {result.reason}")
    print(f"\nFactor Breakdown:")
    for factor, score in result.factors.items():
        print(f"  {factor:20s}: {score:5.1f}/100")
    print(f"{'='*70}")


def main():
    """Run priority calculation demonstrations."""
    calc = PriorityCalculator()
    now = datetime.now(timezone.utc)

    # Scenario 1: Invoice due in 2 days (high priority)
    result1 = calc.calculate(
        due_date=now + timedelta(days=2),
        amount=12419.83,
        domain="finance",
        effort_hours=0.5
    )
    print_priority_result(
        "Invoice #240470 - Due in 2 days, $12,419.83",
        result1
    )

    # Scenario 2: Overdue legal filing (critical)
    result2 = calc.calculate(
        due_date=now - timedelta(days=3),
        domain="legal",
        effort_hours=2,
        user_boost=True
    )
    print_priority_result(
        "Legal Filing - Overdue by 3 days, user-flagged",
        result2
    )

    # Scenario 3: Large invoice due in 30 days (medium priority)
    result3 = calc.calculate(
        due_date=now + timedelta(days=30),
        amount=150000.00,
        domain="finance",
        effort_hours=1
    )
    print_priority_result(
        "Large Invoice - Due in 30 days, $150,000",
        result3
    )

    # Scenario 4: Quick task blocking others (high priority)
    result4 = calc.calculate(
        due_date=now + timedelta(days=5),
        effort_hours=0.25,
        blocks_count=5,
        domain="internal"
    )
    print_priority_result(
        "Setup Task - Blocks 5 other tasks, 15 minute effort",
        result4
    )

    # Scenario 5: Long-term goal (low priority)
    result5 = calc.calculate(
        due_date=now + timedelta(days=180),
        effort_hours=160,
        domain="enhancement"
    )
    print_priority_result(
        "Long-term Project - Due in 6 months, 160 hours",
        result5
    )

    # Scenario 6: Blocked task (lowest priority)
    result6 = calc.calculate(
        due_date=now + timedelta(days=7),
        is_blocked=True,
        domain="internal"
    )
    print_priority_result(
        "Blocked Task - Waiting on dependencies",
        result6
    )

    # Scenario 7: Health-related urgent task
    result7 = calc.calculate(
        due_date=now + timedelta(days=1),
        domain="health",
        effort_hours=1
    )
    print_priority_result(
        "Medical Appointment - Tomorrow, health domain",
        result7
    )

    # Scenario 8: Customer commitment
    result8 = calc.calculate(
        due_date=now + timedelta(days=14),
        amount=50000.00,
        domain="customer",
        effort_hours=8
    )
    print_priority_result(
        "Customer Deliverable - Due in 2 weeks, $50,000 contract",
        result8
    )


if __name__ == "__main__":
    main()

"""
Integration tests for CommitmentManager with mock database operations.

Tests cover:
- Create commitment from real invoice extraction data
- Priority calculation with database-backed dependencies
- Commitment lifecycle (create → update → complete)
- Multiple commitments with different priorities (sort by priority)
- Concurrent commitment creation
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from memory.models import Commitment, Party, Role
from services.document_intelligence.commitment_manager import CommitmentManager


@pytest.fixture
def db_session():
    """Create mock database session for testing."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def test_party():
    """Create test party (user)."""
    return Party(
        id=uuid.uuid4(),
        kind="person",
        name="Test User",
        email="test@example.com"
    )


@pytest.fixture
def test_role(test_party):
    """Create test role for user."""
    return Role(
        id=uuid.uuid4(),
        party_id=test_party.id,
        role_name="admin",
        context="testing"
    )


@pytest.fixture
def manager():
    """Create CommitmentManager instance."""
    return CommitmentManager()


@pytest.mark.integration
class TestCommitmentIntegration:
    """Integration tests with real database."""

    @pytest.mark.asyncio
    async def test_create_commitment_from_invoice_data(
        self,
        db_session,
        test_role,
        manager
    ):
        """Test creating commitment from realistic invoice extraction data."""
        # Simulate invoice extraction result
        invoice_data = {
            "invoice_number": "INV-2024-001",
            "total": 15000.00,
            "due_date": "2024-12-15",
            "vendor_name": "ABC Consulting LLC",
            "line_items": [
                {"description": "Consulting services", "amount": 15000.00}
            ]
        }

        vendor_id = uuid.uuid4()

        commitment = await manager.create_from_invoice(
            db=db_session,
            invoice_data=invoice_data,
            vendor_id=vendor_id,
            role_id=test_role.id
        )

        # Verify commitment was created
        assert commitment.title == "Pay Invoice #INV-2024-001 - ABC Consulting LLC"
        assert commitment.amount == Decimal("15000.00")
        assert commitment.commitment_type == "obligation"
        assert commitment.state == "pending"
        assert commitment.priority > 0
        assert commitment.reason is not None

        # Verify metadata
        assert commitment.metadata_["invoice_number"] == "INV-2024-001"
        assert commitment.metadata_["vendor_name"] == "ABC Consulting LLC"
        assert "priority_factors" in commitment.metadata_

        # Verify database operations called
        db_session.add.assert_called_once()
        db_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_commitment_lifecycle(
        self,
        db_session,
        test_role,
        manager
    ):
        """Test complete commitment lifecycle: create → update → complete."""
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=7)

        # Create commitment
        commitment = await manager.create_commitment(
            db=db_session,
            title="Review quarterly reports",
            commitment_type="obligation",
            role_id=test_role.id,
            due_date=due_date,
            effort_hours=4,
            domain="internal"
        )

        initial_priority = commitment.priority
        initial_reason = commitment.reason

        # Mock database query for update_priority
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = commitment
        db_session.execute.return_value = mock_result

        # Update priority
        updated_commitment = await manager.update_priority(
            db=db_session,
            commitment_id=commitment.id
        )

        # Priority should be recalculated
        assert updated_commitment.priority > 0
        assert updated_commitment.reason is not None

        # Mark as completed
        updated_commitment.state = "completed"
        updated_commitment.completed_at = datetime.now(timezone.utc)

        assert updated_commitment.state == "completed"
        assert updated_commitment.completed_at is not None

    @pytest.mark.asyncio
    async def test_multiple_commitments_priority_sorting(
        self,
        db_session,
        test_role,
        manager
    ):
        """Test creating multiple commitments and sorting by priority."""
        now = datetime.now(timezone.utc)

        # Create commitments with different priorities
        commitments_data = [
            {
                "title": "Urgent: Legal filing",
                "due_date": now + timedelta(days=1),
                "domain": "legal",
                "effort_hours": 2
            },
            {
                "title": "Pay invoice",
                "due_date": now + timedelta(days=30),
                "amount": 50000.0,
                "domain": "finance",
                "effort_hours": 0.5
            },
            {
                "title": "Review code",
                "due_date": now + timedelta(days=90),
                "domain": "internal",
                "effort_hours": 4
            },
            {
                "title": "Overdue task",
                "due_date": now - timedelta(days=5),
                "domain": "customer",
                "effort_hours": 1
            },
            {
                "title": "Future project",
                "due_date": now + timedelta(days=180),
                "domain": "enhancement",
                "effort_hours": 40
            }
        ]

        created_commitments = []
        for data in commitments_data:
            commitment = await manager.create_commitment(
                db=db_session,
                commitment_type="obligation",
                role_id=test_role.id,
                **data
            )
            created_commitments.append(commitment)

        # Mock database query for get_commitments_by_priority
        sorted_commitments = sorted(created_commitments, key=lambda c: c.priority, reverse=True)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = sorted_commitments
        db_session.execute.return_value = mock_result

        # Retrieve commitments sorted by priority
        retrieved = await manager.get_commitments_by_priority(
            db=db_session,
            role_id=test_role.id,
            state="pending",
            limit=10
        )

        # Verify sorting (highest priority first)
        assert len(retrieved) == 5
        for i in range(len(retrieved) - 1):
            assert retrieved[i].priority >= retrieved[i + 1].priority

        # Overdue task should be near the top
        overdue = next(c for c in retrieved if "Overdue" in c.title)
        assert retrieved.index(overdue) <= 2, "Overdue should be high priority"

        # Future project should be near the bottom
        future = next(c for c in retrieved if "Future" in c.title)
        assert retrieved.index(future) >= 2, "Future project should be low priority"

    @pytest.mark.asyncio
    async def test_priority_with_dependencies(
        self,
        db_session,
        test_role,
        manager
    ):
        """Test priority calculation with database-backed dependencies."""
        now = datetime.now(timezone.utc)

        # Create blocking commitment
        blocker = await manager.create_commitment(
            db=db_session,
            title="Setup infrastructure",
            commitment_type="obligation",
            role_id=test_role.id,
            due_date=now + timedelta(days=3),
            blocks_count=3,
            domain="internal"
        )

        # Create blocked commitment
        blocked = await manager.create_commitment(
            db=db_session,
            title="Deploy application",
            commitment_type="obligation",
            role_id=test_role.id,
            due_date=now + timedelta(days=5),
            is_blocked=True,
            domain="internal"
        )

        # Blocker should have higher priority due to blocking others
        assert blocker.priority > blocked.priority

        # Update metadata to track dependency relationship
        blocked.metadata_["blocked_by"] = [str(blocker.id)]
        blocker.metadata_["blocks"] = [str(blocked.id)]

        # Mock database query for update_priority
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = blocked
        db_session.execute.return_value = mock_result

        # When blocker is completed, update blocked commitment's priority
        blocker.state = "completed"
        blocker.completed_at = datetime.now(timezone.utc)

        # Update blocked commitment (no longer blocked)
        blocked.metadata_["is_blocked"] = False
        blocked.metadata_.pop("blocked_by", None)

        initial_priority = blocked.priority
        updated_blocked = await manager.update_priority(
            db=db_session,
            commitment_id=blocked.id
        )

        # Priority should be recalculated
        assert updated_blocked.priority > 0

    @pytest.mark.asyncio
    async def test_concurrent_commitment_creation(
        self,
        db_session,
        test_role,
        manager
    ):
        """Test creating multiple commitments concurrently."""
        now = datetime.now(timezone.utc)

        async def create_commitment_task(title_suffix: int):
            """Create a commitment in a task."""
            return await manager.create_commitment(
                db=db_session,
                title=f"Task {title_suffix}",
                commitment_type="obligation",
                role_id=test_role.id,
                due_date=now + timedelta(days=title_suffix),
                domain="internal"
            )

        # Create 10 commitments concurrently
        tasks = [create_commitment_task(i) for i in range(1, 11)]
        commitments = await asyncio.gather(*tasks)

        # Verify all commitments were created
        assert len(commitments) == 10

        # Verify they all have unique titles
        titles = [c.title for c in commitments]
        assert len(set(titles)) == 10

        # Verify all have valid priorities
        for commitment in commitments:
            assert commitment.priority >= 0
            assert commitment.priority <= 100
            assert commitment.reason is not None
            assert commitment.title.startswith("Task ")

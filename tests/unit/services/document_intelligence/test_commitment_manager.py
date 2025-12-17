"""
Unit tests for CommitmentManager with priority calculation.

Tests cover:
- Priority calculation with all 6 factors
- Reason string generation
- Create commitment from invoice data
- Generic commitment creation
- Priority recalculation
- Edge cases (past due, very high amount, multiple factors)
"""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.models import Commitment
from services.document_intelligence.commitment_manager import CommitmentManager


@pytest.fixture
def manager():
    """Create CommitmentManager instance."""
    return CommitmentManager()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def role_id():
    """Create test role ID."""
    return uuid.uuid4()


@pytest.fixture
def vendor_id():
    """Create test vendor ID."""
    return uuid.uuid4()


class TestPriorityCalculation:
    """Test priority calculation with different factor combinations."""

    def test_time_factor_overdue(self, manager):
        """Test priority calculation for overdue commitment."""
        now = datetime.now(timezone.utc)
        past_due = now - timedelta(days=5)

        result = manager.priority_calculator.calculate(
            due_date=past_due,
            reference_date=now
        )

        # Overdue commitments should have high priority
        assert result.score >= 25, "Overdue should have high time pressure score"
        assert "Overdue" in result.reason or "overdue" in result.reason.lower()

    def test_time_factor_due_soon(self, manager):
        """Test priority calculation for commitment due in 2 days."""
        now = datetime.now(timezone.utc)
        due_soon = now + timedelta(days=2)

        result = manager.priority_calculator.calculate(
            due_date=due_soon,
            reference_date=now
        )

        # Due in 2 days should have very high priority
        assert result.score >= 20, "Due in 2 days should have high priority"
        assert "Due" in result.reason or "in 2 days" in result.reason

    def test_severity_factor_legal(self, manager):
        """Test priority calculation with legal domain (highest severity)."""
        result = manager.priority_calculator.calculate(
            domain="legal"
        )

        # Legal domain should contribute significantly
        assert result.factors["severity"] >= 90, "Legal domain should have high severity"
        assert "legal" in result.reason.lower()

    def test_severity_factor_finance(self, manager):
        """Test priority calculation with finance domain."""
        result = manager.priority_calculator.calculate(
            domain="finance"
        )

        # Finance domain should have high severity
        assert result.factors["severity"] >= 70, "Finance domain should have high severity"
        assert "finance" in result.reason.lower()

    def test_amount_factor_large(self, manager):
        """Test priority calculation with large amount ($100,000+)."""
        result = manager.priority_calculator.calculate(
            amount=120000.0
        )

        # Large amounts should contribute significantly
        assert result.factors["amount"] >= 80, "Large amount should have high score"
        assert "$120,000" in result.reason

    def test_amount_factor_medium(self, manager):
        """Test priority calculation with medium amount ($10,000)."""
        result = manager.priority_calculator.calculate(
            amount=12419.83
        )

        # Medium amounts should have moderate score
        assert 50 <= result.factors["amount"] <= 90, "Medium amount should have moderate score"
        assert "$12,419.83" in result.reason

    def test_effort_factor_quick_win(self, manager):
        """Test priority calculation for quick win (< 1 hour)."""
        result = manager.priority_calculator.calculate(
            effort_hours=0.5
        )

        # Quick wins should have high effort score (inverted)
        assert result.factors["effort"] >= 80, "Quick wins should have high effort score"

    def test_effort_factor_large_task(self, manager):
        """Test priority calculation for large task (40+ hours)."""
        result = manager.priority_calculator.calculate(
            effort_hours=160
        )

        # Large tasks should have low effort score
        assert result.factors["effort"] <= 50, "Large tasks should have low effort score"

    def test_dependency_factor_blocked(self, manager):
        """Test priority calculation for blocked commitment."""
        result = manager.priority_calculator.calculate(
            is_blocked=True
        )

        # Blocked commitments should have zero dependency score
        assert result.factors["dependency"] == 0, "Blocked should have zero dependency score"
        assert "blocked" in result.reason.lower() or "dependencies" in result.reason.lower()

    def test_dependency_factor_blocks_others(self, manager):
        """Test priority calculation for commitment blocking others."""
        result = manager.priority_calculator.calculate(
            blocks_count=3
        )

        # Commitments blocking others should have high dependency score
        assert result.factors["dependency"] >= 90, "Blocking others should have high dependency score"
        assert "3" in result.reason and "commitment" in result.reason.lower()

    def test_user_preference_boost(self, manager):
        """Test priority calculation with user boost."""
        result = manager.priority_calculator.calculate(
            user_boost=True
        )

        # User boost should contribute to score
        assert result.factors["user_preference"] >= 90, "User boost should have high score"
        assert "user" in result.reason.lower() or "flagged" in result.reason.lower()

    def test_combined_factors_high_priority(self, manager):
        """Test priority calculation with multiple high-priority factors."""
        now = datetime.now(timezone.utc)
        due_soon = now + timedelta(days=2)

        result = manager.priority_calculator.calculate(
            due_date=due_soon,
            amount=12419.83,
            domain="finance",
            effort_hours=0.5,
            reference_date=now
        )

        # Multiple high-priority factors should result in high overall score
        assert result.score >= 60, f"Combined factors should yield high priority, got {result.score}"
        assert "Due" in result.reason or "in 2 days" in result.reason
        assert "$12,419.83" in result.reason
        assert "finance" in result.reason.lower()

    def test_priority_score_range(self, manager):
        """Test that priority scores stay within valid range (0-100)."""
        now = datetime.now(timezone.utc)

        # Test minimum (no factors)
        result_min = manager.priority_calculator.calculate()
        assert 0 <= result_min.score <= 100, "Score should be in valid range"

        # Test maximum (all factors maxed)
        past_due = now - timedelta(days=10)
        result_max = manager.priority_calculator.calculate(
            due_date=past_due,
            amount=500000.0,
            domain="legal",
            effort_hours=0.25,
            blocks_count=5,
            user_boost=True,
            reference_date=now
        )
        assert 0 <= result_max.score <= 100, "Score should be in valid range"
        assert result_max.score >= 80, "All max factors should yield very high score"


class TestCommitmentCreation:
    """Test commitment creation methods."""

    @pytest.mark.asyncio
    async def test_create_from_invoice_basic(self, manager, mock_db, role_id, vendor_id):
        """Test creating commitment from invoice data."""
        invoice_data = {
            "invoice_number": "240470",
            "total": 12419.83,
            "due_date": "2024-03-15",
            "vendor_name": "Clipboard Health"
        }

        commitment = await manager.create_from_invoice(
            db=mock_db,
            invoice_data=invoice_data,
            vendor_id=vendor_id,
            role_id=role_id
        )

        # Verify commitment was created
        assert commitment is not None
        assert commitment.title == "Pay Invoice #240470 - Clipboard Health"
        assert commitment.commitment_type == "obligation"
        assert commitment.amount == Decimal("12419.83")
        assert commitment.priority > 0
        assert commitment.reason is not None
        assert commitment.severity == 80  # Finance domain

        # Verify metadata
        assert commitment.metadata_["invoice_number"] == "240470"
        assert commitment.metadata_["vendor_name"] == "Clipboard Health"
        assert "priority_factors" in commitment.metadata_

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_from_invoice_missing_fields(self, manager, mock_db, role_id, vendor_id):
        """Test error handling for missing invoice fields."""
        invoice_data = {
            "invoice_number": "240470",
            # Missing: total, vendor_name
        }

        with pytest.raises(ValueError, match="Missing required invoice fields"):
            await manager.create_from_invoice(
                db=mock_db,
                invoice_data=invoice_data,
                vendor_id=vendor_id,
                role_id=role_id
            )

    @pytest.mark.asyncio
    async def test_create_from_invoice_no_due_date(self, manager, mock_db, role_id, vendor_id):
        """Test creating commitment without due date."""
        invoice_data = {
            "invoice_number": "INV-001",
            "total": 500.0,
            "vendor_name": "Test Vendor"
            # No due_date
        }

        commitment = await manager.create_from_invoice(
            db=mock_db,
            invoice_data=invoice_data,
            vendor_id=vendor_id,
            role_id=role_id
        )

        assert commitment.due_date is None
        assert commitment.priority >= 0  # Should still calculate priority

    @pytest.mark.asyncio
    async def test_create_commitment_generic(self, manager, mock_db, role_id):
        """Test creating generic commitment."""
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=30)

        commitment = await manager.create_commitment(
            db=mock_db,
            title="Migrate to microservices",
            commitment_type="goal",
            role_id=role_id,
            due_date=due_date,
            effort_hours=160,
            domain="internal"
        )

        assert commitment.title == "Migrate to microservices"
        assert commitment.commitment_type == "goal"
        assert commitment.effort_minutes == 160 * 60
        assert commitment.priority > 0
        assert "priority_factors" in commitment.metadata_

    @pytest.mark.asyncio
    async def test_create_commitment_with_amount(self, manager, mock_db, role_id):
        """Test creating commitment with financial amount."""
        commitment = await manager.create_commitment(
            db=mock_db,
            title="Close investment round",
            commitment_type="goal",
            role_id=role_id,
            amount=1000000.0,
            domain="finance"
        )

        assert commitment.amount == Decimal("1000000.00")
        assert commitment.priority > 0
        assert "$1,000,000" in commitment.reason

    @pytest.mark.asyncio
    async def test_create_commitment_with_dependencies(self, manager, mock_db, role_id):
        """Test creating commitment with dependency tracking."""
        commitment = await manager.create_commitment(
            db=mock_db,
            title="Deploy database schema",
            commitment_type="obligation",
            role_id=role_id,
            blocks_count=5,
            domain="internal"
        )

        assert "5" in commitment.reason
        assert "commitment" in commitment.reason.lower()
        assert commitment.metadata_["priority_metadata"]["dependency"]["blocks_count"] == 5


class TestPriorityRecalculation:
    """Test priority recalculation for existing commitments."""

    @pytest.mark.asyncio
    async def test_update_priority_existing_commitment(self, manager, mock_db):
        """Test recalculating priority for existing commitment."""
        commitment_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=7)

        # Mock existing commitment
        existing_commitment = Commitment(
            id=commitment_id,
            role_id=uuid.uuid4(),
            title="Test Commitment",
            commitment_type="obligation",
            priority=50,
            reason="Old reason",
            state="pending",
            due_date=due_date.date(),
            amount=Decimal("1000.00"),
            severity=80,
            effort_minutes=30,
            metadata_={}
        )

        # Mock database query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_commitment
        mock_db.execute.return_value = mock_result

        # Update priority
        updated = await manager.update_priority(
            db=mock_db,
            commitment_id=commitment_id
        )

        # Verify priority was recalculated
        assert updated.priority != 50  # Should be different from original
        assert updated.reason != "Old reason"
        assert "priority_factors" in updated.metadata_

        # Verify database operations
        mock_db.execute.assert_called_once()
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_priority_not_found(self, manager, mock_db):
        """Test error handling when commitment not found."""
        commitment_id = uuid.uuid4()

        # Mock database query with no result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Commitment not found"):
            await manager.update_priority(
                db=mock_db,
                commitment_id=commitment_id
            )


class TestReasonStrings:
    """Test human-readable reason string generation."""

    def test_reason_string_comprehensive(self, manager):
        """Test reason string with all factors present."""
        now = datetime.now(timezone.utc)
        due_date = now + timedelta(days=2)

        result = manager.priority_calculator.calculate(
            due_date=due_date,
            amount=12419.83,
            domain="finance",
            effort_hours=0.5,
            blocks_count=2,
            user_boost=True,
            reference_date=now
        )

        reason = result.reason.lower()

        # Should mention all contributing factors
        assert "due" in reason or "in 2 days" in reason
        assert "$12,419.83" in result.reason  # Exact formatting
        assert "finance" in reason
        assert "2" in result.reason  # blocks_count
        assert "user" in reason or "flagged" in reason

    def test_reason_string_minimal(self, manager):
        """Test reason string with minimal factors."""
        result = manager.priority_calculator.calculate()

        # Should have default reason
        assert result.reason is not None
        assert len(result.reason) > 0

    def test_reason_string_overdue(self, manager):
        """Test reason string for overdue commitment."""
        now = datetime.now(timezone.utc)
        past_due = now - timedelta(days=10)

        result = manager.priority_calculator.calculate(
            due_date=past_due,
            reference_date=now
        )

        # Should clearly indicate overdue status
        assert "overdue" in result.reason.lower() or "10 days" in result.reason.lower()

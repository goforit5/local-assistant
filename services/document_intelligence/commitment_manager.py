"""
Commitment Manager for creating and managing commitments with priority calculation.

This service handles:
- Creating commitments from invoice data (auto-creation)
- Generic commitment creation with priority calculation
- Priority recalculation for existing commitments
- Explainable priority reasoning
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from memory.models import Commitment
from services.document_intelligence.priority import PriorityCalculator


class CommitmentManager:
    """Manage commitment lifecycle with intelligent priority calculation.

    Example:
        >>> from memory.database import get_db_session
        >>> manager = CommitmentManager()
        >>> async with get_db_session() as db:
        ...     commitment = await manager.create_from_invoice(
        ...         db=db,
        ...         invoice_data={
        ...             "invoice_number": "240470",
        ...             "total": 12419.83,
        ...             "due_date": "2024-03-15",
        ...             "vendor_name": "Clipboard Health"
        ...         },
        ...         vendor_id=uuid.uuid4(),
        ...         role_id=uuid.uuid4()
        ...     )
        ...     print(f"Priority: {commitment.priority}, Reason: {commitment.reason}")
    """

    def __init__(self):
        """Initialize CommitmentManager with priority calculator."""
        self.priority_calculator = PriorityCalculator()

    async def create_from_invoice(
        self,
        db: AsyncSession,
        invoice_data: dict,
        vendor_id: uuid.UUID,
        role_id: uuid.UUID,
        commitment_type: str = "obligation",
        domain: str = "finance",
    ) -> Commitment:
        """Create commitment from invoice data with automatic priority calculation.

        Args:
            db: Database session
            invoice_data: Invoice extraction data with keys:
                - invoice_number: Invoice number (str)
                - total: Invoice total amount (float or Decimal)
                - due_date: Due date (str or datetime)
                - vendor_name: Vendor name (str)
            vendor_id: Vendor party ID
            role_id: Role ID (user role for this commitment)
            commitment_type: Type of commitment (default: "obligation")
            domain: Domain for severity calculation (default: "finance")

        Returns:
            Created Commitment object with calculated priority

        Raises:
            ValueError: If required invoice data is missing
            KeyError: If invoice_data is missing required keys

        Example:
            >>> invoice_data = {
            ...     "invoice_number": "240470",
            ...     "total": 12419.83,
            ...     "due_date": "2024-03-15",
            ...     "vendor_name": "Clipboard Health"
            ... }
            >>> commitment = await manager.create_from_invoice(
            ...     db=db,
            ...     invoice_data=invoice_data,
            ...     vendor_id=vendor_id,
            ...     role_id=role_id
            ... )
        """
        # Validate required fields
        required_fields = ["invoice_number", "total", "vendor_name"]
        missing_fields = [f for f in required_fields if f not in invoice_data]
        if missing_fields:
            raise ValueError(f"Missing required invoice fields: {missing_fields}")

        # Extract invoice data
        invoice_number = invoice_data["invoice_number"]
        vendor_name = invoice_data["vendor_name"]
        total = invoice_data["total"]
        due_date_str = invoice_data.get("due_date")

        # Parse due date
        due_date = None
        if due_date_str:
            from lib.shared.local_assistant_shared.utils.date_utils import (
                parse_flexible_date,
            )
            if isinstance(due_date_str, str):
                due_date = parse_flexible_date(due_date_str)
            elif isinstance(due_date_str, datetime):
                due_date = due_date_str
            else:
                raise ValueError(f"Invalid due_date type: {type(due_date_str)}")

        # Convert total to Decimal for database
        if isinstance(total, (int, float)):
            amount = Decimal(str(total))
        elif isinstance(total, Decimal):
            amount = total
        else:
            amount = Decimal(str(total))

        # Calculate priority
        priority_result = self.priority_calculator.calculate(
            due_date=due_date,
            amount=float(amount),
            domain=domain,
            effort_hours=0.5,
        )

        # Build title
        title = f"Pay Invoice #{invoice_number} - {vendor_name}"

        # Build description
        description = f"Invoice #{invoice_number} from {vendor_name}\n"
        description += f"Amount: ${amount:,.2f}\n"
        if due_date:
            description += f"Due: {due_date.date()}\n"

        # Create commitment
        commitment = Commitment(
            role_id=role_id,
            title=title,
            description=description,
            commitment_type=commitment_type,
            priority=priority_result.score,
            reason=priority_result.reason,
            state="pending",
            due_date=due_date.date() if due_date else None,
            amount=amount,
            effort_minutes=30,
            severity=80,
            metadata_={
                "invoice_number": invoice_number,
                "vendor_id": str(vendor_id),
                "vendor_name": vendor_name,
                "priority_factors": priority_result.factors,
                "priority_metadata": priority_result.metadata,
            },
        )

        db.add(commitment)
        await db.flush()
        await db.refresh(commitment)

        return commitment

    async def create_invoice_commitment(
        self,
        db: AsyncSession,
        role_id: uuid.UUID,
        invoice_data: dict,
        vendor_name: str
    ) -> Commitment:
        """Legacy method for backward compatibility.

        Args:
            db: Database session
            role_id: Role ID
            invoice_data: Invoice data
            vendor_name: Vendor name

        Returns:
            Created Commitment
        """
        invoice_data["vendor_name"] = vendor_name
        vendor_id = uuid.uuid4()
        return await self.create_from_invoice(
            db=db,
            invoice_data=invoice_data,
            vendor_id=vendor_id,
            role_id=role_id
        )

    async def create_commitment(
        self,
        db: AsyncSession,
        title: str,
        commitment_type: str,
        role_id: uuid.UUID,
        description: Optional[str] = None,
        due_date: Optional[datetime] = None,
        amount: Optional[float] = None,
        severity: Optional[int] = None,
        domain: Optional[str] = None,
        effort_hours: Optional[float] = None,
        is_blocked: bool = False,
        blocks_count: int = 0,
        user_boost: bool = False,
        metadata: Optional[dict] = None,
    ) -> Commitment:
        """Create generic commitment with priority calculation.

        Args:
            db: Database session
            title: Commitment title (short description)
            commitment_type: Type: obligation, goal, routine
            role_id: Role ID (user role for this commitment)
            description: Long-form description (optional)
            due_date: When commitment is due (optional)
            amount: Financial amount in USD (optional)
            severity: Manual severity rating 0-100 (optional)
            domain: Domain category for severity (optional)
            effort_hours: Estimated hours to complete (optional)
            is_blocked: True if blocked by dependencies
            blocks_count: Number of commitments this blocks
            user_boost: True if user manually flagged
            metadata: Additional metadata (optional)

        Returns:
            Created Commitment object

        Example:
            >>> commitment = await manager.create_commitment(
            ...     db=db,
            ...     title="Migrate to microservices",
            ...     commitment_type="goal",
            ...     role_id=role_id,
            ...     due_date=datetime(2025, 6, 30),
            ...     effort_hours=160,
            ...     domain="internal"
            ... )
        """
        # Calculate priority if factors provided
        priority_result = self.priority_calculator.calculate(
            due_date=due_date,
            amount=amount,
            severity=severity,
            domain=domain,
            effort_hours=effort_hours,
            is_blocked=is_blocked,
            blocks_count=blocks_count,
            user_boost=user_boost,
        )

        # Convert amount to Decimal if provided
        amount_decimal = None
        if amount is not None:
            amount_decimal = Decimal(str(amount))

        # Merge priority metadata with user metadata
        combined_metadata = metadata or {}
        combined_metadata.update({
            "priority_factors": priority_result.factors,
            "priority_metadata": priority_result.metadata,
        })

        # Create commitment
        commitment = Commitment(
            role_id=role_id,
            title=title,
            description=description,
            commitment_type=commitment_type,
            priority=priority_result.score,
            reason=priority_result.reason,
            state="pending",
            due_date=due_date.date() if due_date else None,
            amount=amount_decimal,
            effort_minutes=int(effort_hours * 60) if effort_hours else None,
            severity=severity,
            metadata_=combined_metadata,
        )

        db.add(commitment)
        await db.flush()
        await db.refresh(commitment)

        return commitment

    async def update_priority(
        self,
        db: AsyncSession,
        commitment_id: uuid.UUID,
    ) -> Commitment:
        """Recalculate priority for existing commitment.

        Useful when:
        - Dependencies change (blocked/blocking status)
        - Time passes (due date approaches)
        - User manually updates commitment details

        Args:
            db: Database session
            commitment_id: Commitment ID to update

        Returns:
            Updated Commitment object

        Raises:
            ValueError: If commitment not found

        Example:
            >>> commitment = await manager.update_priority(
            ...     db=db,
            ...     commitment_id=commitment_id
            ... )
        """
        # Fetch commitment
        result = await db.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        commitment = result.scalar_one_or_none()

        if not commitment:
            raise ValueError(f"Commitment not found: {commitment_id}")

        # Extract current data
        due_date = None
        if commitment.due_date:
            # Convert date to datetime
            from datetime import timezone
            due_date = datetime.combine(
                commitment.due_date,
                datetime.min.time()
            ).replace(tzinfo=timezone.utc)

        amount = float(commitment.amount) if commitment.amount else None

        # Extract metadata for dependency tracking
        metadata = commitment.metadata_ or {}
        is_blocked = metadata.get("is_blocked", False)
        blocks_count = metadata.get("blocks_count", 0)
        user_boost = metadata.get("user_boost", False)

        # Calculate domain from severity or metadata
        domain = None
        if commitment.severity:
            # Map severity to domain (inverse of SeverityFactor.DOMAIN_SCORES)
            severity_to_domain = {
                100: "legal",
                90: "health",
                80: "finance",
                60: "customer",
                50: "internal",
                40: "maintenance",
                30: "enhancement",
                20: "research",
                10: "personal",
            }
            domain = severity_to_domain.get(commitment.severity, "internal")

        effort_hours = None
        if commitment.effort_minutes:
            effort_hours = commitment.effort_minutes / 60.0

        # Recalculate priority
        priority_result = self.priority_calculator.calculate(
            due_date=due_date,
            amount=amount,
            severity=commitment.severity,
            domain=domain,
            effort_hours=effort_hours,
            is_blocked=is_blocked,
            blocks_count=blocks_count,
            user_boost=user_boost,
        )

        # Update commitment
        commitment.priority = priority_result.score
        commitment.reason = priority_result.reason

        # Update metadata
        metadata["priority_factors"] = priority_result.factors
        metadata["priority_metadata"] = priority_result.metadata
        commitment.metadata_ = metadata

        await db.flush()
        await db.refresh(commitment)

        return commitment

    async def get_commitments_by_priority(
        self,
        db: AsyncSession,
        role_id: Optional[uuid.UUID] = None,
        state: str = "pending",
        limit: int = 20,
    ) -> list[Commitment]:
        """Get commitments sorted by priority (highest first).

        Args:
            db: Database session
            role_id: Filter by role ID (optional)
            state: Filter by state (default: "pending")
            limit: Maximum number of results (default: 20)

        Returns:
            List of commitments sorted by priority descending

        Example:
            >>> commitments = await manager.get_commitments_by_priority(
            ...     db=db,
            ...     role_id=role_id,
            ...     limit=10
            ... )
        """
        query = select(Commitment).where(Commitment.state == state)

        if role_id:
            query = query.where(Commitment.role_id == role_id)

        query = query.order_by(Commitment.priority.desc()).limit(limit)

        result = await db.execute(query)
        return list(result.scalars().all())

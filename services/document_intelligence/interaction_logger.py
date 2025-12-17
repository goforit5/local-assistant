"""
Interaction Logger for audit trail and time-travel debugging.

Provides append-only event logging to the interactions table with polymorphic
entity references.
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from decimal import Decimal
import uuid

from memory.models import Interaction


class InteractionLogger:
    """Logs interactions for audit trail.

    All methods create immutable Interaction records in the database with:
    - action: What happened (upload, extraction, entity_created, error)
    - entity_type: Type of entity acted upon (document, party, commitment)
    - entity_id: ID of entity acted upon (polymorphic reference)
    - details: Additional metadata (JSONB)
    - cost: Optional cost in USD
    - created_at: Timestamp when action occurred

    Example:
        logger = InteractionLogger()
        interaction = await logger.log_upload(
            db=db_session,
            user_id=user_uuid,
            document_id=doc_uuid,
            metadata={"filename": "invoice.pdf", "size": 1024000}
        )
        print(f"Logged interaction: {interaction.id}")
    """

    async def log_upload(
        self,
        db: AsyncSession,
        user_id: Optional[uuid.UUID],
        document_id: uuid.UUID,
        metadata: Dict[str, Any]
    ) -> Interaction:
        """Log document upload event.

        Args:
            db: Database session
            user_id: User who uploaded (nullable for system uploads)
            document_id: Document ID
            metadata: Upload metadata (filename, size, source, etc.)

        Returns:
            Created Interaction record

        Example:
            interaction = await logger.log_upload(
                db=db_session,
                user_id=None,
                document_id=doc.id,
                metadata={
                    "filename": "invoice.pdf",
                    "size": 1024000,
                    "mime_type": "application/pdf",
                    "source": "vision_upload"
                }
            )
        """
        interaction = Interaction(
            id=uuid.uuid4(),
            user_id=user_id,
            action="upload",
            entity_type="document",
            entity_id=document_id,
            details=metadata,
            cost=None,
            created_at=datetime.utcnow()
        )

        db.add(interaction)
        await db.flush()  # Pipeline manages transaction commit

        return interaction

    async def log_extraction(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
        cost: float,
        model: str,
        duration: float,
        metadata: Dict[str, Any]
    ) -> Interaction:
        """Log document extraction event.

        Args:
            db: Database session
            document_id: Document ID
            cost: Extraction cost in USD
            model: Model used (e.g., "gpt-4o", "claude-3-5-sonnet")
            duration: Processing duration in seconds
            metadata: Extraction metadata (pages_processed, extraction_type, etc.)

        Returns:
            Created Interaction record

        Example:
            interaction = await logger.log_extraction(
                db=db_session,
                document_id=doc.id,
                cost=0.0234,
                model="gpt-4o",
                duration=3.45,
                metadata={
                    "pages_processed": 3,
                    "extraction_type": "invoice",
                    "confidence": 0.95
                }
            )
        """
        interaction = Interaction(
            id=uuid.uuid4(),
            user_id=None,  # System action
            action="extraction",
            entity_type="document",
            entity_id=document_id,
            details={
                **metadata,
                "model": model,
                "duration_seconds": duration
            },
            cost=Decimal(str(cost)),
            created_at=datetime.utcnow()
        )

        db.add(interaction)
        await db.flush()

        return interaction

    async def log_entity_created(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: uuid.UUID,
        metadata: Dict[str, Any]
    ) -> Interaction:
        """Log entity creation event.

        Args:
            db: Database session
            entity_type: Type of entity (party, commitment, role, etc.)
            entity_id: Entity ID
            metadata: Entity creation metadata (name, details, etc.)

        Returns:
            Created Interaction record

        Example:
            interaction = await logger.log_entity_created(
                db=db_session,
                entity_type="party",
                entity_id=party.id,
                metadata={
                    "name": "Clipboard Health",
                    "kind": "org",
                    "created_new": True
                }
            )
        """
        interaction = Interaction(
            id=uuid.uuid4(),
            user_id=None,  # System action
            action="entity_created",
            entity_type=entity_type,
            entity_id=entity_id,
            details=metadata,
            cost=None,
            created_at=datetime.utcnow()
        )

        db.add(interaction)
        await db.flush()

        return interaction

    async def log_error(
        self,
        db: AsyncSession,
        error_type: str,
        error_message: str,
        metadata: Dict[str, Any]
    ) -> Interaction:
        """Log error event.

        Args:
            db: Database session
            error_type: Type of error (extraction_failed, validation_error, etc.)
            error_message: Error message
            metadata: Error context (stack_trace, input_data, etc.)

        Returns:
            Created Interaction record

        Example:
            interaction = await logger.log_error(
                db=db_session,
                error_type="extraction_failed",
                error_message="Vision API timeout",
                metadata={
                    "document_id": str(doc.id),
                    "stack_trace": "...",
                    "retry_count": 0
                }
            )
        """
        interaction = Interaction(
            id=uuid.uuid4(),
            user_id=None,  # System action
            action="error",
            entity_type=None,
            entity_id=None,
            details={
                **metadata,
                "error_type": error_type,
                "error_message": error_message
            },
            cost=None,
            created_at=datetime.utcnow()
        )

        db.add(interaction)
        await db.flush()

        return interaction

    async def log_custom(
        self,
        db: AsyncSession,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        cost: Optional[float] = None
    ) -> Interaction:
        """Log custom interaction event.

        Args:
            db: Database session
            action: Action name
            entity_type: Optional entity type
            entity_id: Optional entity ID
            user_id: Optional user ID
            details: Optional metadata
            cost: Optional cost in USD

        Returns:
            Created Interaction record

        Example:
            interaction = await logger.log_custom(
                db=db_session,
                action="signal_processed",
                entity_type="signal",
                entity_id=signal.id,
                details={"status": "attached"}
            )
        """
        interaction = Interaction(
            id=uuid.uuid4(),
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            cost=Decimal(str(cost)) if cost is not None else None,
            created_at=datetime.utcnow()
        )

        db.add(interaction)
        await db.flush()

        return interaction

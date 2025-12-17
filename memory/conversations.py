"""Conversation management with async SQLAlchemy."""

import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import selectinload

from memory.models import Base, Conversation, Message, CostEntry


class ConversationManager:
    """Manages conversation persistence with async SQLAlchemy."""

    def __init__(self, database_url: Optional[str] = None):
        """Initialize conversation manager.

        Args:
            database_url: PostgreSQL async connection string.
                         Defaults to DATABASE_URL environment variable.
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://localhost/local_assistant"
        )
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def initialize(self) -> None:
        """Initialize database connection and create tables."""
        self.engine = create_async_engine(
            self.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()

    async def create_conversation(
        self,
        title: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """Create a new conversation.

        Args:
            title: Conversation title
            metadata: Optional metadata dictionary

        Returns:
            Created conversation object
        """
        async with self.session_factory() as session:
            conversation = Conversation(
                title=title,
                metadata_=metadata
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def get_conversation(
        self,
        conversation_id: uuid.UUID,
        include_messages: bool = True
    ) -> Optional[Conversation]:
        """Get conversation by ID.

        Args:
            conversation_id: UUID of conversation
            include_messages: Whether to load messages

        Returns:
            Conversation object or None if not found
        """
        async with self.session_factory() as session:
            query = select(Conversation).where(Conversation.id == conversation_id)

            if include_messages:
                query = query.options(selectinload(Conversation.messages))

            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def list_conversations(
        self,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "updated_at"
    ) -> List[Conversation]:
        """List conversations with pagination.

        Args:
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            order_by: Field to order by (updated_at or created_at)

        Returns:
            List of conversation objects
        """
        async with self.session_factory() as session:
            order_column = (
                Conversation.updated_at if order_by == "updated_at"
                else Conversation.created_at
            )

            query = (
                select(Conversation)
                .order_by(desc(order_column))
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def update_conversation(
        self,
        conversation_id: uuid.UUID,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Conversation]:
        """Update conversation.

        Args:
            conversation_id: UUID of conversation
            title: New title (optional)
            metadata: New metadata (optional)

        Returns:
            Updated conversation or None if not found
        """
        async with self.session_factory() as session:
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()

            if not conversation:
                return None

            if title is not None:
                conversation.title = title
            if metadata is not None:
                conversation.metadata_ = metadata

            conversation.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(conversation)
            return conversation

    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool:
        """Delete conversation and associated messages.

        Args:
            conversation_id: UUID of conversation

        Returns:
            True if deleted, False if not found
        """
        async with self.session_factory() as session:
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()

            if not conversation:
                return False

            await session.delete(conversation)
            await session.commit()
            return True

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Add message to conversation.

        Args:
            conversation_id: UUID of conversation
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata dictionary

        Returns:
            Created message object
        """
        async with self.session_factory() as session:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata_=metadata
            )
            session.add(message)

            # Update conversation updated_at
            query = select(Conversation).where(Conversation.id == conversation_id)
            result = await session.execute(query)
            conversation = result.scalar_one_or_none()
            if conversation:
                conversation.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(message)
            return message

    async def get_messages(
        self,
        conversation_id: uuid.UUID,
        limit: Optional[int] = None
    ) -> List[Message]:
        """Get messages for a conversation.

        Args:
            conversation_id: UUID of conversation
            limit: Optional limit on number of messages

        Returns:
            List of message objects ordered by creation time
        """
        async with self.session_factory() as session:
            query = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
            )

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def add_cost_entry(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        conversation_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CostEntry:
        """Add cost tracking entry.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost_usd: Cost in USD
            conversation_id: Optional conversation UUID
            metadata: Optional metadata dictionary

        Returns:
            Created cost entry object
        """
        async with self.session_factory() as session:
            cost_entry = CostEntry(
                conversation_id=conversation_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_usd=cost_usd,
                metadata_=metadata
            )
            session.add(cost_entry)
            await session.commit()
            await session.refresh(cost_entry)
            return cost_entry

    async def get_total_cost(
        self,
        conversation_id: Optional[uuid.UUID] = None,
        model: Optional[str] = None
    ) -> float:
        """Calculate total cost.

        Args:
            conversation_id: Optional filter by conversation
            model: Optional filter by model

        Returns:
            Total cost in USD
        """
        async with self.session_factory() as session:
            query = select(func.sum(CostEntry.cost_usd))

            if conversation_id:
                query = query.where(CostEntry.conversation_id == conversation_id)
            if model:
                query = query.where(CostEntry.model == model)

            result = await session.execute(query)
            total = result.scalar()
            return float(total) if total else 0.0

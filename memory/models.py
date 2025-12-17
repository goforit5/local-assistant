"""SQLAlchemy models for memory persistence."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CHAR,
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Conversation(Base):
    """Conversation thread with metadata."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    __table_args__ = (
        Index("idx_conversation_created", "created_at"),
        Index("idx_conversation_updated", "updated_at"),
    )


class Message(Base):
    """Individual message within a conversation."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages"
    )

    __table_args__ = (
        Index("idx_message_conversation", "conversation_id"),
        Index("idx_message_created", "created_at"),
        Index("idx_message_role", "role"),
    )


class Document(Base):
    """Cached document with metadata and Life Graph integration.

    Enhanced with:
    - Content-addressable storage (SHA-256)
    - File metadata (MIME type, size, source)
    - Storage backend flexibility (local, S3, Azure)
    - AI extraction tracking (type, data, cost, timestamp)
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
        index=True,
        comment="File path or identifier"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Document content (text, markdown, etc.)"
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Hash of content for deduplication"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        index=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional metadata"
    )

    # Life Graph enhancement columns (migration 003)
    sha256: Mapped[Optional[str]] = mapped_column(
        CHAR(64),
        nullable=True,
        unique=True,
        comment="SHA-256 hash of file content (content-addressable storage key)"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Source of document: upload, email, scan, api, etc."
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type: application/pdf, image/png, text/plain, etc."
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="File size in bytes"
    )
    storage_uri: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="URI to actual file: file:///data/documents/<sha256>.pdf, s3://bucket/key, etc."
    )
    extraction_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of extraction: invoice, receipt, contract, form, structured, ocr, etc."
    )
    extraction_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Extracted structured data (invoice fields, receipt items, etc.)"
    )
    extraction_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment="Cost of extraction in USD (GPT-4o, Azure Doc Intel, etc.)"
    )
    extracted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when extraction was performed"
    )

    # Relationships
    document_links: Mapped[list["DocumentLink"]] = relationship(
        "DocumentLink",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_document_path", "path"),
        Index("idx_document_hash", "content_hash"),
        Index("idx_document_updated", "updated_at"),
        Index("idx_documents_sha256_unique", "sha256", unique=True),
        Index("idx_documents_extraction_type", "extraction_type"),
        Index("idx_documents_source", "source"),
    )


class CostEntry(Base):
    """Track LLM API costs per request."""

    __tablename__ = "cost_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(nullable=False)
    output_tokens: Mapped[int] = mapped_column(nullable=False)
    total_tokens: Mapped[int] = mapped_column(nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True
    )

    __table_args__ = (
        Index("idx_cost_conversation", "conversation_id"),
        Index("idx_cost_model", "model"),
        Index("idx_cost_created", "created_at"),
    )


# ========== Life Graph Models ==========


class Party(Base):
    """Vendors, customers, contacts (organizations and people).

    Represents any external entity the user interacts with:
    - Organizations: Clipboard Health, AWS, landlord's LLC
    - People: John Doe (vendor contact), Jane Smith (customer)
    """

    __tablename__ = "parties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type: org, person"
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name (company or person name)"
    )
    tax_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="EIN, SSN, or other tax identifier"
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full address (street, city, state, zip, country)"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Primary phone number"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Primary email address"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional fields (website, contact_person, etc.)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        back_populates="party",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_parties_kind", "kind"),
        Index("idx_parties_tax_id", "tax_id"),
    )


class Role(Base):
    """Context-specific user identities.

    Examples:
    - "Andrew as Customer at Clipboard Health"
    - "Andrew as Admin in Local Assistant"
    - "Andrew as Viewer for vendor invoices"
    """

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    party_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to parties table"
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="FK to users table (if applicable)"
    )
    role_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Role type: customer, vendor, admin, viewer, etc."
    )
    context: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment='Contextual information (e.g., "at Clipboard Health")'
    )
    permissions: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Role-specific permissions (read, write, admin)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    party: Mapped["Party"] = relationship(
        "Party",
        back_populates="roles"
    )
    commitments: Mapped[list["Commitment"]] = relationship(
        "Commitment",
        back_populates="role",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_roles_party_id", "party_id"),
        Index("idx_roles_user_id", "user_id"),
    )


class Commitment(Base):
    """Obligations, goals, routines with priority calculation.

    Examples:
    - Obligation: "Pay Invoice #240470 - Clipboard Health (due in 2 days, $12,419.83)"
    - Goal: "Migrate to microservices by Q2 2025"
    - Routine: "Weekly team standup every Monday at 10am"
    """

    __tablename__ = "commitments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to roles table"
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment='Short description (e.g., "Pay Invoice #240470 - Clipboard Health")'
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Long-form details"
    )
    commitment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type: obligation, goal, routine"
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="Priority score (0-100, higher = more urgent)"
    )
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment='Explainability: why this priority? (e.g., "Due in 2 days, $12,419.83, legal risk")'
    )
    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        comment="State: pending, in_progress, completed, cancelled"
    )
    due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="When this commitment is due"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this commitment was completed"
    )
    effort_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated effort in minutes"
    )
    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Monetary amount (for financial commitments)"
    )
    severity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Domain-based severity (legal=10, finance=8, etc.)"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional fields (tags, dependencies, etc.)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="commitments"
    )

    __table_args__ = (
        Index("idx_commitments_role_id", "role_id"),
        Index("idx_commitments_state_due_date", "state", "due_date"),
        Index("idx_commitments_priority", "priority"),
    )


class Signal(Base):
    """Raw inputs with idempotency (prevent duplicate processing).

    Examples:
    - vision_upload: User uploads invoice.pdf → Signal created with dedupe_key=sha256
    - email: Inbox receives invoice → Signal created with dedupe_key=message_id
    - api: External API sends webhook → Signal created with dedupe_key=webhook_id
    """

    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Source of signal: vision_upload, email, api, scan, etc."
    )
    dedupe_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        comment="Idempotency key (typically SHA-256 hash or unique identifier)"
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Raw input data (filename, size, metadata, etc.)"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="new",
        index=True,
        comment="Processing status: new, processing, attached, error"
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When signal was processed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    __table_args__ = (
        Index("idx_signals_dedupe_key_unique", "dedupe_key", unique=True),
        Index("idx_signals_source", "source"),
        Index("idx_signals_status", "status"),
        Index("idx_signals_status_created_at", "status", "created_at"),
    )


class DocumentLink(Base):
    """Polymorphic links between documents and entities.

    Examples:
    - Link invoice.pdf to vendor (party)
    - Link invoice.pdf to commitment ("Pay Invoice #240470")
    - Link invoice.pdf to signal (upload event)
    """

    __tablename__ = "document_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to documents table"
    )
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of linked entity: party, commitment, signal, role, etc."
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of linked entity (polymorphic)"
    )
    link_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of link: extracted_from, attached_to, related_to, etc."
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Additional link metadata (confidence, extraction_method, etc.)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="document_links"
    )

    __table_args__ = (
        Index("idx_document_links_document_id", "document_id"),
        Index("idx_document_links_entity", "entity_type", "entity_id"),
        Index("idx_document_links_link_type", "link_type"),
    )


class Interaction(Base):
    """Immutable event log for audit trail and time-travel debugging.

    Examples:
    - upload_document: User uploads invoice.pdf
    - create_commitment: System creates "Pay Invoice" commitment
    - resolve_vendor: System resolves "Clipboard Health" as vendor
    """

    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="FK to users table (if applicable, nullable for system actions)"
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Action performed: upload_document, create_commitment, resolve_vendor, etc."
    )
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of entity acted upon: document, party, commitment, etc."
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="ID of entity acted upon (polymorphic)"
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Action details (input data, results, errors, etc.)"
    )
    cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6),
        nullable=True,
        comment="Cost of action in USD (API calls, compute, etc.)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("idx_interactions_user_id", "user_id"),
        Index("idx_interactions_entity", "entity_type", "entity_id"),
        Index("idx_interactions_action", "action"),
        Index("idx_interactions_created_at", "created_at"),
    )


# ============================================================================
# EMAIL SYSTEM MODELS (Superhuman-grade Gmail integration)
# ============================================================================


class EmailAccount(Base):
    """Gmail account with OAuth credentials and sync state."""

    __tablename__ = "email_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email_address: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Gmail email address"
    )

    # OAuth tokens (encrypted)
    access_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted OAuth access token"
    )
    refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted OAuth refresh token"
    )
    token_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When access token expires"
    )
    last_token_refresh: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful token refresh"
    )

    # Sync state
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful sync completion"
    )
    history_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Gmail history ID for incremental sync"
    )
    total_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total message count"
    )
    sync_in_progress: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        index=True,
        comment="Sync currently running"
    )

    # Push notifications (Google Cloud Pub/Sub)
    watch_active: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        comment="Push notification watch active"
    )
    watch_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When watch expires (7 days max)"
    )
    pubsub_topic_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Cloud Pub/Sub topic name"
    )
    watch_last_renewed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful watch renewal"
    )
    watch_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Last watch setup error"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=True,
        nullable=False,
        comment="Account active and authorized"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    emails = relationship("Email", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_email_accounts_email", "email_address"),
        Index("idx_email_accounts_history_id", "history_id"),
        Index("idx_email_accounts_sync_in_progress", "sync_in_progress"),
        Index("idx_email_accounts_is_active", "is_active"),
    )


class Email(Base):
    """Email message with full content and metadata."""

    __tablename__ = "emails"

    # Gmail message ID as primary key
    id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        comment="Gmail message ID"
    )
    thread_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Gmail thread ID (conversation)"
    )
    account_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("email_accounts.email_address", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Account this email belongs to"
    )

    # Email headers
    subject: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Email subject line"
    )
    sender: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="From address"
    )
    recipient: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="To addresses (comma-separated)"
    )
    date_received: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When email was received"
    )

    # Content (Superhuman-style full storage)
    body_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Plain text body"
    )
    body_html: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="HTML body"
    )
    snippet: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Preview snippet (first 200 chars)"
    )

    # Gmail metadata
    labels: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Gmail labels (JSON array)"
    )
    is_read: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        index=True,
        comment="Read status"
    )
    is_starred: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        comment="Starred/important"
    )

    # Fast triage (pre-AI classification)
    fast_category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="newsletter|work|personal|transactional"
    )
    fast_priority: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="high|normal|low"
    )
    sender_importance: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="vip|known|unknown"
    )

    # Processing state
    content_fetched: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        comment="Full content downloaded"
    )
    triage_completed: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        comment="Fast triage complete"
    )
    analysis_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        comment="pending|processing|completed|skipped"
    )

    # Threading
    is_thread_starter: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        index=True,
        comment="First email in thread"
    )
    thread_position: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Position in thread (0-based)"
    )

    # Storage tier (data retention)
    storage_tier: Mapped[str] = mapped_column(
        String(20),
        default="hot",
        nullable=False,
        index=True,
        comment="hot|warm|cold|archived"
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When moved to archive tier"
    )
    last_accessed: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last access time (for caching)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    account = relationship("EmailAccount", back_populates="emails")
    attachments = relationship("EmailAttachment", back_populates="email", cascade="all, delete-orphan")
    analysis = relationship("EmailAnalysis", back_populates="email", uselist=False)

    __table_args__ = (
        Index("idx_emails_thread_id", "thread_id"),
        Index("idx_emails_account_email", "account_email"),
        Index("idx_emails_sender", "sender"),
        Index("idx_emails_date_received", "date_received"),
        Index("idx_emails_thread_date", "thread_id", "date_received"),
        Index("idx_emails_sender_date", "sender", "date_received"),
        Index("idx_emails_account_date", "account_email", "date_received"),
        Index("idx_emails_is_read", "account_email", "is_read", "date_received"),
        Index("idx_emails_fast_priority", "account_email", "fast_priority", "date_received"),
        Index("idx_emails_storage_tier", "storage_tier", "date_received"),
        Index("idx_emails_is_thread_starter", "is_thread_starter"),
    )


class EmailAttachment(Base):
    """Email attachment with content-addressable storage."""

    __tablename__ = "email_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Email this attachment belongs to"
    )

    # Gmail metadata
    attachment_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Gmail attachment ID"
    )
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Original filename"
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type"
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )

    # Content-addressable storage (aligned with existing system)
    content_hash: Mapped[Optional[str]] = mapped_column(
        CHAR(64),
        nullable=True,
        index=True,
        comment="SHA-256 hash of content"
    )
    storage_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Storage path or S3 key"
    )
    storage_type: Mapped[str] = mapped_column(
        String(20),
        default="local",
        nullable=False,
        comment="local|s3"
    )

    # Processing state
    downloaded: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        comment="Attachment downloaded from Gmail"
    )
    processed: Mapped[bool] = mapped_column(
        Integer,  # SQLite compatibility
        default=False,
        nullable=False,
        comment="Sent to document pipeline"
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="Created document (if processed)"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    email = relationship("Email", back_populates="attachments")
    document = relationship("Document")

    __table_args__ = (
        Index("idx_email_attachments_email_id", "email_id"),
        Index("idx_email_attachments_content_hash", "content_hash"),
        Index("idx_email_attachments_processed", "processed"),
    )


class EmailAnalysis(Base):
    """AI analysis results for emails (selective processing)."""

    __tablename__ = "email_analysis"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("emails.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="Email analyzed"
    )

    # AI classification
    refined_category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="AI-refined category"
    )
    actionable: Mapped[Optional[bool]] = mapped_column(
        Integer,  # SQLite compatibility
        nullable=True,
        comment="Requires user action"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="AI-generated summary"
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Classification confidence (0.0-1.0)"
    )

    # Processing metadata
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="AI model used"
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Token count (cost tracking)"
    )
    processing_time_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Processing duration"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error if processing failed"
    )

    # Relationship
    email = relationship("Email", back_populates="analysis")

    __table_args__ = (
        Index("idx_email_analysis_email_id", "email_id"),
    )

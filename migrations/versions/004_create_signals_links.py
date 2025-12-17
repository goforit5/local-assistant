"""Create signals, document_links, and interactions tables

Revision ID: 004
Revises: 003
Create Date: 2025-11-06

Tables created:
- signals: Raw inputs with idempotency (dedupe_key prevents duplicate processing)
- document_links: Polymorphic links between documents and any entity (parties, commitments, etc.)
- interactions: Immutable event log for audit trail and time-travel debugging
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create signal processing, document linking, and interaction logging tables.

    Tables:
    1. signals: Raw inputs with idempotency checking (prevent duplicate processing)
    2. document_links: Polymorphic links between documents and entities
    3. interactions: Immutable event log for audit trail
    """

    # ========== signals table ==========
    # Raw inputs with idempotency (dedupe_key prevents duplicate processing)
    op.create_table(
        'signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('source', sa.String(100), nullable=False, comment='Source of signal: vision_upload, email, api, scan, etc.'),
        sa.Column('dedupe_key', sa.String(255), nullable=False, comment='Idempotency key (typically SHA-256 hash or unique identifier)'),
        sa.Column('payload', postgresql.JSONB, nullable=False, comment='Raw input data (filename, size, metadata, etc.)'),
        sa.Column('status', sa.String(50), nullable=False, default='new', comment='Processing status: new, processing, attached, error'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True, comment='When signal was processed'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        comment='Raw inputs with idempotency (prevent duplicate processing)'
    )

    # Unique index on dedupe_key for idempotency
    # Same dedupe_key → same signal (prevent duplicate processing)
    op.create_index('idx_signals_dedupe_key_unique', 'signals', ['dedupe_key'], unique=True)

    # Index for source filtering
    op.create_index('idx_signals_source', 'signals', ['source'], unique=False)

    # Index for status filtering (find unprocessed signals)
    op.create_index('idx_signals_status', 'signals', ['status'], unique=False)

    # Compound index for status + created_at (find oldest unprocessed signals)
    op.create_index('idx_signals_status_created_at', 'signals', ['status', 'created_at'], unique=False)

    # ========== document_links table ==========
    # Polymorphic links between documents and any entity
    # Example: Link invoice.pdf to vendor (party), commitment (pay invoice), signal (upload event)
    op.create_table(
        'document_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False, comment='FK to documents table'),
        sa.Column('entity_type', sa.String(50), nullable=False, comment='Type of linked entity: party, commitment, signal, role, etc.'),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False, comment='ID of linked entity (polymorphic)'),
        sa.Column('link_type', sa.String(50), nullable=True, comment='Type of link: extracted_from, attached_to, related_to, etc.'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}', comment='Additional link metadata (confidence, extraction_method, etc.)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        comment='Polymorphic links between documents and entities (parties, commitments, signals, etc.)'
    )

    # Foreign key to documents table
    op.create_foreign_key('fk_document_links_document_id', 'document_links', 'documents', ['document_id'], ['id'], ondelete='CASCADE')

    # Compound index for entity lookups (find all documents linked to a specific entity)
    op.create_index('idx_document_links_entity', 'document_links', ['entity_type', 'entity_id'], unique=False)

    # Index for document_id lookups (find all entities linked to a specific document)
    op.create_index('idx_document_links_document_id', 'document_links', ['document_id'], unique=False)

    # Index for link_type filtering
    op.create_index('idx_document_links_link_type', 'document_links', ['link_type'], unique=False)

    # ========== interactions table ==========
    # Immutable event log for audit trail and time-travel debugging
    op.create_table(
        'interactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True, comment='FK to users table (if applicable, nullable for system actions)'),
        sa.Column('action', sa.String(100), nullable=False, comment='Action performed: upload_document, create_commitment, resolve_vendor, etc.'),
        sa.Column('entity_type', sa.String(50), nullable=True, comment='Type of entity acted upon: document, party, commitment, etc.'),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True, comment='ID of entity acted upon (polymorphic)'),
        sa.Column('details', postgresql.JSONB, nullable=True, comment='Action details (input data, results, errors, etc.)'),
        sa.Column('cost', sa.Numeric(10, 6), nullable=True, comment='Cost of action in USD (API calls, compute, etc.)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        comment='Immutable event log for audit trail and time-travel debugging'
    )

    # Index for user_id lookups (find all actions by user)
    op.create_index('idx_interactions_user_id', 'interactions', ['user_id'], unique=False)

    # Compound index for entity lookups (find all interactions for a specific entity)
    op.create_index('idx_interactions_entity', 'interactions', ['entity_type', 'entity_id'], unique=False)

    # Index for action filtering
    op.create_index('idx_interactions_action', 'interactions', ['action'], unique=False)

    # Index for created_at sorting (chronological order)
    op.create_index('idx_interactions_created_at', 'interactions', ['created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})


def downgrade() -> None:
    """
    Drop signals, document_links, and interactions tables.

    Order is important: drop child tables before parent tables.
    """
    # Drop indexes first
    op.drop_index('idx_interactions_created_at', table_name='interactions')
    op.drop_index('idx_interactions_action', table_name='interactions')
    op.drop_index('idx_interactions_entity', table_name='interactions')
    op.drop_index('idx_interactions_user_id', table_name='interactions')

    op.drop_index('idx_document_links_link_type', table_name='document_links')
    op.drop_index('idx_document_links_document_id', table_name='document_links')
    op.drop_index('idx_document_links_entity', table_name='document_links')

    op.drop_index('idx_signals_status_created_at', table_name='signals')
    op.drop_index('idx_signals_status', table_name='signals')
    op.drop_index('idx_signals_source', table_name='signals')
    op.drop_index('idx_signals_dedupe_key_unique', table_name='signals')

    # Drop foreign keys
    op.drop_constraint('fk_document_links_document_id', 'document_links', type_='foreignkey')

    # Drop tables
    op.drop_table('interactions')
    op.drop_table('document_links')
    op.drop_table('signals')

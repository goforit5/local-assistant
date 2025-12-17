"""Enhance documents table with SHA-256, extraction metadata, and storage info

Revision ID: 003
Revises: 002
Create Date: 2025-11-06

Changes to documents table:
- Add sha256 column for content-addressable storage and deduplication
- Add source, mime_type, file_size for file metadata
- Add storage_uri for flexible storage backends (local, S3, Azure)
- Add extraction_type, extraction_data, extraction_cost, extracted_at for AI processing metadata
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create or enhance the documents table with Life Graph integration fields.

    If the table doesn't exist, create it with base schema from memory/models.py.
    Then add Life Graph columns:
    - sha256: Content-addressable storage key (deduplication)
    - source: Where did this document come from? (upload, email, scan, api)
    - mime_type: MIME type (application/pdf, image/png, etc.)
    - file_size: Size in bytes
    - storage_uri: URI to actual file (file:///data/documents/<sha256>.pdf, s3://bucket/key, etc.)
    - extraction_type: Type of extraction performed (invoice, receipt, contract, form, etc.)
    - extraction_data: JSON containing extracted structured data
    - extraction_cost: Cost of extraction in USD (GPT-4o, Azure Doc Intel, etc.)
    - extracted_at: Timestamp of extraction
    """

    # Create documents table if it doesn't exist (base schema from memory/models.py)
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('path', sa.String(1024), nullable=False, unique=True, comment='File path or identifier'),
        sa.Column('content', sa.Text, nullable=False, comment='Document content (text, markdown, etc.)'),
        sa.Column('content_hash', sa.String(64), nullable=False, comment='Hash of content for deduplication'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}', comment='Additional metadata'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),

        comment='Cached documents with content and metadata'
    )

    # Create indexes for base schema
    op.create_index('idx_documents_id', 'documents', ['id'], unique=False)
    op.create_index('idx_documents_path', 'documents', ['path'], unique=True)
    op.create_index('idx_documents_content_hash', 'documents', ['content_hash'], unique=False)
    op.create_index('idx_documents_updated_at', 'documents', ['updated_at'], unique=False)

    # Now add Life Graph enhancement columns
    # Add SHA-256 hash column for content-addressable storage
    # CHAR(64) because SHA-256 produces 64 hexadecimal characters
    op.add_column('documents', sa.Column(
        'sha256',
        sa.CHAR(64),
        nullable=True,  # Nullable for backward compatibility with existing documents
        comment='SHA-256 hash of file content (content-addressable storage key)'
    ))

    # Add source column
    op.add_column('documents', sa.Column(
        'source',
        sa.String(50),
        nullable=True,
        comment='Source of document: upload, email, scan, api, etc.'
    ))

    # Add MIME type column
    op.add_column('documents', sa.Column(
        'mime_type',
        sa.String(100),
        nullable=True,
        comment='MIME type: application/pdf, image/png, text/plain, etc.'
    ))

    # Add file size column (bytes)
    op.add_column('documents', sa.Column(
        'file_size',
        sa.Integer,
        nullable=True,
        comment='File size in bytes'
    ))

    # Add storage URI column
    op.add_column('documents', sa.Column(
        'storage_uri',
        sa.Text,
        nullable=True,
        comment='URI to actual file: file:///data/documents/<sha256>.pdf, s3://bucket/key, etc.'
    ))

    # Add extraction type column
    op.add_column('documents', sa.Column(
        'extraction_type',
        sa.String(50),
        nullable=True,
        comment='Type of extraction: invoice, receipt, contract, form, structured, ocr, etc.'
    ))

    # Add extraction data column (JSONB for structured data)
    op.add_column('documents', sa.Column(
        'extraction_data',
        postgresql.JSONB,
        nullable=True,
        comment='Extracted structured data (invoice fields, receipt items, etc.)'
    ))

    # Add extraction cost column
    op.add_column('documents', sa.Column(
        'extraction_cost',
        sa.Numeric(10, 6),  # Up to $9,999.999999 (sufficient for document processing)
        nullable=True,
        comment='Cost of extraction in USD (GPT-4o, Azure Doc Intel, etc.)'
    ))

    # Add extracted_at timestamp
    op.add_column('documents', sa.Column(
        'extracted_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='Timestamp when extraction was performed'
    ))

    # Create unique index on sha256 for deduplication
    # Partial index (WHERE sha256 IS NOT NULL) to allow NULL values for legacy documents
    op.create_index(
        'idx_documents_sha256_unique',
        'documents',
        ['sha256'],
        unique=True,
        postgresql_where=sa.text('sha256 IS NOT NULL')
    )

    # Create index on extraction_type for filtering
    op.create_index('idx_documents_extraction_type', 'documents', ['extraction_type'], unique=False)

    # Create index on source for filtering
    op.create_index('idx_documents_source', 'documents', ['source'], unique=False)


def downgrade() -> None:
    """
    Drop the entire documents table.

    This completely removes the documents table since we created it in this migration.
    """
    # Drop the entire table (includes all columns and indexes)
    op.drop_table('documents')

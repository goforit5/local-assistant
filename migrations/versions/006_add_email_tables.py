"""Add email tables for Gmail integration

Revision ID: 006
Revises: 005
Create Date: 2025-11-26 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add email system tables."""

    # 1. Create email_accounts table
    op.create_table(
        'email_accounts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email_address', sa.String(255), nullable=False, unique=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('history_id', sa.String(100), nullable=True),
        sa.Column('total_messages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('watch_active', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('watch_expiry', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pubsub_topic_name', sa.String(255), nullable=True),
        sa.Column('watch_error', sa.Text(), nullable=True),
        sa.Column('watch_last_renewed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_type', sa.String(20), nullable=True),
        sa.Column('last_successful_sync', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_error', sa.Text(), nullable=True),
        sa.Column('sync_in_progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_emails_synced', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('incremental_syncs_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('full_syncs_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consecutive_sync_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now())
    )

    # Indexes for email_accounts
    op.create_index('ix_email_accounts_email_address', 'email_accounts', ['email_address'])
    op.create_index('ix_email_accounts_history_id', 'email_accounts', ['history_id'])
    op.create_index('ix_email_accounts_sync_in_progress', 'email_accounts', ['sync_in_progress'])

    # 2. Create emails table
    op.create_table(
        'emails',
        sa.Column('id', sa.String(100), primary_key=True),
        sa.Column('thread_id', sa.String(100), nullable=False),
        sa.Column('account_email', sa.String(255), nullable=False),
        sa.Column('subject', sa.Text(), nullable=True),
        sa.Column('sender', sa.String(255), nullable=True),
        sa.Column('recipient', sa.String(255), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('date_received', sa.DateTime(timezone=True), nullable=True),
        sa.Column('labels', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('content_fetched', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fast_category', sa.String(50), nullable=True),
        sa.Column('fast_priority', sa.String(50), nullable=True),
        sa.Column('needs_ai_analysis', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('sender_importance', sa.String(50), nullable=True),
        sa.Column('triage_completed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analysis_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('is_thread_starter', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('thread_position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('storage_tier', sa.String(20), nullable=False, server_default='hot'),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('s3_body_path', sa.String(500), nullable=True),
        sa.Column('can_restore', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['account_email'], ['email_accounts.email_address'], ondelete='CASCADE')
    )

    # Indexes for emails
    op.create_index('ix_emails_thread_id', 'emails', ['thread_id'])
    op.create_index('ix_emails_account_email', 'emails', ['account_email'])
    op.create_index('ix_emails_sender', 'emails', ['sender'])
    op.create_index('ix_emails_date_received', 'emails', ['date_received'])
    op.create_index('ix_emails_is_thread_starter', 'emails', ['is_thread_starter'])
    op.create_index('ix_emails_storage_tier', 'emails', ['storage_tier'])
    op.create_index('ix_emails_fast_category', 'emails', ['fast_category'])
    op.create_index('ix_emails_fast_priority', 'emails', ['fast_priority'])

    # Composite indexes for common queries
    op.create_index('ix_emails_thread_date', 'emails', ['thread_id', 'date_received'])
    op.create_index('ix_emails_sender_date', 'emails', ['sender', 'date_received'])
    op.create_index('ix_emails_account_date', 'emails', ['account_email', 'date_received'])
    op.create_index('ix_emails_account_thread_date', 'emails', ['account_email', 'thread_id', 'date_received'])
    op.create_index('ix_emails_account_is_read_date', 'emails', ['account_email', 'is_read', 'date_received'])
    op.create_index('ix_emails_account_priority_date', 'emails', ['account_email', 'fast_priority', 'date_received'])
    op.create_index('ix_emails_storage_tier_date', 'emails', ['storage_tier', 'date_received'])

    # Unique constraint for deduplication
    op.create_unique_constraint('uix_emails_id_account', 'emails', ['id', 'account_email'])

    # 3. Create email_attachments table
    op.create_table(
        'email_attachments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email_id', sa.String(100), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('size', sa.Integer(), nullable=True),
        sa.Column('content_hash', sa.CHAR(64), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=True),
        sa.Column('storage_type', sa.String(20), nullable=False, server_default='local'),
        sa.Column('gmail_attachment_id', sa.String(100), nullable=True),
        sa.Column('processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('document_id', UUID(as_uuid=True), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL')
    )

    # Indexes for email_attachments
    op.create_index('ix_email_attachments_email_id', 'email_attachments', ['email_id'])
    op.create_index('ix_email_attachments_content_hash', 'email_attachments', ['content_hash'])
    op.create_index('ix_email_attachments_document_id', 'email_attachments', ['document_id'])
    op.create_index('ix_email_attachments_processed', 'email_attachments', ['processed'])

    # 4. Create email_analysis table
    op.create_table(
        'email_analysis',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('email_id', sa.String(100), nullable=False, unique=True),
        sa.Column('refined_category', sa.String(100), nullable=True),
        sa.Column('actionable', sa.Integer(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('model_version', sa.String(50), nullable=False, server_default='gpt-4.1-mini'),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['email_id'], ['emails.id'], ondelete='CASCADE')
    )

    # Indexes for email_analysis
    op.create_index('ix_email_analysis_email_id', 'email_analysis', ['email_id'])


def downgrade() -> None:
    """Remove email system tables."""
    op.drop_table('email_analysis')
    op.drop_table('email_attachments')
    op.drop_table('emails')
    op.drop_table('email_accounts')

"""Create core Life Graph tables: parties, roles, commitments

Revision ID: 002
Revises: 001
Create Date: 2025-11-06

Tables created:
- parties: Vendors, customers, contacts (organizations and people)
- roles: Context-specific identities (user as customer, admin, viewer, etc.)
- commitments: Obligations, goals, routines with priority and explainability
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create core Life Graph tables.

    Tables:
    1. parties: Represents vendors, customers, contacts (both orgs and individuals)
    2. roles: Context-specific user identities (e.g., "Andrew as Customer", "Andrew as Admin")
    3. commitments: Obligations, goals, routines with priority calculation and explainability
    """

    # ========== parties table ==========
    # Represents vendors, customers, contacts (organizations and people)
    op.create_table(
        'parties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kind', sa.String(20), nullable=False, comment='Type: org, person'),
        sa.Column('name', sa.String(255), nullable=False, comment='Display name (company or person name)'),
        sa.Column('tax_id', sa.String(50), nullable=True, comment='EIN, SSN, or other tax identifier'),
        sa.Column('address', sa.Text, nullable=True, comment='Full address (street, city, state, zip, country)'),
        sa.Column('phone', sa.String(50), nullable=True, comment='Primary phone number'),
        sa.Column('email', sa.String(255), nullable=True, comment='Primary email address'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}', comment='Additional fields (website, contact_person, etc.)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),

        comment='Vendors, customers, contacts (organizations and people)'
    )

    # Trigram index for fuzzy name matching (enables fast similarity() queries)
    # Example: SELECT * FROM parties WHERE name % 'Clipboard Health' ORDER BY similarity(name, 'Clipboard Health') DESC
    op.execute('CREATE INDEX idx_parties_name_trigram ON parties USING gin (name gin_trgm_ops);')

    # Index for exact tax_id lookup (deduplication)
    op.create_index('idx_parties_tax_id', 'parties', ['tax_id'], unique=False)

    # Index for kind (filter by org/person)
    op.create_index('idx_parties_kind', 'parties', ['kind'], unique=False)

    # ========== roles table ==========
    # Context-specific user identities (e.g., "Andrew as Customer at Clipboard Health")
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('party_id', postgresql.UUID(as_uuid=True), nullable=False, comment='FK to parties table'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True, comment='FK to users table (if applicable)'),
        sa.Column('role_name', sa.String(100), nullable=False, comment='Role type: customer, vendor, admin, viewer, etc.'),
        sa.Column('context', sa.String(255), nullable=True, comment='Contextual information (e.g., "at Clipboard Health")'),
        sa.Column('permissions', postgresql.JSONB, nullable=True, server_default='{}', comment='Role-specific permissions (read, write, admin)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        comment='Context-specific identities (user as customer, admin, viewer, etc.)'
    )

    # Foreign key to parties
    op.create_foreign_key('fk_roles_party_id', 'roles', 'parties', ['party_id'], ['id'], ondelete='CASCADE')

    # Index for party_id lookup
    op.create_index('idx_roles_party_id', 'roles', ['party_id'], unique=False)

    # Index for user_id lookup
    op.create_index('idx_roles_user_id', 'roles', ['user_id'], unique=False)

    # ========== commitments table ==========
    # Obligations, goals, routines with priority and explainability
    op.create_table(
        'commitments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False, comment='FK to roles table'),
        sa.Column('title', sa.String(500), nullable=False, comment='Short description (e.g., "Pay Invoice #240470 - Clipboard Health")'),
        sa.Column('description', sa.Text, nullable=True, comment='Long-form details'),
        sa.Column('commitment_type', sa.String(50), nullable=False, comment='Type: obligation, goal, routine'),
        sa.Column('priority', sa.Integer, nullable=False, default=50, comment='Priority score (0-100, higher = more urgent)'),
        sa.Column('reason', sa.Text, nullable=True, comment='Explainability: why this priority? (e.g., "Due in 2 days, $12,419.83, legal risk")'),
        sa.Column('state', sa.String(50), nullable=False, default='pending', comment='State: pending, in_progress, completed, cancelled'),
        sa.Column('due_date', sa.Date, nullable=True, comment='When this commitment is due'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='When this commitment was completed'),
        sa.Column('effort_minutes', sa.Integer, nullable=True, comment='Estimated effort in minutes'),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True, comment='Monetary amount (for financial commitments)'),
        sa.Column('severity', sa.Integer, nullable=True, comment='Domain-based severity (legal=10, finance=8, etc.)'),
        sa.Column('metadata', postgresql.JSONB, nullable=True, server_default='{}', comment='Additional fields (tags, dependencies, etc.)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),

        comment='Obligations, goals, routines with priority calculation'
    )

    # Foreign key to roles
    op.create_foreign_key('fk_commitments_role_id', 'commitments', 'roles', ['role_id'], ['id'], ondelete='CASCADE')

    # Compound index for filtering by state and due_date (common query pattern)
    op.create_index('idx_commitments_state_due_date', 'commitments', ['state', 'due_date'], unique=False)

    # Index for priority sorting (high-priority commitments first)
    op.create_index('idx_commitments_priority', 'commitments', ['priority'], unique=False, postgresql_ops={'priority': 'DESC'})

    # Index for role_id lookup
    op.create_index('idx_commitments_role_id', 'commitments', ['role_id'], unique=False)


def downgrade() -> None:
    """
    Drop all core Life Graph tables.

    Order is important: drop child tables before parent tables to avoid FK constraint violations.
    """
    # Drop indexes first (not strictly necessary, but cleaner)
    op.drop_index('idx_commitments_role_id', table_name='commitments')
    op.drop_index('idx_commitments_priority', table_name='commitments')
    op.drop_index('idx_commitments_state_due_date', table_name='commitments')

    op.drop_index('idx_roles_user_id', table_name='roles')
    op.drop_index('idx_roles_party_id', table_name='roles')

    op.drop_index('idx_parties_kind', table_name='parties')
    op.drop_index('idx_parties_tax_id', table_name='parties')
    op.execute('DROP INDEX IF EXISTS idx_parties_name_trigram;')

    # Drop foreign keys explicitly (Alembic may not auto-drop)
    op.drop_constraint('fk_commitments_role_id', 'commitments', type_='foreignkey')
    op.drop_constraint('fk_roles_party_id', 'roles', type_='foreignkey')

    # Drop tables in reverse order (child → parent)
    op.drop_table('commitments')
    op.drop_table('roles')
    op.drop_table('parties')

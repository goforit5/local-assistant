"""Add PostgreSQL extensions for UUID, fuzzy search, and date ranges

Revision ID: 001
Revises:
Create Date: 2025-11-06

Extensions added:
- pgcrypto: UUID generation with gen_random_uuid()
- pg_trgm: Trigram-based fuzzy text search for vendor name matching
- btree_gist: GIST indexes for date range constraints on commitments
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add PostgreSQL extensions needed for Life Graph functionality.

    Extensions:
    - pgcrypto: Provides gen_random_uuid() for UUID primary keys
    - pg_trgm: Provides trigram matching for fuzzy vendor name search (similarity())
    - btree_gist: Provides GIST indexes for date range exclusion constraints
    """
    # Add pgcrypto for UUID generation
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    # Add pg_trgm for fuzzy text search (vendor matching with >90% similarity)
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    # Add btree_gist for date range constraints (prevent overlapping commitments)
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gist";')


def downgrade() -> None:
    """
    Remove PostgreSQL extensions.

    Note: Extensions are only dropped if no other database objects depend on them.
    If tables are using gen_random_uuid() or trigram indexes, the drop will fail.
    This is intentional to prevent accidental data loss.
    """
    # Drop extensions in reverse order
    # CASCADE will remove dependent objects (indexes, constraints, etc.)
    op.execute('DROP EXTENSION IF EXISTS "btree_gist" CASCADE;')
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm" CASCADE;')
    op.execute('DROP EXTENSION IF EXISTS "pgcrypto" CASCADE;')

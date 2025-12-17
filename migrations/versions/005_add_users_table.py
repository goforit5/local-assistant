"""Add users table for authentication

Revision ID: 005
Revises: 004
Create Date: 2025-11-26

Tables created:
- users: User accounts with bcrypt password hashing for JWT authentication
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create users table for JWT authentication.

    Table includes:
    - id: Primary key (integer for simplicity)
    - username: Unique username for login
    - hashed_password: bcrypt hashed password
    - created_at: Account creation timestamp
    - updated_at: Last update timestamp
    """

    # ========== users table ==========
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(50), nullable=False, unique=True, comment='Unique username for login'),
        sa.Column('hashed_password', sa.String(255), nullable=False, comment='bcrypt hashed password'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        comment='User accounts with bcrypt password hashing for JWT authentication'
    )

    # Unique index on username for fast lookups and constraint enforcement
    op.create_index('idx_users_username_unique', 'users', ['username'], unique=True)

    # Index on created_at for sorting users by registration date
    op.create_index('idx_users_created_at', 'users', ['created_at'], unique=False)


def downgrade() -> None:
    """
    Drop users table and associated indexes.
    """
    # Drop indexes first
    op.drop_index('idx_users_created_at', table_name='users')
    op.drop_index('idx_users_username_unique', table_name='users')

    # Drop table
    op.drop_table('users')

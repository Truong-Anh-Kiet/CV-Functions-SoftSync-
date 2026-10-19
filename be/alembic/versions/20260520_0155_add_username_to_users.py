"""add username to users

Revision ID: 20260520_0155
Revises:
Create Date: 2026-05-20 01:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260520_0155"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    op.execute(
        """
        UPDATE users
        SET username = lower(split_part(email, '@', 1)) || '-' || id
        WHERE username IS NULL
        """
    )
    op.alter_column("users", "username", existing_type=sa.String(length=50), nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")

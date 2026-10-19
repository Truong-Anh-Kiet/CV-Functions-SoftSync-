"""Add raw_text to documents

Revision ID: add_raw_text_to_documents
Revises: 20260520_0155_add_username_to_users
Create Date: 2026-06-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_raw_text_to_documents"
down_revision = "20260520_0155"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("raw_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "raw_text")

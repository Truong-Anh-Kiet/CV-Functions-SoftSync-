"""Add password reset OTP fields to users.

Revision ID: 20260722_password_reset
Revises: add_raw_text_to_documents
Create Date: 2026-07-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260722_password_reset"
down_revision = "add_raw_text_to_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_otp_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_reset_expires_at")
    op.drop_column("users", "password_reset_otp_hash")

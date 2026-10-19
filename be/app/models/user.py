from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="hr")
    is_active = Column(Boolean, nullable=False, default=False)
    auth_provider = Column(String(50), nullable=False, default="local")
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    email_verification_otp_hash = Column(String(255), nullable=True)
    email_verification_expires_at = Column(DateTime, nullable=True)
    password_reset_otp_hash = Column(String(255), nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    token_type = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)

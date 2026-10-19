from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import settings


BCRYPT_MAX_BYTES = 72


def utc_now() -> datetime:
    return datetime.now(UTC)


def expires_at(minutes: int) -> datetime:
    return utc_now() + timedelta(minutes=minutes)


def _hash_secret(secret: str) -> str:
    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) > BCRYPT_MAX_BYTES:
        raise ValueError("Bcrypt input cannot exceed 72 bytes")
    return bcrypt.hashpw(secret_bytes, bcrypt.gensalt()).decode("utf-8")


def _verify_secret(secret: str, hashed_secret: str | None) -> bool:
    if not hashed_secret:
        return False
    try:
        return bcrypt.checkpw(secret.encode("utf-8"), hashed_secret.encode("utf-8"))
    except ValueError:
        return False


def hash_password(password: str) -> str:
    return _hash_secret(password)


def verify_password(plain_password: str, hashed_password: str | None) -> bool:
    return _verify_secret(plain_password, hashed_password)


def hash_otp(otp: str) -> str:
    return _hash_secret(otp)


def verify_otp(otp: str, hashed_otp: str | None) -> bool:
    return _verify_secret(otp, hashed_otp)


def create_jwt_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = utc_now()
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc


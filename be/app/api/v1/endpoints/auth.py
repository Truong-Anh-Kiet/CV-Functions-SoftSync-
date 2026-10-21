import logging
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, status

logger = logging.getLogger(__name__)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_jwt_token,
    decode_jwt_token,
    hash_otp,
    hash_password,
    verify_otp,
    verify_password,
)
from app.db.session import get_db
from app.models.user import TokenBlacklist, User
from app.services.email_sender import EmailDeliveryError, send_password_reset_otp
from app.schemas.auth import (
    GoogleClientConfigResponse,
    GoogleLoginRequest,
    CurrentUserResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    RefreshTokenRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)

router = APIRouter()
bearer_scheme = HTTPBearer()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_username(username: str) -> str:
    return username.strip().lower()


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def make_unique_username(db: Session, email: str) -> str:
    base_username = normalize_username(email.split("@")[0])[:40] or "recruiter"
    username = base_username
    suffix = 1
    while get_user_by_username(db, username):
        username = f"{base_username[:40]}-{suffix}"
        suffix += 1
    return username


def create_token_pair(user: User) -> TokenResponse:
    access_token = create_jwt_token(
        subject=str(user.id),
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_jwt_token(
        subject=str(user.id),
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def parse_token(token: str, expected_type: str) -> dict:
    try:
        payload = decode_jwt_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    if payload.get("type") != expected_type or not payload.get("jti"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid {expected_type} token",
        )
    return payload


def is_token_blacklisted(db: Session, jti: str) -> bool:
    return db.query(TokenBlacklist).filter(TokenBlacklist.jti == jti).first() is not None


def add_token_to_blacklist(db: Session, payload: dict) -> None:
    jti = payload["jti"]
    if is_token_blacklisted(db, jti):
        return

    expires_at = datetime.fromtimestamp(int(payload["exp"]), UTC).replace(tzinfo=None)
    user_id = int(payload["sub"]) if str(payload.get("sub", "")).isdigit() else None
    db.add(
        TokenBlacklist(
            jti=jti,
            token_type=payload["type"],
            user_id=user_id,
            expires_at=expires_at,
        )
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    email = normalize_email(payload.email)
    username = normalize_username(payload.username)
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )
    if get_user_by_username(db, username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="hr",
        is_active=True,
        auth_provider="local",
        email_verification_otp_hash=None,
        email_verification_expires_at=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return RegisterResponse(
        status="success",
        message="Account created. You can login now.",
        user_id=user.id,
        otp_for_testing=None,
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> MessageResponse:
    user = get_user_by_email(db, normalize_email(payload.email))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_active:
        return MessageResponse(status="success", message="Email already verified")

    if (
        not user.email_verification_expires_at
        or user.email_verification_expires_at < utc_now_naive()
        or not verify_otp(payload.otp, user.email_verification_otp_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP",
        )

    user.is_active = True
    user.email_verification_otp_hash = None
    user.email_verification_expires_at = None
    db.commit()

    return MessageResponse(status="success", message="Email verified")


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> ForgotPasswordResponse:
    """Issue a short-lived password-reset OTP for a local account."""
    user = get_user_by_email(db, normalize_email(payload.email))
    generic_message = "If the email exists, a password reset code has been issued"

    # Do not expose whether an email is registered.
    if not user:
        return ForgotPasswordResponse(status="success", message=generic_message)

    otp = f"{secrets.randbelow(1_000_000):06d}"
    user.password_reset_otp_hash = hash_otp(otp)
    user.password_reset_expires_at = utc_now_naive() + timedelta(
        minutes=settings.password_reset_otp_expire_minutes
    )
    db.commit()

    # Test mode deliberately skips SMTP delivery and returns the OTP. In all
    # other environments, OTPs are delivered exclusively through email.
    if not settings.auth_return_otp_in_response:
        try:
            send_password_reset_otp(user.email, otp)
        except EmailDeliveryError as exc:
            user.password_reset_otp_hash = None
            user.password_reset_expires_at = None
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to send password reset email. Please try again later.",
            ) from exc

    return ForgotPasswordResponse(
        status="success",
        message=generic_message,
        otp_for_testing=otp if settings.auth_return_otp_in_response else None,
    )


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Validate a password-reset OTP and replace the account password."""
    user = get_user_by_email(db, normalize_email(payload.email))
    if (
        not user
        or not user.password_reset_expires_at
        or user.password_reset_expires_at < utc_now_naive()
        or not verify_otp(payload.otp, user.password_reset_otp_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset OTP",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_otp_hash = None
    user.password_reset_expires_at = None
    if "local" not in {provider.strip() for provider in user.auth_provider.split(",")}:
        user.auth_provider = f"{user.auth_provider},local"
    db.commit()

    return MessageResponse(status="success", message="Password reset successfully")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_user_by_username(db, normalize_username(payload.username))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email has not been verified",
        )

    return create_token_pair(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)) -> TokenResponse:
    refresh_payload = parse_token(payload.refresh_token, expected_type="refresh")
    if is_token_blacklisted(db, refresh_payload["jti"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    try:
        user_id = int(refresh_payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Rotate the refresh token so a token that has already been used cannot be reused.
    add_token_to_blacklist(db, refresh_payload)
    tokens = create_token_pair(user)
    db.commit()
    return tokens


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    """Return the authenticated user's profile for the frontend session."""
    payload = parse_token(credentials.credentials, expected_type="access")
    if is_token_blacklisted(db, payload["jti"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        auth_provider=user.auth_provider,
    )


@router.get("/google-client-id", response_model=GoogleClientConfigResponse)
def get_google_client_id() -> GoogleClientConfigResponse:
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    return GoogleClientConfigResponse(client_id=settings.google_client_id)


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        google_payload = google_id_token.verify_oauth2_token(
            payload.id_token,
            google_requests.Request(),
            settings.google_client_id,
            clock_skew_in_seconds=60,
        )
    except ValueError as exc:
        logger.error("Google id_token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google id_token",
        ) from exc

    if not google_payload.get("email") or not google_payload.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google email is not verified",
        )

    email = normalize_email(google_payload["email"])
    google_sub = google_payload.get("sub")
    user = get_user_by_email(db, email)

    if not user:
        user = User(
            username=make_unique_username(db, email),
            email=email,
            hashed_password=None,
            full_name=google_payload.get("name") or email.split("@")[0],
            role="hr",
            is_active=True,
            auth_provider="google",
            google_sub=google_sub,
        )
        db.add(user)
    else:
        user.is_active = True
        user.google_sub = user.google_sub or google_sub
        if user.auth_provider == "local":
            user.auth_provider = "local,google"

    db.commit()
    db.refresh(user)

    return create_token_pair(user)


@router.post("/logout", response_model=MessageResponse)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    payload: LogoutRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> MessageResponse:
    access_payload = parse_token(credentials.credentials, expected_type="access")
    add_token_to_blacklist(db, access_payload)

    if payload and payload.refresh_token:
        refresh_payload = parse_token(payload.refresh_token, expected_type="refresh")
        add_token_to_blacklist(db, refresh_payload)

    db.commit()

    return MessageResponse(status="success", message="Logged out")

import re

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_core import PydanticCustomError


def validate_password_strength(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("password must not exceed 72 bytes for bcrypt")
    if any(char.isspace() for char in password):
        raise ValueError("password must not contain spaces")
    if not any(char.isupper() for char in password):
        raise ValueError("password must contain at least one uppercase letter")
    if not any(char.islower() for char in password):
        raise ValueError("password must contain at least one lowercase letter")
    if not any(char.isdigit() for char in password):
        raise ValueError("password must contain at least one number")
    if not any(not char.isalnum() for char in password):
        raise ValueError("password must contain at least one special character")
    return password


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, password: str) -> str:
        return validate_password_strength(password)

    @field_validator("username")
    @classmethod
    def username_must_contain_only_allowed_characters(cls, username: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
            raise PydanticCustomError(
                "username_invalid_characters",
                "Username may contain only letters, numbers, periods (.), "
                "underscores (_), and hyphens (-)."
            )
        return username


class RegisterResponse(BaseModel):
    status: str
    message: str
    user_id: int
    otp_for_testing: str | None = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_must_be_strong(cls, password: str) -> str:
        return validate_password_strength(password)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: str
    role: str
    auth_provider: str


class GoogleLoginRequest(BaseModel):
    id_token: str = Field(min_length=1)


class GoogleClientConfigResponse(BaseModel):
    client_id: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class MessageResponse(BaseModel):
    status: str
    message: str


class ForgotPasswordResponse(MessageResponse):
    otp_for_testing: str | None = None

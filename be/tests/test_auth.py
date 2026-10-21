from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.user import TokenBlacklist, User


client = TestClient(app)


def cleanup_user(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            db.query(TokenBlacklist).filter(TokenBlacklist.user_id == user.id).delete(
                synchronize_session=False
            )
            db.delete(user)
            db.commit()
    finally:
        db.close()


def test_register_login_logout_flow() -> None:
    email = f"auth-{uuid4().hex}@example.com"
    username = f"auth-{uuid4().hex[:12]}"

    try:
        register_response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "Password123!",
                "full_name": "Auth Test",
            },
        )

        assert register_response.status_code == 201
        register_data = register_response.json()
        assert register_data["user_id"]
        assert register_data["otp_for_testing"] is None

        login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "Password123!"},
        )

        assert login_response.status_code == 200
        tokens = login_response.json()
        assert set(tokens) == {"access_token", "refresh_token"}

        current_user_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert current_user_response.status_code == 200
        assert current_user_response.json()["email"] == email
        assert current_user_response.json()["username"] == username

        logout_response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={"refresh_token": tokens["refresh_token"]},
        )

        assert logout_response.status_code == 200
        assert logout_response.json() == {"status": "success", "message": "Logged out"}
    finally:
        cleanup_user(email)


def test_refresh_rotates_refresh_token_and_returns_new_access_token() -> None:
    email = f"refresh-{uuid4().hex}@example.com"
    username = f"refresh-{uuid4().hex[:12]}"

    try:
        register_response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "Password123!",
                "full_name": "Refresh Test",
            },
        )
        assert register_response.status_code == 201

        login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "Password123!"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()

        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        refreshed_tokens = refresh_response.json()
        assert set(refreshed_tokens) == {"access_token", "refresh_token"}
        assert refreshed_tokens["refresh_token"] != tokens["refresh_token"]

        current_user_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {refreshed_tokens['access_token']}"},
        )
        assert current_user_response.status_code == 200

        reused_refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert reused_refresh_response.status_code == 401
    finally:
        cleanup_user(email)


def test_register_rejects_weak_password() -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"weak-{uuid4().hex[:12]}",
            "email": f"weak-{uuid4().hex}@example.com",
            "password": "12345678",
            "full_name": "Weak Password",
        },
    )

    assert response.status_code == 422
    assert "uppercase letter" in str(response.json())


def test_forgot_password_and_reset_password_flow() -> None:
    email = f"reset-{uuid4().hex}@example.com"
    username = f"reset-{uuid4().hex[:12]}"
    old_password = "Password123!"
    new_password = "NewPassword456!"

    original_return_otp_setting = settings.auth_return_otp_in_response
    settings.auth_return_otp_in_response = True

    try:
        register_response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": old_password,
                "full_name": "Reset Test",
            },
        )
        assert register_response.status_code == 201

        forgot_response = client.post("/api/auth/forgot-password", json={"email": email})
        assert forgot_response.status_code == 200
        otp = forgot_response.json()["otp_for_testing"]
        assert otp and len(otp) == 6

        reset_response = client.post(
            "/api/auth/reset-password",
            json={"email": email, "otp": otp, "new_password": new_password},
        )
        assert reset_response.status_code == 200
        assert reset_response.json() == {
            "status": "success",
            "message": "Password reset successfully",
        }

        old_login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": old_password},
        )
        assert old_login_response.status_code == 401

        new_login_response = client.post(
            "/api/auth/login",
            json={"username": username, "password": new_password},
        )
        assert new_login_response.status_code == 200
    finally:
        settings.auth_return_otp_in_response = original_return_otp_setting
        cleanup_user(email)


def test_forgot_password_sends_email_when_test_otp_is_disabled() -> None:
    email = f"mail-reset-{uuid4().hex}@example.com"
    username = f"mail-reset-{uuid4().hex[:12]}"
    original_return_otp_setting = settings.auth_return_otp_in_response
    settings.auth_return_otp_in_response = False

    try:
        register_response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "Password123!",
                "full_name": "Mail Reset Test",
            },
        )
        assert register_response.status_code == 201

        with patch("app.api.v1.endpoints.auth.send_password_reset_otp") as send_email:
            forgot_response = client.post("/api/auth/forgot-password", json={"email": email})

        assert forgot_response.status_code == 200
        assert forgot_response.json()["otp_for_testing"] is None
        send_email.assert_called_once()
        assert send_email.call_args.args[0] == email
        assert len(send_email.call_args.args[1]) == 6
    finally:
        settings.auth_return_otp_in_response = original_return_otp_setting
        cleanup_user(email)

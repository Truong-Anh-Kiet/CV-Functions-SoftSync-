import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when the configured SMTP provider cannot deliver an email."""


def send_password_reset_otp(recipient: str, otp: str) -> None:
    """Send a password-reset OTP through the configured SMTP account."""
    sender = settings.smtp_from_email or settings.smtp_username
    if not settings.smtp_username or not settings.smtp_password or not sender:
        raise EmailDeliveryError("SMTP credentials are not configured")

    expiry_minutes = settings.password_reset_otp_expire_minutes
    message = EmailMessage()
    message["Subject"] = "Password reset code"
    message["From"] = formataddr((settings.smtp_from_name, sender))
    message["To"] = recipient
    message.set_content(
        f"Your password reset code is {otp}. It expires in {expiry_minutes} minutes."
    )
    message.add_alternative(
        f"""\
<!doctype html>
<html>
  <body style="font-family:Arial,sans-serif;background:#f8fafc;padding:24px;color:#0f172a">
    <div style="max-width:520px;margin:auto;background:#ffffff;border-radius:12px;padding:32px;border:1px solid #e2e8f0">
      <h2 style="margin:0 0 12px">Reset your password</h2>
      <p style="line-height:1.5">Use this verification code to reset your AIP491 account password.</p>
      <p style="font-size:28px;font-weight:700;letter-spacing:8px;color:#0891b2;margin:24px 0">{otp}</p>
      <p style="line-height:1.5;color:#475569">This code expires in {expiry_minutes} minutes and can be used once.</p>
      <p style="line-height:1.5;color:#475569">If you did not request a password reset, you can ignore this email.</p>
    </div>
  </body>
</html>
""",
        subtype="html",
    )

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        logger.warning("Unable to send password reset email: %s", exc)
        raise EmailDeliveryError("Unable to send password reset email") from exc

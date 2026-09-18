import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email using the configured SMTP server."""
    if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
        logger.error("SMTP email is not configured")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=15,
        ) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(
                settings.SMTP_USER,
                to_email,
                msg.as_string(),
            )

        logger.info("Email sent successfully to %s", to_email)
        return True

    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False


def send_otp_email(to_email: str, code: str) -> bool:
    """Send an OTP verification email."""
    subject = "Your JanSeva Connect verification code"
    body = (
        f"Your one-time verification code is: {code}\n\n"
        f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.\n"
        "If you did not request this code, you can ignore this email."
    )
    return _send_email(to_email, subject, body)


def send_password_reset_otp_email(to_email: str, code: str) -> bool:
    """Send a password-reset OTP email."""
    subject = "Your JanSeva Connect password reset code"
    body = (
        f"Your password reset code is: {code}\n\n"
        f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.\n"
        "If you did not request a password reset, you can ignore this email."
    )
    return _send_email(to_email, subject, body)


def send_login_alert_email(
    to_email: str,
    ip_address: str,
    user_agent: str,
) -> bool:
    """Send a login alert email."""
    subject = "JanSeva Connect login alert"
    body = (
        "A login to your JanSeva Connect account was detected.\n\n"
        f"IP address: {ip_address}\n"
        f"Device/browser: {user_agent}\n\n"
        "If this was not you, please change your password."
    )
    return _send_email(to_email, subject, body)
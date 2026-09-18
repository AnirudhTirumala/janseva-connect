"""Secure lifecycle helpers for short-lived email verification codes."""

from datetime import timedelta
import hashlib
import hmac
import secrets
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.timeutils import as_utc, utcnow
from app.models.otp import EmailOTP


def generate_otp_code() -> str:
    """Return a cryptographically secure, zero-padded six-digit code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(code: str) -> str:
    """Hash an OTP with the deployment secret before persisting it.

    HMAC keeps a database-only compromise from revealing still-valid codes,
    while compare_digest below avoids timing leaks during verification.
    """
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), code.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"hmac-sha256${digest}"


def otp_matches(otp: EmailOTP, supplied_code: str) -> bool:
    if otp.code_hash:
        return hmac.compare_digest(otp.code_hash, hash_otp_code(supplied_code))
    # Records issued by a pre-hardening deployment remain usable only for
    # their original short expiry window. New records never store raw codes.
    return hmac.compare_digest(otp.code or "", supplied_code)


def issue_otp(db: Session, *, email: str, purpose: str, **pending_fields: Any) -> tuple[EmailOTP, str]:
    """Invalidate prior active codes for this flow, then create one new OTP."""
    normalized_email = email.strip().lower()
    db.query(EmailOTP).filter(
        EmailOTP.email == normalized_email,
        EmailOTP.purpose == purpose,
        EmailOTP.is_used == False,  # noqa: E712
    ).update({EmailOTP.is_used: True}, synchronize_session=False)

    code = generate_otp_code()
    otp = EmailOTP(
        email=normalized_email,
        # `code` is retained as an empty compatibility field for databases
        # where the legacy non-null column already exists.
        code="",
        code_hash=hash_otp_code(code),
        purpose=purpose,
        expires_at=utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        **pending_fields,
    )
    db.add(otp)
    db.commit()
    return otp, code


def get_valid_otp(db: Session, *, email: str, purpose: str, supplied_code: str) -> EmailOTP | None:
    """Fetch and validate the newest non-consumed code for a flow."""
    otp = (
        db.query(EmailOTP)
        .filter(
            EmailOTP.email == email.strip().lower(),
            EmailOTP.purpose == purpose,
            EmailOTP.is_used == False,  # noqa: E712
        )
        .order_by(EmailOTP.created_at.desc(), EmailOTP.id.desc())
        .first()
    )
    if not otp or as_utc(otp.expires_at) < utcnow() or not otp_matches(otp, supplied_code):
        return None
    return otp

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from app.core.database import Base


class EmailOTP(Base):
    """
    Short-lived one-time codes emailed for either:
      - passwordless login/signup (purpose="login", no pending_* fields), or
      - verifying a traditional name+email+phone+password signup before the
        account is actually created (purpose="register", pending_* fields
        hold the submitted data until the code is confirmed).

    A new row is created per request; old/used rows are left in place for
    audit purposes rather than deleted.
    """
    __tablename__ = "email_otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), index=True, nullable=False)
    code = Column(String(6), nullable=False)
    # New OTPs are HMAC-hashed before persistence. `code` remains only for
    # short-lived legacy records created before this migration.
    code_hash = Column(String(128), nullable=True)
    purpose = Column(String(20), nullable=False, default="login", index=True)  # login | register
    is_used = Column(Boolean, default=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Only populated for password-based registration verification -
    # the account isn't created until the code is confirmed, so we hold
    # the submitted signup details here in the meantime.
    pending_full_name = Column(String(150), nullable=True)
    pending_phone = Column(String(20), nullable=True)
    pending_hashed_password = Column(String(255), nullable=True)
    pending_role = Column(String(20), nullable=True)  # only set for admin-created staff/citizen accounts
    # Scope and the optional citizen household record are held only until the
    # owner proves their email. This lets the office register a complete
    # citizen in one formal workflow without creating unverified accounts.
    pending_jurisdiction_level = Column(String(20), nullable=True)
    pending_district = Column(String(100), nullable=True)
    pending_mandal = Column(String(100), nullable=True)
    pending_village = Column(String(100), nullable=True)
    pending_member_profile = Column(Text, nullable=True)  # JSON, cleared after confirmation

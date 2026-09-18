from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func

from app.core.database import Base


class AuditEvent(Base):
    """Append-only operational history for UI and server-side activity.

    This table deliberately stores action metadata rather than secrets: never
    passwords, OTP values, document contents, or full request bodies.
    """
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_role = Column(String(20), nullable=True)
    event_type = Column(String(40), nullable=False, index=True)
    action = Column(String(120), nullable=False, index=True)
    route = Column(String(255), nullable=True)
    target_type = Column(String(50), nullable=True, index=True)
    target_id = Column(String(80), nullable=True, index=True)
    outcome = Column(String(30), nullable=True, index=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

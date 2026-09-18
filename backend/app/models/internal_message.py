from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class InternalMessage(Base):
    """District/mandal staff workspace conversation visible to administrators."""

    __tablename__ = "internal_messages"

    id = Column(Integer, primary_key=True, index=True)
    district = Column(String(100), nullable=False, index=True)
    mandal = Column(String(100), nullable=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey, func
from app.core.database import Base


class Message(Base):
    """
    A single chat message in a citizen's support conversation with the
    Panchayat office. Conversations are grouped by citizen (citizen_user_id)
    rather than by individual staff member - any staff/admin can see and
    reply to a citizen's thread, like a shared support inbox, since the
    office as a whole is answering, not one specific staff member.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    citizen_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

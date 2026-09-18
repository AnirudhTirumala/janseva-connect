from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from app.core.database import Base


class Notification(Base):
    """
    An in-portal notification for a user - created automatically whenever
    something happens that affects them (certificate issued, application
    approved/rejected, new chat message, account created). Shown in the
    sidebar "Notifications" section so nothing gets missed even if the
    matching email doesn't arrive.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    # Indexed: unread badges and "mark read by link" both filter on it.
    link = Column(String(255), nullable=True, index=True)  # frontend route, e.g. "/applications"
    # Set when this notification is about a specific Issue (a reply, or a
    # new AI-assistant escalation) - lets nav-count queries distinguish an
    # AI-sourced issue update from every other kind of issue/notification
    # without parsing the link string.
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

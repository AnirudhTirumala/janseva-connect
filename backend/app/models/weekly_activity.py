from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class WeeklyActivity(Base):
    """Formal weekly report submitted by a district administrator."""

    __tablename__ = "weekly_activities"

    id = Column(Integer, primary_key=True, index=True)
    district = Column(String(100), nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    summary = Column(Text, nullable=False)
    achievements = Column(Text, nullable=True)
    blockers = Column(Text, nullable=True)
    submitted_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

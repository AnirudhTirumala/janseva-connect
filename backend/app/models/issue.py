from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Issue(Base):
    """A local issue a citizen raises about their locality (water, roads,
    sanitation, streetlights, etc.), tracked through to an office reply.

    district/mandal/village are captured directly from the citizen's
    household record at creation time rather than joined live - the same
    denormalised pattern InternalMessage uses - so jurisdiction scoping
    never needs an extra join and the record stays accurate even if the
    citizen edits their household profile afterwards.
    """

    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    citizen_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text, nullable=False)
    village = Column(String(100), nullable=True)
    mandal = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
    # civic (default - roads/water/sanitation etc, raised manually) |
    # portal (a technical bug in the website/app itself) | application (a
    # stuck/incorrect scheme application, certificate, or service-delivery
    # problem). The latter two are created automatically by the AI
    # assistant (see app/utils/issue_escalation.py) when it recognises a
    # problem it cannot resolve itself, instead of just replying in-chat
    # with an empty promise to "report this" that nothing backs up.
    category = Column(String(20), nullable=False, default="civic", index=True)
    # citizen (default - raised manually via the Issues page) | ai_assistant
    # (auto-logged from an AI assistant conversation). Despite the column
    # name, citizen_user_id also holds the reporting user's id when a
    # staff/admin account reports something through the assistant.
    source = Column(String(20), nullable=False, default="citizen", index=True)
    # open -> in_progress -> resolved (staff says done, awaiting citizen
    # confirmation) -> closed (citizen confirmed) or reopened (citizen
    # rejected the resolution - goes back through in_progress/resolved again).
    status = Column(String(20), nullable=False, default="open", index=True)
    reply = Column(Text, nullable=True)
    replied_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    # Set when the citizen accepts or rejects a "resolved" issue.
    citizen_feedback = Column(Text, nullable=True)
    citizen_responded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    citizen = relationship("User", foreign_keys=[citizen_user_id])
    replied_by = relationship("User", foreign_keys=[replied_by_id])

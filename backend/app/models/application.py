from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SchemeApplication(Base):
    """
    Tracks a citizen's application to a scheme through its full lifecycle.
    This replaces the paper -> office verification -> manual register flow
    described in the requirements, giving citizens real-time status and
    admins an auditable approval history.
    """
    __tablename__ = "scheme_applications"

    id = Column(Integer, primary_key=True, index=True)
    # Indexed: every staff queue, citizen "my applications" view, and
    # dashboard aggregate filters on these three columns.
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False, index=True)

    # pending -> under_review -> approved / rejected
    status = Column(String(20), default="pending", nullable=False, index=True)

    remarks = Column(Text, nullable=True)  # staff/admin notes, e.g. reason for rejection
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", back_populates="applications")
    scheme = relationship("Scheme", back_populates="applications")
    documents = relationship(
        "ApplicationDocument", back_populates="application",
        cascade="all, delete-orphan", order_by="ApplicationDocument.id",
    )

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class CertificateRequest(Base):
    """A citizen's request awaiting an office review and certificate issue."""
    __tablename__ = "certificate_requests"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    requested_by_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    certificate_type = Column(String(30), nullable=False)
    purpose = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    review_remarks = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    certificate_id = Column(Integer, ForeignKey("certificates.id"), nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", foreign_keys=[member_id])
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    certificate = relationship("Certificate", foreign_keys=[certificate_id])

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Certificate(Base):
    """
    A generated official document (income / residence / birth certificate).
    Stores enough metadata to reproduce/re-download the PDF and to search
    old certificates instantly (the #2 pain point in the requirements).
    """
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)

    # income | residence | birth
    certificate_type = Column(String(30), nullable=False)
    certificate_number = Column(String(50), unique=True, nullable=False)  # e.g. INC-2026-000123

    issued_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_path = Column(String(255), nullable=True)  # where the generated PDF lives

    issued_at = Column(DateTime(timezone=True), server_default=func.now())

    member = relationship("Member", back_populates="certificates")
    issued_by = relationship("User", foreign_keys=[issued_by_id])

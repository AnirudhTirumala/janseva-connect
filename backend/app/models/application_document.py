from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class ApplicationDocument(Base):
    """
    A single uploaded file against one required document for a scheme
    application (e.g. the Aadhaar Card upload, separate from the Income
    Proof upload). Each requirement gets its own row/file rather than
    citizens bundling everything into one PDF, so staff can review and
    approve/reject each document independently.
    """
    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("scheme_applications.id"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("scheme_document_requirements.id"), nullable=True)

    # Denormalized so the label survives even if the scheme's requirement
    # list changes later.
    document_name = Column(String(150), nullable=False)

    file_path = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=True)

    # pending -> approved / rejected, reviewed independently per document
    status = Column(String(20), default="pending", nullable=False)
    remarks = Column(Text, nullable=True)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    application = relationship("SchemeApplication", back_populates="documents")

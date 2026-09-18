from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Scheme(Base):
    """
    A government welfare scheme the Panchayat administers (e.g. old-age
    pension, housing scheme). Admin-managed catalog that citizens browse
    and apply against.
    """
    __tablename__ = "schemes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    eligibility_criteria = Column(Text, nullable=True)
    required_documents = Column(Text, nullable=True)  # legacy free-text field, kept for old data; new schemes use document_requirements below
    max_income_limit = Column(Integer, nullable=True)  # simple eligibility rule example
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    applications = relationship("SchemeApplication", back_populates="scheme")
    document_requirements = relationship(
        "SchemeDocumentRequirement", back_populates="scheme",
        cascade="all, delete-orphan", order_by="SchemeDocumentRequirement.id",
    )


class SchemeDocumentRequirement(Base):
    """
    One specific document a citizen must upload for a scheme (e.g.
    "Aadhaar Card", "Income Certificate"). Admin defines these one at a
    time when creating/editing a scheme, so each becomes its own separate
    upload slot on the application form rather than one bundled PDF.
    """
    __tablename__ = "scheme_document_requirements"

    id = Column(Integer, primary_key=True, index=True)
    scheme_id = Column(Integer, ForeignKey("schemes.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False)  # e.g. "Aadhaar Card", "Income Proof", "PAN Card", "Driving License"
    is_mandatory = Column(Boolean, default=True)

    scheme = relationship("Scheme", back_populates="document_requirements")

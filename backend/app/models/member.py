from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Member(Base):
    """
    A villager's household/civic record - the digitized version of the
    Panchayat's paper family register. Linked to a User only if that
    villager has portal login access (citizens do; some members registered
    by staff on paper-visit may not have logged in yet).
    """
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)

    full_name = Column(String(150), nullable=False)
    father_or_husband_name = Column(String(150), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    aadhaar_number = Column(String(20), unique=True, nullable=True)  # national ID, sensitive
    address = Column(String(255), nullable=False)
    # Jurisdiction scoping filters on district/mandal for nearly every
    # staff-facing query in the app (see app/utils/scope.py).
    village = Column(String(100), nullable=False, index=True)
    mandal = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
    state = Column(String(100), default="Andhra Pradesh")
    phone = Column(String(20), nullable=True)
    annual_income = Column(Integer, nullable=True)  # used for scheme eligibility & income certs

    family_head_id = Column(Integer, ForeignKey("members.id"), nullable=True)  # groups households

    created_by_staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="member_profile", foreign_keys=[user_id])
    applications = relationship("SchemeApplication", back_populates="member")
    certificates = relationship("Certificate", back_populates="member")

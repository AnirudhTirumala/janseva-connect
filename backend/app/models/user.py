from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    """
    Login identity for the platform. Every actor (citizen, staff, admin)
    is a User row, distinguished by `role`. A citizen User is linked 1:1
    to a Member profile via Member.user_id.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)

    # citizen | staff | admin
    role = Column(String(20), nullable=False, default="citizen")

    # Jurisdiction makes the single `admin` role useful at two levels without
    # giving a district office access to the whole state. Existing admin rows
    # with no level are deliberately treated as state admins by scope.py so a
    # running installation is upgraded safely.
    jurisdiction_level = Column(String(20), nullable=True)  # state | district | mandal
    district = Column(String(100), nullable=True, index=True)
    mandal = Column(String(100), nullable=True, index=True)
    village = Column(String(100), nullable=True)

    is_active = Column(Boolean, default=True)
    # Incremented whenever every existing JWT for this user must be revoked.
    session_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    member_profile = relationship(
        "Member", back_populates="user", uselist=False, foreign_keys="Member.user_id"
    )

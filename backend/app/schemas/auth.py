from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime

from app.schemas.common import Name150, NormalizedEmail, PhoneStr, ShortText
from app.schemas.password import StrongPassword


class UserRegister(BaseModel):
    full_name: Name150 = Field(..., min_length=2)
    email: NormalizedEmail
    phone: Optional[PhoneStr] = None
    password: StrongPassword
    # Only citizens self-register through the public form.
    # Staff/admin accounts are created by an existing admin (see users router).


class UserLogin(BaseModel):
    email: NormalizedEmail
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: int


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    jurisdiction_level: Optional[str] = None
    district: Optional[str] = None
    mandal: Optional[str] = None
    village: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserSelfUpdate(BaseModel):
    """Safe self-service changes for every signed-in account."""
    full_name: Name150 = Field(..., min_length=2)
    # 20 characters, matching users.phone - a longer value is a hard
    # DataError on PostgreSQL rather than a truncation.
    phone: Optional[PhoneStr] = None


class UserCreateByAdmin(BaseModel):
    """Admin uses this to create staff or additional admin accounts."""
    full_name: Name150 = Field(..., min_length=2)
    email: NormalizedEmail
    phone: Optional[PhoneStr] = None
    password: StrongPassword
    role: str = Field(..., pattern="^(staff|admin|citizen)$")
    jurisdiction_level: Optional[str] = Field(None, pattern="^(state|district|mandal)$")
    district: Optional[ShortText] = None
    mandal: Optional[ShortText] = None
    village: Optional[ShortText] = None
    member_profile: Optional[dict] = None

    @model_validator(mode="after")
    def validate_scope(self):
        if self.role == "admin" and self.jurisdiction_level not in ("state", "district"):
            raise ValueError("An administrator must be a state or district administrator")
        if self.role in ("staff", "admin") and not self.district and self.jurisdiction_level != "state":
            raise ValueError("District is required for staff and district administrators")
        if self.jurisdiction_level == "mandal" and not self.mandal:
            raise ValueError("Mandal is required for mandal staff")
        return self


class UserReassign(BaseModel):
    """Admin uses this to move a staff/admin account to a different
    district/mandal, or to promote staff up through mandal staff -> district
    staff -> district admin (or move an admin between districts). Only the
    fields provided are changed; anything left as None keeps its current
    value. district/mandal moved out of scope for the new role/level are
    cleared automatically by the endpoint - not the caller's job."""
    role: Optional[str] = Field(None, pattern="^(staff|admin)$")
    jurisdiction_level: Optional[str] = Field(None, pattern="^(state|district|mandal)$")
    district: Optional[ShortText] = None
    mandal: Optional[ShortText] = None

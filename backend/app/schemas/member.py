from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date, datetime

from app.schemas.common import Address255, Name150, PhoneStr, ShortText


class _MemberFieldRules(BaseModel):
    """Validation shared by create, update, and output models.

    Keeping it in one base means a PATCH can never be a way around a rule
    a POST enforces - which is exactly how bad household data gets in.
    """

    @field_validator("date_of_birth", mode="before", check_fields=False)
    @classmethod
    def blank_date_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator(
        "father_or_husband_name", "gender", "aadhaar_number", "mandal",
        "district", "phone", "state", mode="before", check_fields=False,
    )
    @classmethod
    def blank_to_none(cls, v):
        """Treats an empty-string form field the same as 'not provided'."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("aadhaar_number", check_fields=False)
    @classmethod
    def validate_aadhaar(cls, v):
        """An Aadhaar number is exactly twelve digits.

        Accepting anything else would make the uniqueness check meaningless:
        the same number typed with spaces or dashes would register as a
        second, separate household.
        """
        if v is None:
            return v
        digits = "".join(char for char in v if char.isdigit())
        if len(digits) != 12:
            raise ValueError("Aadhaar number must be exactly 12 digits.")
        return digits

    @field_validator("date_of_birth", check_fields=False)
    @classmethod
    def validate_date_of_birth(cls, v):
        if v is not None and v > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return v


# Every max_length below mirrors the column width in app/models/member.py.
# On SQLite an over-long value is silently stored; on PostgreSQL it is a
# hard DataError, so the limit is validated here and returned as a 422 the
# form can show against the right field instead.
class MemberBase(_MemberFieldRules):
    full_name: Name150 = Field(..., min_length=2)
    father_or_husband_name: Optional[Name150] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    aadhaar_number: Optional[str] = Field(None, min_length=12, max_length=20)
    address: Address255 = Field(..., min_length=1)
    village: ShortText = Field(..., min_length=1)
    mandal: Optional[ShortText] = None
    district: Optional[ShortText] = None
    state: Optional[ShortText] = "Andhra Pradesh"
    phone: Optional[PhoneStr] = None
    annual_income: Optional[int] = Field(None, ge=0, le=1_000_000_000)
    family_head_id: Optional[int] = None


class MemberCreate(MemberBase):
    user_id: Optional[int] = None  # link to a citizen login, if applicable


class MemberUpdate(_MemberFieldRules):
    """Partial update - only the fields supplied are changed."""
    full_name: Optional[Name150] = Field(None, min_length=2)
    father_or_husband_name: Optional[Name150] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    aadhaar_number: Optional[str] = Field(None, min_length=12, max_length=20)
    address: Optional[Address255] = Field(None, min_length=1)
    village: Optional[ShortText] = Field(None, min_length=1)
    mandal: Optional[ShortText] = None
    district: Optional[ShortText] = None
    state: Optional[ShortText] = None
    phone: Optional[PhoneStr] = None
    annual_income: Optional[int] = Field(None, ge=0, le=1_000_000_000)
    family_head_id: Optional[int] = None


class CitizenProfileUpdate(MemberUpdate):
    """A citizen may keep every personal household detail current.

    family_head_id is the one exception: it links one household record to
    another and is an office decision, so a value sent from the citizen
    form is ignored rather than rejected (the field is simply not theirs
    to set, and failing the whole save over it would be unhelpful).
    """

    @field_validator("family_head_id", mode="before")
    @classmethod
    def ignore_family_head(cls, _v):
        return None


class MemberOut(BaseModel):
    """Read model - deliberately unvalidated.

    Output must faithfully reflect what is stored, including rows written
    before a rule existed; re-running write-side validation here would turn
    old data into a 500 on a read.
    """
    id: int
    user_id: Optional[int] = None
    full_name: str
    father_or_husband_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    aadhaar_number: Optional[str] = None
    address: str
    village: str
    mandal: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    annual_income: Optional[int] = None
    family_head_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

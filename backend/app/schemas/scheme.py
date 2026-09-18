from pydantic import BaseModel, Field, StringConstraints, field_validator
from typing import Annotated, Optional, List
from datetime import datetime

DocumentName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)]


class DocumentRequirementOut(BaseModel):
    id: int
    name: str
    is_mandatory: bool

    class Config:
        from_attributes = True


class SchemeBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = Field(..., min_length=1, max_length=5000)
    eligibility_criteria: Optional[str] = Field(None, max_length=5000)
    max_income_limit: Optional[int] = Field(None, ge=0, le=1_000_000_000)
    is_active: bool = True

    @field_validator("eligibility_criteria", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("max_income_limit", mode="before")
    @classmethod
    def blank_income_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class SchemeCreate(SchemeBase):
    # Each entry becomes its own separate upload slot on the application
    # form, e.g. ["Aadhaar Card", "Income Proof", "PAN Card"] - not one
    # combined document.
    document_requirement_names: List[DocumentName] = Field(default_factory=list, max_length=25)


class SchemeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = Field(None, min_length=1, max_length=5000)
    eligibility_criteria: Optional[str] = Field(None, max_length=5000)
    max_income_limit: Optional[int] = Field(None, ge=0, le=1_000_000_000)
    is_active: Optional[bool] = None
    # If provided, REPLACES the full set of document requirements.
    # scheme_document_requirements.name is VARCHAR(150), and an unbounded
    # list would let one scheme create arbitrarily many upload slots.
    document_requirement_names: Optional[List[DocumentName]] = Field(None, max_length=25)


class SchemeOut(SchemeBase):
    id: int
    created_at: datetime
    document_requirements: List[DocumentRequirementOut] = []

    class Config:
        from_attributes = True

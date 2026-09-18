from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class CertificateCreate(BaseModel):
    member_id: int
    certificate_type: str = Field(..., min_length=2, max_length=50)


class CertificateOut(BaseModel):
    id: int
    member_id: int
    member_name: str | None = None
    certificate_type: str
    certificate_number: str
    issued_by_id: int
    issued_by_name: str | None = None
    file_path: str | None = None
    issued_at: datetime

    class Config:
        from_attributes = True


class CertificateRequestCreate(BaseModel):
    certificate_type: str = Field(..., min_length=2, max_length=50)
    purpose: str | None = Field(None, max_length=1000)


class CertificateRequestReview(BaseModel):
    status: Literal["approved", "rejected"]
    review_remarks: str | None = Field(None, max_length=1000)


class CertificateRequestOut(BaseModel):
    id: int
    member_id: int
    member_name: str | None = None
    requested_by_name: str | None = None
    certificate_type: str
    purpose: str | None = None
    status: str
    review_remarks: str | None = None
    reviewed_by_name: str | None = None
    certificate_id: int | None = None
    certificate_number: str | None = None
    issued_by_name: str | None = None
    issued_at: datetime | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

    class Config:
        from_attributes = True

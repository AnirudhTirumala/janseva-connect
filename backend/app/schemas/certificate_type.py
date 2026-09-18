from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class CertificateTypeCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=150)
    description: str | None = Field(None, max_length=1000)
    prefix: str = Field("CRT", min_length=2, max_length=8)

    @field_validator("prefix")
    @classmethod
    def clean_prefix(cls, value: str):
        return "".join(c for c in value.upper() if c.isalnum())


class CertificateTypeUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=150)
    description: str | None = Field(None, max_length=1000)
    prefix: str | None = Field(None, min_length=2, max_length=8)
    is_active: bool | None = None


class CertificateTypeOut(BaseModel):
    id: int | None = None
    key: str
    name: str
    description: str | None = None
    prefix: str
    is_active: bool
    created_at: datetime | None = None

    class Config:
        from_attributes = True

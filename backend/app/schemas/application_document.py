from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


class ApplicationDocumentOut(BaseModel):
    id: int
    application_id: int
    requirement_id: Optional[int] = None
    document_name: str
    original_filename: str
    content_type: Optional[str] = None
    status: str
    remarks: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class DocumentReview(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    remarks: Optional[str] = Field(None, max_length=2000)

    @model_validator(mode="after")
    def require_remarks_on_rejection(self):
        if self.status == "rejected" and not (self.remarks and self.remarks.strip()):
            raise ValueError("A reason is required when rejecting a document.")
        return self

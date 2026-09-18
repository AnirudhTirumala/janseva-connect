from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime


class ApplicationCreate(BaseModel):
    scheme_id: int
    member_id: Optional[int] = None  # staff can submit on behalf of a member; citizens use their own


class ApplicationReview(BaseModel):
    status: str = Field(..., pattern="^(under_review|approved|rejected)$")
    remarks: Optional[str] = Field(None, max_length=2000)

    @model_validator(mode="after")
    def require_remarks_on_rejection(self):
        """
        A rejection must always come with a reason - both so the citizen
        understands what to fix, and so there's a transparent record of
        why for anyone reviewing the application's history later.
        """
        if self.status == "rejected" and not (self.remarks and self.remarks.strip()):
            raise ValueError("A reason is required when rejecting an application.")
        return self


class ApplicationOut(BaseModel):
    id: int
    member_id: int
    # Served with the application so a staff table does not have to download
    # the entire member register just to show who applied.
    member_name: Optional[str] = None
    scheme_id: int
    status: str
    remarks: Optional[str] = None
    reviewed_by_id: Optional[int] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    submitted_at: datetime
    # Whether every mandatory document for this scheme has been uploaded.
    # True when the scheme has no mandatory documents at all. A citizen
    # should only ever see "Already applied" once this is true - otherwise
    # they applied but haven't actually finished providing what's needed.
    documents_complete: bool = True
    required_document_count: int = 0
    uploaded_document_count: int = 0
    # A required document is reviewed only after staff has recorded its own
    # approve/reject result. These fields keep the UI honest and explain why
    # an application-level action is disabled.
    documents_reviewed: bool = True
    documents_approved: bool = True
    document_review_pending_count: int = 0

    class Config:
        from_attributes = True

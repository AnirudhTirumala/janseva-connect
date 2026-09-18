from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class IssueCreate(BaseModel):
    title: str = Field(..., min_length=4, max_length=150)
    description: str = Field(..., min_length=10, max_length=2000)
    # Previously fixed at "civic": the application and portal desks could only
    # be filled by the AI assistant's escalation path, so a citizen looking at
    # those tabs found a read-only page with no way to report anything - and
    # no way at all if the AI provider was not configured.
    category: Literal["civic", "application", "portal"] = "civic"


class IssueReply(BaseModel):
    status: Literal["open", "in_progress", "resolved"]
    reply: str = Field(..., min_length=2, max_length=2000)


class IssueCitizenResponse(BaseModel):
    """Citizen confirms or disputes a 'resolved' issue. accepted=True closes
    it for good; accepted=False reopens it, optionally with feedback on
    why the fix wasn't good enough."""
    accepted: bool
    feedback: str | None = Field(None, max_length=2000)


class IssueOut(BaseModel):
    id: int
    citizen_user_id: int
    citizen_name: str | None = None
    title: str
    description: str
    village: str | None = None
    mandal: str | None = None
    district: str | None = None
    category: str = "civic"  # civic | portal | application
    source: str = "citizen"  # citizen | ai_assistant
    status: str  # open | in_progress | resolved | closed | reopened
    reply: str | None = None
    replied_by_name: str | None = None
    replied_at: datetime | None = None
    citizen_feedback: str | None = None
    citizen_responded_at: datetime | None = None
    created_at: datetime
    is_overdue: bool = False

    class Config:
        from_attributes = True

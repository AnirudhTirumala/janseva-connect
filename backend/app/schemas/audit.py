from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AuditClickCreate(BaseModel):
    event_type: str = Field(default="ui_click", max_length=40)
    path: str = Field(..., min_length=1, max_length=255)
    target: str = Field(..., min_length=1, max_length=120)
    metadata: Optional[Dict[str, str]] = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value):
        if value is None:
            return value
        if set(value) - {"element"}:
            raise ValueError("Unsupported audit metadata")
        if any(len(item) > 40 for item in value.values()):
            raise ValueError("Audit metadata values must be 40 characters or fewer")
        return value


class AuditEventOut(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    actor_role: Optional[str] = None
    event_type: str
    action: str
    route: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    outcome: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OtpHistoryOut(BaseModel):
    id: int
    email: str
    purpose: str
    is_used: bool
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True

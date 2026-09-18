from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationOut(BaseModel):
    id: int
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    issue_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

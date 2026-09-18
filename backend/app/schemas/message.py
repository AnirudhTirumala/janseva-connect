from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

from app.schemas.common import ShortText


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)
    citizen_user_id: int | None = None  # required when staff/admin sends; ignored for citizens (always their own thread)


class MessageOut(BaseModel):
    id: int
    citizen_user_id: int
    sender_id: int
    sender_name: str | None = None
    sender_role: str | None = None
    body: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    citizen_user_id: int
    citizen_name: str
    citizen_email: str
    last_message: str | None = None
    last_message_at: datetime | None = None
    unread_count: int
    has_conversation: bool = False


class StaffContactOut(BaseModel):
    id: int
    full_name: str
    role: str
    jurisdiction_level: str | None = None


class InternalMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)
    # Explicit channel send. leadership is only super/state admins;
    # district_admins is the management forum; district and mandal are the
    # staff working groups. scope="leadership"|"district_admins"|"district"|
    # "mandal" (legacy "all" is retained for old links); when
    # scope is omitted entirely, the message posts to the sender's own
    # default channel (the original behaviour, still used by mandal-level
    # staff who don't get a channel picker).
    scope: Literal["all", "leadership", "district_admins", "district", "mandal"] | None = None
    district: ShortText | None = None
    mandal: ShortText | None = None


class InternalMessageOut(BaseModel):
    id: int
    district: str
    mandal: str | None = None
    sender_id: int
    sender_name: str | None = None
    sender_role: str | None = None
    body: str
    created_at: datetime

    class Config:
        from_attributes = True

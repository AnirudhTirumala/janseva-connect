from datetime import date, datetime
from pydantic import BaseModel, Field


class WeeklyActivityCreate(BaseModel):
    week_start: date
    summary: str = Field(..., min_length=10, max_length=5000)
    achievements: str | None = Field(None, max_length=3000)
    blockers: str | None = Field(None, max_length=3000)


class WeeklyActivityOut(WeeklyActivityCreate):
    id: int
    district: str
    submitted_by_id: int
    submitted_by_name: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True

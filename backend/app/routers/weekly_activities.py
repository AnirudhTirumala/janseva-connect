from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.models.weekly_activity import WeeklyActivity
from app.schemas.weekly_activity import WeeklyActivityCreate, WeeklyActivityOut
from app.utils.scope import is_district_admin, is_state_admin


router = APIRouter(prefix="/api/weekly-activities", tags=["Weekly activities"])


def _out(item: WeeklyActivity, db: Session):
    item.submitted_by_name = db.query(User.full_name).filter(User.id == item.submitted_by_id).scalar()
    return item


@router.get("/", response_model=List[WeeklyActivityOut])
def list_weekly_activities(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin")),
):
    query = db.query(WeeklyActivity)
    if is_district_admin(current_user):
        query = query.filter(WeeklyActivity.district == current_user.district)
    elif not is_state_admin(current_user):
        raise HTTPException(status_code=403, detail="Only state and district administrators can view weekly activity")
    return [_out(item, db) for item in query.order_by(WeeklyActivity.week_start.desc(), WeeklyActivity.created_at.desc()).all()]


@router.post("/", response_model=WeeklyActivityOut, status_code=201)
def submit_weekly_activity(
    payload: WeeklyActivityCreate,
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin")),
):
    if not is_district_admin(current_user) or not current_user.district:
        raise HTTPException(status_code=403, detail="Only a district administrator can formally submit a weekly activity")
    existing = db.query(WeeklyActivity).filter(
        WeeklyActivity.district == current_user.district,
        WeeklyActivity.week_start == payload.week_start,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A weekly activity has already been submitted for this district and week")
    activity = WeeklyActivity(district=current_user.district, submitted_by_id=current_user.id, **payload.model_dump())
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return _out(activity, db)

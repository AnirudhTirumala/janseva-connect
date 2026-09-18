from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.rate_limit import limiter
from app.models.audit_event import AuditEvent
from app.models.otp import EmailOTP
from app.models.user import User
from app.schemas.audit import AuditClickCreate, AuditEventOut, OtpHistoryOut
from app.utils.audit import log_event
from app.utils.scope import is_state_admin

router = APIRouter(prefix="/api/audit", tags=["Audit Trail"])


@router.post("/click", status_code=201)
# The frontend attaches one document-level click listener, so this is the
# highest-volume write in the app. The cap keeps a stuck UI (or a scripted
# client) from turning the audit table into an unbounded write amplifier.
@limiter.limit("120/minute")
def track_click(
    payload: AuditClickCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records an authenticated interaction without collecting form values."""
    log_event(
        db,
        event_type="ui_click",
        action=payload.target,
        actor=current_user,
        route=payload.path,
        target_type=(payload.metadata or {}).get("element"),
        details={"source": "web"},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"recorded": True}


@router.get("/events", response_model=List[AuditEventOut])
def list_events(
    limit: int = 250,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    safe_limit = min(max(limit, 1), 500)
    if not is_state_admin(_admin):
        raise HTTPException(status_code=403, detail="Only state administrators can view the platform audit trail")
    return db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(safe_limit).all()


@router.get("/otps", response_model=List[OtpHistoryOut])
def list_otp_history(
    limit: int = 250,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    """Shows delivery history metadata only; OTP codes are never returned."""
    safe_limit = min(max(limit, 1), 500)
    if not is_state_admin(_admin):
        raise HTTPException(status_code=403, detail="Only state administrators can view OTP delivery history")
    return db.query(EmailOTP).order_by(EmailOTP.created_at.desc()).limit(safe_limit).all()

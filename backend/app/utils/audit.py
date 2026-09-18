"""Small helpers for safe, structured, append-only audit entries."""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent
from app.models.user import User
from app.core.database import SessionLocal
from app.core.security import decode_access_token


def log_event(
    db: Session,
    *,
    event_type: str,
    action: str,
    actor=None,
    route: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[object] = None,
    outcome: Optional[str] = "success",
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> AuditEvent:
    """Queue an event in the caller's transaction; callers commit as usual."""
    event = AuditEvent(
        actor_user_id=getattr(actor, "id", None),
        actor_role=getattr(actor, "role", None),
        event_type=event_type,
        action=action,
        route=route,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        outcome=outcome,
        details=details,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(event)
    return event


def log_api_action(method: str, path: str, status_code: int, authorization: Optional[str] = None) -> None:
    """Persists the outcome of each state-changing API call in its own session.

    It intentionally records no request body, which keeps passwords, OTPs,
    uploaded documents, and personal data out of the audit trail.
    """
    db = SessionLocal()
    try:
        actor = None
        if authorization and authorization.lower().startswith("bearer "):
            payload = decode_access_token(authorization.split(" ", 1)[1])
            user_id = payload.get("sub") if payload else None
            if user_id:
                actor = db.query(User).filter(User.id == user_id).first()
        log_event(
            db,
            event_type="api_action",
            action=f"{method} {path}",
            actor=actor,
            route=path,
            target_type="api_endpoint",
            outcome="success" if status_code < 400 else "failed",
            details={"status_code": status_code},
        )
        db.commit()
    except Exception:
        # Audit availability must not take the citizen portal offline.
        db.rollback()
    finally:
        db.close()

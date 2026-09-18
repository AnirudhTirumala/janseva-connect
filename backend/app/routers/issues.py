from datetime import timedelta
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.rate_limit import limiter
from app.models.user import User
from app.models.member import Member
from app.models.issue import Issue
from app.schemas.issue import IssueCitizenResponse, IssueCreate, IssueOut, IssueReply
from app.core.timeutils import as_utc, utcnow
from app.utils.email_client import send_issue_reply_email
from app.services.citizen_actions import CitizenActionError, raise_issue_for
from app.utils.notifications import create_notification
from app.utils.scope import can_access_location, officers_for_location, scope_issues_for_officer

router = APIRouter(prefix="/api/issues", tags=["Local issues"])

REPLY_WINDOW = timedelta(days=7)


def _with_issue_info(issue: Issue) -> Issue:
    issue.citizen_name = issue.citizen.full_name if issue.citizen else None
    issue.replied_by_name = issue.replied_by.full_name if issue.replied_by else None
    created_at = as_utc(issue.created_at)
    issue.is_overdue = (
        issue.status not in ("resolved", "closed")
        and created_at is not None
        and (utcnow() - created_at) > REPLY_WINDOW
    )
    return issue


@router.post("/", response_model=IssueOut, status_code=201)
@limiter.limit("20/hour")
def raise_issue(
    request: Request,
    payload: IssueCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("citizen")),
):
    """Citizen raises a local issue for their village/mandal/district. The
    office aims to reply within a week; office staff see a countdown."""
    try:
        issue = raise_issue_for(
            db, current_user, payload.title, payload.description,
            category=payload.category, background_tasks=background_tasks
        )
    except CitizenActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _with_issue_info(issue)


@router.get("/", response_model=List[IssueOut])
def list_issues(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Citizen: only their own raised issues. Staff/Admin: every issue
    inside their assigned jurisdiction (state admin sees everything)."""
    query = db.query(Issue).options(joinedload(Issue.citizen), joinedload(Issue.replied_by))
    if current_user.role == "citizen":
        query = query.filter(Issue.citizen_user_id == current_user.id)
    elif current_user.role in ("staff", "admin"):
        query = scope_issues_for_officer(query, current_user, Issue)
    else:
        raise HTTPException(status_code=403, detail="Not authorized")
    return [_with_issue_info(i) for i in query.order_by(Issue.created_at.desc()).all()]


@router.patch("/{issue_id}", response_model=IssueOut)
def reply_to_issue(
    issue_id: int,
    payload: IssueReply,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    issue = (
        db.query(Issue)
        .options(joinedload(Issue.citizen), joinedload(Issue.replied_by))
        .filter(Issue.id == issue_id)
        .first()
    )
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if not can_access_location(current_user, issue.district, issue.mandal):
        raise HTTPException(status_code=403, detail="You can only reply to issues in your assigned jurisdiction")
    issue.status = payload.status
    issue.reply = payload.reply.strip()
    issue.replied_by_id = current_user.id
    issue.replied_at = utcnow()
    if payload.status == "resolved":
        # A fresh resolution attempt supersedes any earlier rejection.
        issue.citizen_feedback = None
        issue.citizen_responded_at = None
    create_notification(db, issue.citizen_user_id, f"Update on your issue: {issue.title}", issue.reply, link="/issues", issue_id=issue.id)
    db.commit()
    db.refresh(issue)
    # The office's answer went only to the in-portal bell before this, so a
    # citizen who does not sign in again never learns their issue was handled.
    if issue.citizen and issue.citizen.email:
        background_tasks.add_task(
            send_issue_reply_email, issue.citizen.email, issue.citizen.full_name,
            issue.title, issue.status, issue.reply,
        )
    return _with_issue_info(issue)


@router.patch("/{issue_id}/respond", response_model=IssueOut)
def respond_to_resolution(
    issue_id: int,
    payload: IssueCitizenResponse,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("citizen")),
):
    """The citizen who raised the issue confirms or disputes a 'resolved'
    reply. Accepting closes it for good; rejecting reopens it (with
    optional feedback on what's still wrong) and notifies whoever replied,
    so a fix that didn't actually land doesn't just sit there marked done."""
    issue = (
        db.query(Issue)
        .options(joinedload(Issue.citizen), joinedload(Issue.replied_by))
        .filter(Issue.id == issue_id)
        .first()
    )
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.citizen_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This isn't your issue to respond to")
    if issue.status != "resolved":
        raise HTTPException(status_code=400, detail="Only a resolved issue can be accepted or rejected")

    issue.citizen_feedback = (payload.feedback or "").strip() or None
    issue.citizen_responded_at = utcnow()

    if payload.accepted:
        issue.status = "closed"
        if issue.replied_by_id:
            create_notification(db, issue.replied_by_id, f"Issue confirmed resolved: {issue.title}", f"{current_user.full_name} confirmed this issue is resolved.", link="/issues", issue_id=issue.id)
    else:
        issue.status = "reopened"
        if issue.replied_by_id:
            note = issue.citizen_feedback or "No additional details were given."
            create_notification(db, issue.replied_by_id, f"Issue reopened: {issue.title}", f"{current_user.full_name} was not satisfied with the resolution: {note}", link="/issues", issue_id=issue.id)

    db.commit()
    db.refresh(issue)
    return _with_issue_info(issue)

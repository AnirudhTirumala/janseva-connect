from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, not_

from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.core.timeutils import utc_ago
from app.models.user import User
from app.models.member import Member
from app.models.scheme import Scheme
from app.models.application import SchemeApplication
from app.models.certificate import Certificate
from app.models.certificate_request import CertificateRequest
from app.models.issue import Issue
from app.models.notification import Notification
from app.utils.application_readiness import awaiting_citizen_clause
from app.utils.scope import scope_members, scope_issues_for_officer

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard & Reports"])


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin: single-call aggregate stats for the dashboard home screen -
    replaces the manual monthly counting the office currently does by hand.
    """
    thirty_days_ago = utc_ago(days=30)

    members = scope_members(db.query(Member), current_user)
    certificates = scope_members(db.query(Certificate).join(Member, Member.id == Certificate.member_id), current_user)
    applications = scope_members(db.query(SchemeApplication).join(Member, Member.id == SchemeApplication.member_id), current_user)

    total_members = members.with_entities(func.count(Member.id)).scalar()
    new_members_30d = members.filter(Member.created_at >= thirty_days_ago).with_entities(func.count(Member.id)).scalar()

    total_certificates = certificates.with_entities(func.count(Certificate.id)).scalar()
    certificates_30d = certificates.filter(Certificate.issued_at >= thirty_days_ago).with_entities(func.count(Certificate.id)).scalar()

    applications_by_status = dict(
        applications.with_entities(SchemeApplication.status, func.count(SchemeApplication.id))
        .group_by(SchemeApplication.status)
        .all()
    )

    active_schemes = db.query(func.count(Scheme.id)).filter(Scheme.is_active == True).scalar()  # noqa: E712

    certificates_by_type = dict(
        certificates.with_entities(Certificate.certificate_type, func.count(Certificate.id))
        .group_by(Certificate.certificate_type)
        .all()
    )

    return {
        "total_members": total_members,
        "new_members_last_30_days": new_members_30d,
        "total_certificates_issued": total_certificates,
        "certificates_issued_last_30_days": certificates_30d,
        "active_schemes": active_schemes,
        "applications_by_status": applications_by_status,
        "certificates_by_type": certificates_by_type,
    }


@router.get("/weekly")
def weekly_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin: a rolling 7-day view of throughput - certificates issued,
    and how many scheme applications were cleared (approved/rejected) vs.
    are still pending - so the office can see at a glance whether this
    week's workload is being kept up with.
    """
    seven_days_ago = utc_ago(days=7)

    certificates = scope_members(db.query(Certificate).join(Member, Member.id == Certificate.member_id), current_user)
    applications = scope_members(db.query(SchemeApplication).join(Member, Member.id == SchemeApplication.member_id), current_user)
    certificates_this_week = certificates.filter(Certificate.issued_at >= seven_days_ago).with_entities(func.count(Certificate.id)).scalar()
    certificates_by_type_week = dict(
        certificates.with_entities(Certificate.certificate_type, func.count(Certificate.id))
        .filter(Certificate.issued_at >= seven_days_ago)
        .group_by(Certificate.certificate_type)
        .all()
    )

    applications_submitted_this_week = (
        applications.filter(SchemeApplication.submitted_at >= seven_days_ago).with_entities(func.count(SchemeApplication.id)).scalar()
    )
    approved_this_week = (
        applications.with_entities(func.count(SchemeApplication.id))
        .filter(SchemeApplication.status == "approved", SchemeApplication.reviewed_at >= seven_days_ago)
        .scalar()
    )
    rejected_this_week = (
        applications.with_entities(func.count(SchemeApplication.id))
        .filter(SchemeApplication.status == "rejected", SchemeApplication.reviewed_at >= seven_days_ago)
        .scalar()
    )
    total_pending = (
        applications.with_entities(func.count(SchemeApplication.id))
        .filter(SchemeApplication.status.in_(["pending", "under_review"]))
        .scalar()
    )

    cleared = approved_this_week + rejected_this_week

    return {
        "period": "last_7_days",
        "certificates_issued": certificates_this_week,
        "certificates_by_type": certificates_by_type_week,
        "applications_submitted": applications_submitted_this_week,
        "applications_cleared": cleared,
        "applications_approved": approved_this_week,
        "applications_rejected": rejected_this_week,
        "applications_still_pending_total": total_pending,
    }


@router.get("/nav-counts")
def nav_counts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Real-time sidebar badge counts, always computed live (never cached):
    for staff/admin, how many items in their own jurisdiction are still
    waiting on them right now; for citizens, how many unread updates they
    have in each section (reuses the existing notification read-tracking,
    since there's no separate "seen" flag on applications/certificates/
    issues themselves). Chat has its own dedicated unread-count endpoint
    and isn't duplicated here.

    "assistant" is a distinct lens on top of "issues": specifically how
    much of that came through an AI assistant conversation (Issue.source
    == "ai_assistant") rather than every open/updated issue regardless of
    source - so the AI Assistant nav item's own badge means something,
    instead of just repeating the Issues badge.
    """
    if current_user.role == "citizen":
        rows = (
            db.query(Notification.link, func.count(Notification.id))
            .filter(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
            .group_by(Notification.link)
            .all()
        )
        by_link = {link: count for link, count in rows if link}
        assistant_unread = (
            db.query(func.count(Notification.id))
            .join(Issue, Issue.id == Notification.issue_id)
            .filter(Notification.user_id == current_user.id, Notification.is_read == False, Issue.source == "ai_assistant")  # noqa: E712
            .scalar()
        )
        return {
            "applications": by_link.get("/applications", 0),
            "certificates": by_link.get("/certificates", 0),
            "issues": by_link.get("/issues", 0),
            "assistant": assistant_unread or 0,
        }

    if current_user.role not in ("staff", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    # The badge sits on the link that opens the queue, so it is a promise
    # about the length of the list behind it. The queue defaults to actionable
    # rows, so this must exclude the ones still waiting on the citizen -
    # otherwise the badge reads 3 over a list of 1, which is exactly the
    # badge/list contradiction this app just had to fix once already.
    pending_applications = (
        scope_members(db.query(SchemeApplication).join(Member, Member.id == SchemeApplication.member_id), current_user)
        .filter(SchemeApplication.status.in_(["pending", "under_review"]))
        .filter(not_(awaiting_citizen_clause()))
        .with_entities(func.count(SchemeApplication.id))
        .scalar()
    )
    pending_certificates = (
        scope_members(db.query(CertificateRequest).join(Member, Member.id == CertificateRequest.member_id), current_user)
        .filter(CertificateRequest.status == "pending")
        .with_entities(func.count(CertificateRequest.id))
        .scalar()
    )
    visible_issues = scope_issues_for_officer(db.query(Issue), current_user, Issue)
    open_issues = (
        visible_issues
        .filter(Issue.status == "open")
        .with_entities(func.count(Issue.id))
        .scalar()
    )
    assistant_flagged = (
        scope_issues_for_officer(db.query(Issue), current_user, Issue)
        .filter(Issue.status == "open", Issue.source == "ai_assistant")
        .with_entities(func.count(Issue.id))
        .scalar()
    )
    return {
        "applications": pending_applications or 0,
        "certificates": pending_certificates or 0,
        "issues": open_issues or 0,
        "assistant": assistant_flagged or 0,
    }

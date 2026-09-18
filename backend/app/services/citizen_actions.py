"""The two things a citizen can ask the platform to DO, in one place.

Requesting a certificate and raising an issue are reachable two ways now: the
ordinary forms, and the AI assistant acting on a citizen's behalf. Both go
through these functions.

That is deliberate and it is the whole security design. If the assistant had
its own copy of "create a CertificateRequest", every rule enforced by the REST
endpoint - you must have a household profile, the type must exist and be
active, you may not hold two live requests for the same certificate - would
have to be remembered and re-implemented there, and the first one forgotten
becomes a way to get through the portal by asking a language model nicely.

Two invariants these functions guarantee, and callers cannot override:

* Every record is attached to the SIGNED-IN citizen. There is no member_id or
  user_id parameter. A model cannot be argued into filing something against
  somebody else's household, because the identity is not part of its input.
* Nothing here approves, rejects, issues, or deletes anything. These are the
  create-side actions a citizen may already perform themselves; the assistant
  gets no authority its user does not have.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models.certificate_request import CertificateRequest
from app.models.issue import Issue
from app.models.member import Member
from app.models.user import User
from app.utils.email_client import (
    send_certificate_request_received_email,
    send_issue_received_email,
)
from app.utils.issue_escalation import issue_audience
from app.utils.notifications import create_notification
from app.utils.scope import officer_users_for_member, officers_for_location

ISSUE_CATEGORIES = ("civic", "application", "portal")


class CitizenActionError(Exception):
    """A refusal the citizen should read, not a server fault.

    `status_code` lets the REST routers translate it back into the exact HTTP
    codes they returned before, while the assistant turns `message` into plain
    words. One rule, two presentations.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _require_member(db: Session, citizen: User, action: str) -> Member:
    member = db.query(Member).filter(Member.user_id == citizen.id).first()
    if not member:
        raise CitizenActionError(
            f"Complete your citizen profile before {action}", status_code=400
        )
    return member


def request_certificate_for(
    db: Session,
    citizen: User,
    certificate_type: str,
    purpose: Optional[str] = None,
    background_tasks=None,
) -> CertificateRequest:
    """File a certificate request for this citizen's own household record.

    `purpose` is optional by design - the office can review a request without
    one - so the assistant is free to submit immediately when the citizen does
    not volunteer a reason.
    """
    # Imported here: certificates.py imports this module for its own routes,
    # so a module-level import would be circular.
    from app.routers.certificates import _type_info, _type_name

    member = _require_member(db, citizen, "requesting a certificate")

    try:
        info = _type_info(db, certificate_type)
    except Exception as exc:  # _type_info raises HTTPException for unknown/inactive
        detail = getattr(exc, "detail", "That certificate type is not available.")
        raise CitizenActionError(str(detail), status_code=getattr(exc, "status_code", 404)) from exc

    normalized = certificate_type.strip().lower().replace(" ", "-")
    duplicate = (
        db.query(CertificateRequest)
        .filter(
            CertificateRequest.member_id == member.id,
            CertificateRequest.certificate_type == normalized,
            CertificateRequest.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if duplicate:
        raise CitizenActionError(
            "You already have an active request for this certificate type", status_code=409
        )

    request = CertificateRequest(
        member_id=member.id,
        requested_by_id=citizen.id,
        certificate_type=normalized,
        purpose=(purpose or "").strip() or None,
    )
    db.add(request)
    for officer in officer_users_for_member(db.query(User), member).all():
        create_notification(
            db, officer.id, "New certificate request",
            f"{citizen.full_name} requested a {_type_name(info)}.", link="/certificates",
        )
    db.commit()
    db.refresh(request)

    if background_tasks is not None:
        background_tasks.add_task(
            send_certificate_request_received_email,
            citizen.email, citizen.full_name, _type_name(info),
        )
    return request


def raise_issue_for(
    db: Session,
    citizen: User,
    title: str,
    description: str,
    category: str = "civic",
    source: str = "citizen",
    background_tasks=None,
) -> Issue:
    """Record an issue and notify whoever can actually act on it.

    Routing differs by category and is not the caller's choice to make: a
    portal defect goes to the platform administrators and carries no location,
    because it is not one mandal's problem.
    """
    if category not in ISSUE_CATEGORIES:
        raise CitizenActionError(
            f"Unknown issue type. Use one of: {', '.join(ISSUE_CATEGORIES)}.", status_code=422
        )

    member = _require_member(db, citizen, "raising an issue")
    is_portal = category == "portal"

    issue = Issue(
        citizen_user_id=citizen.id,
        title=title.strip()[:150],
        description=description.strip()[:2000],
        category=category,
        source=source,
        village=None if is_portal else member.village,
        mandal=None if is_portal else member.mandal,
        district=None if is_portal else member.district,
    )
    db.add(issue)
    db.flush()

    if category == "civic":
        recipients = officers_for_location(db.query(User), member.district, member.mandal).all()
        heading = "New local issue raised"
    else:
        recipients, _ = issue_audience(db, category)
        heading = (
            "New portal problem reported" if is_portal else "New application/service problem reported"
        )
    for officer in recipients:
        create_notification(
            db, officer.id, heading, f"{citizen.full_name}: {issue.title}",
            link="/issues", issue_id=issue.id,
        )
    db.commit()
    db.refresh(issue)

    # Proof of receipt. Reporting a problem is the one action whose entire
    # point is being noticed, and it was the only one that acknowledged
    # nothing back to the person who reported it.
    if background_tasks is not None and citizen.email:
        background_tasks.add_task(
            send_issue_received_email, citizen.email, citizen.full_name, issue.category, issue.title
        )
    return issue

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.timeutils import utcnow
from app.models.user import User
from app.models.member import Member
from app.models.scheme import Scheme
from app.models.application import SchemeApplication
from app.schemas.application import ApplicationCreate, ApplicationReview, ApplicationOut
from sqlalchemy import func

from app.utils.application_readiness import apply_queue_view, awaiting_citizen_clause
from app.utils.notifications import create_notification
from app.utils.email_client import send_application_received_email, send_application_status_email
from app.utils.pdf_generator import generate_approval_pdf
from app.utils.scope import can_access_member, officer_users_for_member, scope_members

router = APIRouter(prefix="/api/applications", tags=["Scheme Applications"])


def _with_reviewer_name(application: SchemeApplication, db: Session) -> SchemeApplication:
    if application.reviewed_by_id:
        reviewer = db.query(User).filter(User.id == application.reviewed_by_id).first()
        application.reviewed_by_name = reviewer.full_name if reviewer else None
    else:
        application.reviewed_by_name = None
    return application


def _decorate_all(applications: list[SchemeApplication], db: Session) -> list[SchemeApplication]:
    """Attach reviewer name, applicant name, and document state to a list.

    Names are resolved with two batched queries rather than two per row: the
    per-application lookups were an N+1 that made a district queue of a few
    hundred applications issue hundreds of round trips to render one table.
    """
    if not applications:
        return []

    reviewer_ids = {a.reviewed_by_id for a in applications if a.reviewed_by_id}
    reviewer_names = dict(
        db.query(User.id, User.full_name).filter(User.id.in_(reviewer_ids)).all()
    ) if reviewer_ids else {}

    member_ids = {a.member_id for a in applications}
    member_names = dict(
        db.query(Member.id, Member.full_name).filter(Member.id.in_(member_ids)).all()
    )

    scheme_ids = {a.scheme_id for a in applications}
    schemes = {
        s.id: s for s in db.query(Scheme).filter(Scheme.id.in_(scheme_ids)).all()
    }

    for application in applications:
        application.reviewed_by_name = reviewer_names.get(application.reviewed_by_id)
        application.member_name = member_names.get(application.member_id)
        for key, value in _document_review_summary(application, schemes.get(application.scheme_id)).items():
            setattr(application, key, value)
    return applications


def _document_review_summary(application: SchemeApplication, scheme: Scheme | None) -> dict:
    """Return the required-document state for both the UI and server-side
    decision guard. A document is *reviewed* only once an officer has made
    its individual approve/reject decision; simply opening a modal cannot
    unlock an application approval."""
    mandatory_requirements = [r for r in (scheme.document_requirements if scheme else []) if r.is_mandatory]
    documents_by_requirement = {d.requirement_id: d for d in application.documents if d.requirement_id is not None}
    documents_by_name = {d.document_name: d for d in application.documents}
    required_documents = [documents_by_requirement.get(req.id) or documents_by_name.get(req.name) for req in mandatory_requirements]
    uploaded_documents = [document for document in required_documents if document]
    pending_review_count = sum(document.status == "pending" for document in uploaded_documents)
    rejected_count = sum(document.status == "rejected" for document in uploaded_documents)
    documents_complete = len(uploaded_documents) == len(mandatory_requirements)
    documents_reviewed = documents_complete and pending_review_count == 0
    documents_approved = documents_reviewed and rejected_count == 0
    return {
        "required_document_count": len(mandatory_requirements),
        "uploaded_document_count": len(uploaded_documents),
        "document_review_pending_count": pending_review_count,
        "documents_complete": documents_complete,
        "documents_reviewed": documents_reviewed,
        "documents_approved": documents_approved,
    }


def _with_applicant_name(application: SchemeApplication, db: Session) -> SchemeApplication:
    member = db.query(Member.full_name).filter(Member.id == application.member_id).scalar()
    application.member_name = member
    return application


def _with_document_status(application: SchemeApplication, db: Session) -> SchemeApplication:
    """Attach the required-document and individual-review state to an
    application response. This lets the client explain exactly why an
    application action is locked, while the same truth is enforced below on
    the API rather than trusting a browser-only button state."""
    scheme = db.query(Scheme).filter(Scheme.id == application.scheme_id).first()
    for key, value in _document_review_summary(application, scheme).items():
        setattr(application, key, value)
    return application


def _resolve_member_for_user(current_user: User, db: Session) -> Optional[Member]:
    return db.query(Member).filter(Member.user_id == current_user.id).first()


@router.post("/", response_model=ApplicationOut, status_code=201)
def apply_for_scheme(
    payload: ApplicationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Citizen applies for a scheme (or staff submits on a citizen's behalf).
    This is the digital replacement for the paper-application step in the
    workflow diagram - it immediately creates a trackable record instead
    of a physical form that can get lost.
    """
    scheme = db.query(Scheme).filter(Scheme.id == payload.scheme_id, Scheme.is_active == True).first()  # noqa: E712
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found or inactive")

    if current_user.role == "citizen":
        member = _resolve_member_for_user(current_user, db)
        if not member:
            raise HTTPException(status_code=400, detail="Complete your member profile before applying")
        member_id = member.id
    else:
        if not payload.member_id:
            raise HTTPException(status_code=400, detail="member_id is required when staff submits on behalf of a citizen")
        member_id = payload.member_id
        member = db.query(Member).filter(Member.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        if not can_access_member(current_user, member):
            raise HTTPException(status_code=403, detail="You can only submit applications within your assigned jurisdiction")

    # Prevent duplicate pending applications for the same scheme
    existing = (
        db.query(SchemeApplication)
        .filter(
            SchemeApplication.member_id == member_id,
            SchemeApplication.scheme_id == payload.scheme_id,
            SchemeApplication.status.in_(["pending", "under_review"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="An active application for this scheme already exists")

    application = SchemeApplication(member_id=member_id, scheme_id=payload.scheme_id, status="pending")
    db.add(application)
    db.flush()
    # Notify only the office users allowed to work on this citizen's record.
    for officer in officer_users_for_member(db.query(User), member).all():
        create_notification(db, officer.id, "New scheme application", f"{member.full_name} applied for {scheme.name}.", link="/applications")
    db.commit()
    db.refresh(application)
    citizen = db.query(User).filter(User.id == member.user_id).first() if member.user_id else None
    if citizen:
        # The in-app notification and database record are already committed.
        # SMTP must not leave the citizen looking at a frozen “Submitting…”
        # button while an external mail server times out.
        background_tasks.add_task(
            send_application_received_email, citizen.email, citizen.full_name, scheme.name
        )
    return _with_applicant_name(_with_document_status(_with_reviewer_name(application, db), db), db)


@router.get("/my", response_model=List[ApplicationOut])
def my_applications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Citizen: check status of their own applications - answers 'What is my application status?'."""
    member = _resolve_member_for_user(current_user, db)
    if not member:
        return []
    applications = (
        db.query(SchemeApplication)
        .filter(SchemeApplication.member_id == member.id)
        .order_by(SchemeApplication.submitted_at.desc())
        .all()
    )
    return _decorate_all(applications, db)


@router.get("/", response_model=List[ApplicationOut])
def list_applications(
    status_filter: Optional[str] = None,
    # Readiness is a separate axis from status: an officer wants "pending AND
    # actionable", so folding it into status_filter would destroy the actual
    # work queue. Default "actionable" keeps rows the citizen still owes
    # documents for out of the way without deleting them from the app.
    view: Optional[str] = Query(None, pattern="^(actionable|awaiting_citizen|all)$"),
    skip: int = Query(0, ge=0),
    # The queue is rendered as one table; an unbounded query would load every
    # application in the district (and build a document summary for each).
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _staff: User = Depends(require_roles("staff", "admin")),
):
    """Staff/Admin: view all applications, optionally filtered by status, for processing."""
    query = db.query(SchemeApplication).join(Member, Member.id == SchemeApplication.member_id)
    query = scope_members(query, _staff)
    if status_filter:
        query = query.filter(SchemeApplication.status == status_filter)
    # Applied in SQL, before OFFSET/LIMIT - filtering the page in the browser
    # would hide rows past the cap and make every tab count a count of the page.
    query = apply_queue_view(query, view)
    applications = query.order_by(SchemeApplication.submitted_at.desc()).offset(skip).limit(limit).all()
    return _decorate_all(applications, db)


@router.get("/queue-counts")
def queue_counts(
    db: Session = Depends(get_db),
    _staff: User = Depends(require_roles("staff", "admin")),
):
    """Tab counts for the staff queue, from the same predicate as the filter.

    One request returning all three keeps them a single consistent snapshot,
    and computing them here (no OFFSET/LIMIT) is what stops a tab label from
    reporting "of the 200 rows that happened to load".
    """
    base = scope_members(
        db.query(SchemeApplication).join(Member, Member.id == SchemeApplication.member_id), _staff
    )
    total = base.with_entities(func.count(SchemeApplication.id)).scalar() or 0
    awaiting = (
        base.filter(awaiting_citizen_clause())
        .with_entities(func.count(SchemeApplication.id))
        .scalar()
    ) or 0
    return {"total": total, "awaiting_citizen": awaiting, "actionable": total - awaiting}


@router.patch("/{application_id}/review", response_model=ApplicationOut)
def review_application(
    application_id: int,
    payload: ApplicationReview,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin: move an application through under_review -> approved/rejected.
    Every decision is stamped with who reviewed it and when - the approval
    history/transparency the current paper process is missing. Approving
    or rejecting notifies the citizen both by email and in-portal, and a
    rejection always carries the reason (enforced by the schema).
    """
    application = db.query(SchemeApplication).filter(SchemeApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    member = db.query(Member).filter(Member.id == application.member_id).first()
    if not member or not can_access_member(current_user, member):
        raise HTTPException(status_code=403, detail="You can only review applications in your assigned jurisdiction")
    if application.status in ("approved", "rejected"):
        raise HTTPException(status_code=409, detail="This application has already received a final decision")

    scheme = db.query(Scheme).filter(Scheme.id == application.scheme_id).first()
    document_state = _document_review_summary(application, scheme)
    if document_state["required_document_count"] and not document_state["documents_complete"]:
        raise HTTPException(
            status_code=409,
            detail="All required documents must be uploaded before this application can be reviewed.",
        )
    if document_state["required_document_count"] and not document_state["documents_reviewed"]:
        raise HTTPException(
            status_code=409,
            detail="Review every submitted required document before changing the application status.",
        )
    if payload.status == "approved" and document_state["required_document_count"] and not document_state["documents_approved"]:
        raise HTTPException(
            status_code=409,
            detail="An application can only be approved after every required document is approved.",
        )

    application.status = payload.status
    application.remarks = payload.remarks
    application.reviewed_by_id = current_user.id
    application.reviewed_at = utcnow()

    if payload.status in ("approved", "rejected"):
        if member and member.user_id:
            citizen = db.query(User).filter(User.id == member.user_id).first()
            if citizen:
                title = f"Application {payload.status}: {scheme.name if scheme else ''}"
                create_notification(db, citizen.id, title, payload.remarks, link="/applications")
    db.commit()
    db.refresh(application)
    if payload.status in ("approved", "rejected") and member.user_id:
        citizen = db.query(User).filter(User.id == member.user_id).first()
        scheme = db.query(Scheme).filter(Scheme.id == application.scheme_id).first()
        if citizen:
            # The final-state guard above makes this a single delivery per
            # decision, even when an officer double-clicks an approval button.
            background_tasks.add_task(
                send_application_status_email,
                citizen.email,
                citizen.full_name,
                scheme.name if scheme else "the scheme",
                payload.status,
                payload.remarks,
            )
    return _with_applicant_name(_with_document_status(_with_reviewer_name(application, db), db), db)


@router.get("/{application_id}/approval-pdf/download")
def download_approval_pdf(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Downloads a simple approval confirmation letter for an approved
    application - the citizen's proof of approval, generated on demand
    rather than stored, since it's cheap to regenerate.
    """
    application = db.query(SchemeApplication).filter(SchemeApplication.id == application_id).first()
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved applications have an approval letter")

    member = db.query(Member).filter(Member.id == application.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member record not found")

    if not can_access_member(current_user, member):
        raise HTTPException(status_code=403, detail="Not authorized to download this")

    scheme = db.query(Scheme).filter(Scheme.id == application.scheme_id).first()
    reviewer = db.query(User).filter(User.id == application.reviewed_by_id).first() if application.reviewed_by_id else None

    file_path = generate_approval_pdf(application, member, scheme, reviewer.full_name if reviewer else "JanSeva Connect Office")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=f"approval_{application.id}.pdf",
    )

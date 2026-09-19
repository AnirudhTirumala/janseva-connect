from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.timeutils import utcnow
from app.models.user import User
from app.models.member import Member
from app.models.application import SchemeApplication
from app.models.application_document import ApplicationDocument
from app.models.scheme import SchemeDocumentRequirement
from app.schemas.application_document import ApplicationDocumentOut, DocumentReview
from app.utils.document_storage import (
    canonical_content_type,
    delete_uploaded_file,
    read_upload_within_limit,
    read_uploaded_file,
    save_uploaded_file,
)
from app.utils.email_client import send_document_rejected_email
from app.utils.notifications import create_notification
from app.utils.scope import can_access_member

router = APIRouter(prefix="/api/applications", tags=["Application Documents"])


def _get_application_or_404(application_id: int, db: Session) -> SchemeApplication:
    application = (
        db.query(SchemeApplication)
        .filter(SchemeApplication.id == application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _assert_citizen_owns_application(
    application: SchemeApplication,
    current_user: User,
    db: Session,
):
    member = (
        db.query(Member)
        .filter(Member.user_id == current_user.id)
        .first()
    )
    if not member or member.id != application.member_id:
        raise HTTPException(
            status_code=403,
            detail="You can only manage documents on your own application",
        )


def _assert_staff_can_access_application(
    application: SchemeApplication,
    current_user: User,
    db: Session,
):
    """These documents are the citizen's Aadhaar card, income proof, and
    similar PII - a staff/admin account must be scoped to this application's
    member the same way every other staff action in the app is (see
    can_access_member), not just any authenticated staff/admin account.
    Application/document IDs are small sequential integers, so without this
    check anyone with a staff or admin login could page through every
    citizen's uploaded ID documents statewide, not just their own district.
    """
    member = (
        db.query(Member)
        .filter(Member.id == application.member_id)
        .first()
    )
    if not member or not can_access_member(current_user, member):
        raise HTTPException(
            status_code=403,
            detail="You can only access applications in your assigned jurisdiction",
        )


@router.post(
    "/{application_id}/documents",
    response_model=ApplicationDocumentOut,
    status_code=201,
)
async def upload_document(
    application_id: int,
    document_name: str = Form(...),
    requirement_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Uploads ONE document against ONE required-document slot for an
    application (e.g. just the Aadhaar Card). Citizens upload each required
    document separately by calling this once per document, rather than
    bundling everything into a single file.
    """
    application = _get_application_or_404(application_id, db)

    if current_user.role == "citizen":
        _assert_citizen_owns_application(application, current_user, db)
    elif current_user.role in ("staff", "admin"):
        _assert_staff_can_access_application(application, current_user, db)
    else:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        content = await read_upload_within_limit(file)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(document_name.strip()) > 150:
        raise HTTPException(
            status_code=422,
            detail="Document name must be 150 characters or fewer.",
        )

    if not file.filename or len(file.filename) > 255:
        raise HTTPException(
            status_code=422,
            detail="A valid file name is required.",
        )

    try:
        content_type = canonical_content_type(
            file.content_type,
            content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if requirement_id is not None:
        requirement = (
            db.query(SchemeDocumentRequirement)
            .filter(
                SchemeDocumentRequirement.id == requirement_id,
                SchemeDocumentRequirement.scheme_id == application.scheme_id,
            )
            .first()
        )

        if not requirement:
            raise HTTPException(
                status_code=400,
                detail="This document requirement does not belong to this scheme.",
            )

    file_path = save_uploaded_file(
        application_id,
        content_type,
        content,
    )

    # Replace any previous upload for the same requirement/slot, so
    # re-uploading a corrected document doesn't leave duplicates behind.
    if requirement_id is not None:
        existing = (
            db.query(ApplicationDocument)
            .filter(
                ApplicationDocument.application_id == application_id,
                ApplicationDocument.requirement_id == requirement_id,
            )
            .first()
        )

        if existing:
            delete_uploaded_file(existing.file_path)
            db.delete(existing)
            db.flush()

    document = ApplicationDocument(
        application_id=application_id,
        requirement_id=requirement_id,
        document_name=document_name,
        file_path=file_path,
        original_filename=file.filename,
        content_type=content_type,
        status="pending",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@router.get(
    "/{application_id}/documents",
    response_model=List[ApplicationDocumentOut],
)
def list_documents(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists documents uploaded for an application - citizen sees their own, staff/admin see any in their jurisdiction."""
    application = _get_application_or_404(application_id, db)

    if current_user.role == "citizen":
        _assert_citizen_owns_application(
            application,
            current_user,
            db,
        )
    else:
        _assert_staff_can_access_application(
            application,
            current_user,
            db,
        )

    return (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.application_id == application_id
        )
        .order_by(ApplicationDocument.id)
        .all()
    )


@router.get(
    "/{application_id}/documents/{document_id}/download"
)
def download_document(
    application_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Streams the uploaded file back - for staff/admin to review (within their jurisdiction), or the citizen to confirm what they sent."""
    application = _get_application_or_404(
        application_id,
        db,
    )

    if current_user.role == "citizen":
        _assert_citizen_owns_application(
            application,
            current_user,
            db,
        )
    else:
        _assert_staff_can_access_application(
            application,
            current_user,
            db,
        )

    document = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == application_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    content = read_uploaded_file(document.file_path)

    if content is None:
        raise HTTPException(
            status_code=404,
            detail="Document file is unavailable",
        )

    return Response(
        content=content,
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{document.original_filename}"'
            )
        },
    )


@router.patch(
    "/{application_id}/documents/{document_id}/review",
    response_model=ApplicationDocumentOut,
)
def review_document(
    application_id: int,
    document_id: int,
    payload: DocumentReview,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """Staff/Admin: approve or reject one specific uploaded document, independent of the overall application status."""
    application = _get_application_or_404(
        application_id,
        db,
    )

    _assert_staff_can_access_application(
        application,
        current_user,
        db,
    )

    document = (
        db.query(ApplicationDocument)
        .filter(
            ApplicationDocument.id == document_id,
            ApplicationDocument.application_id == application_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    document.status = payload.status
    document.remarks = payload.remarks
    document.reviewed_by_id = current_user.id
    document.reviewed_at = utcnow()

    # A rejected document used to notify nobody at all: the row was marked
    # rejected and the request returned. The citizen was never told, and the
    # officer's reason ("illegible, please re-upload") was reachable only if
    # they happened to reopen the upload modal. The application then sat
    # waiting on someone who had no idea - which is also why it is safe to
    # move these rows out of the default staff queue only now.
    citizen = None

    if payload.status == "rejected":
        member = (
            db.query(Member)
            .filter(Member.id == application.member_id)
            .first()
        )

        if member and member.user_id:
            citizen = (
                db.query(User)
                .filter(User.id == member.user_id)
                .first()
            )

        if citizen:
            create_notification(
                db,
                citizen.id,
                f"Re-upload needed: {document.document_name}",
                payload.remarks
                or "The office could not accept this document. Please upload it again.",
                link="/applications",
            )

    db.commit()
    db.refresh(document)

    if citizen:
        background_tasks.add_task(
            send_document_rejected_email,
            citizen.email,
            citizen.full_name,
            document.document_name,
            payload.remarks,
        )

    return document

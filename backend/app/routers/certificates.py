import secrets
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.core.timeutils import utcnow
from app.models.user import User
from app.models.member import Member
from app.models.certificate import Certificate
from app.models.certificate_request import CertificateRequest
from app.models.certificate_type import CertificateType
from app.schemas.certificate import CertificateCreate, CertificateOut, CertificateRequestCreate, CertificateRequestOut, CertificateRequestReview
from app.schemas.certificate_type import CertificateTypeCreate, CertificateTypeOut, CertificateTypeUpdate
from app.utils.pdf_generator import delete_certificate_file, generate_certificate_pdf, safe_certificate_path
from app.utils.notifications import create_notification
from app.utils.email_client import (
    send_certificate_issued_email, send_certificate_request_received_email,
    send_certificate_request_status_email,
)
from app.services.citizen_actions import CitizenActionError, request_certificate_for
from app.utils.scope import can_access_member, officer_users_for_member, scope_members, is_state_admin, is_superadmin

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])

TYPE_PREFIX = {"income": "INC", "residence": "RES", "birth": "BRT"}
DEFAULT_TYPES = [
    {"key": "income", "name": "Income Certificate", "description": "Official household income record", "prefix": "INC", "is_active": True},
    {"key": "residence", "name": "Residence Certificate", "description": "Official residence verification", "prefix": "RES", "is_active": True},
    {"key": "birth", "name": "Birth Certificate", "description": "Official birth record", "prefix": "BRT", "is_active": True},
]


def _generate_certificate_number(cert_type: str, prefix: str | None = None) -> str:
    """Certificate numbers are printed on an official document and quoted
    back by citizens, so they are generated with `secrets` rather than the
    `random` module - a Mersenne Twister sequence is reconstructable from a
    handful of observed outputs, which is the wrong property for an
    identifier on a government record."""
    year = utcnow().year
    suffix = f"{secrets.randbelow(1_000_000):06d}"
    return f"{prefix or TYPE_PREFIX.get(cert_type, 'CRT')}-{year}-{suffix}"


def _type_info(db: Session, cert_type: str, require_active: bool = True):
    key = cert_type.strip().lower().replace(" ", "-")
    item = db.query(CertificateType).filter(CertificateType.key == key).first()
    if item:
        if require_active and not item.is_active:
            raise HTTPException(status_code=400, detail="This certificate type is not currently available")
        return item
    builtin = next((item for item in DEFAULT_TYPES if item["key"] == key), None)
    if builtin:
        return builtin
    raise HTTPException(status_code=404, detail="Certificate type not found")


def _type_name(info) -> str:
    return info.name if isinstance(info, CertificateType) else info["name"]


def _type_prefix(info) -> str:
    return info.prefix if isinstance(info, CertificateType) else info["prefix"]


def _require_catalogue_manager(user: User) -> None:
    if not is_state_admin(user):
        raise HTTPException(status_code=403, detail="Only a state administrator or superadmin can manage the certificate catalogue")


def _with_member_name(certificate: Certificate) -> Certificate:
    certificate.member_name = certificate.member.full_name if certificate.member else None
    certificate.issued_by_name = certificate.issued_by.full_name if certificate.issued_by else None
    return certificate


def _with_request_info(request: CertificateRequest) -> CertificateRequest:
    request.member_name = request.member.full_name if request.member else None
    request.requested_by_name = request.requested_by.full_name if request.requested_by else None
    request.certificate_number = request.certificate.certificate_number if request.certificate else None
    request.reviewed_by_name = request.reviewed_by.full_name if request.reviewed_by else None
    request.issued_by_name = request.certificate.issued_by.full_name if request.certificate and request.certificate.issued_by else None
    request.issued_at = request.certificate.issued_at if request.certificate else None
    return request


def _issue(db: Session, member: Member, cert_type: str, issuer: User) -> Certificate:
    info = _type_info(db, cert_type)
    cert_type = cert_type.strip().lower().replace(" ", "-")
    cert_number = _generate_certificate_number(cert_type, _type_prefix(info))
    # A collision is extraordinarily unlikely, but protect the unique database constraint.
    while db.query(Certificate.id).filter(Certificate.certificate_number == cert_number).first():
        cert_number = _generate_certificate_number(cert_type, _type_prefix(info))
    file_path = generate_certificate_pdf(cert_number, cert_type, member, issuer.full_name, _type_name(info))
    certificate = Certificate(member_id=member.id, certificate_type=cert_type, certificate_number=cert_number,
                              issued_by_id=issuer.id, file_path=file_path)
    db.add(certificate)
    return certificate


@router.get("/types", response_model=List[CertificateTypeOut])
def list_certificate_types(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    custom = db.query(CertificateType).order_by(CertificateType.name).all()
    custom_keys = {item.key for item in custom}
    return [CertificateTypeOut(**item) for item in DEFAULT_TYPES if item["key"] not in custom_keys] + custom


@router.post("/types", response_model=CertificateTypeOut, status_code=201)
def add_certificate_type(payload: CertificateTypeCreate, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    _require_catalogue_manager(_admin)
    key = "-".join("".join(char.lower() if char.isalnum() else " " for char in payload.name).split())
    # The name may be up to 150 characters, but certificate_types.key is
    # VARCHAR(50) and the key is later copied into certificates.certificate_type
    # and certificate_requests.certificate_type, both VARCHAR(30). Truncating
    # silently would collide two long names onto one key, so refuse instead -
    # on PostgreSQL the alternative is a DataError 500 at issue time, long
    # after the type was accepted.
    if len(key) > 30:
        raise HTTPException(
            status_code=422,
            detail="This certificate type's name is too long. Please use a shorter name (about 30 characters).",
        )
    if not key:
        raise HTTPException(status_code=422, detail="A certificate type needs a name with letters or numbers in it.")
    if db.query(CertificateType).filter(CertificateType.key == key).first() or key in TYPE_PREFIX:
        raise HTTPException(status_code=409, detail="A certificate type with this name already exists")
    item = CertificateType(key=key, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/types/{type_id}", response_model=CertificateTypeOut)
def update_certificate_type(type_id: int, payload: CertificateTypeUpdate, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    _require_catalogue_manager(_admin)
    item = db.query(CertificateType).filter(CertificateType.id == type_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Certificate type not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/types/{type_id}", status_code=204)
def delete_certificate_type(type_id: int, db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    """Removes a certificate type the admin added. Built-in defaults (income,
    residence, birth) have no catalogue row of their own and so aren't
    reachable by this endpoint - only custom types can be deleted. Already
    issued certificates of this type are untouched; a pending/approved
    request against it must be resolved first so it isn't left stranded."""
    _require_catalogue_manager(_admin)
    item = db.query(CertificateType).filter(CertificateType.id == type_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Certificate type not found")
    has_active_requests = db.query(CertificateRequest.id).filter(
        CertificateRequest.certificate_type == item.key,
        CertificateRequest.status.in_(["pending", "approved"]),
    ).first()
    if has_active_requests:
        raise HTTPException(status_code=409, detail="This type has pending or approved requests; resolve them before deleting it")
    db.delete(item)
    db.commit()
    return None


@router.post("/", response_model=CertificateOut, status_code=201)
def issue_certificate(
    payload: CertificateCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin: generate an official certificate PDF for a member.
    Replaces manual handwriting - instant, error-free, and searchable
    forever afterwards via certificate_number.
    """
    member = db.query(Member).filter(Member.id == payload.member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not can_access_member(current_user, member):
        raise HTTPException(status_code=403, detail="You can only issue certificates in your assigned jurisdiction")

    certificate = _issue(db, member, payload.certificate_type, current_user)

    if member.user_id:
        citizen = db.query(User).filter(User.id == member.user_id).first()
        if citizen:
            create_notification(
                db, citizen.id, f"{payload.certificate_type.title()} certificate issued",
                f"Certificate {certificate.certificate_number} is ready to download.", link="/certificates",
            )
    db.commit()
    db.refresh(certificate)
    if member.user_id:
        citizen = db.query(User).filter(User.id == member.user_id).first()
        if citizen:
            background_tasks.add_task(
                send_certificate_issued_email,
                citizen.email,
                citizen.full_name,
                payload.certificate_type,
                certificate.certificate_number,
            )
    return _with_member_name(certificate)


@router.post("/requests", response_model=CertificateRequestOut, status_code=201)
def request_certificate(
    payload: CertificateRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("citizen")),
):
    """Citizen requests a certificate linked only to their own member record.

    The work lives in services/citizen_actions so the AI assistant's tool and
    this endpoint enforce exactly the same rules - see that module's docstring.
    """
    try:
        request = request_certificate_for(
            db, current_user, payload.certificate_type, payload.purpose, background_tasks
        )
    except CitizenActionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _with_request_info(request)


@router.get("/requests", response_model=List[CertificateRequestOut])
def list_certificate_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(CertificateRequest).options(
        joinedload(CertificateRequest.member), joinedload(CertificateRequest.requested_by),
        joinedload(CertificateRequest.reviewed_by),
        joinedload(CertificateRequest.certificate).joinedload(Certificate.issued_by),
    )
    if current_user.role == "citizen":
        query = query.filter(CertificateRequest.requested_by_id == current_user.id)
    elif current_user.role not in ("staff", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    else:
        query = scope_members(query.join(Member, Member.id == CertificateRequest.member_id), current_user)
    return [_with_request_info(r) for r in query.order_by(CertificateRequest.created_at.desc()).all()]


@router.patch("/requests/{request_id}", response_model=CertificateRequestOut)
def review_certificate_request(request_id: int, payload: CertificateRequestReview, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(require_roles("staff", "admin"))):
    request = db.query(CertificateRequest).options(
        joinedload(CertificateRequest.member), joinedload(CertificateRequest.requested_by),
        joinedload(CertificateRequest.reviewed_by),
        joinedload(CertificateRequest.certificate).joinedload(Certificate.issued_by),
    ).filter(CertificateRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Certificate request not found")
    if not request.member or not can_access_member(current_user, request.member):
        raise HTTPException(status_code=403, detail="You can only review certificate requests in your assigned jurisdiction")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="This request has already been reviewed")
    if payload.status == "rejected" and not (payload.review_remarks or "").strip():
        raise HTTPException(status_code=422, detail="A reason is required when rejecting a request")
    request.status, request.review_remarks = payload.status, payload.review_remarks
    request.reviewed_by_id, request.reviewed_at = current_user.id, utcnow()
    create_notification(db, request.requested_by_id, f"Certificate request {payload.status}", payload.review_remarks or "The office has reviewed your request.", link="/certificates")
    db.commit()
    db.refresh(request)
    citizen = db.query(User).filter(User.id == request.requested_by_id).first()
    if citizen:
        info = _type_info(db, request.certificate_type, require_active=False)
        background_tasks.add_task(
            send_certificate_request_status_email,
            citizen.email,
            citizen.full_name,
            _type_name(info),
            payload.status,
            payload.review_remarks,
        )
    return _with_request_info(request)


@router.post("/requests/{request_id}/issue", response_model=CertificateOut, status_code=201)
def issue_requested_certificate(request_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(require_roles("staff", "admin"))):
    request = db.query(CertificateRequest).options(joinedload(CertificateRequest.member)).filter(CertificateRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Certificate request not found")
    if not request.member or not can_access_member(current_user, request.member):
        raise HTTPException(status_code=403, detail="You can only issue certificates in your assigned jurisdiction")
    if request.status != "approved":
        raise HTTPException(status_code=409, detail="Approve the request before generating a certificate")
    if request.certificate_id:
        raise HTTPException(status_code=409, detail="A certificate has already been generated for this request")
    certificate = _issue(db, request.member, request.certificate_type, current_user)
    db.flush()
    request.certificate_id, request.status = certificate.id, "issued"
    create_notification(db, request.requested_by_id, f"{request.certificate_type.title()} certificate issued", f"Certificate {certificate.certificate_number} is ready to download.", link="/certificates")
    db.commit()
    db.refresh(certificate)
    citizen = db.query(User).filter(User.id == request.requested_by_id).first()
    if citizen:
        background_tasks.add_task(
            send_certificate_issued_email,
            citizen.email,
            citizen.full_name,
            request.certificate_type,
            certificate.certificate_number,
        )
    return _with_member_name(certificate)


@router.get("/", response_model=List[CertificateOut])
def list_certificates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """Staff/Admin: browse all issued certificates - instant search vs. old paper files."""
    certs = (
        scope_members(db.query(Certificate).join(Member, Member.id == Certificate.member_id), current_user)
        .options(joinedload(Certificate.member), joinedload(Certificate.issued_by))
        .order_by(Certificate.issued_at.desc())
        .all()
    )
    return [_with_member_name(c) for c in certs]


@router.get("/my", response_model=List[CertificateOut])
def my_certificates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Citizen: list certificates issued to them, ready for download."""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        return []
    certs = (
        db.query(Certificate)
        .filter(Certificate.member_id == member.id)
        .options(joinedload(Certificate.member), joinedload(Certificate.issued_by))
        .order_by(Certificate.issued_at.desc())
        .all()
    )
    return [_with_member_name(c) for c in certs]


@router.get("/{certificate_id}/download")
def download_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    file_path = safe_certificate_path(certificate.file_path) if certificate else None
    if not certificate or not file_path:
        raise HTTPException(status_code=404, detail="Certificate not found")

    member = db.query(Member).filter(Member.id == certificate.member_id).first()
    if not member or not can_access_member(current_user, member):
        raise HTTPException(status_code=403, detail="Not authorized to download this certificate")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=f"{certificate.certificate_number}.pdf",
    )


@router.delete("/{certificate_id}", status_code=204)
def delete_certificate(
    certificate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Superadmin-only: permanently revoke an issued certificate (record and PDF).
    If the certificate came from a citizen's request, the
    request record is kept (as the audit trail of what happened) but
    unlinked from the now-deleted certificate."""
    if not is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Only the superadmin can delete an issued certificate")
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found")
    linked_request = db.query(CertificateRequest).filter(CertificateRequest.certificate_id == certificate.id).first()
    if linked_request:
        linked_request.certificate_id = None

    delete_certificate_file(certificate.file_path)

    db.delete(certificate)
    db.commit()
    return None

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User
from app.models.scheme import Scheme, SchemeDocumentRequirement
from app.models.application import SchemeApplication
from app.models.application_document import ApplicationDocument
from app.schemas.scheme import SchemeCreate, SchemeUpdate, SchemeOut
from app.utils.scope import is_state_admin, is_superadmin

router = APIRouter(prefix="/api/schemes", tags=["Schemes"])


def _scheme_query(db: Session):
    return db.query(Scheme).options(joinedload(Scheme.document_requirements))


def _require_catalogue_manager(user: User) -> None:
    """Catalogue maintenance is a state-level responsibility.

    District admins can process applications, but must not alter the set of
    schemes citizens can discover or apply for.
    """
    if not is_state_admin(user):
        raise HTTPException(status_code=403, detail="Only a state administrator or superadmin can manage the scheme catalogue")


@router.get("/", response_model=List[SchemeOut])
def list_schemes(active_only: bool = True, db: Session = Depends(get_db)):
    """
    Public/any-authenticated-role: browse the scheme catalog, including
    each scheme's list of required documents so the frontend can render
    one upload slot per document.
    """
    query = _scheme_query(db)
    if active_only:
        query = query.filter(Scheme.is_active == True)  # noqa: E712
    return query.order_by(Scheme.name).all()


@router.get("/{scheme_id}", response_model=SchemeOut)
def get_scheme(scheme_id: int, db: Session = Depends(get_db)):
    scheme = _scheme_query(db).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    return scheme


@router.post("/", response_model=SchemeOut, status_code=201)
def create_scheme(
    payload: SchemeCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    """
    Admin-only: add a new government scheme to the catalog, along with its
    required documents - each name given becomes its own separate upload
    slot for citizens applying, e.g. "Aadhaar Card", "Income Proof",
    "PAN Card" are three distinct uploads, not one combined file.
    """
    _require_catalogue_manager(_admin)
    data = payload.model_dump(exclude={"document_requirement_names"})
    scheme = Scheme(**data)
    db.add(scheme)
    db.flush()  # get scheme.id before creating requirement rows

    for doc_name in payload.document_requirement_names:
        doc_name = doc_name.strip()
        if doc_name:
            db.add(SchemeDocumentRequirement(scheme_id=scheme.id, name=doc_name))

    db.commit()
    return _scheme_query(db).filter(Scheme.id == scheme.id).first()


@router.put("/{scheme_id}", response_model=SchemeOut)
def update_scheme(
    scheme_id: int,
    payload: SchemeUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    _require_catalogue_manager(_admin)
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    update_data = payload.model_dump(exclude_unset=True, exclude={"document_requirement_names"})
    for field, value in update_data.items():
        setattr(scheme, field, value)

    if payload.document_requirement_names is not None:
        # Replace the full set - simplest consistent behavior for an
        # admin-managed, infrequently-edited list.
        #
        # Already-uploaded documents point at these requirement rows
        # (application_documents.requirement_id). Deleting the parents while
        # children still reference them is a ForeignKeyViolation on
        # PostgreSQL - a 500 on every edit of a scheme citizens have actually
        # applied to. SQLite does not enforce foreign keys by default, which
        # is why it never surfaced locally. Unlink first; the document keeps
        # its denormalised document_name, so nothing is lost from the record.
        requirement_ids = [
            row[0] for row in
            db.query(SchemeDocumentRequirement.id)
            .filter(SchemeDocumentRequirement.scheme_id == scheme.id)
            .all()
        ]
        if requirement_ids:
            db.query(ApplicationDocument).filter(
                ApplicationDocument.requirement_id.in_(requirement_ids)
            ).update({ApplicationDocument.requirement_id: None}, synchronize_session=False)
            db.flush()
        db.query(SchemeDocumentRequirement).filter(SchemeDocumentRequirement.scheme_id == scheme.id).delete()
        for doc_name in payload.document_requirement_names:
            doc_name = doc_name.strip()
            if doc_name:
                db.add(SchemeDocumentRequirement(scheme_id=scheme.id, name=doc_name))

    db.commit()
    return _scheme_query(db).filter(Scheme.id == scheme.id).first()


@router.delete("/{scheme_id}")
def delete_scheme(
    scheme_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    if not is_state_admin(_admin):
        raise HTTPException(status_code=403, detail="Only a state administrator or superadmin can remove a scheme from the catalogue")
    scheme = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")
    # Never delete the parent of a citizen application.  SQLite's default
    # FK behaviour lets SQLAlchemy try to NULL its non-nullable scheme_id,
    # which caused the logged 500.  Retiring keeps the complete historical
    # record, removes it from the citizen catalogue, and is the correct
    # outcome even when a superadmin chooses "delete" in the UI.
    has_applications = db.query(SchemeApplication.id).filter(SchemeApplication.scheme_id == scheme.id).first()
    if has_applications or not is_superadmin(_admin):
        scheme.is_active = False
        db.commit()
        return {
            "action": "retired",
            "message": "This scheme was retired from the citizen catalogue so its service history remains safe.",
        }

    db.delete(scheme)
    db.commit()
    return {"action": "deleted", "message": "Scheme deleted from the catalogue."}

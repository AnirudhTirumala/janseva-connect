from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.user import User
from app.models.member import Member
from app.schemas.member import MemberCreate, MemberUpdate, MemberOut, CitizenProfileUpdate
from app.utils.record_deletion import member_deletion_blocker
from app.utils.user_lookup import phone_is_taken
from app.utils.scope import can_access_member, scope_members

router = APIRouter(prefix="/api/members", tags=["Members"])


@router.get("/", response_model=List[MemberOut])
def list_members(
    search: Optional[str] = Query(None, description="Search by name, village, or phone"),
    village: Optional[str] = None,
    skip: int = Query(0, ge=0),
    # Bounded on purpose: ?limit=999999999 would otherwise ask PostgreSQL for
    # the entire household register in one response.
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin only: search & list member records.
    This is the digital replacement for flipping through paper registers -
    a name/village/phone search that used to take minutes now takes ms.
    """
    query = scope_members(db.query(Member), current_user)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Member.full_name.ilike(like), Member.phone.ilike(like), Member.village.ilike(like))
        )
    if village:
        query = query.filter(Member.village == village)
    return query.order_by(Member.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/me", response_model=MemberOut)
def get_my_member_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Citizen: fetch their own linked member profile."""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="No member profile linked to your account yet")
    return member


@router.post("/me", response_model=MemberOut, status_code=201)
def create_my_member_profile(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Citizen: self-service household registration. Lets a citizen who
    self-registered (no office visit yet) fill in their own household
    details immediately, rather than being blocked until staff manually
    creates the record. Staff/admin can still review and edit it later
    from the Members screen - this just removes the "stuck with no profile"
    dead end for citizens signing up online.
    """
    if current_user.role != "citizen":
        raise HTTPException(status_code=403, detail="Only citizens can self-register a profile here")

    existing = db.query(Member).filter(Member.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have a member profile")

    if payload.aadhaar_number:
        dup = db.query(Member).filter(Member.aadhaar_number == payload.aadhaar_number).first()
        if dup:
            raise HTTPException(status_code=400, detail="A member with this Aadhaar number already exists")

    data = payload.model_dump()
    data["user_id"] = current_user.id  # always self-link, regardless of what was posted
    member = Member(**data)
    db.add(member)
    current_user.district = member.district
    current_user.mandal = member.mandal
    current_user.village = member.village
    db.commit()
    db.refresh(member)
    return member


@router.patch("/me", response_model=MemberOut)
def update_my_member_profile(
    payload: CitizenProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("citizen")),
):
    """Citizens can keep their identity, phone, and location current."""
    member = db.query(Member).filter(Member.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=404, detail="No member profile linked to your account yet")
    changes = payload.model_dump(exclude_unset=True)
    if "aadhaar_number" in changes and changes["aadhaar_number"]:
        duplicate = db.query(Member).filter(Member.aadhaar_number == changes["aadhaar_number"], Member.id != member.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="A member with this Aadhaar number already exists")
    for field, value in changes.items():
        setattr(member, field, value)
    # The sign-in identity follows the citizen's self-service name/phone update.
    if "full_name" in changes:
        current_user.full_name = changes["full_name"]
    if "phone" in changes:
        # This mirrors into users.phone, which is UNIQUE - so a number already
        # held by another login has to be refused here, not at the database.
        if phone_is_taken(db, changes["phone"], exclude_user_id=current_user.id):
            raise HTTPException(status_code=409, detail="This phone number is already linked to another account")
        current_user.phone = changes["phone"]
    if "district" in changes:
        current_user.district = changes["district"]
    if "mandal" in changes:
        current_user.mandal = changes["mandal"]
    if "village" in changes:
        current_user.village = changes["village"]
    db.commit()
    db.refresh(member)
    return member


@router.get("/{member_id}", response_model=MemberOut)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not can_access_member(current_user, member):
        raise HTTPException(status_code=403, detail="Not authorized to view this record")
    return member


@router.post("/", response_model=MemberOut, status_code=201)
def create_member(
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    """Staff/Admin: register a new member (digitizes the paper intake form)."""
    if payload.aadhaar_number:
        dup = db.query(Member).filter(Member.aadhaar_number == payload.aadhaar_number).first()
        if dup:
            raise HTTPException(status_code=400, detail="A member with this Aadhaar number already exists")

    candidate = Member(**payload.model_dump(), created_by_staff_id=current_user.id)
    if not can_access_member(current_user, candidate):
        raise HTTPException(status_code=403, detail="You can only register members in your assigned jurisdiction")
    if payload.user_id:
        citizen = db.query(User).filter(
            User.id == payload.user_id,
            User.role == "citizen",
            User.is_active == True,  # noqa: E712
        ).first()
        if not citizen:
            raise HTTPException(status_code=422, detail="The linked account must be an active citizen account")
        if db.query(Member).filter(Member.user_id == citizen.id).first():
            raise HTTPException(status_code=409, detail="This citizen account already has a household profile")
    member = candidate
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.put("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "admin")),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not can_access_member(current_user, member):
        raise HTTPException(status_code=403, detail="You can only update members in your assigned jurisdiction")

    changes = payload.model_dump(exclude_unset=True)
    # members.aadhaar_number is UNIQUE. The create paths check this; without
    # the same check here, an edit that collides is an IntegrityError 500
    # rather than a message the clerk can act on.
    if changes.get("aadhaar_number"):
        duplicate = (
            db.query(Member.id)
            .filter(Member.aadhaar_number == changes["aadhaar_number"], Member.id != member.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="A member with this Aadhaar number already exists")

    for field, value in changes.items():
        setattr(member, field, value)

    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204)
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles("admin")),
):
    """Admin-only: hard delete. Reserved for genuine duplicate/erroneous entries."""
    member = db.query(Member).filter(Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if not can_access_member(_admin, member):
        raise HTTPException(status_code=403, detail="You can only delete members in your assigned jurisdiction")
    blocker = member_deletion_blocker(db, member)
    if blocker:
        raise HTTPException(status_code=409, detail=blocker)
    db.delete(member)
    db.commit()
    return None

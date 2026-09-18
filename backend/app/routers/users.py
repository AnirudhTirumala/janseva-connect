from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import json

from app.core.database import get_db
from app.core.config import settings
from app.core.security import hash_password
from app.core.otp import get_valid_otp, issue_otp
from app.core.dependencies import require_roles
from app.core.rate_limit import limiter
from app.models.user import User
from app.models.member import Member
from app.schemas.auth import UserOut, UserCreateByAdmin, UserReassign
from app.schemas.member import MemberCreate
from app.schemas.otp import AdminUserCreateConfirm
from app.utils.email_client import send_otp_email, send_account_created_email, send_role_change_email
from app.utils.record_deletion import RetainedRecordError, delete_user_record
from app.utils.user_lookup import email_is_taken, find_user_by_email, phone_is_taken
from app.utils.scope import can_delete_officer, can_manage_user, can_reassign_officer, is_state_admin, is_superadmin

router = APIRouter(prefix="/api/users", tags=["User Management"])


def _officer_scope_label(role: str, jurisdiction_level: str | None, district: str | None, mandal: str | None) -> str:
    """Human-readable description of an officer's role/jurisdiction, used in
    the promotion/demotion email so 'District staff' -> 'District admin' is
    obvious at a glance rather than expressed as raw field names."""
    if role == "admin" and jurisdiction_level == "super":
        return "Superadmin"
    if role == "admin" and jurisdiction_level in (None, "", "state"):
        return "State admin"
    if role == "admin":
        return f"{district or 'Unassigned'} district admin"
    if jurisdiction_level == "mandal":
        return f"{mandal or 'Unassigned'} mandal staff"
    return f"{district or 'Unassigned'} district staff"


@router.get("/", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_roles("admin"))):
    """Admin-only: list all platform users (citizens, staff, admins)."""
    query = db.query(User)
    if not is_state_admin(current_user):
        query = query.filter(User.district == current_user.district)
    return query.order_by(User.created_at.desc()).all()


@router.get("/citizen-lookup", response_model=UserOut)
def lookup_citizen_by_email(
    email: str,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_roles("staff", "admin")),
):
    """
    Staff/Admin: look up a citizen's account by email so their member
    record can be linked to their login during registration at the
    office counter.
    """
    user = find_user_by_email(db, email)
    if not user or user.role != "citizen":
        raise HTTPException(status_code=404, detail="No citizen account found with this email")
    return user


@router.post("/request", status_code=202)
@limiter.limit("20/hour")
def request_create_user(
    request: Request,
    payload: UserCreateByAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """
    Admin-only: step 1 of provisioning a staff/citizen account. Sends a
    6-digit code to the new account's email - the admin asks the new
    person for that code (in person or by call) and enters it via
    /request confirm, so a mistyped or fake email can't silently become a
    platform login before anyone confirms they actually own it.
    """
    if not can_manage_user(current_user, payload.role, payload.district, payload.jurisdiction_level):
        raise HTTPException(status_code=403, detail="You can only create staff within your assigned district. Only the state administrator can create district administrators.")
    if payload.role == "citizen" and not payload.member_profile:
        raise HTTPException(status_code=422, detail="A complete household profile is required when registering a citizen.")
    if payload.member_profile and payload.role != "citizen":
        raise HTTPException(status_code=422, detail="Household details may only be attached to a citizen account.")
    if payload.member_profile:
        required = ("full_name", "address", "village", "district", "mandal")
        missing = [field for field in required if not payload.member_profile.get(field)]
        if missing:
            raise HTTPException(status_code=422, detail=f"Citizen profile is missing: {', '.join(missing)}")

    if email_is_taken(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already in use")
    if phone_is_taken(db, payload.phone):
        raise HTTPException(status_code=422, detail="This phone number is already linked to another account")

    _, code = issue_otp(
        db,
        email=payload.email,
        purpose="admin_create_user",
        pending_full_name=payload.full_name,
        pending_phone=payload.phone,
        pending_hashed_password=hash_password(payload.password),
        pending_role=payload.role,
        pending_jurisdiction_level=payload.jurisdiction_level,
        pending_district=payload.district or (payload.member_profile or {}).get("district"),
        pending_mandal=payload.mandal or (payload.member_profile or {}).get("mandal"),
        pending_village=payload.village or (payload.member_profile or {}).get("village"),
        pending_member_profile=json.dumps(payload.member_profile) if payload.member_profile else None,
    )
    delivered = send_otp_email(payload.email, code, "admin_create_user")
    if not delivered:
        raise HTTPException(status_code=502, detail="Could not send the verification email. Please check the address and try again.")

    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)
    return {
        "message": (
            f"A verification code has been sent to {payload.email}. Ask them for it to finish creating the account."
            if smtp_configured
            else f"Email is not configured yet - check the backend console for the code sent to {payload.email}."
        )
    }


@router.post("/confirm", response_model=UserOut, status_code=201)
@limiter.limit("10/hour")
def confirm_create_user(
    request: Request,
    payload: AdminUserCreateConfirm,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """
    Step 2: confirms the code and actually creates the account.  The
    administrator provides the one-time password through an approved secure
    channel; credentials are never emailed or stored in plaintext.
    """
    if email_is_taken(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already in use")

    otp = get_valid_otp(db, email=payload.email, purpose="admin_create_user", supplied_code=payload.code)
    if not otp or not otp.pending_hashed_password:
        raise HTTPException(status_code=400, detail="Invalid verification code.")
    if not can_manage_user(current_user, otp.pending_role, otp.pending_district, otp.pending_jurisdiction_level):
        raise HTTPException(status_code=403, detail="You no longer have permission to create this account.")

    otp.is_used = True
    if phone_is_taken(db, otp.pending_phone):
        raise HTTPException(status_code=422, detail="This phone number is already linked to another account")

    user = User(
        full_name=otp.pending_full_name,
        email=otp.email,
        phone=otp.pending_phone,
        hashed_password=otp.pending_hashed_password,
        role=otp.pending_role,
        jurisdiction_level=otp.pending_jurisdiction_level,
        district=otp.pending_district,
        mandal=otp.pending_mandal,
        village=otp.pending_village,
    )
    db.add(user)
    db.flush()

    if otp.pending_member_profile:
        try:
            profile = json.loads(otp.pending_member_profile)
            member_data = MemberCreate.model_validate(profile).model_dump()
            member_data.pop("user_id", None)
            # members.aadhaar_number is UNIQUE. Without this the whole
            # two-step provisioning flow ends in an IntegrityError 500 after
            # the citizen has already been emailed and read back a code.
            if member_data.get("aadhaar_number") and db.query(Member.id).filter(
                Member.aadhaar_number == member_data["aadhaar_number"]
            ).first():
                raise HTTPException(status_code=409, detail="A member with this Aadhaar number already exists")
            member = Member(**member_data, user_id=user.id, created_by_staff_id=current_user.id)
            db.add(member)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=422, detail="The pending citizen profile is invalid. Please start registration again.")

    # Profile data is only required for this short confirmation workflow.
    otp.pending_member_profile = None

    db.commit()
    db.refresh(user)

    background_tasks.add_task(send_account_created_email, user.email, user.full_name, user.role)

    return user


@router.patch("/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """Admin-only: disable a user's login without deleting their history."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account from here.")
    if is_superadmin(user):
        raise HTTPException(status_code=400, detail="The superadmin account cannot be deactivated")
    if user.role == "admin" and not can_delete_officer(current_user, user):
        raise HTTPException(status_code=403, detail="You don't have permission to manage this administrator.")
    if not is_state_admin(current_user) and user.district != current_user.district:
        raise HTTPException(status_code=403, detail="You can only manage accounts in your district")
    user.is_active = False
    user.session_version += 1
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if is_superadmin(user) and not is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="You don't have permission to manage the superadmin account.")
    if user.role == "admin" and not can_delete_officer(current_user, user) and user.id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't have permission to manage this administrator.")
    if not is_state_admin(current_user) and user.district != current_user.district:
        raise HTTPException(status_code=403, detail="You can only manage accounts in your district")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/reassign", response_model=UserOut)
def reassign_user(
    user_id: int,
    payload: UserReassign,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    """
    Admin-only: relocate a staff/admin account to a different district or
    mandal, or promote them up through mandal staff -> district staff ->
    district admin. The state administrator can reassign anyone anywhere;
    a district admin can reassign staff (never another admin) within their
    own district only. Only the fields provided in the payload change -
    anything left out keeps its current value.
    """
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot reassign your own account from here.")

    old_label = _officer_scope_label(target.role, target.jurisdiction_level, target.district, target.mandal)

    new_role = payload.role or target.role
    new_district = payload.district if payload.district is not None else target.district
    if not can_reassign_officer(current_user, target, new_role, new_district):
        raise HTTPException(
            status_code=403,
            detail="Only the state administrator can promote to district admin; a district admin can only reassign staff within their own district.",
        )

    new_level = payload.jurisdiction_level if payload.jurisdiction_level is not None else target.jurisdiction_level
    new_mandal = payload.mandal if payload.mandal is not None else target.mandal
    if new_role == "admin":
        # Admins are state or district scoped, never mandal. Only the
        # superadmin may promote someone to state level (can_reassign_officer
        # above already confirmed the actor may reassign this target at all);
        # anyone else reassigning to admin gets a district admin.
        new_level = "state" if (is_superadmin(current_user) and new_level == "state") else "district"
        new_mandal = None
    if new_level == "state":
        new_district = None  # state admins are not scoped to a single district
    elif new_level == "district":
        new_mandal = None  # district-level staff have no mandal of their own
    if new_level != "state" and not new_district:
        raise HTTPException(status_code=422, detail="A district is required.")
    if new_level == "mandal" and not new_mandal:
        raise HTTPException(status_code=422, detail="A mandal is required for mandal-level staff.")

    target.role = new_role
    target.jurisdiction_level = new_level
    target.district = new_district
    target.mandal = new_mandal
    db.commit()
    db.refresh(target)

    new_label = _officer_scope_label(target.role, target.jurisdiction_level, target.district, target.mandal)
    if new_label != old_label and target.email:
        background_tasks.add_task(send_role_change_email, target.email, target.full_name, old_label, new_label)

    return target


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """
    Admin-only: permanently delete a staff, admin, or citizen login. The
    superadmin may delete any other admin; a state admin may delete a
    district admin (see can_delete_officer); a district admin can still
    only delete staff/citizens in their own district, never another admin.
    No one can delete the superadmin, or their own account, from here.

    For a deleted citizen, their household/member record and any
    certificates or applications are kept as official Panchayat records -
    only unlinked from the now-deleted login, not erased.
    """
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account from here.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        if not can_delete_officer(admin, user):
            raise HTTPException(status_code=403, detail="You don't have permission to delete this admin account.")
    elif not is_state_admin(admin) and user.district != admin.district:
        raise HTTPException(status_code=403, detail="You can only manage accounts in your district")

    try:
        delete_user_record(db, user)
    except RetainedRecordError as exc:
        raise HTTPException(status_code=409, detail=exc.reason) from exc
    db.commit()
    return None

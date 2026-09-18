import os
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token_for_user, dummy_verify
from app.core.otp import get_valid_otp, issue_otp
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.user import User
from app.models.member import Member
from app.schemas.auth import UserRegister, UserLogin, Token, UserOut, UserSelfUpdate
from app.schemas.otp import RegisterVerify, PasswordResetRequest, PasswordResetConfirm, DeleteAccountConfirm, ChangePasswordConfirm
from app.core.timeutils import utcnow
from app.utils.email_client import send_new_signin_email, send_otp_email, send_welcome_email
from app.utils.signin_alerts import client_fingerprint, describe_device, is_new_signin_device, signin_audit_fields
from app.utils.audit import log_event
from app.utils.record_deletion import RetainedRecordError, delete_user_record
from app.utils.user_lookup import email_is_taken, find_user_by_email, phone_is_taken

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register")
@limiter.limit("5/hour")
def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)):
    """
    Public self-registration - step 1 of 2. Does NOT create the account yet:
    it emails a 6-digit code to verify the person actually owns this email
    address, and holds the submitted name/phone/password until that code is
    confirmed via /register/verify. This prevents fake or mistyped emails
    from being registered as citizen accounts.
    """
    if email_is_taken(db, payload.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    # users.phone is UNIQUE. Catching it here returns an actionable 422 on
    # the form instead of an IntegrityError 500 at the end of the flow,
    # after the person has already waited for an emailed code.
    if phone_is_taken(db, payload.phone):
        raise HTTPException(status_code=422, detail="This phone number is already linked to another account")

    _, code = issue_otp(
        db,
        email=payload.email,
        purpose="register",
        pending_full_name=payload.full_name,
        pending_phone=payload.phone,
        pending_hashed_password=hash_password(payload.password),
    )

    delivered = send_otp_email(payload.email, code, "register")
    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)

    if not delivered:
        raise HTTPException(
            status_code=502,
            detail="Could not send the verification email. Please check your email address, or try again shortly.",
        )

    return {
        "message": (
            f"A verification code has been sent to {payload.email}."
            if smtp_configured
            else f"Email is not configured yet - check the backend console for the code sent to {payload.email}."
        ),
    }


@router.post("/register/verify", response_model=Token)
@limiter.limit("10/hour")
def verify_registration(request: Request, payload: RegisterVerify, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Step 2 of registration: confirms the code from /register and actually
    creates the account using the name/phone/password submitted in step 1.
    """
    if email_is_taken(db, payload.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    otp = get_valid_otp(db, email=payload.email, purpose="register", supplied_code=payload.code)
    if not otp or not otp.pending_hashed_password:
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    otp.is_used = True
    if phone_is_taken(db, otp.pending_phone):
        raise HTTPException(status_code=422, detail="This phone number is already linked to another account")

    user = User(
        full_name=otp.pending_full_name,
        email=otp.email,
        phone=otp.pending_phone,
        hashed_password=otp.pending_hashed_password,
        role="citizen",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    background_tasks.add_task(send_welcome_email, user.email, user.full_name)

    token = create_access_token_for_user(user)
    return Token(access_token=token, role=user.role, full_name=user.full_name, user_id=user.id)


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, background_tasks: BackgroundTasks, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    OAuth2-compatible login (form fields: username=email, password).
    Returns a JWT the frontend attaches as 'Authorization: Bearer <token>'.
    """
    # Email addresses are case-insensitive in practice; trimming also avoids
    # frustrating 401 responses caused by accidental spaces when pasting.
    email = form_data.username.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    # Always spend the bcrypt work factor, even for an unknown address.
    # Skipping it would make "no such account" return measurably faster than
    # "wrong password", which is enough to enumerate who has an account here.
    password_ok = verify_password(form_data.password, user.hashed_password) if user else dummy_verify()
    print(f"LOGIN DEBUG: user_found={user is not None}, password_ok={password_ok}")
    print(f"LOGIN DEBUG ENV MATCH: {form_data.password == os.getenv('SEED_ADMIN_PASSWORD')}")
    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token_for_user(user)
    ip_address, user_agent = client_fingerprint(request)
    # Checked BEFORE the audit row is written, or this sign-in would match
    # itself and no alert would ever fire.
    new_device = is_new_signin_device(db, user, ip_address, user_agent)
    log_event(
        db,
        event_type="authentication",
        action="login_succeeded",
        actor=user,
        route="/api/auth/login",
        **signin_audit_fields(ip_address, user_agent),
    )
    db.commit()

    if new_device:
        # Background task: a slow or unreachable mail server must never hold
        # up a sign-in, and the session is already valid at this point.
        background_tasks.add_task(
            send_new_signin_email,
            user.email,
            user.full_name,
            utcnow().strftime("%d %b %Y at %H:%M UTC"),
            ip_address,
            describe_device(user_agent),
        )
    return Token(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
        user_id=user.id,
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserSelfUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lets staff, admins, and citizens keep their account contact details current.

    Jurisdiction and email remain protected: a jurisdiction is assigned by an
    authorized administrator, and changing email requires a separate OTP flow.
    """
    new_phone = payload.phone.strip() if payload.phone else None
    if phone_is_taken(db, new_phone, exclude_user_id=current_user.id):
        raise HTTPException(status_code=422, detail="This phone number is already linked to another account")
    current_user.full_name = payload.full_name.strip()
    current_user.phone = new_phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/password-reset/request")
@limiter.limit("5/hour")
def request_password_reset(request: Request, payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Sends a 6-digit code to reset a forgotten password. Works for any role
    (citizen, staff, admin) since anyone can forget their password.

    Always returns the same message whether or not the email has an
    account - this avoids leaking which emails are registered on the
    platform to someone probing random addresses.
    """
    generic_message = f"If an account exists for {payload.email}, a reset code has been sent to it."

    user = find_user_by_email(db, payload.email)
    if not user or not user.is_active:
        return {"message": generic_message}

    _, code = issue_otp(db, email=payload.email, purpose="password_reset")

    delivered = send_otp_email(payload.email, code, "password_reset")
    if not delivered:
        raise HTTPException(
            status_code=502,
            detail="Could not send the reset email right now. Please try again shortly.",
        )

    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)
    if not smtp_configured:
        return {"message": f"Email is not configured yet - check the backend console for the code sent to {payload.email}."}

    return {"message": generic_message}


@router.post("/password-reset/confirm", response_model=Token)
@limiter.limit("10/hour")
def confirm_password_reset(request: Request, payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Verifies the reset code and sets the new password, logging the user in."""
    otp = get_valid_otp(db, email=payload.email, purpose="password_reset", supplied_code=payload.code)
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    user = find_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    otp.is_used = True
    user.hashed_password = hash_password(payload.new_password)
    user.session_version += 1
    db.commit()
    db.refresh(user)

    token = create_access_token_for_user(user)
    return Token(access_token=token, role=user.role, full_name=user.full_name, user_id=user.id)


@router.post("/delete-account/request")
@limiter.limit("5/hour")
def request_account_deletion(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Step 1 of citizen self-deletion: emails a 6-digit code to the citizen's
    own address. Deleting a login is irreversible, so this requires proving
    access to the account's email before /delete-account/confirm will
    actually remove anything - typing "DELETE" alone isn't enough.
    """
    if current_user.role != "citizen":
        raise HTTPException(
            status_code=403,
            detail="Staff and admin accounts are managed by an administrator, not self-deleted.",
        )

    _, code = issue_otp(db, email=current_user.email, purpose="delete_account")

    delivered = send_otp_email(current_user.email, code, "delete_account")
    if not delivered:
        raise HTTPException(
            status_code=502,
            detail="Could not send the confirmation email right now. Please try again shortly.",
        )

    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)
    return {
        "message": (
            f"A confirmation code has been sent to {current_user.email}."
            if smtp_configured
            else "Email is not configured yet - check the backend console for the code."
        )
    }


@router.post("/delete-account/confirm", status_code=204)
@limiter.limit("10/hour")
def confirm_account_deletion(
    request: Request,
    payload: DeleteAccountConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Step 2: verifies the emailed code before permanently deleting the
    citizen's login. Any household/member record, certificates, or scheme
    applications tied to it are kept as official Panchayat records - only
    unlinked from the now-deleted login, not erased, since the office
    still needs that history.
    """
    if current_user.role != "citizen":
        raise HTTPException(status_code=403, detail="Staff and admin accounts are managed by an administrator.")

    otp = get_valid_otp(db, email=current_user.email, purpose="delete_account", supplied_code=payload.code)
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid confirmation code.")

    otp.is_used = True

    try:
        delete_user_record(db, current_user)
    except RetainedRecordError as exc:
        raise HTTPException(status_code=409, detail=exc.reason) from exc
    db.commit()
    return None


@router.post("/change-password/request-otp")
@limiter.limit("5/hour")
def request_change_password_otp(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Any role: step 1 of changing your password while logged in. Emails a
    code to your own address - required alongside your old password so a
    compromised/left-open session alone can't silently change the password.
    """
    _, code = issue_otp(db, email=current_user.email, purpose="change_password")

    delivered = send_otp_email(current_user.email, code, "change_password")
    if not delivered:
        raise HTTPException(status_code=502, detail="Could not send the confirmation email right now. Please try again shortly.")

    smtp_configured = bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)
    return {
        "message": (
            f"A confirmation code has been sent to {current_user.email}."
            if smtp_configured
            else "Email is not configured yet - check the backend console for the code."
        )
    }


@router.post("/change-password/confirm", status_code=204)
@limiter.limit("10/hour")
def confirm_change_password(
    request: Request,
    payload: ChangePasswordConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Step 2: verifies the old password AND the emailed code before setting the new password."""
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Your current password is incorrect.")

    otp = get_valid_otp(db, email=current_user.email, purpose="change_password", supplied_code=payload.code)
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid confirmation code.")

    otp.is_used = True
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.session_version += 1
    db.commit()
    return None




"""
Seeds the database with:
  - one superadmin account
  - one district staff account
  - a few sample government schemes
"""

import os
import secrets
import string
import sys

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.models.scheme import Scheme, SchemeDocumentRequirement
from app.schemas.password import validate_password_strength


ADMIN_EMAIL = os.getenv(
    "SEED_ADMIN_EMAIL",
    "admin@panchayat.gov.in"
).strip().lower()

STAFF_EMAIL = os.getenv(
    "SEED_STAFF_EMAIL",
    "staff@panchayat.gov.in"
).strip().lower()

STAFF_DISTRICT = os.getenv(
    "SEED_STAFF_DISTRICT",
    "Guntur"
).strip()

_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"


def generate_password() -> str:
    """Generate a random password satisfying the platform password policy."""
    while True:
        candidate = "".join(
            secrets.choice(_ALPHABET) for _ in range(20)
        )
        try:
            return validate_password_strength(candidate)
        except ValueError:
            continue


def resolve_password(env_var: str, label: str) -> tuple[str, bool]:
    """Return (password, was_generated)."""
    supplied = os.getenv(env_var)

    if supplied:
        try:
            validate_password_strength(supplied)
        except ValueError as exc:
            print(
                f"ERROR: {env_var} for the {label} account "
                f"is not acceptable: {exc}"
            )
            sys.exit(1)

        return supplied, False

    return generate_password(), True


def sync_existing_password(user, env_var: str, label: str) -> bool:
    """Apply <env_var> to an account that already exists. Returns True if set.

    On a hosting plan with no shell access this is the ONLY way to reach an
    existing account, because seed skips anything that already exists - which
    is precisely wrong when the problem is an account whose password nobody
    knows.

    A weak value warns rather than sys.exit: the start command is
    "python seed.py && uvicorn ...", so a non-zero exit takes the entire API
    down over one bad environment variable, punishing every citizen for an
    operator typo.
    """
    supplied = os.getenv(env_var)

    if not supplied:
        print(f"{label} {user.email} already exists - password left unchanged.")
        print(f"    (set {env_var} and deploy again to choose a new one)")
        return False

    try:
        validate_password_strength(supplied)
    except ValueError as exc:
        print("!" * 68)
        print(f"WARNING: {env_var} is not acceptable: {exc}")
        print(f"{label} {user.email} was NOT changed. The API is still starting;")
        print("fix the variable and deploy again to apply it.")
        print("!" * 68)
        return False

    user.hashed_password = hash_password(supplied)
    # Any session issued under the old password has to stop working.
    user.session_version = (user.session_version or 0) + 1
    print(f"{label} {user.email} password synchronized from {env_var}.")
    return True


Base.metadata.create_all(bind=engine)

db = SessionLocal()
created_credentials: list[tuple[str, str, str]] = []
password_syncs: list[tuple[str, str]] = []

try:
    # ---------------------------------------------------------
    # SUPERADMIN - password sync
    # ---------------------------------------------------------
    admin = db.query(User).filter(
        User.email == ADMIN_EMAIL
    ).first()

    if not admin:
        password, generated = resolve_password(
            "SEED_ADMIN_PASSWORD",
            "superadmin"
        )

        db.add(
            User(
                full_name="Panchayat Administrator",
                email=ADMIN_EMAIL,
                phone="9999999999",
                hashed_password=hash_password(password),
                role="admin",
                jurisdiction_level="super",
            )
        )

        created_credentials.append(
            (
                "Superadmin",
                ADMIN_EMAIL,
                password if generated else "(the password you supplied)"
            )
        )

    else:
        if sync_existing_password(admin, "SEED_ADMIN_PASSWORD", "Superadmin"):
            password_syncs.append((ADMIN_EMAIL, os.environ["SEED_ADMIN_PASSWORD"]))

    # ---------------------------------------------------------
    # STAFF
    # ---------------------------------------------------------
    staff = db.query(User).filter(
        User.email == STAFF_EMAIL
    ).first()

    if not staff:
        password, generated = resolve_password(
            "SEED_STAFF_PASSWORD",
            "staff"
        )

        db.add(
            User(
                full_name="Panchayat Staff",
                email=STAFF_EMAIL,
                phone="8888888888",
                hashed_password=hash_password(password),
                role="staff",
                jurisdiction_level="district",
                district=STAFF_DISTRICT,
            )
        )

        created_credentials.append(
            (
                f"Staff ({STAFF_DISTRICT} district)",
                STAFF_EMAIL,
                password if generated else "(the password you supplied)"
            )
        )

    else:
        if sync_existing_password(staff, "SEED_STAFF_PASSWORD", "Staff"):
            password_syncs.append((STAFF_EMAIL, os.environ["SEED_STAFF_PASSWORD"]))

    db.commit()

    # Re-read each synchronized account from the database and check the new
    # password against the stored hash. The whole reason login was unreachable
    # was a run that reported success for a credential nobody could use, so a
    # sync that did not persist must not be allowed to print "synchronized".
    db.expire_all()
    for synced_email, synced_password in password_syncs:
        stored = db.query(User).filter(User.email == synced_email).one()
        if verify_password(synced_password, stored.hashed_password):
            print(f"Verified: {synced_email} can sign in with the new password.")
        else:
            print("!" * 68)
            print(f"FAILED: {synced_email} does NOT accept the new password.")
            print("Do not treat this account as recovered.")
            print("!" * 68)

    # SAMPLE SCHEMES
    # ---------------------------------------------------------
    if db.query(Scheme).count() == 0:
        schemes_data = [
            (
                Scheme(
                    name="Old Age Pension Scheme",
                    description=(
                        "Monthly pension support for senior citizens "
                        "above 60 years without other income support."
                    ),
                    eligibility_criteria=(
                        "Age 60+, resident of the village for 5+ years, "
                        "no government pension already received."
                    ),
                    max_income_limit=100000,
                ),
                [
                    "Aadhaar Card",
                    "Age Proof",
                    "Residence Certificate",
                    "Income Certificate",
                ],
            ),
            (
                Scheme(
                    name="Rural Housing Scheme (PMAY-G style)",
                    description=(
                        "Financial assistance to build a pucca house "
                        "for families living in kutcha houses."
                    ),
                    eligibility_criteria=(
                        "Family currently lives in a kutcha/temporary house, "
                        "annual income below threshold."
                    ),
                    max_income_limit=150000,
                ),
                [
                    "Aadhaar Card",
                    "Income Certificate",
                    "Residence Certificate",
                    "Land Documents",
                ],
            ),
            (
                Scheme(
                    name="Girl Child Education Support",
                    description=(
                        "Scholarship support for girl children enrolled "
                        "in government schools, grades 1-10."
                    ),
                    eligibility_criteria=(
                        "Girl child enrolled in a government school, "
                        "family income below threshold."
                    ),
                    max_income_limit=120000,
                ),
                [
                    "Aadhaar Card",
                    "School Enrollment Proof",
                    "Income Certificate",
                ],
            ),
            (
                Scheme(
                    name="Agricultural Input Subsidy",
                    description=(
                        "Subsidy on seeds and fertilizers for small "
                        "and marginal farmers."
                    ),
                    eligibility_criteria=(
                        "Owns less than 2 acres of agricultural land, "
                        "primary occupation is farming."
                    ),
                    max_income_limit=None,
                ),
                [
                    "Aadhaar Card",
                    "Land Records",
                    "Residence Certificate",
                ],
            ),
        ]

        for scheme, doc_names in schemes_data:
            db.add(scheme)
            db.flush()

            for doc_name in doc_names:
                db.add(
                    SchemeDocumentRequirement(
                        scheme_id=scheme.id,
                        name=doc_name,
                    )
                )

        db.commit()

        print(
            f"Created {len(schemes_data)} sample schemes "
            f"with document requirements."
        )

    # The generated passwords only ever existed in this process. The list was
    # built and then never read back, so a fresh deployment created a
    # superadmin whose password nobody - not the operator, not even the deploy
    # log - ever saw. The account was live and permanently unreachable. Print
    # them here, once, which is the whole reason the list is collected.
    if created_credentials:
        print()
        print("=" * 68)
        print("  NEW ACCOUNTS CREATED - COPY THESE NOW, THEY ARE SHOWN ONCE")
        print("=" * 68)
        for label, account_email, account_password in created_credentials:
            print(f"  {label}")
            print(f"    email:    {account_email}")
            print(f"    password: {account_password}")
        print("=" * 68)
        print()
    elif not os.getenv("SEED_ADMIN_PASSWORD"):
        # The silent trap: every account already exists, nothing was changed,
        # and if the password is unknown this run did nothing to help.
        print()
        print("NOTE: all accounts already existed and SEED_ADMIN_PASSWORD is not")
        print("      set, so no password was changed by this run. If you cannot")
        print("      sign in, set SEED_ADMIN_PASSWORD and deploy again.")
        print()

    print("Seeding complete.")

finally:
    db.close()

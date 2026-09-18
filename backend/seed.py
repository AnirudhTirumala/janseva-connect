"""
Seeds the database with:
  - one superadmin account
  - one district staff account
  - a few sample government schemes

Run with:  python seed.py
(Run this once after the backend has started at least once, or standalone -
 it creates tables itself if needed.)

Passwords
---------
This script does NOT ship with fixed passwords. Earlier versions seeded
"Admin@123" / "Staff@123", which are now public knowledge in this repo's
history - anyone who found a deployment could sign in as its administrator.

Instead, each account gets a strong random password that is printed ONCE,
here, at creation time. Copy it somewhere safe immediately; it is never
stored in plaintext and cannot be recovered afterwards (use the Forgot
Password flow if it is lost).

To choose your own instead, set them in the environment before running:

    SEED_ADMIN_EMAIL=...       SEED_ADMIN_PASSWORD=...
    SEED_STAFF_EMAIL=...       SEED_STAFF_PASSWORD=...

Any password you supply must satisfy the same policy the API enforces.
"""
import os
import secrets
import string
import sys

from app.core.database import Base, engine, SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.scheme import Scheme, SchemeDocumentRequirement
from app.schemas.password import validate_password_strength

ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@panchayat.gov.in").strip().lower()
STAFF_EMAIL = os.getenv("SEED_STAFF_EMAIL", "staff@panchayat.gov.in").strip().lower()
STAFF_DISTRICT = os.getenv("SEED_STAFF_DISTRICT", "Guntur").strip()

_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"


def generate_password() -> str:
    """A random password that satisfies the platform's own strength policy."""
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(20))
        try:
            return validate_password_strength(candidate)
        except ValueError:  # pragma: no cover - re-roll on a missing char class
            continue


def resolve_password(env_var: str, label: str) -> tuple[str, bool]:
    """Return (password, was_generated), validating anything supplied by hand."""
    supplied = os.getenv(env_var)
    if supplied:
        try:
            validate_password_strength(supplied)
        except ValueError as exc:
            print(f"ERROR: {env_var} for the {label} account is not acceptable: {exc}")
            sys.exit(1)
        return supplied, False
    return generate_password(), True


Base.metadata.create_all(bind=engine)

db = SessionLocal()
created_credentials: list[tuple[str, str, str]] = []

try:
    if not db.query(User).filter(User.email == ADMIN_EMAIL).first():
        password, generated = resolve_password("SEED_ADMIN_PASSWORD", "superadmin")
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
        created_credentials.append(("Superadmin", ADMIN_EMAIL, password if generated else "(the password you supplied)"))
    else:
        print(f"Superadmin {ADMIN_EMAIL} already exists - left untouched.")

    if not db.query(User).filter(User.email == STAFF_EMAIL).first():
        password, generated = resolve_password("SEED_STAFF_PASSWORD", "staff")
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
        created_credentials.append((f"Staff ({STAFF_DISTRICT} district)", STAFF_EMAIL, password if generated else "(the password you supplied)"))
    else:
        print(f"Staff {STAFF_EMAIL} already exists - left untouched.")

    db.commit()

    if db.query(Scheme).count() == 0:
        schemes_data = [
            (
                Scheme(
                    name="Old Age Pension Scheme",
                    description="Monthly pension support for senior citizens above 60 years without other income support.",
                    eligibility_criteria="Age 60+, resident of the village for 5+ years, no government pension already received.",
                    max_income_limit=100000,
                ),
                ["Aadhaar Card", "Age Proof", "Residence Certificate", "Income Certificate"],
            ),
            (
                Scheme(
                    name="Rural Housing Scheme (PMAY-G style)",
                    description="Financial assistance to build a pucca house for families living in kutcha houses.",
                    eligibility_criteria="Family currently lives in a kutcha/temporary house, annual income below threshold.",
                    max_income_limit=150000,
                ),
                ["Aadhaar Card", "Income Certificate", "Residence Certificate", "Land Documents"],
            ),
            (
                Scheme(
                    name="Girl Child Education Support",
                    description="Scholarship support for girl children enrolled in government schools, grades 1-10.",
                    eligibility_criteria="Girl child enrolled in a government school, family income below threshold.",
                    max_income_limit=120000,
                ),
                ["Aadhaar Card", "School Enrollment Proof", "Income Certificate"],
            ),
            (
                Scheme(
                    name="Agricultural Input Subsidy",
                    description="Subsidy on seeds and fertilizers for small and marginal farmers.",
                    eligibility_criteria="Owns less than 2 acres of agricultural land, primary occupation is farming.",
                    max_income_limit=None,
                ),
                ["Aadhaar Card", "Land Records", "Residence Certificate"],
            ),
        ]
        for scheme, doc_names in schemes_data:
            db.add(scheme)
            db.flush()  # get scheme.id
            for doc_name in doc_names:
                db.add(SchemeDocumentRequirement(scheme_id=scheme.id, name=doc_name))
        db.commit()
        print(f"Created {len(schemes_data)} sample schemes with document requirements.")

    if created_credentials:
        print("\n" + "=" * 72)
        print("  ACCOUNT CREDENTIALS - shown once, not recoverable. Save them now.")
        print("=" * 72)
        for label, email, password in created_credentials:
            print(f"  {label}\n    email:    {email}\n    password: {password}\n")
        print("  Sign in and change these passwords before handing the portal over.")
        print("=" * 72 + "\n")

    print("Seeding complete.")
finally:
    db.close()

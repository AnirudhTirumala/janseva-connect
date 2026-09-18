"""Set an administrator's password, and prove it worked.

Run this in the Render shell when nobody can sign in. It is deliberately
separate from seed.py: seed is "set up a new deployment" and skips anything
that already exists, which is exactly the wrong behaviour when the problem is
that an account exists with a password nobody knows.

    python reset_admin_password.py                       # default admin, random password
    python reset_admin_password.py you@example.com       # a specific account
    RESET_PASSWORD='Kollur#Village42' python reset_admin_password.py

What it does differently from guessing:

* Reports whether the account existed, so "wrong password" and "wrong email"
  stop looking identical.
* Rejects a weak password with the reason, rather than dying on a traceback.
* Re-reads the row from the database AFTER the commit and verifies the new
  password against the stored hash. A sync that prints success but never
  persisted is the failure mode this exists to rule out.
* Lists every account on the instance, so you can see what you can sign in as.
"""

import os
import secrets
import string
import sys

from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.password import validate_password_strength

DEFAULT_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@panchayat.gov.in").strip().lower()
_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_=+"


def generate_password() -> str:
    while True:
        candidate = "".join(secrets.choice(_ALPHABET) for _ in range(20))
        try:
            return validate_password_strength(candidate)
        except ValueError:  # pragma: no cover - re-roll on a missing char class
            continue


def main() -> int:
    target_email = (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL).strip().lower()

    supplied = os.getenv("RESET_PASSWORD") or os.getenv("SEED_ADMIN_PASSWORD")
    if supplied:
        try:
            validate_password_strength(supplied)
        except ValueError as exc:
            print(f"REFUSED: that password is not acceptable - {exc}")
            print("Nothing was changed. Choose a stronger one and run again.")
            return 1
        password, generated = supplied, False
    else:
        password, generated = generate_password(), True

    db = SessionLocal()
    try:
        accounts = db.query(User).order_by(User.id).all()
        print(f"\nAccounts on this instance ({len(accounts)}):")
        for account in accounts:
            print(f"  {account.id:>3}  {account.role:<8} {account.email}"
                  f"{'' if account.is_active else '   [DEACTIVATED]'}")
        if not accounts:
            print("  (none - this database is empty. Run `python seed.py` first.)")

        # Case-insensitive, because that is how login looks accounts up.
        user = next((a for a in accounts if a.email.lower() == target_email), None)
        if user is None:
            print(f"\nNo account found for {target_email}.")
            print("Sign in with one of the addresses listed above, or pass the right one:")
            print("    python reset_admin_password.py the.address@you.use")
            return 1

        user.hashed_password = hash_password(password)
        user.is_active = True
        # Existing sessions must not survive a password reset.
        user.session_version = (user.session_version or 0) + 1
        db.commit()

        # Re-read from the database rather than trusting the in-memory object:
        # this is what proves the change actually persisted.
        db.expire_all()
        stored = db.query(User).filter(User.id == user.id).one()
        if not verify_password(password, stored.hashed_password):
            print("\nFAILED: the new password does not verify against the stored hash.")
            print("Nothing is usable - do not treat this as done.")
            return 1

        print("\n" + "=" * 68)
        print("  PASSWORD RESET AND VERIFIED AGAINST THE DATABASE")
        print("=" * 68)
        print(f"  email:    {stored.email}")
        print(f"  password: {password if generated else '(the one you supplied)'}")
        print(f"  role:     {stored.role}")
        print("\n  Every existing session for this account has been signed out.")
        if generated:
            print("  This password is shown once. Copy it now.")
        print("=" * 68 + "\n")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

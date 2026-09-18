"""Consistent, case-insensitive account lookup and uniqueness checks.

``users.email`` and ``users.phone`` are both UNIQUE.  Request schemas now
normalise email to lowercase, but rows created by earlier versions of this
app may still hold mixed case, so every lookup goes through ``func.lower``
rather than an exact match.  Without this, "Priya@Gmail.com" fails to find
the existing "priya@gmail.com" row, the duplicate check passes, and the
INSERT dies with an IntegrityError - a 500 in the middle of registration.
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User


def normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def find_user_by_email(db: Session, email: Optional[str]) -> Optional[User]:
    normalized = normalize_email(email)
    if not normalized:
        return None
    return db.query(User).filter(func.lower(User.email) == normalized).first()


def email_is_taken(db: Session, email: Optional[str]) -> bool:
    return find_user_by_email(db, email) is not None


def phone_is_taken(db: Session, phone: Optional[str], exclude_user_id: Optional[int] = None) -> bool:
    """Whether another account already holds this phone number.

    ``users.phone`` is UNIQUE, so a duplicate must be reported as a clear
    422 at the form rather than surfacing as a database IntegrityError.
    """
    cleaned = (phone or "").strip()
    if not cleaned:
        return False
    query = db.query(User.id).filter(User.phone == cleaned)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first() is not None

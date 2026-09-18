"""Shared field types used across request schemas."""

from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints


def _normalize_email(value: str) -> str:
    """Store and compare every address in one canonical form.

    ``users.email`` is UNIQUE.  Without this, "Priya@Gmail.com" passes the
    duplicate check against an existing "priya@gmail.com" row and then
    fails at the database with an IntegrityError - a 500 in the middle of
    registration.  Normalising at the edge means one person is one row,
    and the login/reset lookups all agree on the same key.
    """
    return value.strip().lower()


NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]

# ``users.phone`` is VARCHAR(20) and UNIQUE; ``members.phone`` is VARCHAR(20).
# PostgreSQL rejects anything longer outright, so the limit belongs here
# rather than being discovered as a 500 at insert time.
PhoneStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Name150 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)]
Address255 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]

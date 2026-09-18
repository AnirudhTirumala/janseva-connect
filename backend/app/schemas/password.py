"""Password policy for every place a password is set.

Length alone is not a policy: "password" and "12345678" both pass an
eight-character minimum, and both are in the first few hundred entries of
any credential-stuffing list.  A portal holding Aadhaar numbers and income
records should not accept them.

The rules below are deliberately the ones people can actually satisfy on
a phone keyboard - a mix of character classes, a real minimum length, and
a small deny-list of the passwords that show up first in every breach
corpus - rather than a maze of rules that pushes people to "Password@1"
written on a sticky note.
"""

from typing import Annotated

from pydantic import AfterValidator, Field

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 128

# bcrypt truncates silently at 72 *bytes*; refusing longer input is clearer
# than accepting a password whose tail is ignored at verification time.
BCRYPT_MAX_BYTES = 72

_COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "p@ssw0rd", "p@ssword",
    "12345678", "123456789", "1234567890", "qwertyuiop", "qwerty123", "1q2w3e4r",
    "iloveyou", "admin123", "administrator", "letmein123", "welcome123",
    "abcd1234", "abc123456", "changeme", "changeme123", "secret123",
    "janseva123", "panchayat", "panchayat123", "india@123", "admin@123",
    "staff@123", "citizen123", "test1234", "aadhaar123",
}


def validate_password_strength(value: str) -> str:
    """Enforce length, character variety, and a common-password deny-list."""
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(value.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("Password is too long - please use 72 characters or fewer.")

    classes = sum(
        [
            any(char.islower() for char in value),
            any(char.isupper() for char in value),
            any(char.isdigit() for char in value),
            any(not char.isalnum() for char in value),
        ]
    )
    if classes < 3:
        raise ValueError(
            "Password must combine at least three of: lowercase letters, uppercase "
            "letters, numbers, and symbols."
        )

    simplified = value.strip().lower()
    if simplified in _COMMON_PASSWORDS:
        raise ValueError("That password is too common. Please choose something less guessable.")
    if len(set(simplified)) < 5:
        raise ValueError("Password repeats too few distinct characters. Please choose something less guessable.")

    return value


StrongPassword = Annotated[
    str,
    Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH),
    AfterValidator(validate_password_strength),
]

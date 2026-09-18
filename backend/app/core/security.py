from datetime import timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
from app.core.timeutils import naive_utc

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# A precomputed hash of a value nothing can match, used to spend the same
# bcrypt time on a login attempt for an address that has no account.
_DUMMY_HASH = pwd_context.hash("account-enumeration-guard-not-a-real-password")


def dummy_verify() -> bool:
    """Burn one bcrypt verification and return False.

    Called when no user matched, so a login for an unregistered address
    takes the same time as one with a wrong password. Without it the
    response time alone reveals which email addresses are registered.
    """
    pwd_context.verify("x", _DUMMY_HASH)
    return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT containing the given claims (typically user id, role, email).
    Used for stateless authentication across all roles (admin/staff/citizen).
    """
    to_encode = data.copy()
    issued_at = naive_utc()
    expire = issued_at + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"iat": issued_at, "exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token_for_user(user) -> str:
    """Issue a token tied to the user's current session generation.

    A password reset/change or account deactivation increments this value,
    which invalidates previously issued tokens immediately instead of waiting
    for the (up to one-day) JWT expiry window.
    """
    return create_access_token(
        data={"sub": str(user.id), "role": user.role, "sv": user.session_version}
    )


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

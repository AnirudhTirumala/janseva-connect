from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Decodes the JWT, validates it, and loads the corresponding user from DB."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # A token whose `sub` is missing or not an integer is a forged or
    # corrupted token, not a server fault - int() would otherwise raise
    # ValueError and turn a rejected credential into a 500.
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")
    # Tokens issued before a password reset, password change, or account
    # deactivation must no longer work.  Old deployments did not include the
    # session-version claim, so those tokens are deliberately rejected too.
    if payload.get("sv") != user.session_version:
        raise credentials_exception
    return user


def require_roles(*allowed_roles: str):
    """
    Dependency factory for role-based access control.
    Usage: Depends(require_roles("admin", "staff"))
    """

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker

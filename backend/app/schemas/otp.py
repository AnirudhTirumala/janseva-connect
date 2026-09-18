from pydantic import BaseModel, Field

from app.schemas.common import NormalizedEmail
from app.schemas.password import StrongPassword


class RegisterVerify(BaseModel):
    email: NormalizedEmail
    code: str = Field(..., min_length=6, max_length=6)


class PasswordResetRequest(BaseModel):
    email: NormalizedEmail


class PasswordResetConfirm(BaseModel):
    email: NormalizedEmail
    code: str = Field(..., min_length=6, max_length=6)
    new_password: StrongPassword


class DeleteAccountConfirm(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class ChangePasswordConfirm(BaseModel):
    old_password: str
    code: str = Field(..., min_length=6, max_length=6)
    new_password: StrongPassword


class AdminUserCreateConfirm(BaseModel):
    email: NormalizedEmail
    code: str = Field(..., min_length=6, max_length=6)

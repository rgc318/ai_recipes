from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class AuthTokenResponse(BaseModel):
    access_token: str
    expires_at: datetime


class ChangePasswordRequest(BaseModel):
    user_id: UUID
    old_password: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str

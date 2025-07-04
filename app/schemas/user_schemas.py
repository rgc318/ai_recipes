from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str

class UserRead(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    is_active: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class UserUpdate(BaseModel):
    full_name: Optional[str]
    avatar_url: Optional[str]
    password: Optional[str]

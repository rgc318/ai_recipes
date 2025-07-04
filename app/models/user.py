from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field
from app.models.base.base_model import BaseModel


class User(BaseModel, table=True):
    __tablename__ = "user"

    username: str = Field(index=True, nullable=False, unique=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)
    phone: Optional[str] = Field(default=None, index=True, unique=True)

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    hashed_password: str = Field(nullable=False)

    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    is_verified: bool = Field(default=False)

    last_login_at: Optional[datetime] = None
    login_count: int = Field(default=0)

class UserAuth(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    provider: str  # "github" / "wechat" / "apple" / "local"
    provider_user_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

class UserSavedRecipe(BaseModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    recipe_id: UUID = Field(foreign_key="recipe.id", primary_key=True)
    saved_at: datetime = Field(default_factory=datetime.utcnow)

class UserAIHistory(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    query: str
    ai_response: str
    # created_at: datetime = Field(default_factory=datetime.utcnow)

class UserFeedback(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    content: str
    contact_email: Optional[str] = None
    # created_at: datetime = Field(default_factory=datetime.utcnow)

class UserLoginLog(BaseModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    login_at: datetime = Field(default_factory=datetime.utcnow)

class Role(BaseModel, table=True):
    name: str
    description: Optional[str] = None

class Permission(BaseModel, table=True):
    name: str
    description: Optional[str] = None

class UserRole(BaseModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    role_id: UUID = Field(foreign_key="role.id", primary_key=True)

class RolePermission(BaseModel, table=True):
    role_id: UUID = Field(foreign_key="role.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="permission.id", primary_key=True)

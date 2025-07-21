from datetime import datetime
from typing import Optional, Set, List
from uuid import UUID, uuid4

from sqlalchemy import Column, Integer, DateTime
from sqlmodel import SQLModel, Field, Relationship

from app.enums.auth_method import AuthMethod
from app.models._model_utils.datetime import utcnow
from app.models.base.base_model import BaseModel
from app.models.file_record import FileRecord
from app.schemas.user_schemas import UserRead


class UserRole(BaseModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    role_id: UUID = Field(foreign_key="role.id", primary_key=True)

class RolePermission(BaseModel, table=True):
    role_id: UUID = Field(foreign_key="role.id", primary_key=True)
    permission_id: UUID = Field(foreign_key="permission.id", primary_key=True)

class Role(BaseModel, table=True):
    # 【新增】code 字段，作为系统内部唯一、不可变的标识符
    code: str = Field(..., unique=True, index=True, description="角色的唯一代码，系统内部使用，不可变")
    # name 字段现在作为可随时修改的、对用户友好的显示名称
    name: str = Field(..., description="角色的显示名称，人类可读，可修改")
    description: Optional[str] = None

    users: List["User"] = Relationship(back_populates="roles", link_model=UserRole)
    permissions: List["Permission"] = Relationship(back_populates="roles", link_model=RolePermission)


class Permission(BaseModel, table=True):
    # 【新增】code 字段，作为系统内部唯一、不可变的标识符
    code: str = Field(..., unique=True, index=True, description="权限的唯一代码，如 'recipe:create'")
    # name 字段现在作为可随时修改的、对用户友好的显示名称
    name: str = Field(..., description="权限的显示名称，如 '创建菜谱'")
    description: Optional[str] = None

    roles: List["Role"] = Relationship(back_populates="permissions", link_model=RolePermission)

class User(BaseModel, table=True):
    __tablename__ = "user"
    __pydantic_model__ = UserRead
    # _version_col = Column(Integer, nullable=False, server_default="1")

    username: str = Field(index=True, nullable=False, unique=True)
    email: Optional[str] = Field(default=None, index=True, unique=True)
    phone: Optional[str] = Field(default=None, index=True, unique=True)

    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

    hashed_password: str = Field(nullable=False)
    auth_method: AuthMethod = Field(default=AuthMethod.app,nullable=True)  # ✅ 新增
    login_attempts: int = Field(default=0)  # 👈 添加此行
    is_superuser: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    is_locked: bool = Field(default=False)
    is_active: bool = Field(default=True, nullable=False)

    last_login_at: Optional[datetime] = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    # last_login_at: Optional[datetime] = Field(
    #     sa_column=Column(DateTime(timezone=True), nullable=True)
    # )
    login_count: int = Field(default=0)

    roles: List["Role"] = Relationship(back_populates="users", link_model=UserRole)
    uploaded_files: List["FileRecord"] = Relationship(
        back_populates="uploader"
        # No need for foreign_keys hint if there's only one link
    )
    # 【新增】乐观锁的版本号字段

    version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default="1"),
        description="数据版本号，用于乐观锁"
    )

    # 【新增】告知SQLAlchemy使用 version 字段进行版本控制
    # 3. 在 __mapper_args__ 中，也引用同一个列变量对象。
    __mapper_args__ = {
        "version_id_col": version.sa_column,
        "version_id_generator": False  # 或根据需求自定义
    }
    @property
    def permissions(self) -> Set[str]:
        perms = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.code)
        return perms

class UserAuth(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    provider: str  # "github" / "wechat" / "apple" / "local"
    provider_user_id: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None

class UserSavedRecipe(BaseModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    recipe_id: UUID = Field(foreign_key="recipe.id", primary_key=True)
    saved_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))

class UserAIHistory(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    query: str
    ai_response: str

class UserFeedback(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    content: str
    contact_email: Optional[str] = None

class UserLoginLog(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    login_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))






class UserPreference(BaseModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    preferred_language: Optional[str] = Field(default="zh")
    ai_style: Optional[str] = Field(default="healthy")
    subscribe_newsletter: bool = Field(default=False)


class UserLoginFailLog(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    username_attempted: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    reason: Optional[str] = None  # 密码错误、多次失败、验证码未通过等
    login_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))


class VerificationCode(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    contact: str  # email 或 phone
    code: str
    purpose: str  # register, login, reset_password, verify
    is_used: bool = Field(default=False)
    expires_at: datetime
    sent_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))


class UserActionLog(BaseModel, table=True):
    # id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    action: str  # e.g., "create_recipe", "delete_account"
    target_id: Optional[UUID] = None
    target_type: Optional[str] = None  # e.g., "Recipe", "Comment"
    extra_data: Optional[str] = None


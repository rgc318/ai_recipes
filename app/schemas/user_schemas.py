from typing import Annotated, Optional, List, Generic
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from app.core.types.common import ModelType, T
from app.enums.auth_method import AuthMethod
from app.schemas.role_schemas import RoleRead

# ==========================
# 💡 通用类型定义
# ==========================
UsernameStr = Annotated[str, StringConstraints(min_length=3, max_length=30, to_lower=True, strip_whitespace=True)]
PasswordStr = Annotated[str, StringConstraints(min_length=8, strip_whitespace=True)]


# ==========================
# 🧾 用户创建模型
# ==========================
class UserCreate(BaseModel):
    username: UsernameStr = Field(..., description="用户名（小写、去空格）")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, description="手机号")
    password: PasswordStr = Field(..., description="密码，最少 8 位")

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value and not value.isdigit():
            raise ValueError("手机号应为数字")
        return value


# ==========================
# 📤 用户读取模型
# ==========================
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

    model_config = {
        "from_attributes": True
    }


# ==========================
# 🔄 用户更新模型
# ==========================
class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, description="完整姓名")
    avatar_url: Optional[str] = Field(None, description="头像 URL")
    password: Optional[PasswordStr] = Field(None, description="新密码，至少 8 位")

class UserReadWithRoles(UserRead):
    """
    一个更详细的用户读取模型，继承自 UserRead，并额外包含了用户的角色列表。
    主要用于后台管理的用户列表展示。
    """
    roles: List[RoleRead] = []
# ==========================
# 🔐 用户修改密码模型
# ==========================
class UserPasswordUpdate(BaseModel):
    old_password: PasswordStr = Field(..., description="当前密码")
    new_password: PasswordStr = Field(..., description="新密码，至少 8 位")

    @model_validator(mode="after")
    def validate_not_same(self):
        if self.old_password == self.new_password:
            raise ValueError("新密码不能和旧密码相同")
        return self

class CredentialsRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    remember_me: bool = Field(default=False)
    captcha: Optional[bool] = Field(default=None, description="验证码校验结果")
    select_account: Optional[str] = Field(default=None, description="选择的账户")

class PrivateUser(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    password: str
    auth_method: AuthMethod
    login_attempts: int = 0
    locked_at: Optional[datetime] = None

    @property
    def is_locked(self) -> bool:
        from datetime import UTC, timedelta, datetime
        from app.config import settings

        if self.locked_at is None:
            return False
        lockout_expires_at = self.locked_at + timedelta(hours=settings.SECURITY_USER_LOCKOUT_TIME)
        return lockout_expires_at > datetime.now(UTC)
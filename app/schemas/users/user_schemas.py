from typing import Annotated, Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, computed_field

from app.core.logger import logger
from app.enums.auth_method import AuthMethod
from app.infra.storage.storage_factory import storage_factory
from app.schemas.file.file_record_schemas import FileRecordRead
from app.schemas.users.role_schemas import RoleRead
from app.utils.url_builder import build_public_storage_url

# ==========================
# 💡 通用类型定义
# ==========================
UsernameStr = Annotated[str, StringConstraints(min_length=3, max_length=30, to_lower=True, strip_whitespace=True)]
PasswordStr = Annotated[str, StringConstraints(min_length=8, strip_whitespace=True)]


class UserBase(BaseModel):
    full_name: Optional[str] = Field(None, description="完整姓名或昵称")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, description="手机号")
    avatar_url: Optional[str] = Field(None, description="头像 URL")

    @field_validator("phone", mode="before")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value and not value.isdigit():
            raise ValueError("手机号应为数字")
        return value

# ==========================
# 🧾 用户创建模型
# ==========================
class UserCreate(UserBase):
    username: UsernameStr = Field(..., description="用户名")
    password: PasswordStr = Field(..., description="密码，最少 8 位")
    role_ids: Optional[List[UUID]] = Field(None, description="创建用户时要关联的角色ID列表。")
    avatar_file_record_id: Optional[UUID] = None

# ==========================
# 🔄 用户更新模型 (核心修改)
# ==========================
class UserUpdate(BaseModel): # 【修改】不再继承自 UserBase
    """管理员更新用户信息的模型，不包含头像更新。"""
    full_name: Optional[str] = Field(None, description="完整姓名或昵称")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, description="手机号")
    password: Optional[PasswordStr] = Field(None, description="新密码，留空则不修改")
    is_active: Optional[bool] = Field(None, description="是否激活账户")
    is_superuser: Optional[bool] = Field(None, description="是否为超级用户")
    is_verified: Optional[bool] = Field(None, description="是否已验证")
    is_locked: Optional[bool] = Field(None, description="是否已锁定")
    role_ids: Optional[List[UUID]] = Field(None, description="分配给用户的角色ID列表")
    avatar_file_record_id: Optional[UUID] = None

# ==========================
# 🙋 用户更新自己的个人资料模型 (核心修改)
# ==========================
class UserUpdateProfile(BaseModel): # 【修改】不再包含 avatar_url
    """用户更新自己个人资料的模型，不包含头像更新。"""
    full_name: Optional[str] = Field(None, description="完整姓名或昵称")
    email: Optional[EmailStr] = Field(None, description="邮箱地址")
    phone: Optional[str] = Field(None, description="手机号")

# ==========================
# 📤 用户读取模型
# ==========================


class UserRead(BaseModel):
    id: UUID
    username: str
    email: Optional[str]
    phone: Optional[str]
    full_name: Optional[str]
    avatar: Optional[FileRecordRead] = None
    is_active: bool
    is_superuser: bool
    is_verified: bool
    is_locked: bool  # <-- 建议在Read模型也加上，以便前端展示
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = Field(None, description="上次登录时间")

    @computed_field
    @property
    def full_avatar_url(self) -> Optional[str]:
        """
        动态生成前端需要的完整头像URL。
        它利用内部 'avatar' (FileRecordRead DTO) 字段的 'url' 属性。
        """
        # 假设 FileRecordRead 已经有一个 .url 属性 (如上所示)
        if self.avatar and self.avatar.url:
            return self.avatar.url

        # 如果 self.avatar 是 None, 或者 self.avatar.url 是 None,
        # 最终都返回 null，这正是前端想要的
        return None

    model_config = {
        "from_attributes": True
    }

class UserReadWithRoles(UserRead):
    """
    一个更详细的用户读取模型，继承自 UserRead，并额外包含了用户的角色列表。
    主要用于后台管理的用户列表展示。
    """
    roles: List[RoleRead] = []
    permissions: List[str] = set()  # <-- 新增这一行
# ==========================
# 🔐 用户修改密码模型
# ==========================
class UserPasswordUpdate(BaseModel):
    old_password: PasswordStr = Field(..., description="当前密码")
    new_password: PasswordStr = Field(..., description="新密码，至少 8 位")

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

class UserFilterParams(BaseModel):
    """
    用户动态查询的过滤参数模型。
    前端可以根据需要传递任意组合。
    """
    username: Optional[str] = Field(None, description="按用户名模糊搜索")
    email: Optional[str] = Field(None, description="按邮箱模糊搜索")
    phone: Optional[str] = Field(None, description="按手机号模糊搜索")
    full_name: Optional[str] = Field(None, description="按全名模糊搜索") # 示例：轻松添加新字段
    is_active: Optional[bool] = Field(None, description="按激活状态过滤")
    is_superuser: Optional[bool] = Field(None, description="按是否为超级用户过滤")
    is_locked: Optional[bool] = Field(None, description="按是否锁定过滤")
    role_ids: Optional[List[UUID]] = Field(None, description="根据关联的角色ID列表过滤")

class BatchDeletePayload(BaseModel):
    user_ids: List[UUID] = Field(..., min_length=1, description="要删除的用户ID列表")

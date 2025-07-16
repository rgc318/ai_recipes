from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from .permission_schemas import PermissionRead

# --- Role Schemas ---

class RoleBase(BaseModel):
    """
    角色的基础模型，包含所有角色共有的核心字段。
    """
    name: str = Field(..., description="角色的唯一名称，例如：'admin', 'content_manager'")
    description: Optional[str] = Field(None, description="角色的详细描述。")


class RoleCreate(RoleBase):
    """
    用于创建新角色的模型。
    """
    pass


class RoleUpdate(RoleBase):
    """
    用于更新现有角色的模型，允许部分更新。
    """
    name: Optional[str] = None
    description: Optional[str] = None


class RoleRead(RoleBase):
    """
    用于从API返回基本角色信息的模型。
    """
    id: UUID

    class Config:
        from_attributes = True


class RoleReadWithPermissions(RoleRead):
    """
    一个更详细的角色读取模型，包含了与该角色关联的所有权限信息。
    常用于角色详情页面。
    """
    permissions: List[PermissionRead] = []


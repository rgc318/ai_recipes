from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

# --- Permission Schemas ---

class PermissionBase(BaseModel):
    """
    权限的基础模型，包含所有权限共有的核心字段。
    """
    name: str = Field(..., description="权限的唯一名称，例如：'order:create', 'management:read_all'")
    description: Optional[str] = Field(None, description="权限的详细描述，解释该权限的作用。")


class PermissionCreate(PermissionBase):
    """
    用于创建新权限的模型。
    目前与基础模型相同，但分开定义便于未来扩展。
    """
    pass


class PermissionUpdate(PermissionBase):
    """
    用于更新现有权限的模型。
    所有字段都是可选的，允许进行部分更新。
    """
    name: Optional[str] = None
    description: Optional[str] = None


class PermissionRead(PermissionBase):
    """
    用于从API返回权限数据的模型。
    包含了数据库生成的ID，并配置为可从ORM对象转换。
    """
    id: UUID

    class Config:
        from_attributes = True

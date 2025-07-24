from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, conlist

from .permission_schemas import PermissionRead

# --- Role Schemas ---

class RoleBase(BaseModel):
    """
    角色的基础模型，定义了所有角色共有的核心字段。
    """
    code: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9_]+$",  # 推荐对code使用正则，保证格式统一
        description="角色的唯一代码，系统内部使用。例如：'content_editor'。只能包含小写字母、数字和下划线。"
    )
    name: str = Field(..., min_length=2, max_length=50, description="角色的显示名称，用于UI展示。例如：'内容编辑'。")
    description: Optional[str] = Field(None, max_length=255, description="角色的详细描述。")



class RoleCreate(RoleBase):
    """
    用于创建新角色的模型。
    在创建时，可以同时关联一组权限。
    """
    permission_ids: List[UUID] = Field([], description="创建角色时要关联的权限ID列表。")


class RoleUpdate(BaseModel):
    """
    用于更新现有角色的模型，所有字段都是可选的。
    这个模型功能强大，可以同时更新角色的基础信息和其关联的所有权限。
    """
    code: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-z0-9_]+$", description="新的唯一代码。")
    name: Optional[str] = Field(None, min_length=2, max_length=50, description="新的显示名称。")
    description: Optional[str] = Field(None, max_length=255, description="新的详细描述。")
    permission_ids: Optional[List[UUID]] = Field(None, description="要为此角色设置的权限ID完整列表。如果提供，将覆盖所有现有权限。")


class RoleRead(RoleBase):
    """
    用于从API返回基本角色信息的模型，不含权限详情。
    """
    id: UUID
    created_at: Optional[datetime] = Field(None)

    model_config = {
        "from_attributes": True
    }


class RoleReadWithPermissions(RoleRead):
    """
    一个更详细的角色读取模型，包含了与该角色关联的所有权限的详细信息。
    常用于角色详情页面。
    """
    permissions: List[PermissionRead] = []


# --- 专用 Schemas ---

class RolePermissionsUpdate(BaseModel):
    """
    专门用于批量设置角色权限的请求模型。
    对应 `PUT /roles/{role_id}/permissions` 接口。
    """
    permission_ids: List[UUID] = Field(..., description="要为此角色设置的权限ID完整列表，此操作会覆盖所有现有权限。")


class RoleSelectorRead(BaseModel):
    """
    专门用于选择器（如下拉框）的超轻量级角色模型。
    对应 `GET /roles/selector` 接口。
    """
    id: UUID
    name: str

    model_config = {
        "from_attributes": True
    }

class RoleFilterParams(BaseModel):
    """
    角色列表查询的过滤参数模型。
    FastAPI 将会自动从查询参数中解析并填充这个对象。
    """
    # 保持与 permission 模块一致的通用搜索框设计
    search: Optional[str] = Field(None, description="按角色名称或代码进行模糊搜索")
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

# --- Permission Schemas ---

class PermissionBase(BaseModel):
    """
    权限的基础模型，包含所有权限共有的核心字段。
    """
    code: str = Field(..., description="权限的唯一代码，系统内部使用，例如：'recipe:create'")
    name: str = Field(..., description="权限的唯一名称，例如：'order:create', 'user:read_all'")
    group: str = Field(..., description="权限的所属模块，例如：'用户管理', '角色管理'")
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
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class PermissionRead(PermissionBase):
    """
    用于从API返回权限数据的模型。
    包含了数据库生成的ID，并配置为可从ORM对象转换。
    """
    id: UUID

    model_config = {
        "from_attributes": True
    }


class PermissionSyncResponse(BaseModel):
    """
    用于权限同步操作的响应模型。
    提供了操作的统计摘要和详细列表。
    """
    total: int = Field(..., description="本次同步请求中包含的权限总数。")
    found: int = Field(..., description="在数据库中已存在的权限数量。")
    created: int = Field(..., description="本次同步中新创建的权限数量。")

    # 包含详细信息，便于日志记录或前端展示更丰富的反馈
    created_items: List[PermissionRead] = Field(
        default=[],
        description="本次新创建的权限对象的详细列表。"
    )

    model_config = {
        "from_attributes": True
    }



class PermissionFilterParams(BaseModel):
    """
    权限列表查询的过滤参数模型。
    FastAPI 将会自动从查询参数中解析并填充这个对象。
    """
    group: Optional[str] = None
    # 统一将模糊搜索字段命名为 search
    search: Optional[str] = None

class PermissionSelectorRead(BaseModel):
    """
    专门用于选择器（如下拉框）的超轻量级权限模型。
    只包含前端选择时必要的 id 和 name 字段。
    """
    id: UUID
    name: str

    model_config = {"from_attributes": True}
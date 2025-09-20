# app/schemas/ingredient_schemas.py
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from app.enums.query_enums import ViewMode


# --- 基础与读取 ---

class IngredientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="食材名称，如'鸡胸肉'")
    description: Optional[str] = Field(None, max_length=500, description="食材的详细描述")
    plural_name: Optional[str] = Field(None, max_length=100, description="复数形式，如'eggs'")

class IngredientRead(IngredientBase):
    """用于从数据库读取并返回给客户端的食材模型。"""
    id: UUID
    normalized_name: str = Field(..., description="用于系统内部查询和去重的标准化名称")
    recipe_count: int = Field(0, description="关联的菜谱数量")
    created_at: Optional[datetime] = None
    is_deleted: bool = Field(False, description="是否已被软删除")

    model_config = {
        "from_attributes": True
    }

# --- 创建与更新 ---

class IngredientCreate(IngredientBase):
    """用于创建新食材的 Schema。"""
    pass

class IngredientUpdate(BaseModel):
    """用于更新食材的 Schema，所有字段都是可选的。"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    plural_name: Optional[str] = Field(None, max_length=100)

# --- 查询与过滤 ---

class IngredientFilterParams(BaseModel):
    """食材列表的动态查询过滤参数模型。"""
    name: Optional[str] = Field(None, description="按食材名称进行模糊搜索")
    description: Optional[str] = Field(None, description="按描述进行模糊搜索")

    search: Optional[str] = Field(None, description="按食材名称进行模糊搜索")
    # [新增] 增加 view_mode 以支持回收站功能
    view_mode: ViewMode = Field(ViewMode.ACTIVE, description="查看模式: active, all, deleted")

class IngredientMergePayload(BaseModel):
    """用于合并食材的请求体模型。"""
    source_ingredient_ids: List[UUID] = Field(..., min_length=1, description="一个或多个源食材ID列表（将被合并并删除）")
    target_ingredient_id: UUID = Field(..., description="一个目标食材ID（将被保留）")

class BatchActionIngredientsPayload(BaseModel):
    """用于批量操作（如删除、恢复）的请求体模型。"""
    ingredient_ids: List[UUID] = Field(..., min_length=1)
from datetime import datetime
# app/schemas/tag_schemas.py

from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from app.enums.query_enums import ViewMode


# --- 基础与读取 ---

class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="标签名称")

class TagRead(TagBase):
    """用于从数据库读取并返回给客户端的标签模型。"""
    id: UUID
    recipe_count: int = Field(0, description="关联的菜谱数量")  # <-- 【新增】
    created_at: Optional[datetime] = None  # <-- 【新增】
    is_deleted: bool = Field(False, description="是否已被软删除")  # <-- 【核心新增】
    
    model_config = {
        "from_attributes": True  # 允许从 ORM 对象创建
    }

class TagMergePayload(BaseModel):
    source_tag_ids: List[UUID] = Field(..., min_length=1)
    target_tag_id: UUID# --- 创建与更新 ---

class TagCreate(TagBase):
    """用于创建新标签的 Schema。"""
    pass # 目前与 TagBase 相同，但为了未来扩展性而独立定义

class TagUpdate(BaseModel):
    """用于更新标签的 Schema，所有字段都是可选的。"""
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="新的标签名称")

# --- 查询与过滤 ---

class TagFilterParams(BaseModel):
    """标签列表的动态查询过滤参数模型。"""
    search: Optional[str] = Field(None, description="按标签名称进行模糊搜索")
    view_mode: ViewMode = Field(ViewMode.ACTIVE, description="查看模式: active, all, deleted")


class BatchDeleteTagsPayload(BaseModel):
    tag_ids: List[UUID] = Field(..., min_length=1)
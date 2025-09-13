
# app/schemas/unit_schemas.py

from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

# --- 基础与读取 ---

class UnitBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="单位名称 (如: 克)")
    abbreviation: Optional[str] = Field(None, max_length=20, description="缩写 (如: g)")
    plural_name: Optional[str] = Field(None, max_length=50, description="复数名称 (如: cups)")

class UnitRead(UnitBase):
    """用于API响应的单位数据模型。"""
    id: UUID
    ingredient_count: int = Field(0, description="使用此单位的配料数量")
    is_deleted: bool = Field(False, description="是否已被软删除")  # <-- 【核心新增】

    model_config = {
        "from_attributes": True
    }

# --- 创建与更新 ---

class UnitCreate(UnitBase):
    """创建新单位的请求体。"""
    pass

class UnitUpdate(BaseModel):
    """更新单位的请求体，所有字段可选。"""
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    abbreviation: Optional[str] = Field(None, max_length=20)
    plural_name: Optional[str] = Field(None, max_length=50)

# --- 查询与过滤 ---

class UnitFilterParams(BaseModel):
    """单位列表（后台管理）的动态查询过滤参数。"""
    name: Optional[str] = Field(None, description="按单位名称或缩写模糊搜索")


class BatchDeleteUnitsPayload(BaseModel):
    """批量删除单位的请求体。"""
    unit_ids: List[UUID] = Field(..., min_length=1)

class UnitMergePayload(BaseModel):
    """合并单位的请求体。"""
    source_unit_ids: List[UUID] = Field(..., min_length=1, description="要被合并的源单位ID列表")
    target_unit_id: UUID = Field(..., description="合并目标单位的ID")
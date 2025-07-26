
# app/schemas/unit_schemas.py

from typing import Optional
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
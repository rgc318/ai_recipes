# app/schemas/ingredient_schemas.py

from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

# --- 基础与读取 ---

class IngredientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="食材名称，如'鸡胸肉'")
    description: Optional[str] = Field(None, max_length=500, description="食材的详细描述")
    plural_name: Optional[str] = Field(None, max_length=100, description="复数形式，如'eggs'")

class IngredientRead(IngredientBase):
    """用于从数据库读取并返回给客户端的食材模型。"""
    id: UUID
    normalized_name: str = Field(..., description="用于系统内部查询和去重的标准化名称")

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
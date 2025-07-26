from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


# === Tag ===
class TagBase(BaseModel):
    name: str

class TagRead(TagBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }


# === Unit ===
class UnitBase(BaseModel):
    name: str
    abbreviation: Optional[str] = None
    use_abbreviation: Optional[bool] = False
    plural_name: Optional[str] = None
    plural_abbreviation: Optional[str] = None

class UnitRead(UnitBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }


# === Ingredient ===
class IngredientBase(BaseModel):
    name: str
    description: Optional[str] = None
    normalized_name: Optional[str] = None
    plural_name: Optional[str] = None

class IngredientRead(IngredientBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }


# === RecipeIngredient ===
class RecipeIngredientInput(BaseModel):
    ingredient_id: UUID
    unit_id: Optional[UUID] = None
    quantity: Optional[float] = None
    note: Optional[str] = None

class RecipeIngredientRead(BaseModel):
    id: UUID
    quantity: Optional[float] = None
    note: Optional[str] = None

    ingredient: IngredientRead
    unit: Optional[UnitRead] = None

    model_config = {
        "from_attributes": True
    }


# === Recipe ===

class RecipeBase(BaseModel):
    title: str
    description: Optional[str] = None
    steps: str

class RecipeCreate(RecipeBase):
    tag_ids: Optional[List[UUID]] = None
    ingredients: Optional[List[RecipeIngredientInput]] = None

class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[str] = None
    tag_ids: Optional[List[UUID]] = None
    ingredients: Optional[List[RecipeIngredientInput]] = None

class RecipeRead(RecipeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    tags: List[TagRead] = []
    ingredients: List[RecipeIngredientRead] = []

    model_config = {
        "from_attributes": True
    }

class RecipeFilterParams(BaseModel):
    """菜谱列表的动态查询过滤参数模型。"""
    title: Optional[str] = Field(None, description="按菜谱标题进行模糊搜索")
    description: Optional[str] = Field(None, description="按菜谱描述进行模糊搜索")
    # created_by: Optional[UUID] = Field(None, description="按创建者ID精确过滤") # 示例：未来可轻松扩展

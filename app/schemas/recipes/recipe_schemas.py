# app/schemas/recipes/recipe_schemas.py

from typing import List, Optional, Union
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.file.file_record_schemas import FileRecordRead
from app.schemas.common.category_schemas import CategoryRead


# --- 其他 Schema 保持不变 ---


class RecipeStepInput(BaseModel):
    """用于创建/更新菜谱时，输入的单个步骤的数据结构。"""
    instruction: str
    duration: Optional[str] = Field(None, description="此步骤预计花费的时间, e.g., '10分钟'")
    image_ids: Optional[List[UUID]] = Field(None, description="关联到此步骤的图片(FileRecord)ID列表")

class RecipeStepRead(BaseModel):
    """用于API响应的单个步骤的数据结构。"""
    id: UUID
    step_number: int
    instruction: str
    duration: Optional[str] = Field(None, description="此步骤预计花费的时间, e.g., '10分钟'")
    images: List[FileRecordRead] = [] # 返回完整的图片信息
    model_config = {"from_attributes": True}

# === Tag ===
class TagBase(BaseModel):
    name: str


class TagRead(TagBase):
    id: UUID
    model_config = {"from_attributes": True}


# === Unit ===
class UnitBase(BaseModel):
    name: str
    abbreviation: Optional[str] = None
    use_abbreviation: Optional[bool] = False
    plural_name: Optional[str] = None
    plural_abbreviation: Optional[str] = None


class UnitRead(UnitBase):
    id: UUID
    model_config = {"from_attributes": True}


# === Ingredient ===
class IngredientBase(BaseModel):
    name: str
    description: Optional[str] = None
    normalized_name: Optional[str] = None
    plural_name: Optional[str] = None


class IngredientRead(IngredientBase):
    id: UUID
    model_config = {"from_attributes": True}


# === RecipeIngredient ===
class RecipeIngredientInput(BaseModel):
    ingredient: Union[UUID, str] = Field(..., description="已存在的食材ID或新的食材名称")
    unit_id: Optional[UUID] = None
    group: Optional[str] = Field(None, description="配料分组名, e.g., '面团部分'")
    quantity: Optional[float] = None
    note: Optional[str] = None


class RecipeIngredientRead(BaseModel):
    id: UUID
    group: Optional[str] = Field(None, description="配料分组名, e.g., '面团部分'")
    quantity: Optional[float] = None
    note: Optional[str] = None
    ingredient: IngredientRead
    unit: Optional[UnitRead] = None
    model_config = {"from_attributes": True}


# === Recipe ===

class RecipeBase(BaseModel):
    title: str
    description: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    servings: Optional[str] = None
    difficulty: Optional[str] = Field(None, description="难度等级")
    equipment: Optional[str] = Field(None, description="所需厨具清单, 用换行符分隔")
    author_notes: Optional[str] = Field(None, description="作者小贴士")

# =================================================================
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修改点 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# =================================================================

class RecipeCreate(RecipeBase):
    """创建新菜谱的请求体 (V3 - 结构化版)。"""
    tags: Optional[List[Union[UUID, str]]] = None
    ingredients: Optional[List[RecipeIngredientInput]] = None

    # 【新增】接收结构化数据
    cover_image_id: Optional[UUID] = Field(None, description="封面图片的FileRecord ID")
    gallery_image_ids: Optional[List[UUID]] = Field(None, description="画廊图片的FileRecord ID列表")
    steps: Optional[List[RecipeStepInput]] = Field(None, description="结构化的烹饪步骤列表")
    category_ids: Optional[List[UUID]] = Field(None, description="关联的分类ID列表")


class RecipeUpdate(RecipeBase):  # 【修改】让 RecipeUpdate 继承自 RecipeBase
    """更新菜谱的请求体 (V3 - 结构化版)，所有字段均为可选。"""
    # RecipeBase 中的所有字段 (title, description, difficulty等) 自动继承
    # 并且我们需要将它们全部变为可选
    title: Optional[str] = None
    description: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    servings: Optional[str] = None
    difficulty: Optional[str] = None
    equipment: Optional[str] = None
    author_notes: Optional[str] = None

    # 关联关系字段保持不变
    tags: Optional[List[Union[UUID, str]]] = None
    ingredients: Optional[List[RecipeIngredientInput]] = None
    cover_image_id: Optional[UUID] = None
    gallery_image_ids: Optional[List[UUID]] = None
    steps: Optional[List[RecipeStepInput]] = None
    category_ids: Optional[List[UUID]] = None


# =================================================================

class RecipeRead(RecipeBase):
    """用于API响应的完整菜谱数据模型 (V3 - 结构化版)。"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    tags: List[TagRead] = []
    ingredients: List[RecipeIngredientRead] = []

    # 【新增】返回结构化数据
    cover_image: Optional[FileRecordRead] = None
    gallery_images: List[FileRecordRead] = []
    steps: List[RecipeStepRead] = []
    categories: List["CategoryRead"] = []

    model_config = {"from_attributes": True}


class RecipeSummaryRead(RecipeBase):
    """
    用于【列表页】的菜谱摘要数据模型。
    只包含列表展示所必需的字段，不包含步骤、配料等重型数据。
    """
    id: UUID
    created_at: datetime
    updated_at: datetime

    # 列表页通常需要封面、标签和分类用于展示和筛选
    cover_image: Optional[FileRecordRead] = None
    tags: List[TagRead] = []
    categories: List["CategoryRead"] = []

    model_config = {"from_attributes": True}

class RecipeFilterParams(BaseModel):
    title: Optional[str] = Field(None, description="按菜谱标题进行模糊搜索")
    description: Optional[str] = Field(None, description="按菜谱描述进行模糊搜索")

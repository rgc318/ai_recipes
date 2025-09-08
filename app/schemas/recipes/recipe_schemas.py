# app/schemas/recipes/recipe_schemas.py

from typing import List, Optional, Union
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, create_model, conlist

from app.schemas.file.file_record_schemas import FileRecordRead
from app.schemas.common.category_schemas import CategoryRead


# --- 其他 Schema 保持不变 ---


class RecipeStepInput(BaseModel):
    """用于创建/更新菜谱时，输入的单个步骤的数据结构。"""
    instruction: str = Field(..., max_length=2000) # <-- 【新增】文本长度限制
    duration: Optional[str] = Field(None, description="此步骤预计花费的时间, e.g., '10分钟'")
    image_ids: Optional[conlist(UUID, max_length=5)] = Field(None, description="每个步骤最多5张图")

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
    group: Optional[str] = Field(None, max_length=20, description="配料分组名, e.g., '面团部分'")  # <-- 【新增】文本长度限制
    quantity: Optional[float] = Field(None, ge=0, le=99999)  # <-- 【新增】数值范围限制
    note: Optional[str] = Field(None, max_length=100)  # <-- 【新增】文本长度限制


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
    title: str = Field(..., max_length=100)  # <-- 【新增】文本长度限制
    description: Optional[str] = Field(None, max_length=1000)  # <-- 【新增】文本长度限制
    prep_time: Optional[str] = Field(None, max_length=50)  # <-- 【新增】文本长度限制
    cook_time: Optional[str] = Field(None, max_length=50)  # <-- 【新增】文本长度限制
    servings: Optional[str] = Field(None, max_length=50)  # <-- 【新增】文本长度限制
    difficulty: Optional[str] = Field(None, description="难度等级")
    equipment: Optional[str] = Field(None, max_length=1000, description="所需厨具清单, 用换行符分隔")
    author_notes: Optional[str] = Field(None, max_length=1000, description="作者小贴士")

# =================================================================
# ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心修改点 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
# =================================================================

class RecipeCreate(RecipeBase):
    """创建新菜谱的请求体 (V3 - 结构化版)。"""
    tags: Optional[conlist(Union[UUID, str], max_length=8)] = None
    ingredients: Optional[conlist(RecipeIngredientInput, max_length=50)] = None
    steps: Optional[conlist(RecipeStepInput, max_length=20)] = None
    category_ids: Optional[conlist(UUID, max_length=5)] = None
    gallery_image_ids: Optional[conlist(UUID, max_length=9)] = None

    cover_image_id: Optional[UUID] = Field(None, description="封面图片的FileRecord ID")


def make_optional(model: type[BaseModel]) -> type[BaseModel]:
    fields = model.model_fields
    optional_fields = {
        name: (Optional[field.annotation], None) for name, field in fields.items()
    }
    return create_model(f'{model.__name__}Optional', **optional_fields)

# RecipeUpdate 现在包含了 RecipeBase 和 RecipeCreate 中所有字段的可选版本
class RecipeUpdate(BaseModel):
    """
    【最终版】用于更新菜谱的 Pydantic 模型。
    采用“购物车”/“差量更新”模式。
    """
    # 1. 菜谱的基础信息字段 (全部设为可选)
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    prep_time: Optional[str] = Field(None, max_length=50)
    cook_time: Optional[str] = Field(None, max_length=50)
    servings: Optional[str] = Field(None, max_length=50)
    difficulty: Optional[str] = None
    equipment: Optional[str] = Field(None, max_length=1000)
    author_notes: Optional[str] = Field(None, max_length=1000)

    # 2. 菜谱的关联关系字段（“全量替换”模式）
    #    如果前端传入这些字段，则后端会用新列表完全覆盖旧列表
    tags: Optional[conlist(Union[UUID, str], max_length=8)] = None
    ingredients: Optional[conlist(RecipeIngredientInput, max_length=50)] = None
    steps: Optional[conlist(RecipeStepInput, max_length=20)] = None
    category_ids: Optional[conlist(UUID, max_length=5)] = None
    gallery_image_ids: Optional[conlist(UUID, max_length=9)] = None

    cover_image_id: Optional[UUID] = None

    # 3. 【核心新增】用于图片集合的“差量更新”字段
    #    这些字段专门用于“购物车”模式
    images_to_add: Optional[List[UUID]] = Field(None, description="需要新增到画廊的图片ID列表")
    images_to_delete: Optional[List[UUID]] = Field(None, description="需要从画廊删除的图片ID列表")

    # 注意：步骤图片(step images)通常是跟随步骤(steps)整体更新的，
    # 所以它们的变更信息已经包含在 steps 字段中了，一般无需在此处再添加差量字段。

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

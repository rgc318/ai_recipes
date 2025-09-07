# app/schemas/recipes/recipe_schemas.py

from typing import List, Optional, Union
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, create_model

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
    title: Optional[str] = None
    description: Optional[str] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    servings: Optional[str] = None
    difficulty: Optional[str] = None
    equipment: Optional[str] = None
    author_notes: Optional[str] = None

    # 2. 菜谱的关联关系字段（“全量替换”模式）
    #    如果前端传入这些字段，则后端会用新列表完全覆盖旧列表
    tags: Optional[List[Union[UUID, str]]] = None
    ingredients: Optional[List[RecipeIngredientInput]] = None
    steps: Optional[List[RecipeStepInput]] = None
    category_ids: Optional[List[UUID]] = None
    # 注意：封面图的更新通常是独立的原子操作，但也可以放在这里
    cover_image_id: Optional[UUID] = None

    # 3. 【核心新增】用于图片集合的“差量更新”字段
    #    这些字段专门用于“购物车”模式
    images_to_add: Optional[List[UUID]] = Field(None, description="需要新增到画廊的图片ID列表")
    images_to_delete: Optional[List[UUID]] = Field(None, description="需要从画廊删除的图片ID列表")
    gallery_image_ids: Optional[List[UUID]] = Field(None, description="画廊图片的最终完整顺序ID列表")

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

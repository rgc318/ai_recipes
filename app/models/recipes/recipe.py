from typing import Optional, List
import uuid

from sqlmodel import SQLModel, Field, Relationship
from app.models._model_utils.guid import GUID
from app.models.base.base_model import BaseModel, AutoTableNameMixin
from app.models.files.file_record import FileRecord
from app.models.common.category_model import Category, RecipeCategoryLink


class RecipeGalleryLink(BaseModel, table=True):
    """关联“菜谱”与“画廊图片(FileRecord)”的多对多关系。"""
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", primary_key=True)
    file_id: uuid.UUID = Field(foreign_key="file_record.id", primary_key=True)
    display_order: int = Field(default=0, description="图片显示顺序")

class RecipeStepImageLink(BaseModel, table=True):
    """关联“烹饪步骤”与“步骤图片(FileRecord)”的多对多关系。"""
    step_id: uuid.UUID = Field(foreign_key="recipe_step.id", primary_key=True)
    file_id: uuid.UUID = Field(foreign_key="file_record.id", primary_key=True)
    display_order: int = Field(default=0, description="图片显示顺序")

# === 标签 Tag ===
class RecipeTagLink(AutoTableNameMixin, SQLModel,  table=True):
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", primary_key=True, sa_type=GUID())
    tag_id: uuid.UUID = Field(foreign_key="tag.id", primary_key=True, sa_type=GUID())


class RecipeStep(BaseModel, table=True):
    """结构化的烹饪步骤模型。"""
    __tablename__ = "recipe_step"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id")
    step_number: int = Field(..., description="步骤序号, 从1开始")
    instruction: str = Field(..., description="这一步的具体操作文本")

    # 一个步骤可以有多张图片
    images: List["FileRecord"] = Relationship(link_model=RecipeStepImageLink)
    recipe: "Recipe" = Relationship(back_populates="steps")

class Tag(BaseModel, table=True):
    name: str = Field(index=True, nullable=False)
    recipes: List["Recipe"] = Relationship(back_populates="tags", link_model=RecipeTagLink)


# === 单位 Unit ===
class Unit(BaseModel, table=True):
    name: str
    abbreviation: Optional[str] = None
    use_abbreviation: bool = Field(default=False)
    plural_name: Optional[str] = None
    plural_abbreviation: Optional[str] = None


# === 食材 Ingredient ===
class Ingredient(BaseModel, table=True):
    name: str
    description: Optional[str] = None
    normalized_name: Optional[str] = Field(default=None, index=True)
    plural_name: Optional[str] = None


# === 菜谱中的配料 RecipeIngredient（中间表）===
class RecipeIngredient(AutoTableNameMixin, SQLModel,  table=True):
    id: uuid.UUID = Field(default_factory=GUID.generate, sa_type=GUID(), primary_key=True)

    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", sa_type=GUID())
    ingredient_id: uuid.UUID = Field(foreign_key="ingredient.id", sa_type=GUID())
    unit_id: Optional[uuid.UUID] = Field(default=None, foreign_key="unit.id", sa_type=GUID())

    quantity: Optional[float] = Field(default=None)
    note: Optional[str] = None

    recipe: Optional["Recipe"] = Relationship(back_populates="ingredients")
    ingredient: Optional[Ingredient] = Relationship()
    unit: Optional[Unit] = Relationship()


# === 菜谱 Recipe ===
class Recipe(BaseModel, table=True):
    title: str
    description: Optional[str] = None
    prep_time: Optional[str] = Field(None, description="准备时间, e.g., '15分钟'")
    cook_time: Optional[str] = Field(None, description="烹饪时间, e.g., '30分钟'")
    servings: Optional[str] = Field(None, description="份量, e.g., '2-3人份'")

    cover_image_id: Optional[uuid.UUID] = Field(default=None, foreign_key="file_record.id")
    cover_image: Optional["FileRecord"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "Recipe.cover_image_id == FileRecord.id",
        }
    )
    # 2. 图片画廊 (多对多关系)
    gallery_images: List["FileRecord"] = Relationship(link_model=RecipeGalleryLink)

    # 3. 结构化步骤 (一对多关系)
    steps: List["RecipeStep"] = Relationship(
        back_populates="recipe",
        sa_relationship_kwargs={
            "order_by": "RecipeStep.step_number",
            "cascade": "all, delete-orphan"  # 删除菜谱时，级联删除其所有步骤
        }
    )

    ingredients: List["RecipeIngredient"] = Relationship(back_populates="recipe")
    tags: List["Tag"] = Relationship(back_populates="recipes", link_model=RecipeTagLink)
    categories: List["Category"] = Relationship(back_populates="recipes", link_model=RecipeCategoryLink)

# 设置反向关系
RecipeIngredient.recipe = Relationship(back_populates="ingredients")

from typing import Optional, List
import uuid

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import declared_attr
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

    __table_args__ = (
        UniqueConstraint("recipe_id", "tag_id", name="uq_recipe_tag"),
    )

class RecipeStep(BaseModel, table=True):
    """结构化的烹饪步骤模型。"""
    __tablename__ = "recipe_step"

    recipe_id: uuid.UUID = Field(foreign_key="recipe.id")
    step_number: int = Field(..., description="步骤序号, 从1开始")
    instruction: str = Field(..., description="这一步的具体操作文本")
    duration: Optional[str] = Field(None, description="此步骤预计花费的时间, e.g., '10分钟'")

    # 一个步骤可以有多张图片
    images: List["FileRecord"] = Relationship(
        link_model=RecipeStepImageLink,
        sa_relationship_kwargs={
            "secondaryjoin": "and_(RecipeStepImageLink.file_id == FileRecord.id, FileRecord.is_deleted == False)"
        }
    )
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
    normalized_name: Optional[str] = Field(default=None, index=True, )
    plural_name: Optional[str] = None

    # __table_args__ = BaseModel.soft_unique_index("normalized_name")

    @declared_attr
    def __table_args__(cls):
        return cls.soft_unique_index(cls.__tablename__, "normalized_name",)

# === 菜谱中的配料 RecipeIngredient（中间表）===
class RecipeIngredient(AutoTableNameMixin, SQLModel,  table=True):
    id: uuid.UUID = Field(default_factory=GUID.generate, sa_type=GUID(), primary_key=True)

    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", sa_type=GUID())
    ingredient_id: uuid.UUID = Field(foreign_key="ingredient.id", sa_type=GUID())
    unit_id: Optional[uuid.UUID] = Field(default=None, foreign_key="unit.id", sa_type=GUID())
    group: Optional[str] = Field(None, description="配料分组名, e.g., '面团部分'")
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
    difficulty: Optional[str] = Field(None, description="难度等级")
    equipment: Optional[str] = Field(None, description="所需厨具清单, 用换行符分隔")
    cover_image_id: Optional[uuid.UUID] = Field(default=None, foreign_key="file_record.id")
    cover_image: Optional["FileRecord"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "and_(Recipe.cover_image_id == FileRecord.id, FileRecord.is_deleted == False)",
        }
    )
    author_notes: Optional[str] = Field(None, description="作者小贴士")
    # 2. 图片画廊 (多对多关系)
    gallery_images: List["FileRecord"] = Relationship(
        link_model=RecipeGalleryLink,
        sa_relationship_kwargs={
            "secondaryjoin": "and_(RecipeGalleryLink.file_id == FileRecord.id, FileRecord.is_deleted == False)"
        }
    )

    # 3. 结构化步骤 (一对多关系)
    steps: List["RecipeStep"] = Relationship(
        back_populates="recipe",
        sa_relationship_kwargs={
            "primaryjoin": "and_(Recipe.id == RecipeStep.recipe_id, RecipeStep.is_deleted == False)",
            "order_by": "RecipeStep.step_number",
            "cascade": "all, delete-orphan"
        }
    )

    ingredients: List["RecipeIngredient"] = Relationship(
        back_populates="recipe",
        sa_relationship_kwargs={
            # 假设 RecipeIngredient 继承了 BaseModel 并有 is_deleted
            # "primaryjoin": "and_(Recipe.id == RecipeIngredient.recipe_id, RecipeIngredient.is_deleted == False)",
            "cascade": "all, delete-orphan"
        }
    )

    tags: List["Tag"] = Relationship(
        back_populates="recipes",
        link_model=RecipeTagLink,
        sa_relationship_kwargs={
            "secondaryjoin": "and_(RecipeTagLink.tag_id == Tag.id, Tag.is_deleted == False)"
        }
    )

    # 【核心修正 7】
    # 分类 (多对多关系)，只加载未被软删除的分类
    categories: List["Category"] = Relationship(
        back_populates="recipes",
        link_model=RecipeCategoryLink,
        sa_relationship_kwargs={
            "secondaryjoin": "and_(RecipeCategoryLink.category_id == Category.id, Category.is_deleted == False)"
        }
    )

# 设置反向关系
RecipeIngredient.recipe = Relationship(back_populates="ingredients")

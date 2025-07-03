from typing import Optional, List
import uuid

from sqlmodel import SQLModel, Field, Relationship
from app.models._model_utils.guid import GUID
from app.models.base.base_model import BaseModel




# === 标签 Tag ===
class RecipeTagLink(SQLModel, table=True):
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", primary_key=True, sa_type=GUID())
    tag_id: uuid.UUID = Field(foreign_key="tag.id", primary_key=True, sa_type=GUID())


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
class RecipeIngredient(SQLModel, table=True):
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
    steps: str

    ingredients: List[RecipeIngredient] = Relationship(back_populates="recipe")
    tags: List[Tag] = Relationship(back_populates="recipes", link_model=RecipeTagLink)


# 设置反向关系
RecipeIngredient.recipe = Relationship(back_populates="ingredients")

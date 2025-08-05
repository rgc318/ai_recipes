# app/models/recipes/category_model.py
from typing import List, Optional, TYPE_CHECKING
import uuid
from sqlmodel import Field, Relationship

from app.models.base.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.recipes.recipe import Recipe


# 菜谱与分类的多对多关联表
class RecipeCategoryLink(BaseModel, table=True):
    recipe_id: uuid.UUID = Field(foreign_key="recipe.id", primary_key=True)
    category_id: uuid.UUID = Field(foreign_key="category.id", primary_key=True)


class Category(BaseModel, table=True):
    __tablename__ = "category"

    name: str = Field(..., index=True, unique=True)
    slug: str = Field(..., index=True, unique=True, description="用于URL的唯一标识")
    description: Optional[str] = None

    # --- 用于实现层级关系 ---

    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="category.id")

    # '多对一' 的关系 (你的修复方案，非常正确)
    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Category.id"}
    )

    # '一对多' 的关系
    children: List["Category"] = Relationship(
        back_populates="parent",
        # 【核心优化】添加级联删除配置
        # cascade="all, delete-orphan" 的意思是：
        # 对父对象的所有操作（保存、删除等）都会传递给子对象。
        # 当一个父对象被从会话中移除时，所有子对象也会被删除。
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    recipes: List["Recipe"] = Relationship(back_populates="categories", link_model=RecipeCategoryLink)
# app/models/recipes/category_model.py
from typing import List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import UniqueConstraint, and_
from sqlalchemy.orm import declared_attr, remote, foreign
from sqlmodel import Field, Relationship

from app.models.base.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.recipes.recipe import Recipe


# 菜谱与分类的多对多关联表
class RecipeCategoryLink(BaseModel, table=True):
    recipe_id: UUID = Field(foreign_key="recipe.id", primary_key=True)
    category_id: UUID = Field(foreign_key="category.id", primary_key=True)

    __table_args__ = (
        UniqueConstraint("recipe_id", "category_id", name="uq_recipe_category"),
    )


class Category(BaseModel, table=True):
    __tablename__ = "category"

    name: str = Field(..., index=True, )
    slug: str = Field(..., index=True, description="用于URL的唯一标识")
    description: Optional[str] = None

    # --- 用于实现层级关系 ---

    parent_id: Optional[UUID] = Field(default=None, foreign_key="category.id")

    # '多对一' 的关系 (你的修复方案，非常正确)
    parent: Optional["Category"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "Category.id"}
    )

    # '一对多' 的关系
    children: List["Category"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={
            # 使用 remote() 包裹住 parent_id，明确它是远程列
            "primaryjoin": lambda: and_(
                Category.id == remote(foreign(Category.parent_id)),
                Category.is_deleted == False
            ),
            "cascade": "all, delete-orphan"
        }
    )

    recipes: List["Recipe"] = Relationship(
        back_populates="categories",
        link_model=RecipeCategoryLink,
        sa_relationship_kwargs={
            "secondaryjoin": "and_(RecipeCategoryLink.recipe_id == Recipe.id, Recipe.is_deleted == False)"
        }
    )
    # __table_args__ = BaseModel.soft_unique_index("slug", "name", batch= True)

    @declared_attr
    def __table_args__(cls):
        return cls.soft_unique_index(cls.__tablename__, "slug", "name", batch= True)

def get_descendant_ids(category_id: UUID, all_categories: list[Category]) -> set[UUID]:
    """
    递归地从一个扁平的分类列表中找到一个分类的所有后代ID。
    注意：需要你的 all_categories 列表包含 parent_id 资讯。
    """
    descendants = {category_id}  # 包含自身
    children = [cat.id for cat in all_categories if cat.parent_id == category_id]
    for child_id in children:
        descendants.update(get_descendant_ids(child_id, all_categories))
    return descendants

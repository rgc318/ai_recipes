# app/schemas/recipes/category_schemas.py
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

class CategoryBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None

class CategoryRead(CategoryBase):
    id: UUID
    model_config = {"from_attributes": True}

class CategoryReadWithChildren(CategoryRead):
    children: List["CategoryRead"] = []


class CategoryFilterParams(BaseModel):
    """
    分类列表的动态查询过滤参数模型。

    这个模型用于 FastAPI 的依赖注入，它会自动解析 URL 查询参数。
    例如: GET /categories?name=美食&slug=food
    """
    name: Optional[str] = Field(None, description="按分类名称进行模糊搜索")
    slug: Optional[str] = Field(None, description="按 slug 精确搜索")
    parent_id: Optional[UUID] = Field(None, description="按父分类ID筛选顶级分类下的子分类")
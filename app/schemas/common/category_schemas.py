# app/schemas/recipes/category_schemas.py
from datetime import datetime
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

class CategoryParentRead(BaseModel):
    id: UUID
    name: str
    model_config = {"from_attributes": True}

class CategoryRead(CategoryBase):
    id: UUID
    parent: Optional[CategoryParentRead] = None # <-- 新增的字段
    is_deleted: bool = Field(False, description="是否已被软删除")  # <-- 【新增】
    recipe_count: int = Field(0, description="关联的菜谱数量")  # <-- 【新增】
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

class CategoryReadWithChildren(CategoryRead):
    # 将 children 的类型从 List["CategoryRead"] 改为 List["CategoryReadWithChildren"]
    # 这样 Pydantic 就会用正确的、支持递归的模型去序列化子节点
    children: List["CategoryReadWithChildren"] = []


class CategoryFilterParams(BaseModel):
    """
    分类列表的动态查询过滤参数模型。

    这个模型用于 FastAPI 的依赖注入，它会自动解析 URL 查询参数。
    例如: GET /categories?name=美食&slug=food
    """
    name: Optional[str] = Field(None, description="按分类名称进行模糊搜索")
    slug: Optional[str] = Field(None, description="按 slug 精确搜索")
    parent_id: Optional[UUID] = Field(None, description="按父分类ID筛选顶级分类下的子分类")


class BatchDeleteCategoriesPayload(BaseModel): # <-- 【新增】
    category_ids: List[UUID]

class CategoryMergePayload(BaseModel): # <-- 【新增】
    source_category_ids: List[UUID]
    target_category_id: UUID
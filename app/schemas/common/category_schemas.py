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
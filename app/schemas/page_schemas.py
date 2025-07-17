from typing import Annotated, Optional, List, Generic
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator
from pydantic_core.core_schema import ValidationInfo

from app.core.types.common import ModelType, T
from app.enums.auth_method import AuthMethod
from app.schemas.role_schemas import RoleRead

# ==========================
# 💡 通用类型定义
# ==========================
class PageResponse(BaseModel, Generic[ModelType]):
    items: List[ModelType]
    total: int
    page: int
    total_pages: int
    per_page: int

    model_config = {
        "from_attributes": True
    }
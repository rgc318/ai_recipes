from typing import List, Generic

from pydantic import BaseModel

from app.core.types.common import T


# ==========================
# 💡 通用类型定义
# ==========================
class PageResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    total_pages: int
    per_page: int

    model_config = {
        "from_attributes": True
    }
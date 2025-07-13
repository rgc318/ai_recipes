# 专门用于接口上下文中注入当前用户的身份和权限信息
from typing import List
from uuid import UUID
from pydantic import BaseModel


class UserContext(BaseModel):
    id: UUID
    username: str
    roles: List[str]
    permissions: List[str]
    is_superuser: bool

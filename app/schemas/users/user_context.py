# 专门用于接口上下文中注入当前用户的身份和权限信息
from typing import List

from app.schemas.users.user_schemas import UserRead


class UserContext(UserRead):
    roles: List[str]
    permissions: List[str]


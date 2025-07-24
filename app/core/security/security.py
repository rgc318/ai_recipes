# app/core/security.py
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.api.dependencies.services import get_user_service
from app.core.exceptions import InvalidTokenException
from app.schemas.user_context import UserContext
from app.utils.jwt_utils import decode_token, validate_token_type
from app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_service: UserService = Depends(get_user_service),
) -> UserContext:
    payload = await decode_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise InvalidTokenException(message="Token payload is missing user identifier (sub)")
    validate_token_type(payload, expected="access")
    user_id: str = payload.get("sub")

    user = await user_service.get_user_with_roles(UUID(user_id))

    if not user or not user.is_active:
        raise InvalidTokenException(message="User not found or is inactive")

        # 1. 从 User ORM 对象中提取基础信息
        #    model_dump() 会将 user 对象的基础属性转为字典
    user_data = user.model_dump()

    # 2. 手动将 Role 对象列表 转换为 角色代码的字符串列表
    #    这正是为了匹配 UserContext 中 `roles: List[str]` 的定义
    user_data['roles'] = [role.code for role in user.roles]

    # 3. 直接使用 User 模型上已经计算好的权限集合
    #    user.permissions 返回的是一个 set，我们将其转为 list 以匹配 UserContext 定义
    user_data['permissions'] = list(user.permissions)

    # 4. 用准备好的、结构完全匹配的数据字典来创建 UserContext 实例
    #    这里的 **user_data 会将字典解包成关键字参数
    user_context = UserContext(**user_data)

    return user_context

async def get_current_active_user(
    # 这个依赖现在返回的是 UserContext，为了类型提示更准确，可以进行相应调整
    # 但为了保持简单，我们暂时让它接收 UserContext
    user_context: UserContext = Depends(get_current_user),
) -> UserContext:
    """
    一个简单的依赖，确保在 get_current_user 的基础上，用户是激活状态。
    （实际上 get_current_user 内部已经检查了 is_active，所以这个依赖主要是为了语义清晰）
    """
    # get_current_user 内部已经检查了 is_active，所以这里无需重复检查
    return user_context

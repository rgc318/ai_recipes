# app/core/security.py
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.services import get_user_service
from app.core.exceptions import InvalidTokenException
from app.schemas.user_context import UserContext
from app.utils.jwt_utils import decode_token, validate_token_type
from app.models.user import User
from app.services.user_service import UserService
from app.db.session import get_session

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
    return UserContext(
        id=user.id,
        username=user.username,
        is_superuser=user.is_superuser,
        roles=[role.name for role in user.roles],
        permissions=[perm.name for perm in user.permissions],
    )

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

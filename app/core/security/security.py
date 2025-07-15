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

    user = await user_service.get_by_id_with_roles_permissions(UUID(user_id))

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
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
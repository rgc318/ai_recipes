# app/api/dependencies/permissions_enum.py

from fastapi import Depends, HTTPException
from starlette import status

from app.core.security.security import get_current_user
from app.models.user import User
from app.schemas.users.user_context import UserContext


def require_login(current_user: UserContext = Depends(get_current_user)) -> UserContext:
    """
    一个基础的依赖，仅确保用户已登录。
    可用于所有需要用户登录但没有特定角色/权限要求的接口。
    """
    return current_user

def require_superuser(current_user: UserContext = Depends(get_current_user)) -> UserContext:
    """
    一个专门的依赖，用于确保当前用户是超级用户 (is_superuser=True)。
    这是保护最高级别管理接口（如角色、权限管理）的最佳实践。
    """
    if not current_user.is_superuser:
        # 如果不是超级用户，立即抛出 403 Forbidden 错误。
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="操作失败：需要超级管理员权限"
        )
    return current_user

def require_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="User not verified")
    return user


# --- 【未来扩展】基于角色的权限依赖 ---

def require_role(role_name: str):
    """
    一个依赖工厂，用于创建检查特定角色的依赖。
    示例: @router.get("/", dependencies=[Depends(require_role("manager"))])
    """
    async def dependency(current_user: UserContext = Depends(get_current_user)) -> UserContext:
        if not current_user.is_superuser and role_name not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"操作失败：需要 '{role_name}' 角色"
            )
        return current_user
    return dependency


# --- 【未来扩展】基于权限的权限依赖 ---

def require_permission(permission_name: str):
    """
    一个依赖工厂，用于创建检查特定权限的依赖。
    示例: @router.post("/", dependencies=[Depends(require_permission("order:create"))])
    """
    async def dependency(current_user: UserContext = Depends(get_current_user)) -> UserContext:
        # 超级用户总是拥有所有权限
        if not current_user.is_superuser and permission_name not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"操作失败：缺少 '{permission_name}' 权限"
            )
        return current_user
    return dependency
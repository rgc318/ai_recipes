from types import NoneType
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.security import get_current_user
from app.db.session import get_session
from app.schemas.user_context import UserContext
from app.services.user_service import UserService
from app.api.dependencies.services import get_user_service
from app.schemas.user_schemas import UserCreate, UserUpdate, UserRead, UserReadWithRoles, UserUpdateProfile
from app.schemas.page_schemas import PageResponse
from app.core.api_response import response_success, response_error, StandardResponse
from app.core.response_codes import ResponseCodeEnum

router = APIRouter()


@router.get(
    "/info",
    response_model=StandardResponse[UserRead],
    summary="获取当前用户信息",
    status_code=status.HTTP_200_OK,
)
async def get_user_info(
    current_user: UserRead = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    user = await service.get_user_by_id(current_user.id)
    if not user:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户不存在",
        )
    return response_success(data=UserRead.model_validate(user), message="获取用户信息成功")

# ==========================
# 🙋 用户自服务接口 (Self-Service)
# ==========================
@router.get(
    "/me",
    response_model=StandardResponse[UserContext],
    summary="获取当前登录用户的完整信息"
)
async def read_current_user(
    # 这个依赖已经完成了所有工作：验证token、从数据库获取用户、角色、权限
    current_user: UserContext = Depends(get_current_user)
):
    """
    获取当前登录用户的完整上下文信息，包括：
    - 基本个人资料
    - 是否为超级用户
    - 拥有的所有角色代码列表
    - 聚合后的所有权限代码列表

    前端通常在应用加载后立即调用此接口，以构建用户的“权限快照”。
    """
    # 直接返回依赖注入的结果即可，无需再调用 service
    return response_success(data=current_user)

@router.put("/me", response_model=StandardResponse[UserRead], summary="更新当前用户信息")
async def update_my_profile(
    updates: UserUpdateProfile, # 使用受限的更新模型
    service: UserService = Depends(get_user_service),
    current_user: UserContext = Depends(get_current_user)
):
    """更新当前登录用户自己的个人资料，如昵称、邮箱等。"""
    updated_user = await service.update_profile(current_user.id, updates)
    return response_success(data=updated_user, message="个人资料更新成功")



# ==========================
# 👮‍ 管理员接口 (Admin)
# ==========================
@router.get(
    "/",
    response_model=StandardResponse[PageResponse[UserReadWithRoles]],
    summary="获取用户列表（带分页和筛选）"
)
async def read_users(
    service: UserService = Depends(get_user_service),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量", alias="pageSize"),
    username: Optional[str] = Query(None, description="按用户名模糊搜索"),
    email: Optional[str] = Query(None, description="按邮箱模糊搜索"),
    phone: Optional[str] = Query(None, description="按电话模糊搜索"),
    is_active: Optional[bool] = Query(None, description="按用户是否激活状态筛选")
):
    """
    获取用户列表，支持分页和筛选。
    FastAPI会根据response_model自动将ORM对象转换为Pydantic模型。
    """
    # 直接从service层获取包含ORM对象的响应
    paged_orm_response = await service.page_list_users(
        page=page,
        per_page=page_size,
        username=username,
        email=email,
        phone=phone,
        is_active=is_active,
    )

    # 直接将它作为数据返回，FastAPI会处理剩下的一切
    return response_success(data=paged_orm_response, message="获取用户列表成功")

# === Create User ===
@router.post(
    "/",
    response_model=StandardResponse[UserRead],
    status_code=status.HTTP_200_OK
)
async def create_user(user_data: UserCreate, service: UserService = Depends(get_user_service)):
    try:
        user = await service.create_user(user_data)
        return response_success(
            data=user,
            code=ResponseCodeEnum.CREATED,
            message="用户创建成功"
        )
    except ValueError as e:
        return response_error(
            code=ResponseCodeEnum.USER_ALREADY_EXISTS,
            message=str(e)
        )


# === Get User By ID ===
@router.get(
    "/{user_id}",
    response_model=StandardResponse[UserReadWithRoles]
)
async def read_user(user_id: UUID, service: UserService = Depends(get_user_service)):
    user = await service.get_user_with_roles(user_id)
    if not user:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户不存在",
        )
    return response_success(data=UserRead.model_validate(user))


# === Update User ===
@router.put(
    "/{user_id}",
    response_model=StandardResponse[UserReadWithRoles]
)
async def update_user(
        user_id: UUID,
        user_data: UserUpdate,
        service: UserService = Depends(get_user_service)
):
    updated_user = await service.update_user(user_id, user_data)
    if not updated_user:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户更新失败，用户不存在",
        )
    return response_success(data=updated_user, message="用户更新成功")


# === Soft Delete User ===
@router.delete(
    "/{user_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK
)
async def delete_user(user_id: UUID, service: UserService = Depends(get_user_service)):
    deleted = await service.delete_user(user_id)
    if not deleted:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户删除失败，用户不存在",
        )
    return response_success(data=None, message="用户已删除")



from types import NoneType
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.security import get_current_user
from app.db.session import get_session
from app.schemas.user_context import UserContext
from app.services.user_service import UserService
from app.api.dependencies.services import get_user_service
from app.schemas.user_schemas import UserCreate, UserUpdate, UserRead, UserReadWithRoles, UserUpdateProfile, \
    UserFilterParams
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
    summary="动态分页、排序和过滤用户列表"
)
async def list_users_paginated(
        service: UserService = Depends(get_user_service),
        page: int = Query(1, ge=1, description="页码"),
        # 保持与后端 service/repo 一致的命名
        per_page: int = Query(10, ge=1, le=100, description="每页数量"),
        # 2. 排序参数现在是一个简单的字符串，由前端按约定格式提供
        sort: Optional[str] = Query(
            None,
            description="排序字段，逗号分隔，-号表示降序。例如: -created_at,username",
            examples=["-created_at,username"]
        ),
        # 3. 使用 Depends 将所有过滤参数自动注入到 filter_params 对象中
        filter_params: UserFilterParams = Depends()
):
    """
    获取用户的分页列表，支持动态过滤和排序。

    - **排序**: `?sort=-created_at,username`
    - **过滤**: `?username=admin&is_active=true&role_ids=uuid1&role_ids=uuid2`
    """
    # 4. 在 Router 层进行简单的数据格式转换
    # 将逗号分隔的字符串转为列表，如果存在的话
    sort_by = sort.split(',') if sort else None

    # 将 Pydantic 模型转为字典，只包含前端实际传入的参数
    # 这是最关键的一步，确保了只有用户请求的过滤器才会被传递
    filters = filter_params.model_dump(exclude_unset=True)

    # 5. 使用新的、简洁的接口调用 Service
    page_data = await service.page_list_users(
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        filters=filters
    )

    return response_success(data=page_data, message="获取用户列表成功")

# === Create User ===
@router.post(
    "/",
    response_model=StandardResponse[UserRead],
    status_code=status.HTTP_200_OK
)
async def create_user(user_data: UserCreate, service: UserService = Depends(get_user_service)):
    new_user = await service.create_user(user_data)
    return response_success(data=new_user, message="用户创建成功")


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



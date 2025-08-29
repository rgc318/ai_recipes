from types import NoneType
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query, UploadFile, File
from app.config.config_settings.config_loader import logger
from app.api.dependencies.permissions import require_superuser
from app.core.exceptions import UnauthorizedException, BaseBusinessException
from app.core.security.security import get_current_user
from app.schemas.file.file_schemas import PresignedUploadURL, PresignedAvatarRequest, AvatarLinkDTO, PresignedUploadPolicy, \
    PresignedPolicyRequest
from app.schemas.users.user_context import UserContext
from app.services.file.file_service import FileService
from app.services.users.user_service import UserService
from app.api.dependencies.service_getters.users_service_getter import get_user_service
from app.api.dependencies.service_getters.common_service_getter import get_file_service
from app.schemas.users.user_schemas import UserCreate, UserUpdate, UserRead, UserReadWithRoles, UserUpdateProfile, \
    UserFilterParams, UserPasswordUpdate, BatchDeletePayload
from app.schemas.common.page_schemas import PageResponse
from app.schemas.common.api_response import response_success, response_error, StandardResponse
from app.enums.response_codes import ResponseCodeEnum

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


@router.patch(  # 使用 PATCH 更合适，因为它只更新用户的一个字段
    "/me/avatar",
    response_model=StandardResponse[UserRead],  # 返回更新后的完整用户信息
    summary="更新当前用户的头像"
)
async def update_my_avatar(
        file: UploadFile = File(..., description="新的头像文件"),
        current_user: UserContext = Depends(get_current_user),
        user_service: UserService = Depends(get_user_service),
):
    """
    一站式更新当前登录用户的头像。
    后端将处理文件上传、旧头像清理、数据库更新等所有逻辑。
    """
    # 直接调用 Service 层的一个新方法来完成所有工作
    updated_user = await user_service.update_avatar(
        user_id=current_user.id,
        upload_file=file
    )

    return response_success(data=UserRead.model_validate(updated_user), message="头像更新成功")

@router.post(
    "/me/avatar/generate-upload-url",
    response_model=StandardResponse[PresignedUploadURL], # 复用您已有的Schema
    summary="为上传新头像生成预签名URL"
)
async def generate_avatar_upload_url(
    payload: PresignedAvatarRequest,
    current_user: UserContext = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service) # 假设依赖注入函数已存在
):
    """
    第一步：客户端调用此接口获取一个用于直接上传文件的预签名URL。
    """
    # 调用您已有的FileService方法来生成URL
    # 我们将user_id作为路径参数，以保持存储结构的整洁
    presigned_data = await file_service.generate_presigned_put_url(
        profile_name="user_avatars",
        original_filename=payload.original_filename,
        user_id=str(current_user.id) # 路径参数
    )
    return response_success(data=presigned_data)


@router.post(
    "/me/avatar/generate-upload-policy",
    response_model=StandardResponse[PresignedUploadPolicy],
    summary="【安全模式】为上传新头像生成预签名POST策略 (推荐)"
)
async def generate_avatar_upload_policy(
    payload: PresignedPolicyRequest, # 【修改】使用新的请求体模型
    current_user: UserContext = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
):
    """
    第一步（安全模式）：客户端调用此接口获取一个带安全策略的、用于POST上传的凭证。
    """
    policy_data = await file_service.generate_presigned_upload_policy(
        profile_name="user_avatars",
        original_filename=payload.original_filename,
        content_type=payload.content_type, # 【修改】传入 content_type
        user_id=str(current_user.id)
    )
    return response_success(data=policy_data)

# 【新增】预签名流程的闭环接口
@router.patch(
    "/me/avatar/link-uploaded-file",
    response_model=StandardResponse[UserRead],
    summary="关联已通过预签名URL上传的头像"
)
async def link_uploaded_avatar(
    payload: AvatarLinkDTO,
    current_user: UserContext = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """第三步：客户端在文件成功上传到对象存储后，调用此接口完成最终的关联。"""
    updated_user = await user_service.link_new_avatar(
        user_id=current_user.id,
        avatar_dto=payload
    )
    return response_success(data=UserRead.model_validate(updated_user), message="头像更新成功")
@router.patch("/me", response_model=StandardResponse[UserRead], summary="更新当前用户信息")
async def update_my_profile(
    updates: UserUpdateProfile, # 使用受限的更新模型
    service: UserService = Depends(get_user_service),
    current_user: UserContext = Depends(get_current_user)
):
    """更新当前登录用户自己的个人资料，如昵称、邮箱等。"""
    updated_user = await service.update_profile(current_user.id, updates)
    return response_success(data=UserRead.model_validate(updated_user), message="个人资料更新成功")

@router.patch(
    "/me/password",
    response_model=StandardResponse[NoneType],
    summary="当前用户修改自己的密码"
)
async def change_current_user_password(
    payload: UserPasswordUpdate,
    current_user: UserContext = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    """
    验证当前用户的旧密码，并更新为新密码。
    """
    try:
        await service.change_password_with_verification(
            user_id=current_user.id,
            old_plain_password=payload.old_password,
            new_plain_password=payload.new_password
        )
        return response_success(data=None, message="密码更新成功")
    except UnauthorizedException as e:
        logger.warning(f"密码更新失败：{e}")
        return response_error(code=ResponseCodeEnum.AUTH_ERROR, message=e.message)
    except Exception as e:
        logger.error(f"密码更新失败: {e}")
        return response_error(code=ResponseCodeEnum.SERVER_ERROR, message=str(e))



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
        filter_params: UserFilterParams = Depends(),

        role_ids: Optional[List[UUID]] = Query(None, description="根据关联的角色ID列表过滤")

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
    # 1. 定义一个列表，包含所有希望自动应用模糊搜索的字段名
    fuzzy_search_fields = ['username', 'email', 'phone', 'full_name']
    # 2. 遍历这个列表，检查 filters 字典中是否存在这些键
    for field in fuzzy_search_fields:
        if field in filters:
            # 3. 如果存在，就从原字典中弹出(pop)这个键值对
            value = filters.pop(field)
            # 4. 同时，以 "字段名__ilike" 的新键名，将它重新放回字典
            filters[f'{field}__ilike'] = value

    if role_ids:
        filters['role_ids__in'] = role_ids
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
    try:
        updated_user = await service.update_user(user_id, user_data)
        if not updated_user:
            return response_error(
                code=ResponseCodeEnum.USER_NOT_FOUND,
                message="用户更新失败，用户不存在",
            )
        return response_success(data=UserReadWithRoles.model_validate(updated_user), message="用户更新成功")
    except BaseBusinessException as e:
        logger.error(f"用户更新失败: {e}")
        return response_error(
            code=ResponseCodeEnum.SERVER_ERROR,
            message=e.message,
        )
    except Exception as e:
        logger.error(f"用户更新失败: {e}")
        return response_error(
            code=ResponseCodeEnum.SERVER_ERROR,
            message=str(e),
        )


@router.delete(
    "/batch",
    summary="批量软删除用户",
    response_model=StandardResponse[dict],
    dependencies=[Depends(require_superuser)] # 权限：只有超级管理员才能执行此操作
)
async def batch_delete_users(
    payload: BatchDeletePayload,
    service: UserService = Depends(get_user_service),
    current_user: UserContext = Depends(get_current_user),
):
    """
    接收一个包含用户ID列表的数组，并批量软删除这些用户。
    会进行安全校验，防止用户删除自己或非超管删除超管。
    """
    try:
        deleted_count = await service.batch_delete_users(
            user_ids=payload.user_ids,
            current_user=current_user
        )
        return response_success(
            data={"deleted_count": deleted_count},
            message=f"成功删除 {deleted_count} 个用户"
        )
    except UnauthorizedException as e:
        logger.warning(f"批量删除权限不足：{e} by {current_user.username}")
        return response_error(code=ResponseCodeEnum.AUTH_ERROR, message=str(e))
    except Exception as e:
        logger.error(f"批量删除用户失败: {e}")
        return response_error(code=ResponseCodeEnum.SERVER_ERROR, message="批量删除操作失败")

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



# 【新增】在管理员接口部分添加
@router.patch(
    "/{user_id}/avatar",
    response_model=StandardResponse[UserRead],
    summary="管理员更新指定用户的头像",
    dependencies=[Depends(require_superuser)] # <--- 同样需要权限校验
)
async def admin_update_user_avatar(
    user_id: UUID, # 从路径中获取要修改的用户ID
    file: UploadFile = File(..., description="新的头像文件"),
    user_service: UserService = Depends(get_user_service),
):
    """
    管理员上传文件，为指定ID的用户更新头像。
    """
    # 直接复用现有的Service层方法，只是user_id的来源不同
    updated_user = await user_service.update_avatar(
        user_id=user_id,
        upload_file=file
    )
    return response_success(data=UserRead.model_validate(updated_user), message="用户头像更新成功")

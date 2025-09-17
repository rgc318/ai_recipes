from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.service_getters.common_service_getter import get_role_service
from app.api.dependencies.permissions import require_superuser
from app.core.logger import logger
from app.core.exceptions import NotFoundException, AlreadyExistsException, ConcurrencyConflictException, \
    BaseBusinessException
from app.enums.query_enums import ViewMode
from app.enums.response_codes import ResponseCodeEnum
from app.services.users.role_service import RoleService
from app.schemas.users.role_schemas import (
    RoleCreate,
    RoleUpdate,
    RoleRead,
    RoleReadWithPermissions,
    RolePermissionsUpdate, RoleSelectorRead, RoleFilterParams, BatchRoleActionPayload,
    RoleMergePayload  # 新增：用于批量更新权限的请求模型
)
from app.schemas.common.api_response import response_success, StandardResponse, response_error
from app.schemas.common.page_schemas import PageResponse

# 同样，使用全局依赖保护所有接口
router = APIRouter(dependencies=[Depends(require_superuser)])


@router.delete(
    "/",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量软删除角色"
)
async def soft_delete_roles_batch(
    payload: BatchRoleActionPayload,
    service: RoleService = Depends(get_role_service),
):
    """将一个或多个角色移入回收站。"""
    deleted_count = await service.soft_delete_roles(payload.role_ids)
    return response_success(data={"deleted_count": deleted_count}, message=f"成功将 {deleted_count} 个角色移入回收站")


@router.post(
    "/restore",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量恢复角色",
)
async def restore_roles_batch(
    payload: BatchRoleActionPayload,
    service: RoleService = Depends(get_role_service),
):
    """从回收站中恢复一个或多个角色。"""
    restored_count = await service.restore_roles(payload.role_ids)
    return response_success(data={"restored_count": restored_count}, message=f"成功恢复 {restored_count} 个角色")


@router.delete(
    "/permanent",
    response_model=StandardResponse[dict],
    summary="[管理员] 批量永久删除角色 (高危操作)",
)
async def permanent_delete_roles_batch(
    payload: BatchRoleActionPayload,
    service: RoleService = Depends(get_role_service),
):
    """永久删除一个或多个角色。只能删除回收站中且未被任何用户使用的角色。"""
    try:
        deleted_count = await service.permanent_delete_roles(payload.role_ids)
        return response_success(data={"deleted_count": deleted_count}, message=f"成功永久删除 {deleted_count} 个角色")
    except BaseBusinessException as e:
        return response_error(code=e.code, message=e.message)
    except Exception as e:
        logger.error(f"永久删除角色时发生未知错误: {e}")
        return response_error(code=ResponseCodeEnum.SERVER_ERROR, message="服务器内部错误")


@router.post(
    "/merge",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="[管理员] 合并多个角色"
)
async def merge_roles(
    payload: RoleMergePayload,
    service: RoleService = Depends(get_role_service),
):
    """将多个源角色的权限和用户合并到一个目标角色，然后软删除源角色。"""
    try:
        updated_destination_role = await service.merge_roles(
            source_role_ids=payload.source_role_ids,
            destination_role_id=payload.destination_role_id
        )
        return response_success(data=updated_destination_role, message="角色合并成功")
    except (BaseBusinessException, NotFoundException) as e:
        return response_error(code=e.code, message=e.message)
    except Exception as e:
        logger.error(f"合并角色时发生未知错误: {e}")
        return response_error(code=ResponseCodeEnum.SERVER_ERROR, message="服务器内部错误")



@router.get(
    "/selector", # 接口路径清晰地表明了它的用途
    response_model=StandardResponse[List[RoleSelectorRead]],
    summary="获取用于下拉选择框的角色列表"
)
async def get_roles_for_selector(
    service: RoleService = Depends(get_role_service)
):
    """
    获取一个轻量级的角色列表，专门用于前端的下拉选择框。
    - **此接口会返回所有角色，但有内置数量上限以保证性能。**
    - 只包含 id 和 name 字段，以减小响应体积。
    """
    roles = await service.get_all_roles() # 我们将在 Service 中重新实现这个方法
    return response_success(data=[RoleSelectorRead.model_validate(r) for r in roles])


@router.get(
    "/",
    # 优化：通常列表返回的角色信息也应包含权限，便于前端展示
    response_model=StandardResponse[PageResponse[RoleReadWithPermissions]],
    summary="分页、排序和过滤角色列表"
)
async def list_roles_paginated(
    service: RoleService = Depends(get_role_service),
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    # 统一排序参数
    sort: Optional[str] = Query("-created_at", description="排序字段，逗号分隔，-号表示降序"),
    # 使用 Depends 注入过滤器参数
    filter_params: RoleFilterParams = Depends(),
    view_mode: ViewMode = Query(ViewMode.ACTIVE, description="查看模式: active, all, deleted"),
):
    """
    获取角色的分页列表，支持动态过滤和排序。
    - **需要超级管理员权限。**
    - **search**: 按角色名称或代码进行模糊搜索。
    """
    sort_by_list = sort.split(',') if sort else None
    filters = filter_params.model_dump(exclude_unset=True)

    page_data = await service.page_list_roles(
        page=page,
        per_page=per_page,
        sort_by=sort_by_list,
        filters=filters,
        view_mode=view_mode
    )
    return response_success(data=page_data)


@router.post(
    "/",
    response_model=StandardResponse[RoleRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建新角色"
)
async def create_role(
    role_in: RoleCreate,
    service: RoleService = Depends(get_role_service)
):
    """
    创建一个新的角色。
    - **需要超级管理员权限。**
    - 角色的 `code` 必须唯一。
    """
    try:
        new_role = await service.create_role(role_in)
        return response_success(data=RoleRead.model_validate(new_role), message="角色创建成功")
    except (AlreadyExistsException, NotFoundException) as e:
        return response_error(code=e.code, message=e.message)


@router.get(
    "/{role_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="获取角色详情（含权限）"
)
async def get_role_details(
    role_id: UUID,
    service: RoleService = Depends(get_role_service),
    view_mode: ViewMode = Query(ViewMode.ACTIVE, description="查看模式: active, all, deleted"),
):
    """
    获取单个角色的详细信息，包括其拥有的所有权限。
    - **需要超级管理员权限。**
    """
    # 修复：调用正确的方法
    role = await service.get_role_with_permissions(role_id, view_mode=view_mode)
    return response_success(data=RoleReadWithPermissions.model_validate(role))


@router.put(
    "/{role_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="更新角色信息（含权限）"
)
async def update_role(
    role_id: UUID,
    role_in: RoleUpdate,
    service: RoleService = Depends(get_role_service)
):
    """
    更新一个角色的信息。
    ...
    """
    try:
        updated_role = await service.update_role(role_id, role_in)
        return response_success(
            data=RoleReadWithPermissions.model_validate(updated_role),
            message="角色更新成功"
        )
    # 捕获具体的业务异常，返回更友好的错误信息
    except (NotFoundException, AlreadyExistsException, ConcurrencyConflictException) as e:
        # 使用 e.message 可以将服务层定义的具体错误原因（如“角色代码已存在”）返回给前端
        return response_error(code=e.code, message=e.message)
    except Exception as e:
        # 捕获所有其他未知异常，防止敏感信息泄露
        # 这里的日志记录很重要
        # logger.error(f"更新角色 {role_id} 时发生未知错误: {e}")
        return response_error(code=ResponseCodeEnum.SERVER_ERROR, message="服务器内部错误")



# @router.delete(
#     "/{role_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="软删除角色"
# )
# async def delete_role(
#     role_id: UUID,
#     service: RoleService = Depends(get_role_service)
# ):
#     """
#     软删除一个角色。
#     - **需要超级管理员权限。**
#     """
#     try:
#         await service.soft_delete_role(role_id)
#         return response_success(message="角色删除")
#     except Exception as e:
#         return response_error(code=ResponseCodeEnum.SERVER_ERROR, message=str(e))

# @router.put(
#     "/{role_id}",
#     response_model=StandardResponse[RoleReadWithPermissions],
#     summary="[管理员] 更新角色信息（含权限）"
# )
# async def update_role(
#     role_id: UUID,
#     role_in: RoleUpdate,
#     service: RoleService = Depends(get_role_service)
# ):
#     """原子化地更新一个角色的信息和其完整的权限列表。"""
#     try:
#         updated_role = await service.update_role(role_id, role_in)
#         return response_success(data=updated_role, message="角色更新成功")
#     except (NotFoundException, AlreadyExistsException, ConcurrencyConflictException) as e:
#         return response_error(code=e.code, message=e.message)
#     except Exception as e:
#         logger.error(f"更新角色 {role_id} 时发生未知错误: {e}")
#         return response_error(code=ResponseCodeEnum.SERVER_ERROR, message="服务器内部错误")
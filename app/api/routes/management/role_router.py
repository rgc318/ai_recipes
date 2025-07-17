from uuid import UUID
from typing import List, Optional

from fastapi import APIRouter, Depends, status, Query, Body

from app.api.dependencies.services import get_role_service
from app.api.dependencies.permissions import require_superuser
from app.services.role_service import RoleService
from app.schemas.role_schemas import (
    RoleCreate,
    RoleUpdate,
    RoleRead,
    RoleReadWithPermissions,
    RolePermissionsUpdate, RoleSelectorRead  # 新增：用于批量更新权限的请求模型
)
from app.core.api_response import response_success, StandardResponse
from app.schemas.page_schemas import PageResponse

# 同样，使用全局依赖保护所有接口
router = APIRouter(dependencies=[Depends(require_superuser)])


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
    "/",  # 优化：路径使用根路径 '/' 更符合 RESTful 风格
    response_model=StandardResponse[PageResponse[RoleRead]],
    summary="分页、排序和过滤角色列表"
)
async def list_roles_paginated(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    order_by: str = Query("created_at:desc", description="排序字段"),
    name: Optional[str] = Query(None, description="按角色名模糊搜索"),
    code: Optional[str] = Query(None, description="按角色代码精确过滤"),
    service: RoleService = Depends(get_role_service)
):
    """
    获取角色的分页列表，并支持按名称搜索和按代码过滤。
    - **需要超级管理员权限。**
    """
    page_data = await service.page_list_roles(
        page=page,
        per_page=per_page,
        order_by=order_by,
        name=name,
        code=code
    )
    # 修复：直接返回服务层构建好的 PageResponse 对象
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
    new_role = await service.create_role(role_in)
    return response_success(data=RoleRead.model_validate(new_role), message="角色创建成功")


@router.get(
    "/{role_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="获取角色详情（含权限）"
)
async def get_role_details(
    role_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    获取单个角色的详细信息，包括其拥有的所有权限。
    - **需要超级管理员权限。**
    """
    # 修复：调用正确的方法
    role = await service.get_role_with_permissions(role_id)
    return response_success(data=RoleReadWithPermissions.model_validate(role))


@router.put(
    "/{role_id}",
    response_model=StandardResponse[RoleReadWithPermissions], # 优化：更新后返回带权限的角色信息
    summary="更新角色信息（含权限）"
)
async def update_role(
    role_id: UUID,
    role_in: RoleUpdate,
    service: RoleService = Depends(get_role_service)
):
    """
    更新一个角色的信息。
    这个接口功能强大，可以同时更新角色的基本信息（名称、代码）和其关联的所有权限。
    - **需要超级管理员权限。**
    - 如果提供了 `permission_ids` 列表，它将覆盖该角色现有的所有权限。
    """
    updated_role = await service.update_role(role_id, role_in)
    return response_success(
        data=RoleReadWithPermissions.model_validate(updated_role),
        message="角色更新成功"
    )


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="软删除角色"
)
async def delete_role(
    role_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    软删除一个角色。
    - **需要超级管理员权限。**
    """
    await service.delete_role(role_id)


# --- 角色与权限的关联管理 ---

@router.put(
    "/{role_id}/permissions", # 新增：批量设置权限接口
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="批量设置角色的所有权限"
)
async def set_role_permissions(
    role_id: UUID,
    permissions_in: RolePermissionsUpdate, # 使用专用模型
    service: RoleService = Depends(get_role_service)
):
    """
    一次性设置一个角色的所有权限。
    这个操作会**覆盖**该角色当前的所有权限设置。
    - **需要超级管理员权限。**
    """
    updated_role = await service.set_role_permissions(role_id, permissions_in.permission_ids)
    return response_success(
        data=RoleReadWithPermissions.model_validate(updated_role),
        message="角色权限设置成功"
    )


@router.post(
    "/{role_id}/permissions/{permission_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    status_code=status.HTTP_200_OK, # 优化：添加关联通常返回 200 OK 更常见
    summary="为角色分配单个权限"
)
async def assign_permission_to_role(
    role_id: UUID,
    permission_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    为一个角色增量添加一个指定的权限。
    - **需要超级管理员权限。**
    """
    updated_role = await service.assign_permission_to_role(role_id, permission_id)
    return response_success(
        data=RoleReadWithPermissions.model_validate(updated_role),
        message="权限分配成功"
    )


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="从角色中撤销单个权限"
)
async def revoke_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    从一个角色中移除一个指定的权限。
    - **需要超级管理员权限。**
    """
    updated_role = await service.revoke_permission_from_role(role_id, permission_id)
    return response_success(
        data=RoleReadWithPermissions.model_validate(updated_role),
        message="权限撤销成功"
    )
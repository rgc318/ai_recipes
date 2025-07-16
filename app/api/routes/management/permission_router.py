from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.dependencies.services import get_permission_service
from app.api.dependencies.permissions import require_superuser # 假设的权限依赖
from app.services.permission_service import PermissionService
from app.schemas.permission_schemas import PermissionCreate, PermissionUpdate, PermissionRead
from app.core.api_response import response_success, StandardResponse

# 创建一个专门用于权限管理的路由器
# 和 role_router 一样，我们在这里使用全局依赖来保护所有接口
router = APIRouter(dependencies=[Depends(require_superuser)])


@router.post(
    "/",
    response_model=StandardResponse[PermissionRead],
    status_code=status.HTTP_201_CREATED,
    summary="创建新权限"
)
async def create_permission(
    permission_in: PermissionCreate,
    service: PermissionService = Depends(get_permission_service)
):
    """
    创建一个新的权限点 (例如: "user:create", "recipe:delete")。
    - 需要管理员权限。
    - 权限名称必须唯一。
    """
    new_permission = await service.create_permission(permission_in)
    return response_success(data=PermissionRead.model_validate(new_permission), message="权限创建成功")


@router.get(
    "/",
    response_model=StandardResponse[List[PermissionRead]],
    summary="获取权限列表"
)
async def list_permissions(
    service: PermissionService = Depends(get_permission_service)
):
    """
    获取所有可用权限的列表。
    - 需要管理员权限。
    - 通常权限数量不多，因此直接返回完整列表，暂不分页。
    """
    permissions = await service.list_permissions(skip=0, limit=1000) # 设置一个高限额以获取全部
    return response_success(data=[PermissionRead.model_validate(p) for p in permissions])


@router.get(
    "/{permission_id}",
    response_model=StandardResponse[PermissionRead],
    summary="获取权限详情"
)
async def get_permission_details(
    permission_id: UUID,
    service: PermissionService = Depends(get_permission_service)
):
    """
    获取单个权限的详细信息。
    - 需要管理员权限。
    """
    permission = await service.get_permission_by_id(permission_id)
    return response_success(data=PermissionRead.model_validate(permission))


@router.put(
    "/{permission_id}",
    response_model=StandardResponse[PermissionRead],
    summary="更新权限信息"
)
async def update_permission(
    permission_id: UUID,
    permission_in: PermissionUpdate,
    service: PermissionService = Depends(get_permission_service)
):
    """
    更新一个权限的名称或描述。
    - 需要管理员权限。
    """
    updated_permission = await service.update_permission(permission_id, permission_in)
    return response_success(data=PermissionRead.model_validate(updated_permission), message="权限更新成功")


@router.delete(
    "/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除权限"
)
async def delete_permission(
    permission_id: UUID,
    service: PermissionService = Depends(get_permission_service)
):
    """
    删除一个权限。
    - 需要管理员权限。
    """
    await service.delete_permission(permission_id)
    # 对于 DELETE 成功操作，返回 204 No Content，表示成功但无内容返回

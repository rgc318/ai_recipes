from uuid import UUID
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, status, Query

from app.api.dependencies.services import get_permission_service
from app.api.dependencies.permissions import require_superuser  # 假设的权限依赖
from app.services.permission_service import PermissionService
from app.schemas.permission_schemas import (
    PermissionCreate,
    PermissionUpdate,
    PermissionRead,
    PermissionSyncResponse  # 新增：用于同步结果的响应模型
)
from app.schemas.page_schemas import PageResponse  # 新增：引入分页响应模型
from app.core.api_response import response_success, StandardResponse

# 创建一个专门用于权限管理的路由器
# 使用全局依赖来保护所有接口，这是非常好的实践
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
    创建一个新的权限点。

    - **需要超级管理员权限。**
    - 权限的 `code` 字段必须全局唯一。
    """
    new_permission = await service.create_permission(permission_in)
    return response_success(
        data=PermissionRead.model_validate(new_permission),
        message="权限创建成功"
    )


@router.get(
    "/",
    response_model=StandardResponse[PageResponse[PermissionRead]], # 优化：使用分页响应模型
    summary="分页、排序和过滤权限列表"
)
async def list_permissions_paginated(
    page: int = Query(1, ge=1, description="页码"),
    per_page: int = Query(10, ge=1, le=100, description="每页数量"),
    order_by: str = Query("group:asc,name:asc", description="排序字段，格式: 'field:direction'"),
    group: Optional[str] = Query(None, description="按权限组精确过滤"),
    search: Optional[str] = Query(None, description="在code, name, description中进行模糊搜索"),
    service: PermissionService = Depends(get_permission_service)
):
    """
    获取权限的分页列表，并支持多种查询参数。

    - **需要超级管理员权限。**
    """
    page_data = await service.page_list_permissions(
        page=page,
        per_page=per_page,
        order_by=order_by,
        group=group,
        search=search
    )
    # 对于分页数据，直接将其作为 data 字段返回
    return response_success(data=page_data)


@router.post(
    "/sync",
    response_model=StandardResponse[PermissionSyncResponse], # 新增：使用专用的响应模型
    summary="同步权限列表 (高阶管理功能)"
)
async def sync_permissions(
    permissions_data: List[Dict[str, Any]], # 直接接收字典列表，更灵活
    service: PermissionService = Depends(get_permission_service)
):
    """
    从一个给定的列表（例如，来自配置文件）同步权限。

    这个接口会批量检查权限是否存在，如果不存在则创建它们。
    这是在系统初始化或版本更新时，确保所有必需权限都存在的关键接口。

    - **需要超级管理员权限。**
    - 请求体是一个JSON数组，每个对象必须包含 "code" 字段。
      `[{"code": "orders:read", "name": "查看订单", "group": "订单管理"}, ...]`
    """
    sync_result = await service.sync_permissions(permissions_data)
    return response_success(data=sync_result, message="权限同步完成")


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
    根据 UUID 获取单个权限的详细信息。

    - **需要超级管理员权限。**
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
    更新一个现有权限的信息。

    - **需要超级管理员权限。**
    - 如果尝试修改`code`，新`code`不能与其他权限冲突。
    """
    updated_permission = await service.update_permission(permission_id, permission_in)
    return response_success(
        data=PermissionRead.model_validate(updated_permission),
        message="权限更新成功"
    )


@router.delete(
    "/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="软删除权限"
)
async def delete_permission(
    permission_id: UUID,
    service: PermissionService = Depends(get_permission_service)
):
    """
    软删除一个权限。

    - **需要超级管理员权限。**
    - 数据不会被物理移除，而是被标记为已删除。
    """
    await service.delete_permission(permission_id)
    # 对于 DELETE 成功操作，规范是返回 204 No Content，表示成功但无内容返回
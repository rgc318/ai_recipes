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
    PermissionSyncResponse, PermissionFilterParams  # 新增：用于同步结果的响应模型
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
    response_model=StandardResponse[PageResponse[PermissionRead]],
    summary="分页、排序和过滤权限列表"
)
async def list_permissions_paginated(
        service: PermissionService = Depends(get_permission_service),
        page: int = Query(1, ge=1, description="页码"),
        per_page: int = Query(10, ge=1, le=100, description="每页数量"),
        # 2. 将排序参数统一为 sort，与 user_router 保持一致
        sort: Optional[str] = Query(
            "group,name",  # 默认排序
            description="排序字段，逗号分隔，-号表示降序。例如: -group,name"
        ),
        # 3. 使用 Depends 将所有过滤参数自动注入到 filter_params 对象中
        filter_params: PermissionFilterParams = Depends(),
):
    """
    获取权限的分页列表，支持动态过滤和排序。
    """
    # 4. 在 Router 层进行数据格式转换
    sort_by_list = sort.split(',') if sort else None

    # 5. 将 Pydantic 模型转为字典，只包含前端实际传入的参数
    filters = filter_params.model_dump(exclude_unset=True)

    # 6. 调用新的、简洁的 Service 接口
    page_data = await service.page_list_permissions(
        page=page,
        per_page=per_page,
        sort_by=sort_by_list,
        filters=filters
    )
    return response_success(data=page_data)


# @router.post(
#     "/sync",
#     response_model=StandardResponse[PermissionSyncResponse], # 新增：使用专用的响应模型
#     summary="同步权限列表 (高阶管理功能)"
# )
# async def sync_permissions(
#     permissions_data: List[Dict[str, Any]], # 直接接收字典列表，更灵活
#     service: PermissionService = Depends(get_permission_service)
# ):
#     """
#     从一个给定的列表（例如，来自配置文件）同步权限。
#
#     这个接口会批量检查权限是否存在，如果不存在则创建它们。
#     这是在系统初始化或版本更新时，确保所有必需权限都存在的关键接口。
#
#     - **需要超级管理员权限。**
#     - 请求体是一个JSON数组，每个对象必须包含 "code" 字段。
#       `[{"code": "orders:read", "name": "查看订单", "group": "订单管理"}, ...]`
#     """
#     sync_result = await service.sync_permissions(permissions_data)
#     return response_success(data=sync_result, message="权限同步完成")


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


@router.post(
    "/sync-from-source", # 新路径，更明确
    response_model=StandardResponse[PermissionSyncResponse],
    summary="【后端中心模式】从服务器配置文件同步权限"
)
async def sync_permissions_from_source(
    service: PermissionService = Depends(get_permission_service)
):
    """
    触发一次从后端配置文件 (permissions_enum.py) 到数据库的权限同步。
    这是推荐的、更安全的自动化同步方式。
    - **需要超级管理员权限。**
    """
    sync_result = await service.sync_permissions_from_source()
    return response_success(data=sync_result, message="权限已从后端源文件同步完成")


@router.post(
    "/sync-from-payload", # 修改路径，使其职责更清晰
    response_model=StandardResponse[PermissionSyncResponse],
    summary="【前端驱动模式】根据请求体内容同步权限"
)
async def sync_permissions_from_payload(
    permissions_data: List[Dict[str, Any]],
    service: PermissionService = Depends(get_permission_service)
):
    """
    从请求体 (payload) 中接收一个权限列表，并与数据库同步。
    这个接口提供了极大的灵活性，允许任何客户端提供权限定义源。
    - **需要超级管理员权限。**
    """
    sync_result = await service.sync_permissions(permissions_data)
    return response_success(data=sync_result, message="权限已从请求体同步完成")
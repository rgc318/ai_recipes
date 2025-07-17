from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, status

from app.api.dependencies.services import get_role_service
from app.api.dependencies.permissions import require_superuser # 假设的权限依赖
from app.services.role_service import RoleService
from app.schemas.role_schemas import RoleCreate, RoleUpdate, RoleRead, RoleReadWithPermissions
from app.schemas.user_schemas import UserRead # 如果需要返回用户信息
from app.core.api_response import response_success, StandardResponse
from app.schemas.page_schemas import PageResponse

# 创建一个专门用于角色管理的路由器
# 我们在这里使用 dependencies=[Depends(require_admin)]
# 来确保这个路由器下的所有接口都自动受到管理员权限的保护。
router = APIRouter(dependencies=[Depends(require_superuser)])


@router.get(
    "/all",
    response_model=StandardResponse[PageResponse[RoleRead]], # 假设你需要分页列表
    summary="获取角色列表"
)
async def list_roles(
    page: int = 1,
    per_page: int = 10,
    service: RoleService = Depends(get_role_service)
):
    """
    获取所有角色的分页列表。
    - 需要管理员权限。
    """


    roles = await service.list_roles(skip=(page - 1) * per_page, limit=per_page)
    # 一个更完整的实现会返回一个包含 total, page, per_page 的 PageResponse 对象
    # 这里为了演示，我们直接返回列表
    return response_success(data=[RoleRead.model_validate(role) for role in roles])

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
    - 需要管理员权限。
    - 角色名称必须唯一。
    """
    new_role = await service.create_role(role_in)
    return response_success(data=RoleRead.model_validate(new_role), message="角色创建成功")





@router.get(
    "/{role_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="获取角色详情"
)
async def get_role_details(
    role_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    获取单个角色的详细信息，包括其拥有的所有权限。
    - 需要管理员权限。
    """
    role = await service.get_role_by_id(role_id, with_permissions=True)
    return response_success(data=RoleReadWithPermissions.model_validate(role))


@router.put(
    "/{role_id}",
    response_model=StandardResponse[RoleRead],
    summary="更新角色信息"
)
async def update_role(
    role_id: UUID,
    role_in: RoleUpdate,
    service: RoleService = Depends(get_role_service)
):
    """
    更新一个角色的名称或描述。
    - 需要管理员权限。
    """
    updated_role = await service.update_role(role_id, role_in)
    return response_success(data=RoleRead.model_validate(updated_role), message="角色更新成功")


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除角色"
)
async def delete_role(
    role_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    删除一个角色。
    - 需要管理员权限。
    """
    await service.delete_role(role_id)
    # 对于 DELETE 成功操作，通常返回 204 No Content，不需要响应体


# --- 角色与权限的关联管理 ---

@router.post(
    "/{role_id}/permissions/{permission_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    status_code=status.HTTP_201_CREATED,
    summary="为角色分配权限"
)
async def assign_permission_to_role(
    role_id: UUID,
    permission_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """
    为一个角色添加一个指定的权限。
    - 需要管理员权限。
    """
    updated_role = await service.assign_permission_to_role(role_id, permission_id)
    return response_success(
        data=RoleReadWithPermissions.model_validate(updated_role),
        message="权限分配成功"
    )


@router.delete(
    "/{role_id}/permissions/{permission_id}",
    response_model=StandardResponse[RoleReadWithPermissions],
    summary="从角色中撤销权限"
)
async def revoke_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    service: RoleService = Depends(get_role_service)
):
    """

    从一个角色中移除一个指定的权限。
    - 需要管理员权限。
    """
    updated_role = await service.revoke_permission_from_role(role_id, permission_id)
    return response_success(
        data=RoleReadWithPermissions.model_validate(updated_role),
        message="权限撤销成功"
    )


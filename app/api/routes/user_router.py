from types import NoneType
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.user_service import UserService
from app.schemas.user_schemas import UserCreate, UserUpdate, UserRead
from app.core.api_response import response_success, response_error, StandardResponse
from app.core.response_codes import ResponseCodeEnum

router = APIRouter()

# === Create User ===
@router.post(
    "/",
    response_model=StandardResponse[UserRead],
    status_code=status.HTTP_201_CREATED
)
async def create_user(user_data: UserCreate, service: UserService = Depends()):
    try:
        user = await service.create_user(user_data)
        return response_success(
            data=user,
            code=ResponseCodeEnum.CREATED,
            message="用户创建成功",
            http_status=status.HTTP_201_CREATED
        )
    except ValueError as e:
        return response_error(
            code=ResponseCodeEnum.USER_ALREADY_EXISTS,
            message=str(e),
            http_status=status.HTTP_400_BAD_REQUEST
        )


# === Get User By ID ===
@router.get(
    "/{user_id}",
    response_model=StandardResponse[UserRead]
)
async def read_user(user_id: UUID, service: UserService = Depends()):
    user = await service.get_by_id(user_id)
    if not user:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户不存在",
            http_status=status.HTTP_404_NOT_FOUND
        )
    return response_success(data=user)


# === Update User ===
@router.put(
    "/{user_id}",
    response_model=StandardResponse[UserRead]
)
async def update_user(user_id: UUID, user_data: UserUpdate, service: UserService = Depends()):
    updated_user = await service.update_user(user_id, user_data)
    if not updated_user:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户更新失败，用户不存在",
            http_status=status.HTTP_404_NOT_FOUND
        )
    return response_success(data=updated_user, message="用户更新成功")


# === Soft Delete User ===
@router.delete(
    "/{user_id}",
    response_model=StandardResponse[NoneType],
    status_code=status.HTTP_200_OK
)
async def delete_user(user_id: UUID, service: UserService = Depends()):
    deleted = await service.delete_user(user_id)
    if not deleted:
        return response_error(
            code=ResponseCodeEnum.USER_NOT_FOUND,
            message="用户删除失败，用户不存在",
            http_status=status.HTTP_404_NOT_FOUND
        )
    return response_success(data=None, message="用户已删除")

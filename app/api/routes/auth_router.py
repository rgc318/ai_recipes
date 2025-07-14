from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status

from app.enums.auth_method import AuthMethod
from app.services.auth_service import AuthService
from app.schemas.user_schemas import UserCreate, CredentialsRequest, UserRead
from app.schemas.auth_schemas import (
    AuthTokenResponse,
    ChangePasswordRequest,
    ResetPasswordRequest,
)
from app.core.api_response import response_success, response_error, StandardResponse
from app.api.dependencies.services import get_auth_service
from app.core.response_codes import ResponseCodeEnum
from app.core.logger import logger
from app.core.exceptions import UserLockedOutException

router = APIRouter()


# === Dependencies ===
# def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
#     return AuthService(RepositoryFactory(session))


# === Register ===
@router.post(
    "/register",
    response_model=StandardResponse[UserRead],
    status_code=status.HTTP_200_OK,
)
async def register_user(
    user_data: UserCreate,
    service: AuthService = Depends(get_auth_service)
):
    try:
        user = await service.register_user(user_data)
        return response_success(
            data=UserRead.model_validate(user),
            message="用户注册成功",
        )
    except Exception as e:
        logger.warning(f"用户注册失败: {str(e)}")
        return response_error(
            code=ResponseCodeEnum.USER_ALREADY_EXISTS,
            message=str(e)
        )


# === Login ===
@router.post(
    "/login",
    response_model=StandardResponse[AuthTokenResponse],
    status_code=status.HTTP_200_OK,
)
async def login_user(
    data: CredentialsRequest,
    service: AuthService = Depends(get_auth_service)
):
    try:
        token, expires = await service.login_user(
            method=AuthMethod.app,
            data=data,
        )
        expires_at = datetime.now(timezone.utc) + expires
        return response_success(
            data=AuthTokenResponse(access_token=token, expires_at=expires_at),
            message="登录成功",
        )
    except UserLockedOutException:
        return response_error(
            code=ResponseCodeEnum.USER_LOCKED_OUT,
            message="用户账户已被锁定，请稍后重试",
        )
    except Exception as e:
        logger.warning(f"登录失败: {str(e)}")
        return response_error(
            code=ResponseCodeEnum.LOGIN_FAILED,
            message="用户名或密码错误",
        )


# === Change Password ===
@router.post(
    "/change-password",
    response_model=StandardResponse[bool]
)
async def change_password(
    payload: ChangePasswordRequest,
    service: AuthService = Depends(get_auth_service)
):
    try:
        result = await service.change_password(
            user_id=payload.user_id,
            old_password=payload.old_password,
            new_password=payload.new_password,
        )
        return response_success(
            data=result,
            message="密码修改成功",
        )
    except Exception as e:
        logger.warning(f"密码修改失败: {str(e)}")
        return response_error(
            code=ResponseCodeEnum.USER_UPDATE_FAILED.code,
            message=str(e),
        )


# === Reset Password ===
@router.post(
    "/reset-password",
    response_model=StandardResponse[bool]
)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthService = Depends(get_auth_service)
):
    try:
        result = await service.reset_password(
            email=str(payload.email),
            new_password=payload.new_password,
        )
        return response_success(
            data=result,
            message="密码重置成功",
        )
    except Exception as e:
        logger.warning(f"密码重置失败: {str(e)}")
        return response_error(
            code=ResponseCodeEnum.USER_UPDATE_FAILED.code,
            message=str(e),
        )

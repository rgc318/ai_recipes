from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Header, Cookie

from app.config.settings import settings
from app.core.security.security import get_current_user, oauth2_scheme
from app.enums.auth_method import AuthMethod
from app.services.auth_service import AuthService
from app.schemas.user_schemas import UserCreate, CredentialsRequest, UserRead
from app.schemas.auth_schemas import (
    AuthTokenResponse,
    ChangePasswordRequest,
    ResetPasswordRequest, AuthTokenBundleResponse, RefreshTokenRequest,
)
from app.core.api_response import response_success, response_error, StandardResponse
from app.api.dependencies.services import get_auth_service
from app.core.response_codes import ResponseCodeEnum
from app.core.logger import logger
from app.core.exceptions import UserLockedOutException
from fastapi import Response

from app.utils.cookie_utils import get_refresh_cookie_params

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
        # 1. 接收 service 返回的完整 token 字典
        token_data = await service.login_user(
            method=AuthMethod.app,
            data=data,
        )
        # 2. 从字典中提取需要的信息
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        access_expires_at = token_data["access_expires_at"]

        # 3. 将 refresh_token 安全地设置到 HttpOnly cookie 中
        refresh_cookie_params = get_refresh_cookie_params(refresh_token)
        logger.info(f"refresh_token: {refresh_token}")
        # 4. 在响应体中返回 access_token
        return response_success(
            data=AuthTokenResponse(
            access_token=access_token,
            expires_at=access_expires_at,
            ),
            message="登录成功",
            set_cookies=[refresh_cookie_params]
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


@router.post(
    "/logout",
    response_model=StandardResponse[bool]
)
async def logout(
    token: str = Depends(oauth2_scheme),
    service: AuthService = Depends(get_auth_service)
):
    try:

        result = await service.logout_user(token)
        return response_success(
            data=result,
            message="登出成功",
            delete_cookies=["refresh_token"]
        )
    except Exception as e:
        logger.warning(f"登出失败: {str(e)}")
        return response_error(
            code=ResponseCodeEnum.LOGOUT_FAILED,
            message=str(e),
            delete_cookies=["refresh_token"]
        )



@router.post(
    "/refresh-token",
    response_model=StandardResponse[AuthTokenBundleResponse],
    status_code=status.HTTP_200_OK,
)
async def refresh_token_method(
    refresh_token: str | None = Cookie(default=None, alias="refresh_token"),
    service: AuthService = Depends(get_auth_service)
):
    try:
        # 2. 检查 Cookie 是否存在
        if not refresh_token:
            return response_error(
                code=ResponseCodeEnum.TOKEN_REFRESH_FAILED,
                message="Refresh token not found in cookie"
            )

        # 3. 调用 service 层进行刷新，注意这里 service.refresh_token 的返回值
        # 我们让它和 login 一样，返回包含新 access 和 refresh 的字典
        new_token_data = await service.refresh_token(refresh_token)

        # 4. 准备新的 cookie 参数
        new_refresh_cookie = get_refresh_cookie_params(new_token_data["refresh_token"])

        # 5. 返回新的 access_token，并用新的 refresh_token 覆盖旧的 cookie
        return response_success(
            data=AuthTokenResponse(
                access_token=new_token_data["access_token"],
                expires_at=new_token_data["expires_at"],
            ),
            message="Token 刷新成功",
            set_cookies=[new_refresh_cookie],
        )
    except Exception as e:
        logger.warning(f"刷新 token 失败: {str(e)}")
        # 刷新失败时，最好也清除掉客户端的无效cookie
        return response_error(
            code=ResponseCodeEnum.TOKEN_REFRESH_FAILED,
            message=str(e),
            delete_cookies=["refresh_token"]
        )
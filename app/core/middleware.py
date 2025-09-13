# app/core/middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import JWTError
from starlette.responses import JSONResponse

from app.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.request_scope import set_request_scope
# 【核心修正】直接复用你项目中已有的、强大的 jwt_utils
from app.utils.jwt_utils import decode_token

EXCLUDED_PATHS = {
    f"{settings.server.api_prefix}/auth/login",
    f"{settings.server.api_prefix}/auth/refresh-token",
    f"{settings.server.api_prefix}/auth/register",
    # 如果您的 OpenAPI 文档是公开的，也应该加入
    "/docs",
    "/openapi.json",
}

class RequestScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        # 3. [核心修正] 在所有逻辑开始前，首先检查路径是否在白名单中
        if request.url.path in EXCLUDED_PATHS:
            # 如果是白名单路径，则不进行任何 Token 检查，直接放行
            return await call_next(request)

        try:
            scope = {}
            auth_header = request.headers.get("Authorization")

            # 只有在提供了 Authorization 头时才尝试解析用户信息
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]

                # 【核心修正】调用 jwt_utils 中的 decode_token
                # 我们不再关心内部实现，只需调用即可
                payload = await decode_token(token)
                user_id = payload.get("sub")  # 通常用户ID存在'sub'字段

                if user_id:
                    # 我们只把最核心的 user_id 放入 scope
                    # 获取完整的 UserContext (包括角色、权限) 的工作
                    # 留给后面真正需要它的 get_current_user 依赖去做
                    scope["user_id"] = user_id

            # 无论是否解析出用户，都设置 scope
            set_request_scope(scope)

            response = await call_next(request)
            return response

        except UnauthorizedException as e:
            # 3. [核心] 如果认证失败（Token过期/无效），
            #    中间件自己处理，直接返回一个 401 响应
            return JSONResponse(
                status_code=401,
                content={
                    "code": e.code,
                    "message": e.message,
                    "data": None
                }
            )

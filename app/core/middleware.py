# app/core/middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import JWTError

from app.core.request_scope import set_request_scope
# 【核心修正】直接复用你项目中已有的、强大的 jwt_utils
from app.utils.jwt_utils import decode_token


class RequestScopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        scope = {}
        auth_header = request.headers.get("Authorization")

        # 只有在提供了 Authorization 头时才尝试解析用户信息
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1]
            try:
                # 【核心修正】调用 jwt_utils 中的 decode_token
                # 我们不再关心内部实现，只需调用即可
                payload = await decode_token(token)
                user_id = payload.get("sub")  # 通常用户ID存在'sub'字段

                if user_id:
                    # 我们只把最核心的 user_id 放入 scope
                    # 获取完整的 UserContext (包括角色、权限) 的工作
                    # 留给后面真正需要它的 get_current_user 依赖去做
                    scope["user_id"] = user_id

            except JWTError:
                # Token 无效或过期，静默处理，scope 保持为空
                # 后续的 get_current_user 或 require_superuser 会处理未登录的情况
                pass

        # 无论是否解析出用户，都设置 scope
        set_request_scope(scope)

        response = await call_next(request)
        return response
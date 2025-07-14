from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.core.security.middleware import AuditMiddleware
from app.db.session import create_db_and_tables
from contextlib import asynccontextmanager
from app.core.logger import logger
from app.core.exceptions.base_exception import BaseBusinessException
from app.core.response_codes import ResponseCodeEnum
from app.config.settings import settings
from app.utils.redis_client import RedisClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 应用启动中，正在初始化资源...")

    # 初始化数据库
    await create_db_and_tables()

    # 初始化 Redis
    redis_cfg = settings.redis
    await RedisClient.init(
        redis_url=redis_cfg.url,
        max_connections=redis_cfg.max_connections,
        socket_timeout=redis_cfg.socket_timeout,
        socket_connect_timeout=redis_cfg.socket_connect_timeout,
        serializer=redis_cfg.serializer,
    )
    logger.info("✅ 所有资源初始化完成")

    yield

    # 应用关闭，释放资源
    await RedisClient.close()
    logger.info("🛑 应用已关闭，Redis 已断开连接")


app = FastAPI(title="AI Recipe Project", lifespan=lifespan)

@app.on_event("startup")
async def startup_event():
    redis_cfg = settings.redis
    await RedisClient.init(
        redis_url=redis_cfg.url,
        max_connections=redis_cfg.max_connections,
        socket_timeout=redis_cfg.socket_timeout,
        socket_connect_timeout=redis_cfg.socket_connect_timeout,
        serializer=redis_cfg.serializer,
    )
@app.exception_handler(BaseBusinessException)
async def business_exception_handler(request: Request, exc: BaseBusinessException):
    logger.warning(f"Business Exception | code: {exc.code}, message: {exc.message}, path: {request.url.path}")
    return JSONResponse(
        status_code=200,  # 业务异常返回200，前端根据 code 判断
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception | {repr(exc)} | path: {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": ResponseCodeEnum.INTERNAL_ERROR.code,
            "message": ResponseCodeEnum.INTERNAL_ERROR.message,
            "data": None
        }
    )

# def handle_some_created(event: DomainEvent):
#     print(f"Handled event: {event.name}, payload: {event.payload}")

# event_bus.subscribe("SomeCreated", handle_some_created)

# @app.middleware("http")
# async def audit_middleware(request: Request, call_next):
#     # 记录审计日志
#     response = await call_next(request)
#     return response
app.add_middleware(AuditMiddleware)
app.include_router(api_router, prefix=settings.server.api_prefix)
logger.info(app.routes)
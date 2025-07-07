from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.db.session import create_db_and_tables
from contextlib import asynccontextmanager
from app.core.logger import logger
from app.core.global_exception import BaseBusinessException
from app.core.response_codes import ResponseCodeEnum
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动执行的逻辑
    await create_db_and_tables()
    yield
    # 关闭时可以加资源清理代码（可选）


app = FastAPI(title="AI Recipe Project", lifespan=lifespan)
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
app.include_router(api_router)
logger.info(app.routes)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.db.session import create_db_and_tables
from contextlib import asynccontextmanager
from app.config.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动执行的逻辑
    await create_db_and_tables()
    yield
    # 关闭时可以加资源清理代码（可选）


app = FastAPI(title="AI Recipe Project", lifespan=lifespan)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )
app.include_router(api_router)

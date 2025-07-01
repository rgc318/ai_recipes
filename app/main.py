from fastapi import FastAPI
from app.api.router import api_router
from app.db.session import create_db_and_tables
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时自动执行的逻辑
    await create_db_and_tables()
    yield
    # 关闭时可以加资源清理代码（可选）


app = FastAPI(title="AI Recipe Project", lifespan=lifespan)

app.include_router(api_router)

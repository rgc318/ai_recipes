# app/api/minio_test.py 或者直接在 app/main.py

from fastapi import APIRouter, HTTPException
from app.core.minio_client import minio_client  # 你的 MinioClient 单例

router = APIRouter()

@router.get("/test-connection")
async def test_minio_connection():
    if minio_client.test_connection():
        return {"message": "MinIO connection successful"}
    else:
        raise HTTPException(status_code=500, detail="MinIO connection failed")

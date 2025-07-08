# app/api/routes/minio_router.py

from fastapi import APIRouter, UploadFile, File, Depends
from app.services.minio_service import upload_user_avatar, upload_recipe_image, upload_general_file

router = APIRouter(prefix="/minio", tags=["MinIO 文件上传"])

# 示例：上传用户头像
@router.post("/upload-avatar")
async def upload_avatar(file: UploadFile = File(...), user_id: str = "test-user"):
    url = await upload_user_avatar(file, user_id)
    return {"url": url}

# 示例：上传菜谱图片
@router.post("/upload-recipe-image")
async def upload_recipe(file: UploadFile = File(...), recipe_id: str = "recipe-001"):
    url = await upload_recipe_image(file, recipe_id)
    return {"url": url}

# 通用文件上传接口
@router.post("/upload")
async def upload(file: UploadFile = File(...), folder: str = "uploads"):
    url = await upload_general_file(file, folder)
    return {"url": url}

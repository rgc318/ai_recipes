from fastapi import APIRouter, UploadFile, Form, File, Query, HTTPException, Depends
from typing import Optional
from app.services import minio_service
from app.core.api_response import response_success, response_error
from app.core.response_codes import ResponseCodeEnum
from app.core.logger import logger
from pydantic import BaseModel

router = APIRouter()


class FileResponse(BaseModel):
    url: str
    key: str
    content_type: str
    filename: Optional[str] = None


class FileExistsResponse(BaseModel):
    exists: bool


# 上传用户头像
@router.post("/upload-avatar", response_model=FileResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    user_id: str = Form(..., description="用户ID"),
):
    try:
        result = await minio_service.upload_user_avatar(file, user_id)
        return response_success(data=result, message="Avatar uploaded successfully")
    except HTTPException as e:
        logger.error(f"Failed to upload avatar for user {user_id}: {e.detail}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error during avatar upload for user {user_id}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Unexpected error during avatar upload")


# 上传菜谱图片
@router.post("/upload-recipe-image", response_model=FileResponse)
async def upload_recipe_image(
    file: UploadFile = File(...),
    recipe_id: str = Query(..., description="菜谱ID"),
):
    try:
        result = await minio_service.upload_recipe_image(file, recipe_id)
        return response_success(data=result, message="Recipe image uploaded successfully")
    except HTTPException as e:
        logger.error(f"Failed to upload recipe image for recipe {recipe_id}: {e.detail}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error during recipe image upload for recipe {recipe_id}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Unexpected error during recipe image upload")


# 通用文件上传
@router.post("/upload", response_model=FileResponse)
async def upload_general(
    file: UploadFile = File(...),
    folder: str = Query("uploads", description="目标文件夹"),
):
    try:
        result = await minio_service.upload_general_file(file, folder)
        return response_success(data=result, message="File uploaded successfully")
    except HTTPException as e:
        logger.error(f"Failed to upload file to {folder}: {e.detail}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error during general file upload to {folder}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Unexpected error during file upload")


# 删除文件
@router.delete("/delete")
async def delete_file(
    key: str = Query(..., description="文件 key 路径，如 user-avatars/xxx.png"),
):
    try:
        await minio_service.delete_file(key)
        return response_success(message=f"File {key} deleted successfully")
    except HTTPException as e:
        logger.error(f"Failed to delete file {key}: {e.detail}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message=e.detail)
    except Exception as e:
        logger.error(f"Unexpected error during file deletion for {key}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Unexpected error during file deletion")


# 文件是否存在
@router.get("/exists", response_model=FileExistsResponse)
async def file_exists(
    key: str = Query(..., description="文件 key 路径"),
):
    try:
        exists = await minio_service.file_exists(key)
        return response_success(data=FileExistsResponse(exists=exists))
    except Exception as e:
        logger.error(f"Failed to check existence of file {key}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Failed to check file existence")


# 列出文件
@router.get("/list")
async def list_files(
    prefix: str = Query("", description="前缀过滤，如 user-avatars/"),
):
    try:
        files = await minio_service.list_files(prefix)
        return response_success(data={"files": files})
    except Exception as e:
        logger.error(f"Failed to list files with prefix {prefix}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Failed to list files")


# 生成预签名下载URL
@router.get("/generate-download-url")
async def generate_download_url(
    key: str = Query(..., description="文件 key 路径"),
    expires_in: int = Query(3600, description="过期时间(秒)"),
    use_cdn: bool = Query(True, description="是否使用 CDN URL"),
):
    try:
        url = await minio_service.generate_file_url(key, expires_in=expires_in, use_cdn=use_cdn)
        return response_success(data={"download_url": url})
    except Exception as e:
        logger.error(f"Failed to generate download URL for {key}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Failed to generate download URL")


# 生成预签名上传URL
@router.get("/generate-upload-url")
async def generate_upload_url(
    key: str = Query(..., description="目标文件 key 路径"),
    expires_in: int = Query(3600, description="过期时间(秒)"),
):
    try:
        url = await minio_service.generate_upload_url(key, expires_in=expires_in)
        return response_success(data={"upload_url": url})
    except Exception as e:
        logger.error(f"Failed to generate upload URL for {key}: {str(e)}")
        return response_error(ResponseCodeEnum.INTERNAL_ERROR, message="Failed to generate upload URL")

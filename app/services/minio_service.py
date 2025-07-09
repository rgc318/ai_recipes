import asyncio
from asyncio import Semaphore
from botocore.exceptions import ClientError
from fastapi import UploadFile, HTTPException
from typing import Optional, Literal, BinaryIO
from uuid import uuid4
from starlette.concurrency import run_in_threadpool
from tenacity import retry, stop_after_attempt, wait_fixed
import os

from app.core.minio_client import minio_client
from app.core.logger import logger

ALLOWED_TYPES = {
    "avatar": {"image/jpeg", "image/png"},
    "image": {"image/jpeg", "image/png", "image/webp"},
    "file": {
        "application/pdf", "application/zip", "text/plain",
        "image/jpeg", "image/png", "image/gif", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    },
}

MAX_FILE_SIZE_MB = 10
UPLOAD_SEMAPHORE = Semaphore(5)  # 上传操作并发控制

# 文件验证
async def validate_file(file: UploadFile, file_type: Literal["avatar", "image", "file"] = "file"):
    logger.info(f"Validating file with content_type: {file.content_type} for {file_type}")

    # 扩展支持的 MIME 类型
    if file.content_type not in ALLOWED_TYPES[file_type]:
        logger.error(f"Unsupported file type: {file.content_type}")
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

    # 获取文件大小
    file_size = file.file.seek(0, os.SEEK_END)  # 移动到文件末尾
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File is too large")

    # 恢复文件指针
    file.file.seek(0)


# 生成安全文件名
def generate_safe_filename(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename)[-1]
    return f"{uuid4().hex}{ext}"

# 安全上传
@retry(wait=wait_fixed(1), stop=stop_after_attempt(3))
async def safe_upload(
        file: UploadFile,
        folder: str,
        filename: Optional[str] = None,
) -> dict:
    if not filename:
        filename = generate_safe_filename(file)

    key = f"{folder}/{filename}"

    logger.info(f"[MinIO] Uploading {file.filename} as {key}")

    try:
        result = await run_in_threadpool(
            minio_client.upload_fileobj,
            file,
            folder,
            filename,
        )

        result["filename"] = filename  # 保留最终文件名
        logger.info(f"[MinIO] Upload successful for {key}")
        return result
    except ClientError as e:
        logger.error(f"[MinIO] Upload failed for {key}: {e}")
        raise HTTPException(status_code=500, detail="Upload to object storage failed")
    except Exception as e:
        logger.exception(f"[MinIO] Unexpected error during upload for {key}: {e}")
        raise HTTPException(status_code=500, detail="Upload failed due to unexpected error")

# 批量上传
async def batch_upload(files: list[UploadFile], folder: str, filenames: Optional[list[str]] = None) -> list[dict]:
    if not filenames:
        filenames = [generate_safe_filename(file) for file in files]

    tasks = []
    for i, file in enumerate(files):
        task = safe_upload(file, folder, filenames[i] if filenames else None)
        tasks.append(task)

    return await asyncio.gather(*tasks)

# 上传用户头像
async def upload_user_avatar(file: UploadFile, user_id: str, filename: Optional[str] = None) -> dict:
    await validate_file(file, file_type="avatar")
    folder = f"user-avatars/{user_id}"
    return await safe_upload(file, folder, filename)

# 上传菜谱图片
async def upload_recipe_image(file: UploadFile, recipe_id: str, filename: Optional[str] = None) -> dict:
    await validate_file(file, file_type="image")
    folder = f"recipe-images/{recipe_id}"
    return await safe_upload(file, folder, filename)

# 上传通用文件
async def upload_general_file(file: UploadFile, folder: str = "uploads", filename: Optional[str] = None) -> dict:
    await validate_file(file, file_type="file")
    return await safe_upload(file, folder, filename)

# 上传二进制流
async def upload_binary_stream(
        stream: BinaryIO,
        content_type: str,
        folder: str = "uploads",
        object_name: Optional[str] = None,
) -> dict:
    logger.info(f"[MinIO] Uploading binary stream to {folder}/{object_name}")
    return await run_in_threadpool(minio_client.upload_stream, stream, content_type, folder, object_name)

# 删除文件
async def delete_file(key: str):
    logger.info(f"[MinIO] Deleting file: {key}")
    try:
        await run_in_threadpool(minio_client.delete_object, key)
        logger.info(f"[MinIO] Successfully deleted file: {key}")
    except ClientError as e:
        logger.error(f"[MinIO] Failed to delete file {key}: {e}")
        raise HTTPException(status_code=500, detail="File deletion failed")
    except Exception as e:
        logger.exception(f"[MinIO] Unexpected error during file deletion for {key}: {e}")
        raise HTTPException(status_code=500, detail="File deletion failed due to unexpected error")

# 批量删除文件
async def delete_files(keys: list[str]):
    tasks = [delete_file(key) for key in keys]
    await asyncio.gather(*tasks)

# 检查文件是否存在
async def file_exists(key: str) -> bool:
    logger.info(f"[MinIO] Checking if file exists: {key}")
    return await run_in_threadpool(minio_client.object_exists, key)

# 列出文件
async def list_files(prefix: str = "") -> list[str]:
    logger.info(f"[MinIO] Listing files with prefix: {prefix}")
    return await run_in_threadpool(minio_client.list_objects, prefix)

# 生成文件URL
async def generate_file_url(key: str, expires_in: int = 3600, use_cdn: bool = True) -> str:
    logger.info(f"[MinIO] Generating file URL for {key}, expires in {expires_in}s")
    return await run_in_threadpool(minio_client.generate_presigned_url, key, expires_in, use_cdn)

# 生成上传URL
async def generate_upload_url(key: str, expires_in: int = 3600) -> str:
    logger.info(f"[MinIO] Generating upload URL for {key}, expires in {expires_in}s")
    return await run_in_threadpool(minio_client.generate_presigned_put_url_with_final_url, key, expires_in)

# 生成带上传URL和访问URL的字典
async def generate_presigned_upload_url(folder: str, filename: Optional[str] = None, expires_in: int = 3600) -> dict:
    logger.info(f"[MinIO] Generating presigned upload URL and final URL for {filename}")
    return await run_in_threadpool(minio_client.generate_presigned_put_url_with_final_url, folder, filename, expires_in)

# 上传时带并发限制
async def safe_upload_with_limit(file: UploadFile, folder: str, filename: Optional[str] = None) -> dict:
    async with UPLOAD_SEMAPHORE:
        return await safe_upload(file, folder, filename)

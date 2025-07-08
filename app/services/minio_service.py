# app/services/minio_service.py

from fastapi import UploadFile
from uuid import uuid4
from app.core.minio_client import minio_client
from app.core.logger import logger

async def upload_user_avatar(file: UploadFile, user_id: str) -> str:
    folder = f"user-avatars/{user_id}"
    return minio_client.upload_fileobj(file, folder)

async def upload_recipe_image(file: UploadFile, recipe_id: str) -> str:
    folder = f"recipe-images/{recipe_id}"
    return minio_client.upload_fileobj(file, folder)

async def upload_general_file(file: UploadFile, folder: str = "uploads") -> str:
    logger.debug(f"Uploading general file to MinIO folder: {folder}")
    return minio_client.upload_fileobj(file, folder)

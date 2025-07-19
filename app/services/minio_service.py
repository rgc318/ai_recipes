import asyncio
import os
from asyncio import Semaphore
from typing import BinaryIO, List, Literal, Optional
from uuid import uuid4

from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.exceptions import FileException
from app.core.logger import logger
from app.core.minio_client import MinioClient


class MinioService:
    """
    MinIO 对象存储服务层。
    封装了所有与文件上传、删除和URL生成相关的业务逻辑。
    遵循依赖注入模式，更易于测试和维护。
    """

    def __init__(self, minio_client: MinioClient, concurrency_limit: int = 5, max_file_size_mb: int = 10):
        self.client = minio_client
        self.max_file_size_mb = max_file_size_mb
        self.upload_semaphore = Semaphore(concurrency_limit)
        self.allowed_types = {
            "avatar": {"image/jpeg", "image/png", "image/webp"},
            "image": {"image/jpeg", "image/png", "image/webp", "image/gif"},
            "file": {
                "application/pdf", "application/zip", "text/plain", "image/jpeg",
                "image/png", "image/gif", "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-powerpoint",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            },
        }

    # --- 内部辅助方法 (Internal Helpers) ---

    def _generate_safe_filename(self, original_filename: str) -> str:
        """内部方法：生成安全、唯一的UUID文件名。"""
        ext = os.path.splitext(original_filename)[-1].lower()
        return f"{uuid4().hex}{ext}"

    async def _validate_file(self, file: UploadFile, file_type: Literal["avatar", "image", "file"]) -> int:
        """内部方法：验证文件类型和大小，并返回文件大小。"""
        if file.content_type not in self.allowed_types.get(file_type, set()):
            raise FileException(message=f"Unsupported file type: {file.content_type}")

        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        if file_size > self.max_file_size_mb * 1024 * 1024:
            raise FileException(message=f"File is too large. Max size is {self.max_file_size_mb}MB.")

        await file.seek(0)
        return file_size

    @retry(wait=wait_fixed(1), stop=stop_after_attempt(3), reraise=True)
    async def _safe_upload(self, file: BinaryIO, length: int, object_name: str, content_type: str) -> dict:
        """内部核心上传方法，带重试。"""
        logger.info(f"[MinIO] Uploading to {object_name}")
        try:
            result = await run_in_threadpool(
                self.client.put_object,
                object_name=object_name,
                data=file,
                length=length,
                content_type=content_type,
            )
            response = {"object_name": object_name, "etag": result.get('ETag')}
            logger.info(f"[MinIO] Upload successful for {object_name}")
            return response
        except ClientError as e:
            logger.error(f"[MinIO] Upload failed for {object_name}: {e}")
            raise FileException(message="Upload to object storage failed.")
        except Exception as e:
            logger.exception(f"[MinIO] Unexpected error during upload for {object_name}: {e}")
            raise FileException(message="An unexpected error occurred during upload.")

    # --- 公共服务接口 (Public Service API) ---

    async def upload_file(
            self,
            file: UploadFile,
            folder: str,
            file_type: Literal["avatar", "image", "file"] = "file"
    ) -> dict:
        """
        通用的文件上传方法，自带验证和并发控制。
        :return: 包含 object_name 和 url 的字典。
        """
        file_size = await self._validate_file(file, file_type)
        filename = self._generate_safe_filename(file.filename)
        object_name = f"{folder}/{filename}".lstrip("/")

        async with self.upload_semaphore:
            result = await self._safe_upload(
                file=file.file,
                length=file_size,
                object_name=object_name,
                content_type=file.content_type
            )

        result['url'] = self.client.build_final_url(object_name)
        return result

    async def upload_user_avatar(self, file: UploadFile, user_id: str) -> dict:
        """上传用户头像。"""
        folder = f"avatars/{user_id}"
        return await self.upload_file(file, folder, file_type="avatar")

    async def batch_upload_files(self, files: List[UploadFile], folder: str) -> List[dict]:
        """批量上传多个文件。"""
        tasks = [self.upload_file(file, folder, file_type="file") for file in files]
        results = await asyncio.gather(*tasks)
        return results

    # 【补全】上传二进制流的功能
    async def upload_binary_stream(
            self,
            stream: BinaryIO,
            length: int,
            content_type: str,
            folder: str,
            filename: str
    ) -> dict:
        """
        直接上传二进制数据流。
        :return: 包含 object_name 和 url 的字典。
        """
        object_name = f"{folder}/{filename}".lstrip("/")
        async with self.upload_semaphore:
            result = await self._safe_upload(
                file=stream,
                length=length,
                object_name=object_name,
                content_type=content_type
            )
        result['url'] = self.client.build_final_url(object_name)
        return result

    async def delete_file(self, object_name: str):
        """删除一个文件。"""
        try:
            await run_in_threadpool(self.client.remove_object, object_name)
        except ClientError as e:
            raise FileException(message="File deletion failed.")

    # 【补全】批量删除文件的功能
    async def delete_files(self, object_names: List[str]):
        """批量删除多个文件。"""
        tasks = [self.delete_file(object_name) for object_name in object_names]
        await asyncio.gather(*tasks)

    # 【补全】检查文件是否存在的功能
    async def file_exists(self, object_name: str) -> bool:
        """检查文件是否存在。"""
        try:
            await run_in_threadpool(self.client.stat_object, object_name)
            return True
        except ClientError as e:
            # MinIO/S3 在对象不存在时 head_object 会返回 404
            if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            logger.error(f"Error checking existence for {object_name}: {e}")
            raise FileException("Could not check file existence.")

    # 【补全】列出文件的功能
    async def list_files(self, prefix: str = "") -> List[str]:
        """列出存储桶中所有文件（或带有特定前缀的文件）。"""
        try:
            # 假设 client 中有一个 list_objects 方法
            objects = await run_in_threadpool(self.client.list_objects, prefix)
            return [obj.get("Key") for obj in objects]
        except ClientError as e:
            logger.error(f"Failed to list files with prefix '{prefix}': {e}")
            raise FileException(f"Could not list files.")

    # --- URL 生成接口 ---

    async def generate_presigned_get_url(self, object_name: str, expires_in: int = 3600) -> str:
        """生成文件的预签名访问URL。"""
        try:
            return await run_in_threadpool(
                self.client.get_presigned_url,
                client_method="get_object",
                object_name=object_name,
                expires_in=expires_in
            )
        except ClientError as e:
            logger.error(f"Failed to generate GET URL for {object_name}: {e}")
            raise FileException(message="Could not generate file URL.")

    # 【补全】生成预签名上传URL的功能
    async def generate_presigned_put_url(self, folder: str, original_filename: str, expires_in: int = 3600) -> dict:
        """
        生成一个预签名的上传URL，供客户端直接上传。
        """
        filename = self._generate_safe_filename(original_filename)
        object_name = f"{folder}/{filename}".lstrip("/")

        try:
            upload_url = await run_in_threadpool(
                self.client.get_presigned_url,
                client_method="put_object",
                object_name=object_name,
                expires_in=expires_in
            )
            final_url = self.client.build_final_url(object_name)
            return {
                "upload_url": upload_url,
                "object_name": object_name,
                "url": final_url
            }
        except ClientError as e:
            logger.error(f"Failed to generate PUT URL for {object_name}: {e}")
            raise FileException(message="Could not generate upload URL.")
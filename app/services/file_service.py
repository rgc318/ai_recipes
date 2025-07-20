import asyncio
import os
from asyncio import Semaphore
from datetime import datetime
from typing import BinaryIO, List, Literal
from uuid import uuid4

from botocore.exceptions import ClientError
from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.exceptions import FileException
from app.core.logger import logger
from app.core.storage.minio_client import MinioClient
from app.core.storage.storage_factory import StorageFactory
from app.core.storage.storage_interface import StorageClientInterface
from app.schemas.file_record_schemas import FileRecordRead
from app.schemas.file_schemas import UploadResult, PresignedUploadURL


class FileService:
    """
    一个通用的文件存储服务层。

    它作为业务逻辑和底层存储客户端之间的协调者，使用 StorageFactory
    来动态地处理不同业务场景（Profiles）下的文件操作。
    """

    def __init__(self, factory: StorageFactory, concurrency_limit: int = 5, max_file_size_mb: int = 10):
        self.factory = factory
        self.max_file_size_mb = max_file_size_mb
        self.upload_semaphore = Semaphore(concurrency_limit)


    # --- 内部辅助方法 (Internal Helpers) ---

    def _generate_safe_filename(self, original_filename: str) -> str:
        """内部方法：生成安全、唯一的UUID文件名。"""
        ext = os.path.splitext(original_filename)[-1].lower()
        return f"{uuid4().hex}{ext}"

    # async def _validate_file(self, file: UploadFile, file_type: Literal["avatar", "image", "file"]) -> int:
    #     """内部方法：验证文件类型和大小，并返回文件大小。"""
    #     if file.content_type not in self.allowed_types.get(file_type, set()):
    #         raise FileException(message=f"Unsupported file type: {file.content_type}")
    #
    #     file.file.seek(0, os.SEEK_END)
    #     file_size = file.file.tell()
    #     if file_size > self.max_file_size_mb * 1024 * 1024:
    #         raise FileException(message=f"File is too large. Max size is {self.max_file_size_mb}MB.")
    #
    #     await file.seek(0)
    #     return file_size

    async def _validate_file(self, file: UploadFile, allowed_content_types: set) -> int:
        """内部方法：验证文件类型和大小，并返回文件大小。"""
        if file.content_type not in allowed_content_types:
            raise FileException(message=f"Unsupported file type for this profile: {file.content_type}")

        # 注意：这种检查大小的方式会完整读取文件到内存，对于大文件可能有风险
        # 更优化的方式是流式检查，但对于中小型文件，这种方式是可行的。
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        if file_size > self.max_file_size_mb * 1024 * 1024:
            raise FileException(message=f"File is too large. Max size is {self.max_file_size_mb}MB.")

        await file.seek(0)
        return file_size

    @retry(wait=wait_fixed(1), stop=stop_after_attempt(3), reraise=True)
    async def _safe_upload(
            self,
            client: StorageClientInterface,
            file: BinaryIO,
            length: int,
            object_name: str,
            content_type: str
    ) -> dict:
        """内部核心上传方法，带重试。"""
        logger.info(f"Uploading to {object_name} using client for bucket '{client.bucket_name}'")
        try:
            result = await run_in_threadpool(
                client.put_object,
                object_name=object_name,
                data=file,
                length=length,
                content_type=content_type,
            )
            etag = result.get('ETag')

            logger.info(f"[MinIO] Upload successful for {object_name}")
            return etag
        except ClientError as e:
            logger.error(f"[MinIO] Upload failed for {object_name}: {e}")
            raise FileException(message="Upload to object storage failed.")
        except Exception as e:
            logger.exception(f"[MinIO] Unexpected error during upload for {object_name}: {e}")
            raise FileException(message="An unexpected error occurred during upload.")

    # --- 公共服务接口 (Public Service API) ---

    # async def upload_file(
    #         self,
    #         client: StorageClientInterface,
    #         file: UploadFile,
    #         folder: str,
    #         file_type: Literal["avatar", "image", "file"] = "file"
    # ) -> FileRecordRead:
    #     """
    #     通用的文件上传方法，自带验证和并发控制。
    #     :return: 包含 object_name 和 url 的字典。
    #     """
    #     file_size = await self._validate_file(file, file_type)
    #     filename = self._generate_safe_filename(file.filename)
    #     object_name = f"{folder}/{filename}".lstrip("/")
    #
    #     async with self.upload_semaphore:
    #         result = await self._safe_upload(
    #             file=file.file,
    #             length=file_size,
    #             object_name=object_name,
    #             content_type=file.content_type
    #         )
    #
    #     result['url'] = client.build_final_url(object_name)
    #     return result

    # 在 FileService 类中添加这个新方法
    def _prepare_upload_context(
            self,
            profile_name: str,
            original_filename: str,
            **path_params
    ) -> tuple[StorageClientInterface, str]:
        """
        一个辅助方法，用于准备上传所需的客户端和对象名称。
        """
        client = self.factory.get_client_by_profile(profile_name)
        profile_config = self.factory.get_profile_config(profile_name)

        # ==================================================================
        # 【新增逻辑】在这里自动生成默认参数
        # ==================================================================
        now = datetime.now()
        default_params = {
            "year": now.year,
            "month": now.month,
            "day": now.day
            # 未来还可以添加 "user_id" 等，如果能从上下文中获取
        }
        final_params = {**default_params, **path_params}

        try:
            folder = profile_config.default_folder.format(**final_params)
        except KeyError as e:
            raise ValueError(f"Missing required path parameter '{e.args[0]}' for profile '{profile_name}'")

        filename = self._generate_safe_filename(original_filename)
        object_name = f"{folder}/{filename}".lstrip("/")

        return client, object_name

    async def upload_user_avatar(self, file: UploadFile, user_id: str) -> UploadResult:
        """上传用户头像。"""
        return await self.upload_by_profile(
            file=file,
            profile_name="user_avatars",
            user_id=user_id  # 将 user_id 作为关键字参数传递
        )

    async def upload_secure_report(self, file: UploadFile) -> dict:
        """上传安全报告。"""
        return await self.upload_by_profile(file=file, profile_name="secure_reports")

    async def batch_upload_by_profile(self, files: List[UploadFile], profile_name: str) -> List[dict]:
        """按指定的 Profile 批量上传多个文件。"""
        tasks = [self.upload_by_profile(file, profile_name) for file in files]
        results = await asyncio.gather(*tasks)
        return results

    async def upload_by_profile(self, file: UploadFile, profile_name: str, **path_params) -> UploadResult:
        """
        根据指定的业务场景 Profile 上传文件。
        这是所有上传操作的入口点。
        """
        # 1. 从工厂获取对应的客户端和 Profile 配置
        client, object_name = self._prepare_upload_context(
            profile_name=profile_name,
            original_filename=file.filename,
            **path_params
        )
        profile_config = self.factory.get_profile_config(profile_name)

        # 2. 验证文件 (使用从配置中获取的 allowed_file_types)
        # 注意: 这里假设配置文件中的 allowed_file_types 与旧的 allowed_types 字典的 key 匹配
        # 你需要一个映射或在配置中直接定义 content-type 列表
        # 为简化，我们假设 profile_config.allowed_file_types 就是一个 content-type 的集合
        # 例如: allowed_file_types: ["image/jpeg", "image/png"]
        allowed_types_set = set(profile_config.allowed_file_types)  # 假设配置中是列表
        file_size = await self._validate_file(file, allowed_types_set)

        # 4. 执行上传
        async with self.upload_semaphore:
            etag = await self._safe_upload(
                client=client,
                file=file.file,
                length=file_size,
                object_name=object_name,
                content_type=file.content_type
            )

        # 5. 构建最终 URL 并返回
        return UploadResult(
            object_name=object_name,
            url=client.build_final_url(object_name),
            etag=etag,
            file_size=file_size,
            content_type=file.content_type
        )

    # 【补全】上传二进制流的功能
    async def upload_binary_stream(
            self,
            stream: BinaryIO,
            length: int,
            content_type: str,
            original_filename: str,  # 接收原始文件名以生成安全文件名
            profile_name: str,
            **path_params
    ) -> UploadResult:
        """
        根据 Profile 直接上传二进制数据流。
        """
        # 1. 从工厂获取客户端和 Profile 配置
        client = self.factory.get_client_by_profile(profile_name)
        profile_config = self.factory.get_profile_config(profile_name)

        # 2. 验证（可选，但最好有）
        # 如果需要，可以在这里添加对 content_type 的验证
        # if content_type not in set(profile_config.allowed_file_types): ...

        # 3. 格式化文件夹路径
        try:
            folder = profile_config.default_folder.format(**path_params)
        except KeyError as e:
            raise ValueError(f"Missing required path parameter '{e.args[0]}' for profile '{profile_name}'")

        # 4. 生成对象名称
        filename = self._generate_safe_filename(original_filename)
        object_name = f"{folder}/{filename}".lstrip("/")

        # 5. 执行上传
        async with self.upload_semaphore:
            etag = await self._safe_upload(
                client=client,
                file=stream,
                length=length,
                object_name=object_name,
                content_type=content_type
            )

        # 6. 构建 URL 并返回
        return UploadResult(
            object_name=object_name,
            url=client.build_final_url(object_name),
            etag=etag,
            file_size=length,
            content_type=content_type
        )

    async def delete_file(self, object_name: str, profile_name: str):
        """根据 Profile 删除一个文件。"""
        client = self.factory.get_client_by_profile(profile_name)
        try:
            await run_in_threadpool(client.remove_object, object_name)
            logger.info(f"Deleted {object_name} using profile {profile_name}")
        except ClientError as e:
            raise FileException(message="File deletion failed.")

    # 【补全】批量删除文件的功能
    async def delete_files(self, object_names: List[str], profile_name: str):
        """批量删除多个文件。"""
        tasks = [self.delete_file(object_name, profile_name) for object_name in object_names]
        await asyncio.gather(*tasks)

    # 【补全】检查文件是否存在的功能
    async def file_exists(self, object_name: str, profile_name: str) -> bool:
        """根据 Profile 检查文件是否存在。"""
        client = self.factory.get_client_by_profile(profile_name)
        try:
            await run_in_threadpool(client.stat_object, object_name)
            return True
        except ClientError as e:
            if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            logger.error(f"Error checking existence for {object_name}: {e}")
            raise FileException("Could not check file existence.")

    # 【补全】列出文件的功能
    async def list_files(self, profile_name: str, prefix: str = "") -> List[str]:
        """列出存储桶中所有文件（或带有特定前缀的文件）。"""
        try:
            client = self.factory.get_client_by_profile(profile_name)
            # 假设 client 中有一个 list_objects 方法
            objects = await run_in_threadpool(client.list_objects, prefix)
            return [obj.get("key") for obj in objects if obj.get("key")]
        except ClientError as e:
            logger.error(f"Failed to list files with prefix '{prefix}': {e}")
            raise FileException(f"Could not list files.")

    # --- URL 生成接口 ---

    async def generate_presigned_get_url(
        self,
        object_name: str,
        profile_name: str,
        expires_in: int = 3600
    ) -> str:
        """根据 Profile 生成文件的预签名访问URL。"""
        client = self.factory.get_client_by_profile(profile_name)
        try:
            return await run_in_threadpool(
                client.get_presigned_url,
                client_method="get_object",
                object_name=object_name,
                expires_in=expires_in
            )
        except ClientError as e:
            logger.error(f"Failed to generate GET URL for {object_name}: {e}")
            raise FileException(message="Could not generate file URL.")

    # 【补全】生成预签名上传URL的功能
    async def generate_presigned_put_url(
            self,
            original_filename: str,
            profile_name: str,
            expires_in: int = 3600,
            **path_params
    ) -> PresignedUploadURL:
        """
        生成一个预签名的上传URL，供客户端直接上传。
        """
        client, object_name = self._prepare_upload_context(
            profile_name=profile_name,
            original_filename=original_filename,
            **path_params
        )
        try:
            upload_url = await run_in_threadpool(
                client.get_presigned_url,
                client_method="put_object",
                object_name=object_name,
                expires_in=expires_in
            )
            return PresignedUploadURL(
                upload_url=upload_url,
                object_name=object_name,
                url=client.build_final_url(object_name)
            )
        except ClientError as e:
            logger.error(f"Failed to generate PUT URL for {object_name}: {e}")
            raise FileException(message="Could not generate upload URL.")
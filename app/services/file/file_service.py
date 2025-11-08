import asyncio
import os
from asyncio import Semaphore
from datetime import datetime
from typing import BinaryIO, List, TYPE_CHECKING, Optional, Literal
from uuid import uuid4, UUID

from botocore.exceptions import ClientError
from fastapi import UploadFile, Depends
from starlette.concurrency import run_in_threadpool
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.exceptions import FileException, NotFoundException
from app.core.logger import logger
from app.enums.file_enums import UploadMode
from app.infra.storage.storage_factory import StorageFactory
from app.infra.storage.storage_interface import StorageClientInterface
from app.schemas.file.file_record_schemas import FileRecordRead
from app.schemas.file.file_schemas import UploadResult, PresignedUploadURL, PresignedUploadPolicy, \
    UnifiedPresignedUpload
from app.schemas.users.user_context import UserContext
from app.services._base_service import BaseService
if TYPE_CHECKING:
    from app.services.file.file_record_service import FileRecordService



class FileService(BaseService):
    """
    一个通用的文件存储服务层。

    它作为业务逻辑和底层存储客户端之间的协调者，使用 StorageFactory
    来动态地处理不同业务场景（Profiles）下的文件操作。
    """

    def __init__(
            self,
            factory: StorageFactory,
            file_record_service: "FileRecordService" = Depends(),
            concurrency_limit: int = 5
    ):
        super().__init__()
        self.factory = factory
        self.file_record_service = file_record_service  # <-- 保存实例
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

    async def _validate_file(self, file: UploadFile, profile_config) -> int:
        """内部方法：验证文件类型和大小，并返回文件大小。"""
        allowed_content_types = set(profile_config.allowed_file_types)
        if file.content_type not in allowed_content_types:
            raise FileException(message=f"Unsupported file type for this profile: {file.content_type}")

        # 注意：这种检查大小的方式会完整读取文件到内存，对于大文件可能有风险
        # 更优化的方式是流式检查，但对于中小型文件，这种方式是可行的。
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()

        max_size_mb = getattr(profile_config, 'max_file_size_mb', 10) # 默认为 10MB
        max_size_bytes = max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise FileException(message=f"File is too large. Max size is {max_size_mb}MB.")

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
    ) -> str:  # <-- 【修复】类型提示应为 str
        """内部核心上传方法，带重试。"""
        client_name = client.__class__.__name__  # <-- 【修复】获取客户端类名
        logger.info(
            f"Uploading {object_name} using client: {client_name}"
        )
        try:
            result = await run_in_threadpool(
                client.put_object,
                object_name=object_name,
                data=file,
                length=length,
                content_type=content_type,
            )
            etag = (result.get("ETag") or result.get("etag") or "").strip('"')


            logger.info(f"Upload successful for {object_name} (Client: {client_name})")  # <-- 【修复】
            return etag
        except ClientError as e:
            logger.error(f"Upload failed for {object_name} (Client: {client_name}): {e}")  # <-- 【修复】
            raise FileException(message="Upload to object storage failed.")
        except Exception as e:
            logger.exception(
                f"Unexpected error during upload for {object_name} (Client: {client_name}): {e}")  # <-- 【修复】
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

    async def upload_user_avatar(
        self,
        file: UploadFile,
        uploader_context: UserContext, # <-- 【修正】接收 uploader_context
        user_id: str
    ) -> UploadResult:
        """上传用户头像。"""
        # 【修正】将 uploader_context 传递下去
        return await self.upload_by_profile(
            file=file,
            profile_name="user_avatars",
            uploader_context=uploader_context,
            user_id=user_id
        )

    async def upload_secure_report(
            self,
            file: UploadFile,
            uploader_context: UserContext
    ) -> UploadResult:
        """上传安全报告。"""
        return await self.upload_by_profile(
            file=file,
            profile_name="secure_reports",
            uploader_context=uploader_context  # <-- 传递
        )

    async def batch_upload_by_profile(
        self,
        files: List[UploadFile],
        profile_name: str,
        uploader_context: UserContext # <-- 增加
    ) -> List[dict]:
        """按指定的 Profile 批量上传多个文件。"""
        tasks = [
            self.upload_by_profile(file, profile_name, uploader_context) for file in files
        ]
        results = await asyncio.gather(*tasks)
        return results

    async def upload_by_profile(
            self,
            file: UploadFile,
            profile_name: str,
            uploader_context: Optional[UserContext] = None,  # <-- 1. 增加 uploader_context 参数
            **path_params
    ) -> UploadResult:
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

        file_size = await self._validate_file(file, profile_config)

        # 4. 执行上传
        async with self.upload_semaphore:
            etag = await self._safe_upload(
                client=client,
                file=file.file,
                length=file_size,
                object_name=object_name,
                content_type=file.content_type
            )


        new_file_record = await self.file_record_service.register_uploaded_file(
            object_name=object_name,
            original_filename=file.filename,
            content_type=file.content_type,
            file_size=file_size,
            profile_name=profile_name,
            uploader_context=uploader_context,
            etag=str(etag),
        )
        # 5. 构建最终 URL 并返回
        return UploadResult(
            record_id=new_file_record.id,  # <-- 补上 record_id
            object_name=object_name,
            url=client.build_final_url(object_name),
            etag=str(etag),
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
            uploader_context: Optional[UserContext] = None,
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

        new_file_record = await self.file_record_service.register_uploaded_file(
            object_name=object_name, original_filename=original_filename,
            content_type=content_type, file_size=length,
            profile_name=profile_name, uploader_context=uploader_context, etag=str(etag)
        )

        # 6. 构建 URL 并返回
        return UploadResult(
            object_name=object_name,
            url=client.build_final_url(object_name),
            etag=str(etag),
            file_size=length,
            content_type=content_type,
            record_id=new_file_record.id
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

    async def generate_presigned_upload(
        self,
        original_filename: str,
        content_type: str,
        profile_name: str,
        expires_in: int = 3600,
        force_method: Optional[Literal[UploadMode.PUT_URL, UploadMode.POST_POLICY]] = None,
        **path_params
    ) -> UnifiedPresignedUpload:
        """
        【主方法】根据“业务偏好”智能生成预签名，并在服务不支持时自动降级。

        这是推荐的、供客户端（前端）调用的统一接口。
        它读取 Profile 的 "presigned_upload_method" 配置，并尝试使用它。
        如果客户端 (如 R2) 不支持 (抛出 NotImplementedError)，它会自动降级到 'put_url'。
        """

        final_method = None

        if force_method:
            # 1a. 优先级 1: 使用“强制覆盖”参数
            final_method = force_method
            logger.info(f"Forced upload method '{final_method}' for profile '{profile_name}'.")
        else:
            # 1b. 优先级 2: 使用“配置偏好”
            profile_config = self.factory.get_profile_config(profile_name)
            final_method = getattr(profile_config, 'presigned_upload_method', UploadMode.PUT_URL)

        # 3. 【Try-Except-Fallback 逻辑】
        # 尝试执行“偏好”的方法
        if final_method == UploadMode.POST_POLICY:
            try:
                # 3a. 尝试 POST (e.g., for S3/MinIO)
                policy_data = await self.generate_presigned_upload_policy(
                    original_filename=original_filename,
                    content_type=content_type,
                    profile_name=profile_name,
                    expires_in=expires_in,
                    **path_params
                )

                # 适配为统一响应
                return UnifiedPresignedUpload(
                    method="POST",
                    upload_url=policy_data.url,
                    fields=policy_data.fields,
                    object_name=policy_data.object_name,
                    final_url=policy_data.final_url
                )

            except (NotImplementedError, ClientError) as e:
                # 3b. 【自动降级】
                # 捕获 s3_client (R2) 抛出的 NotImplementedError 或 ClientError
                # 【关键】检查失败的原因：
                if final_method == UploadMode.POST_POLICY:
                    # 如果是“强制 POST”失败了（例如R2），则必须抛出异常
                    # 因为调用者明确要求了POST，不能自动降级
                    logger.error(f"Forced 'post_policy' failed for profile '{profile_name}': {e}")
                    raise FileException(
                        f"Forced 'post_policy' is not supported by the provider for profile '{profile_name}'."
                    )

                # 如果是“默认 POST”失败了（例如R2），则可以自动降级为PUT
                logger.warning(
                    f"Profile '{profile_name}' prefers 'post_policy', but client does not support it. "
                    f"Falling back to 'put_url'. Error: {e}"
                )
                # 代码会“掉落”到下面的 "put_url" 逻辑

        # 4. (默认或降级) 执行 "put_url"
        # (如果 preferred_method 一开始就是 "put_url"，会直接到这里)
        # (如果 preferred_method 是 "post_policy" 但失败了，也会到这里)

        put_data = await self.generate_presigned_put_url(
            original_filename=original_filename,
            profile_name=profile_name,
            expires_in=expires_in,
            **path_params
        )

        # 适配为统一响应
        return UnifiedPresignedUpload(
            method="PUT",
            upload_url=put_data.upload_url,
            fields=None,  # PUT 模式没有 fields
            object_name=put_data.object_name,
            final_url=put_data.url
        )

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

    async def generate_presigned_upload_policy(
            self,
            original_filename: str,
            content_type: str,  # 【新增】前端需要告知文件的MIME类型
            profile_name: str,
            expires_in: int = 3600,
            **path_params
    ) -> PresignedUploadPolicy:
        """
        生成一个【带安全策略】的预签名POST Policy，供客户端上传。
        """
        # 1. 获取 Profile 配置，我们将从中读取策略
        profile_config = self.factory.get_profile_config(profile_name)

        # 2. 【安全检查】在后端验证前端声称的文件类型
        allowed_types = set(profile_config.allowed_file_types)
        if content_type not in allowed_types:
            raise FileException(f"File type '{content_type}' is not allowed for this profile.")

        # 准备上下文
        client, object_name = self._prepare_upload_context(
            profile_name=profile_name,
            original_filename=original_filename,
            **path_params
        )

        # 3. 【安全策略构建】为预签名URL构建上传条件
        conditions = []
        fields = {"Content-Type": content_type}


        # 策略 a: 限制文件大小
        max_size_mb = getattr(profile_config, 'max_file_size_mb', 10)
        max_size_bytes = max_size_mb * 1024 * 1024
        conditions.append(["content-length-range", 1, max_size_bytes])

        # 策略 b: 限制文件类型 (这是对前端声称的 content_type 的再次确认)
        conditions.append(["eq", "$Content-Type", content_type])

        try:
            # 调用底层客户端生成 POST Policy
            policy_data = await run_in_threadpool(
                client.generate_presigned_post_policy,
                object_name=object_name,
                expires_in=expires_in,
                conditions=conditions,
                fields=fields
            )

            logger.info(f"Generated POST Policy for {object_name}: {policy_data}")

            # 使用新的 Pydantic Schema 封装返回结果
            return PresignedUploadPolicy(
                url=policy_data['url'],
                fields=policy_data['fields'],
                # 额外返回 object_name 和最终可访问的 url，方便前端
                object_name=object_name,
                final_url=client.build_final_url(object_name)
            )
        except ClientError as e:
            logger.error(f"Failed to generate POST Policy for {object_name}: {e}")
            raise FileException(message="Could not generate upload policy.")

    async def move_file(
            self,
            source_key: str,
            destination_key: str,
            profile_name: str
    ) -> None:
        """
        在同一个 Profile (存储桶) 内移动（重命名）一个文件。
        这在将临时文件转为正式文件时非常有用。
        """
        # 1. 获取对应的存储客户端
        client = self.factory.get_client_by_profile(profile_name)
        logger.info(f"Attempting to move '{source_key}' to '{destination_key}' in profile '{profile_name}'")

        try:
            # 2. 【核心步骤】调用底层客户端的 "copy_object" 方法
            #    这通常是一个高效的服务器端复制操作。
            #    我们假设您的 StorageClientInterface 有一个 copy_object 方法。
            await run_in_threadpool(
                client.copy_object,
                destination_key=destination_key,
                source_key=source_key
            )
            logger.info(f"Successfully copied '{source_key}' to '{destination_key}'.")

            # 3. 复制成功后，删除源文件
            await self.delete_file(source_key, profile_name)
            logger.info(f"Successfully moved file by deleting source '{source_key}'.")

        except ClientError as e:
            # 如果复制或删除失败，记录错误并抛出异常
            logger.error(f"Failed to move file from '{source_key}' to '{destination_key}': {e}")
            # 在这里可以考虑进行一次清理，尝试删除可能已创建的目标文件，以避免不一致
            # 但更简单的做法是让调用方处理这个异常
            raise FileException(message="File move operation failed in storage.")
        except Exception as e:
            logger.exception(f"Unexpected error during file move: {e}")
            raise FileException(message="An unexpected error occurred during file move.")

    def build_url_for_object(
        self,
        object_name: Optional[str],
        profile_name: Optional[str]
    ) -> Optional[str]:
        """
        一个可复用的、安全的 URL 构建器。
        它拥有所有上下文（通过 self.factory）。
        """
        if not object_name or not profile_name:
            return None
        try:
            # 1. 从 Factory 获取“智能”客户端
            client = self.factory.get_client_by_profile(profile_name)
            # 2. 调用客户端的“智能” URL 构建器
            return client.build_final_url(object_name)
        except Exception as e:
            logger.error(f"Failed to build URL for {object_name} in profile {profile_name}: {e}")
            return None

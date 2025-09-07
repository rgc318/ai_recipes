from typing import List, Optional, Dict, Any, TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from app.core.exceptions import NotFoundException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.repo.crud.file.file_record_repo import FileRecordRepository
from app.models.files.file_record import FileRecord
from app.schemas.file.file_record_schemas import FileRecordCreate, FileRecordUpdate, FileRecordRead
from app.schemas.common.page_schemas import PageResponse
from app.schemas.users.user_context import UserContext
from app.services._base_service import BaseService
if TYPE_CHECKING:
    from app.services.file.file_service import FileService


class FileRecordService(BaseService):
    """
    文件记录业务服务层。
    封装了所有与文件元数据 (FileRecord) 相关的业务逻辑和数据库操作。
    这是文件管理模块 API 的主要服务提供者。
    """

    def __init__(self, repo_factory: RepositoryFactory, file_service: "FileService" = Depends()):
        """
        初始化 FileRecordService。

        Args:
            repo_factory (RepositoryFactory): 用于获取 Repository 实例的工厂。
            file_service (FileService): 用于处理与对象存储相关的操作，如此处用于生成 URL。
        """
        super().__init__()
        self.repo_factory = repo_factory
        self.file_service = file_service
        # 【优化】直接在初始化时获取 repo
        self.file_repo: FileRecordRepository = repo_factory.get_repo_by_type(FileRecordRepository)

    # async def _get_repo(self) -> FileRecordRepository:
    #     """辅助方法：获取 FileRecordRepository 的实例。"""
    #     return self.repo_factory.get_repo_by_type(FileRecordRepository)

    # async def _populate_url(self, record: FileRecord) -> FileRecordRead:
    #     """辅助方法：为 FileRecordRead DTO 填充动态生成的 URL。"""
    #     dto = FileRecordRead.from_orm(record)
    #     # 根据记录的 profile_name 和 object_name 生成可访问的 URL
    #     # 注意：对于私有文件，这里可以生成预签名 URL
    #     if record.profile_name in ["secure_reports", "private_files"]:  # 示例私有 profiles
    #         dto.url = await self.file_service.generate_presigned_get_url(
    #             object_name=record.object_name,
    #             profile_name=record.profile_name
    #         )
    #     else:  # 默认生成公开 URL
    #         client = self.file_service.factory.get_client_by_profile(record.profile_name)
    #         dto.url = client.build_final_url(record.object_name)
    #     return dto

    # --- CRUD 操作 ---

    async def create_file_record(self, record_in: FileRecordCreate) -> FileRecord:
        """
        创建一个新的文件记录。
        这里可以封装通用的业务逻辑，例如：
        - 检查用户存储配额
        - 触发病毒扫描任务等
        """
        # 在这里添加任何创建前的通用业务逻辑
        return await self.file_repo.create(record_in)

    async def get_file_record_by_id(self, record_id: UUID) -> Optional[FileRecordRead]:
        """
        根据 ID 获取单个文件记录的详细信息（包含 URL）。
        """
        record = await self.file_repo.get_by_id(record_id)
        if record:
            # 【核心修改】直接使用 model_validate 进行转换，Pydantic 会自动处理 url
            return FileRecordRead.model_validate(record)
        return None

    async def update_file_record(
            self,
            record_id: UUID,
            record_update: FileRecordUpdate,
            commit: bool = True  # <-- 【核心修改】新增 commit 参数，并默认为 True
    ) -> Optional[FileRecordRead]:
        """
        更新文件记录的元数据（例如，重命名）。
        """

        db_record = await self.file_repo.get_by_id(record_id)
        if not db_record:
            return None

        update_data = record_update.model_dump(exclude_unset=True)
        # update 方法只在内存中修改对象
        updated_record_orm = await self.file_repo.update(db_record, update_data)

        # 【核心修改】只有当 commit 为 True 时，才提交事务
        # 这使得此方法既可以独立工作，也可以作为更大事务的一部分
        if commit:
            try:
                await self.file_repo.commit()
                await self.file_repo.refresh(updated_record_orm)
            except Exception as e:
                await self.file_repo.rollback()
                self.logger.error(f"Failed to commit update for file record {record_id}: {e}")
                raise

        # 转换为 DTO 再返回
        return FileRecordRead.model_validate(updated_record_orm)

    async def delete_file_record(self, record_id: UUID) -> bool:
        """
        软删除一个文件记录。
        注意：此操作只删除数据库记录，不删除对象存储中的物理文件。
              物理文件的删除应由 FileService 处理，并由更高层服务协调。
        """
        db_record = await self.file_repo.get_by_id(record_id)
        if db_record:
            await self.file_repo.soft_delete(db_record)
            return True
        return False

    # --- 复杂查询 ---

    async def get_paged_file_records(
            self,
            page: int = 1,
            per_page: int = 10,
            filters: Optional[Dict[str, Any]] = None,
            sort_by: Optional[List[str]] = None,
    ) -> PageResponse[FileRecordRead]:
        """
        获取文件记录的分页列表，并为每条记录生成可访问的 URL。
        这是文件管理模块后端的核心方法。
        """

        # 从 Repository 获取分页的 ORM 对象
        paged_records = await self.file_repo.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,
            sort_by=sort_by
        )

        # 将 ORM 对象列表转换为包含 URL 的 DTO 列表
        dto_items = [FileRecordRead.model_validate(record) for record in paged_records.items]

        # 使用转换后的 DTO 列表构建并返回最终的 PageResponse
        return PageResponse(
            items=dto_items,
            total=paged_records.total,
            page=paged_records.page,
            per_page=paged_records.per_page,
            total_pages=paged_records.total_pages
        )

    async def register_uploaded_file(
            self,
            object_name: str,
            original_filename: str,
            content_type: str,
            file_size: int,
            profile_name: str,
            uploader_context: UserContext,
            etag: Optional[str] = None,
            commit: bool = True  # <-- 【核心修改】新增一个 commit 参数，并默认为 True
    ) -> FileRecord:
        """
        在数据库中登记一个已上传到对象存储的文件。
        这是一个原子性的数据库操作。
        """
        # 1. 安全校验：确认文件确实存在于对象存储中
        if not await self.file_service.file_exists(object_name, profile_name):
            raise NotFoundException("要登记的文件在存储中不存在。")


        # ... 后续使用 file_record_repo 即可 ...
        existing_record = await self.file_repo.get_by_object_name(object_name)
        if existing_record:
            self.logger.warning(f"文件 {object_name} 已被登记，将直接返回现有记录。")
            return existing_record

        # 3. 创建 FileRecordCreate 数据模型
        record_in = FileRecordCreate(
            object_name=object_name,
            original_filename=original_filename,
            file_size=file_size,
            content_type=content_type,
            profile_name=profile_name,
            uploader_id=uploader_context.id,
            etag=etag
        )

        # 4. 在事务中创建记录
        try:
            new_record = await self.file_repo.create(record_in)
            # 【核心修改】只有当 commit 为 True 时，才提交事务
            if commit:
                await self.file_repo.commit()
            return new_record
        except Exception as e:
            await self.file_repo.rollback()
            self.logger.error(f"登记文件 {object_name} 失败: {e}")
            raise
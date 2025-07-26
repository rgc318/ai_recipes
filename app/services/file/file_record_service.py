from typing import List, Optional, Dict, Any
from uuid import UUID

from app.infra.db.repository_factory_auto import RepositoryFactory
from app.repo.crud.file.file_record_repo import FileRecordRepository
from app.models.file_record import FileRecord
from app.schemas.file.file_record_schemas import FileRecordCreate, FileRecordUpdate, FileRecordRead
from app.schemas.common.page_schemas import PageResponse
from app.services.file.file_service import FileService  # 需要 FileService 来生成 URL


class FileRecordService:
    """
    文件记录业务服务层。
    封装了所有与文件元数据 (FileRecord) 相关的业务逻辑和数据库操作。
    这是文件管理模块 API 的主要服务提供者。
    """

    def __init__(self, repo_factory: RepositoryFactory, file_service: FileService):
        """
        初始化 FileRecordService。

        Args:
            repo_factory (RepositoryFactory): 用于获取 Repository 实例的工厂。
            file_service (FileService): 用于处理与对象存储相关的操作，如此处用于生成 URL。
        """
        self.repo_factory = repo_factory
        self.file_service = file_service

    async def _get_repo(self) -> FileRecordRepository:
        """辅助方法：获取 FileRecordRepository 的实例。"""
        return self.repo_factory.get_repo(FileRecordRepository)

    async def _populate_url(self, record: FileRecord) -> FileRecordRead:
        """辅助方法：为 FileRecordRead DTO 填充动态生成的 URL。"""
        dto = FileRecordRead.from_orm(record)
        # 根据记录的 profile_name 和 object_name 生成可访问的 URL
        # 注意：对于私有文件，这里可以生成预签名 URL
        if record.profile_name in ["secure_reports", "private_files"]:  # 示例私有 profiles
            dto.url = await self.file_service.generate_presigned_get_url(
                object_name=record.object_name,
                profile_name=record.profile_name
            )
        else:  # 默认生成公开 URL
            client = self.file_service.factory.get_client_by_profile(record.profile_name)
            dto.url = client.build_final_url(record.object_name)
        return dto

    # --- CRUD 操作 ---

    async def create_file_record(self, record_in: FileRecordCreate) -> FileRecord:
        """
        创建一个新的文件记录。
        这里可以封装通用的业务逻辑，例如：
        - 检查用户存储配额
        - 触发病毒扫描任务等
        """
        file_repo = await self._get_repo()
        # 在这里添加任何创建前的通用业务逻辑
        return await file_repo.create(record_in)

    async def get_file_record_by_id(self, record_id: UUID) -> Optional[FileRecordRead]:
        """
        根据 ID 获取单个文件记录的详细信息（包含 URL）。
        """
        file_repo = await self._get_repo()
        record = await file_repo.get_by_id(record_id)
        if record:
            return await self._populate_url(record)
        return None

    async def update_file_record(
            self, record_id: UUID, record_update: FileRecordUpdate
    ) -> Optional[FileRecordRead]:
        """
        更新文件记录的元数据（例如，重命名）。
        """
        file_repo = await self._get_repo()
        db_record = await file_repo.get_by_id(record_id)
        if not db_record:
            return None

        updated_record = await file_repo.update(db_record, record_update)
        return await self._populate_url(updated_record)

    async def delete_file_record(self, record_id: UUID) -> bool:
        """
        软删除一个文件记录。
        注意：此操作只删除数据库记录，不删除对象存储中的物理文件。
              物理文件的删除应由 FileService 处理，并由更高层服务协调。
        """
        file_repo = await self._get_repo()
        db_record = await file_repo.get_by_id(record_id)
        if db_record:
            await file_repo.soft_delete(db_record)
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
        file_repo = await self._get_repo()

        # 从 Repository 获取分页的 ORM 对象
        paged_records = await file_repo.get_paged_list(
            page=page,
            per_page=per_page,
            filters=filters,
            sort_by=sort_by
        )

        # 将 ORM 对象列表转换为包含 URL 的 DTO 列表
        dto_items = [await self._populate_url(record) for record in paged_records.items]

        # 使用转换后的 DTO 列表构建并返回最终的 PageResponse
        return PageResponse(
            items=dto_items,
            total=paged_records.total,
            page=paged_records.page,
            per_page=paged_records.per_page,
            total_pages=paged_records.total_pages
        )

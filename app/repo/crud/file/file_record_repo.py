from datetime import datetime
from typing import Optional, List, Union, Dict, Any
from uuid import UUID

from sqlalchemy import func, select, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.query_enums import ViewMode
from app.repo.crud.common.base_repo import BaseRepository
from app.models.files.file_record import FileRecord
from app.schemas.file.file_record_schemas import FileRecordCreate, FileRecordUpdate, StorageUsageStats


class FileRecordRepository(BaseRepository[FileRecord, FileRecordCreate, FileRecordUpdate]):
    """
    FileRecordRepository 提供了所有与文件记录数据库操作相关的方法。
    它继承了 BaseRepository 的所有通用功能，并添加了文件记录特有的查询。
    """
    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        """
        初始化 FileRecordRepository。

        Args:
            db (AsyncSession): 数据库会话。
            context (Optional[dict]): 可选的上下文信息。
        """
        super().__init__(db, FileRecord, context)

        # =================================================================
        # ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼ 核心新增功能 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
        # =================================================================

    # async def are_ids_valid(self, ids: List[UUID], view_mode: str = ViewMode.ACTIVE) -> bool:
    #     """
    #     【升级版】高效地检查一组ID是否存在于表中，并符合指定的 view_mode。
    #     """
    #     if not ids:
    #         return True
    #
    #     unique_ids = set(ids)
    #
    #     # 使用 _base_stmt 来正确应用 view_mode 过滤
    #     stmt = self._base_stmt(view_mode=view_mode)
    #     stmt = stmt.with_only_columns(func.count(self.model.id)).where(self.model.id.in_(unique_ids))
    #
    #     result = await self.db.execute(stmt)
    #     existing_count = result.scalar_one()
    #
    #     return existing_count == len(unique_ids)

    # =================================================================
    async def get_by_object_name(self, object_name: str, view_mode: str = ViewMode.ACTIVE) -> Optional[FileRecord]:
        """
        【升级】根据 object_name 获取文件记录，支持 view_mode。
        """
        # find_by_field 也需要支持 view_mode，或者我们在这里直接构建查询
        stmt = self._base_stmt(view_mode=view_mode).where(self.model.object_name == object_name)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete_by_object_name(self, object_name: str) -> Optional[FileRecord]:
        """
        根据 object_name 软删除一个文件记录。
        这个方法是写操作，不需要 view_mode。它总是查找活跃文件来删除。
        """
        # 查找时，我们明确要找 active 的文件
        db_obj = await self.get_by_object_name(object_name, view_mode=ViewMode.ACTIVE)
        if db_obj:
            return await self.soft_delete(db_obj)
        return None

    # --- 如何使用强大的分页查询 ---
    #
    # 您的 BaseRepository.get_paged_list 方法已经非常强大。
    # 您无需在此处编写新的分页方法，只需在 Service 层像这样调用它即可：
    #
    # file_repo = repo_factory.get_repo(FileRecordRepository)
    #
    # # 示例1: 查找某个用户上传的所有文件，按创建时间降序排序
    # user_files_page = await file_repo.get_paged_list(
    #     page=1,
    #     per_page=20,
    #     filters={"uploader_id": current_user.id},
    #     sort_by=["-created_at"]
    # )
    #
    # # 示例2: 查找所有通过 'secure_reports' Profile 上传的 PDF 文件
    # report_files_page = await file_repo.get_paged_list(
    #     page=1,
    #     per_page=50,
    #     filters={
    #         "profile_name": "secure_reports",
    #         "content_type": "application/pdf"
    #     }
    # )
    #
    # # 示例3: 使用更复杂的过滤器，查找文件名包含 "invoice" 的记录
    # invoice_files = await file_repo.get_paged_list(
    #     page=1,
    #     per_page=10,
    #     filters={"original_filename__ilike": "%invoice%"} # 使用 ilike 进行模糊搜索
    # )

    async def find_duplicates_by_etag(self) -> List[Dict[str, Any]]:
        """
        【新增】按 ETag 查找重复的文件记录。
        """
        stmt = (
            select(
                self.model.etag,
                func.count(self.model.id).label('count'),
                func.array_agg(self.model.id).label('ids')  # for PostgreSQL
            )
            .group_by(self.model.etag)
            .having(func.count(self.model.id) > 1)
        )
        result = await self.db.execute(stmt)
        return result.mappings().all()
    async def find_unreferenced_files(
            self,
            older_than: Optional[datetime] = None,
            limit: int = 100,
            view_mode: str = ViewMode.ACTIVE
    ) -> List[FileRecord]:
        """
        【升级】查找孤立文件记录，支持 view_mode。
        """
        if not hasattr(self.model, 'recipe_id'):
            self.logger.warning("Model FileRecord does not have 'recipe_id' attribute. Cannot find unreferenced files.")
            return []

        # <-- [MODIFIED] 将 view_mode 传递给 _base_stmt
        stmt = (
            self._base_stmt(view_mode=view_mode)
            .where(self.model.recipe_id.is_(None))
        )
        if older_than:
            stmt = stmt.where(self.model.created_at < older_than)

        stmt = stmt.order_by(self.model.created_at.asc()).limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_storage_usage_stats(
            self,
            group_by: Optional[str] = None,
            view_mode: str = ViewMode.ACTIVE
    ) -> Union[StorageUsageStats, List[StorageUsageStats]]:
        """
        【升级】获取文件存储使用统计，支持 view_mode。
        """
        if group_by and not hasattr(self.model, group_by):
            raise ValueError(f"Invalid group_by field: {group_by}")

        # <-- [MODIFIED] 将 view_mode 传递给 _base_stmt
        base_stmt = self._base_stmt(view_mode=view_mode)

        if group_by:
            group_by_col = getattr(self.model, group_by)
            stmt = (
                select(
                    group_by_col.label("group_key"),
                    func.count(self.model.id).label("total_files"),
                    func.sum(self.model.file_size_bytes).label("total_size_bytes")
                )
                .select_from(base_stmt.subquery()) # 使用 subquery 保证过滤先生效
                .group_by(group_by_col)
                .order_by(literal_column("total_size_bytes").desc())
            )
            results = await self.db.execute(stmt)
            return [StorageUsageStats(group_key=str(r.group_key), **r._asdict()) for r in results.all()]
        else:
            stmt = select(
                func.count(self.model.id).label("total_files"),
                func.sum(self.model.file_size_bytes).label("total_size_bytes")
            ).select_from(base_stmt.subquery())

            result = await self.db.execute(stmt).one_or_none()
            if result and result.total_files > 0:
                return StorageUsageStats(total_files=result.total_files, total_size_bytes=result.total_size_bytes)
            return StorageUsageStats(total_files=0, total_size_bytes=0)

    async def find_old_soft_deleted_records(self, cutoff_date: datetime, limit: int = 100) -> List[FileRecord]:
        """查找早于指定日期的、已被软删除的记录。"""
        stmt = (
            self._base_stmt(view_mode=ViewMode.DELETED)  # 只在已删除的记录中查找
            .where(self.model.deleted_at < cutoff_date)  # 假设你有 deleted_at 字段
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
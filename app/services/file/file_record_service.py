import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from uuid import UUID

from fastapi import Depends
from sqlalchemy import text

from app.core.exceptions import NotFoundException, BaseBusinessException
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.repo.crud.file.file_record_repo import FileRecordRepository
from app.models.files.file_record import FileRecord, ForeignKeyReference
from app.repo.crud.recipes.recipe_repo import RecipeRepository
from app.repo.crud.users.user_repo import UserRepository
from app.schemas.file.file_record_schemas import FileRecordCreate, FileRecordUpdate, FileRecordRead, \
    FileDeleteCheckResponse
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
    FOREIGN_KEY_REFERENCES: List[Dict[str, Any]] = [
        # type 'direct' -> 直接用 file_record.id 关联
        {"table_name": "recipe", "column_name": "cover_image_id", "type": "direct"},
        {"table_name": "recipe_gallery_link", "column_name": "file_id", "type": "direct"},
        {"table_name": "recipe_step_image_link", "column_name": "file_id", "type": "direct"},

        # type 'indirect' -> 通过 file_record.object_name 关联
        {"table_name": "user", "column_name": "avatar_url", "type": "indirect"},
    ]
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
        【事务重构】创建一个新的文件记录。
        """
        async with self.file_repo.db.begin_nested():
            # 在这里添加任何创建前的通用业务逻辑
            new_record = await self.file_repo.create(record_in)
        return new_record

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
            self, record_id: UUID, record_update: FileRecordUpdate
    ) -> Optional[FileRecordRead]:
        """
        【事务重构】更新文件记录的元数据。
        """
        # [REMOVED] - commit: bool = True 参数已被移除
        db_record = await self.file_repo.get_by_id(record_id)
        if not db_record:
            return None

        async with self.file_repo.db.begin_nested():
            update_data = record_update.model_dump(exclude_unset=True)
            updated_record_orm = await self.file_repo.update(db_record, update_data)

        # [REMOVED] - 手动的 try/except/commit/rollback 块已被移除
        return FileRecordRead.model_validate(updated_record_orm)

    async def is_record_in_use(self, record_id: UUID) -> bool:
        """
        【新增】检查一个文件记录当前是否被任何核心业务模块引用。
        这是我们“黄金法则”的核心实现。
        """
        # 1. 获取要检查的文件记录的完整信息
        record_to_check = await self.file_repo.get_by_id(record_id, view_mode=ViewMode.ALL)
        if not record_to_check:
            return False  # 记录本身不存在，自然未被使用

        # 2. 检查菜谱封面 (保持不变)
        recipe_repo = self.repo_factory.get_repo_by_type(RecipeRepository)
        if await recipe_repo.exists_by_field(record_id, "cover_image_id", view_mode=ViewMode.ALL):
            self.logger.info(f"File record {record_id} is in use as a recipe cover.")
            return True

        # 3. 检查用户头像 (【核心修正】)
        user_repo = self.repo_factory.get_repo_by_type(UserRepository)
        # 我们用文件的 object_name 去 user 表的 avatar_url 字段里查找
        if record_to_check.object_name and await user_repo.exists_by_field(record_to_check.object_name, "avatar_url", view_mode=ViewMode.ALL):
            self.logger.info(f"File record {record_id} is in use as a user avatar.")
            return True

        # 4. 检查菜谱画廊或步骤 (保持不变)
        if await recipe_repo.is_file_in_gallery_or_steps(record_id):
            self.logger.info(f"File record {record_id} is in use in a recipe gallery or step.")
            return True

        self.logger.info(f"File record {record_id} is not in active use.")
        return False



    async def delete_file_record(self, record_id: UUID) -> bool:
        """
        【事务重构】软删除一个文件记录。
        """
        db_record = await self.file_repo.get_by_id(record_id)
        if not db_record:
            return False

        async with self.file_repo.db.begin_nested():
            await self.file_repo.soft_delete(db_record)

        return True

    # --- 复杂查询 ---

    async def get_paged_file_records(
            self,
            page: int = 1,
            per_page: int = 10,
            filters: Optional[Dict[str, Any]] = None,
            sort_by: Optional[List[str]] = None,
            view_mode: str = ViewMode.ACTIVE,
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
            sort_by=sort_by,
            view_mode=view_mode
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
            self, object_name: str, original_filename: str, content_type: str, file_size: int,
            profile_name: str, uploader_context: UserContext, etag: Optional[str] = None
    ) -> FileRecord:
        """
        【事务重构】在数据库中登记一个已上传到对象存储的文件。
        """
        # 1. 外部校验
        if not await self.file_service.file_exists(object_name, profile_name):
            raise NotFoundException("要登记的文件在存储中不存在。")

        existing_record = await self.file_repo.get_by_object_name(object_name)
        if existing_record:
            self.logger.warning(f"文件 {object_name} 已被登记，将直接返回现有记录。")
            return existing_record

        # 2. 核心数据库操作包裹在嵌套事务中
        async with self.file_repo.db.begin_nested():
            record_in = FileRecordCreate(
                object_name=object_name, original_filename=original_filename, file_size=file_size,
                content_type=content_type, profile_name=profile_name, uploader_id=uploader_context.id, etag=etag
            )
            new_record = await self.file_repo.create(record_in)

        return new_record

    async def merge_duplicate_records(
            self,
            source_record_id: UUID,
            target_record_id: UUID
    ) -> FileRecordRead:
        """
        【根据模型优化】合并两个重复的文件记录。

        此方法会智能合并两条记录的元数据，然后将所有对 `source_record_id` 的外键引用
        （根据 FOREIGN_KEY_REFERENCES 配置）更新为 `target_record_id`，
        最后【物理删除】`source_record_id` 对应的记录。
        """
        repo = self.file_repo

        # --- 1. 严格的输入验证 (保持不变) ---
        if source_record_id == target_record_id:
            raise BaseBusinessException(message="源记录和目标记录不能是同一个。")

        self.logger.info(f"开始合并文件记录: source={source_record_id}, target={target_record_id}")

        records = await repo.get_by_ids([source_record_id, target_record_id], view_mode=ViewMode.ALL)
        record_map = {r.id: r for r in records}
        source_record = record_map.get(source_record_id)
        target_record = record_map.get(target_record_id)

        if not source_record or not target_record:
            raise NotFoundException("源记录或目标记录不存在。")

        if source_record.etag != target_record.etag:
            raise BaseBusinessException(message="两条记录 ETag 不匹配，无法合并。")

        # --- 2. 在事务中执行核心逻辑 ---
        async with self.file_repo.db.begin_nested():
            # --- 【【新增】】2.1 智能合并元数据 ---
            # 在删除源记录之前，将它的重要信息“合并”到目标记录中。
            self.logger.info("正在合并记录元数据...")

            # 逻辑：如果源记录是关联状态，那么目标记录也应该是。
            should_update_target = False
            if source_record.is_associated and not target_record.is_associated:
                target_record.is_associated = True
                should_update_target = True
                self.logger.info(f"目标记录 {target_record_id} 的 is_associated 已更新为 True。")

            # 你可以在这里添加其他字段的合并逻辑，例如：
            # if not target_record.original_filename and source_record.original_filename:
            #     target_record.original_filename = source_record.original_filename
            #     should_update_target = True

            if should_update_target:
                # 注意：这里我们只在内存中更新，最后由 commit() 一并提交
                repo.db.add(target_record)

            # --- 2.2 更新外键引用 (保持不变，以策万全) ---
            # 如果 FOREIGN_KEY_REFERENCES 为空，这个循环会直接跳过，是安全的。
            for ref in self.FOREIGN_KEY_REFERENCES:
                table, column, ref_type = ref['table_name'], ref['column_name'], ref.get('type', 'direct')
                self.logger.info(f"正在更新表 '{table}' 中的外键 '{column}' (类型: {ref_type})...")

                # 准备参数
                params = {}
                where_clause = ""
                set_clause = ""

                if ref_type == 'direct':
                    # 直接关联：用 target_id 替换 source_id
                    set_clause = f'"{column}" = :target_val'
                    where_clause = f'"{column}" = :source_val'
                    params = {"target_val": target_record_id, "source_val": source_record_id}

                elif ref_type == 'indirect':
                    # 间接关联：用 target_record.object_name 替换 source_record.object_name
                    set_clause = f'"{column}" = :target_val'
                    where_clause = f'"{column}" = :source_val'
                    params = {
                        "target_val": target_record.object_name,
                        "source_val": source_record.object_name
                    }

                if not set_clause or not where_clause:
                    continue

                update_statement = text(f'UPDATE "{table}" SET {set_clause} WHERE {where_clause}')
                await repo.db.execute(update_statement, params)

            # --- 2.3 物理删除源记录 (保持不变) ---
            self.logger.info(f"正在物理删除源记录 {source_record_id}...")
            await repo.hard_delete(source_record)

        # --- 3. 返回刷新后的目标记录 ---
        return FileRecordRead.model_validate(target_record)

    async def restore_file_record(self, record_id: UUID) -> Optional[FileRecordRead]:
        """
        【新增】恢复一个被软删除的文件记录。
        """
        repo = self.file_repo

        # 1. 查找时，必须在已删除的记录中查找
        db_record = await repo.get_by_id(record_id, view_mode=ViewMode.DELETED)
        if not db_record:
            self.logger.warning(f"尝试恢复一个不存在或未被删除的记录: {record_id}")
            return None  # 或者抛出 NotFoundException

        # 2. 使用事务包裹恢复操作
        async with repo.db.begin_nested():
            restored_record = await repo.restore(db_record)

        return FileRecordRead.model_validate(restored_record)

    async def restore_file_records_by_ids(self, record_ids: List[UUID]) -> int:
        """
        【新增】根据ID列表，批量恢复被软删除的文件记录。

        Returns:
            成功恢复的记录数量。
        """
        if not record_ids:
            return 0

        repo = self.file_repo

        async with repo.db.begin_nested():
            # 底层 repo.restore_by_ids 已经处理了只恢复 is_deleted=True 的逻辑
            restored_count = await repo.restore_by_ids(record_ids)

        self.logger.info(f"批量恢复了 {restored_count} 条文件记录。")
        return restored_count

    async def delete_file_and_record(self, record: FileRecord, hard_delete_db: bool = True):
        """一个辅助方法，先删文件，再删记录"""
        # 1. 删除真实文件
        await self.file_service.delete_file(record.object_name, record.profile_name)
        # 2. 删除数据库记录
        repo = self.file_repo
        async with repo.db.begin_nested():
            if hard_delete_db:
                await repo.hard_delete(record)
            else:  # 软删除（虽然在这里不常用，但保持灵活性）
                await repo.soft_delete(record)

    async def cleanup_old_soft_deleted_files(self, days: int = 30) -> Dict[str, int]:
        """
        【新增】清理超过指定天数的、已被软删除的文件和记录。
        此方法应由后台定时任务调用。
        """
        self.logger.info(f"开始执行后台清理任务：清理超过 {days} 天的已软删除文件...")
        repo = self.file_repo
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 为了避免一次性加载过多记录，可以循环处理
        total_cleaned = 0
        while True:
            records_to_clean = await repo.find_old_soft_deleted_records(cutoff_date, limit=100)
            if not records_to_clean:
                break

            self.logger.info(f"找到 {len(records_to_clean)} 条待清理的旧记录。")
            for record in records_to_clean:
                try:
                    await self.delete_file_and_record(record, hard_delete_db=True)
                    total_cleaned += 1
                except Exception as e:
                    self.logger.error(
                        f"清理记录 {record.id} (object_name: {record.object_name}) 时失败: {e}",
                        exc_info=True
                    )

            if len(records_to_clean) < 100:
                break  # 处理完最后一批

        self.logger.info(f"后台清理任务完成。总共清理了 {total_cleaned} 个文件和记录。")
        return {"cleaned_count": total_cleaned}

    async def move_file_and_update_record(
            self,
            record_id: UUID,
            destination_key: str,
            profile_name: str  # 需要 profile_name 来调用 FileService
    ) -> FileRecordRead:
        """
        【新增】一个通用的、带事务保证的文件移动方法。
        它负责编排物理文件移动和数据库记录更新。
        """
        # 1. 获取要移动的记录
        record = await self.file_repo.get_by_id(record_id)
        if not record:
            raise NotFoundException(f"File record {record_id} not found.")

        source_key = record.object_name
        if source_key == destination_key:
            self.logger.warning("Source and destination keys are the same. No move needed.")
            return FileRecordRead.model_validate(record)

        # 2. 【核心】先执行外部I/O操作（移动物理文件）
        # 如果这一步失败，会直接抛出异常，根本不会触及下面的数据库操作，保证了数据一致性。
        await self.file_service.move_physical_file(
            source_key=source_key,
            destination_key=destination_key,
            profile_name=profile_name
        )

        # 3. 物理文件移动成功后，在一个事务中更新数据库记录
        # 我们直接调用职责单一的 update_object_name 方法
        updated_record_dto = await self.update_object_name(
            record_id=record_id,
            new_object_name=destination_key
        )

        return updated_record_dto

    async def update_object_name(self, record_id: UUID, new_object_name: str) -> FileRecordRead:
        """
        【职责单一】只负责更新数据库中一条记录的 object_name。
        这是一个底层的、事务性的构建块，主要由本服务中的 move_file_and_update_record 方法编排调用。
        """
        db_record = await self.file_repo.get_by_id(record_id)
        if not db_record:
            raise NotFoundException(f"Cannot update object_name: Record {record_id} not found.")

        async with self.file_repo.db.begin_nested():
            # 使用 update 方法来更新字段
            updated_record = await self.file_repo.update(db_record, {"object_name": new_object_name})

        return FileRecordRead.model_validate(updated_record)

    async def validate_records_for_permanent_delete(self, record_ids: List[UUID]):
        """
        【新增】在批量永久删除前，验证所有记录是否都未被使用。
        如果任何一个记录被使用，则抛出异常。
        """
        in_use_records = []
        # 为了效率，我们可以并发执行检查
        tasks = [self.file_repo.get_by_id(rec_id, view_mode=ViewMode.ALL) for rec_id in record_ids]
        records = await asyncio.gather(*tasks)

        for record in records:
            if record and await self.is_record_in_use(record.id):
                in_use_records.append(record.original_filename)

        if in_use_records:
            # 发现有关联的记录，构造详细的错误信息并抛出异常
            error_message = (
                f"操作被终止，因为以下 {len(in_use_records)} 个文件仍被使用，无法删除: "
                f"{', '.join(in_use_records)}"
            )
            raise BaseBusinessException(message=error_message)

    async def soft_delete_records_by_ids(self, record_ids: List[UUID]) -> int:
        """
        【新增】根据ID列表，批量软删除文件记录。
        """
        if not record_ids:
            return 0

        repo = self.file_repo
        async with repo.db.begin_nested():
            # BaseRepository 中已经有现成的高效方法
            deleted_count = await repo.soft_delete_by_ids(record_ids)

        self.logger.info(f"批量软删除了 {deleted_count} 条文件记录。")
        return deleted_count

    async def permanent_delete_records_by_ids(self, record_ids: List[UUID]) -> int:
        """
        【新增】根据ID列表，批量彻底删除文件记录及其物理文件。
        这是一个高危操作的业务流程编排。
        """
        if not record_ids:
            return 0

        repo = self.file_repo

        # 1. 首先，从数据库中获取这些记录的完整信息 (特别是 object_name 和 profile_name)
        #    get_by_ids 默认只查找活跃的，但我们需要能删除任何状态的，所以用 view_mode='all'
        records_to_delete = await repo.get_by_ids(record_ids, view_mode=ViewMode.ALL)
        if not records_to_delete:
            self.logger.warning(f"尝试批量永久删除，但未找到任何有效记录。IDs: {record_ids}")
            return 0

        # 2. 提取所有需要删除的物理文件的 object_name
        #    为了效率，我们可以按 profile 分组
        objects_by_profile: Dict[str, List[str]] = {}
        for record in records_to_delete:
            if record.profile_name not in objects_by_profile:
                objects_by_profile[record.profile_name] = []
            objects_by_profile[record.profile_name].append(record.object_name)

        # 3. 调用 FileService 批量删除物理文件
        try:
            for profile_name, object_names in objects_by_profile.items():
                await self.file_service.delete_files(object_names, profile_name)
        except Exception as e:
            self.logger.error(f"批量永久删除过程中，删除物理文件失败: {e}", exc_info=True)
            # 物理文件删除失败，我们不应该继续删除数据库记录，直接抛出异常
            raise BaseBusinessException(message="删除存储中的部分文件失败，操作已终止。")

        # 4. 物理文件都成功删除后，在一个事务中批量硬删除数据库记录
        db_ids_to_delete = [record.id for record in records_to_delete]
        async with repo.db.begin_nested():
            deleted_count = await repo.hard_delete_by_ids(db_ids_to_delete)

        self.logger.info(f"批量永久删除了 {deleted_count} 个文件和记录。")
        return deleted_count

    async def check_and_soft_delete_records(
        self, record_ids: List[UUID], force: bool = False
    ) -> FileDeleteCheckResponse:
        """
        一个智能的软删除方法，专门给文件管理API使用。
        它会检查文件使用情况，并根据 force 参数决定行为。
        """
        if not record_ids:
            return FileDeleteCheckResponse(status="success", message="没有需要删除的文件。", safe_to_delete_count=0)

        repo = self.file_repo

        # --- 1. 如果不是强制删除，则先进行使用检查 ---
        if not force:
            records_to_check = await repo.get_by_ids(record_ids, view_mode=ViewMode.ACTIVE)

            in_use_map: Dict[UUID, str] = {}
            safe_to_delete_ids: List[UUID] = []

            # 并发检查以提高效率
            check_tasks = {record.id: self.is_record_in_use(record.id) for record in records_to_check}
            results = await asyncio.gather(*check_tasks.values())

            record_map = {r.id: r for r in records_to_check}
            for (record_id, task), is_in_use in zip(check_tasks.items(), results):
                if is_in_use:
                    in_use_map[record_id] = record_map[record_id].original_filename
                else:
                    safe_to_delete_ids.append(record_id)

            # --- 2. 根据检查结果，决定下一步行为 ---
            if in_use_map:
                # 发现有文件正在被使用
                deleted_count_now = 0
                # a) 如果同时有可以安全删除的文件，先把它们删掉
                if safe_to_delete_ids:
                    deleted_count_now = await self.soft_delete_records_by_ids(safe_to_delete_ids)

                # b) 返回一个警告，要求用户确认
                message = (
                    f"操作部分完成。成功删除 {deleted_count_now} 个未被使用的文件。 "
                    f"但有 {len(in_use_map)} 个文件正在被使用，需要您确认是否删除。"
                )
                return FileDeleteCheckResponse(
                    status="warning",
                    message=message,
                    needs_confirmation=True,
                    in_use_files=list(in_use_map.values()),
                    safe_to_delete_count=deleted_count_now,
                    in_use_count=len(in_use_map)
                )

        # --- 3. 如果是强制删除，或者预检通过（即所有文件都可安全删除），则直接删除所有 ---
        deleted_count = await self.soft_delete_records_by_ids(record_ids)
        return FileDeleteCheckResponse(
            status="success",
            message=f"成功软删除了 {deleted_count} 个文件。",
            safe_to_delete_count=deleted_count
        )

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.crud.base_repo import BaseRepository
from app.models.user import Permission
from app.schemas.permission_schemas import PermissionCreate, PermissionUpdate

logger = logging.getLogger(__name__)


class PermissionRepository(BaseRepository[Permission, PermissionCreate, PermissionUpdate]):
    """
    企业级权限模型数据仓库 (Enterprise-Grade Permission Repository)。

    该仓库封装了所有与 Permission 表相关的数据库操作。
    它继承了 BaseRepository 的所有标准 CRUD 功能，并在此基础上提供了
    针对权限管理业务的、高效且便利的专用方法。

    关键特性:
    - 提供按唯一代码(code)进行查询的核心方法。
    - 支持高效的批量查询 (get_many_by_codes)。
    - 包含 "get_or_create" 模式，用于数据种子或动态权限创建。
    - 提供优化的批量 "get_or_create" 方法，用于系统初始化。
    - 所有写操作均不提交事务，将事务控制权完全交由服务层。
    """

    def __init__(self, db: AsyncSession, context: Optional[dict] = None):
        """
        初始化权限仓库。

        Args:
            db: SQLAlchemy 异步会话。
            context: 可选的上下文信息，用于日志或多租户等。
        """
        super().__init__(db, Permission, context)

    # --- 核心查询方法 (Core Query Methods) ---

    async def get_by_code(self, code: str) -> Optional[Permission]:
        """
        根据权限的唯一代码获取权限。
        这是在程序中最常用的权限查询方法。

        Args:
            code: 权限的唯一代码 (e.g., 'orders:create')。

        Returns:
            找到的 Permission 对象或 None。
        """
        return await self.get_one(value=code, field="code")

    async def get_many_by_codes(self, codes: List[str]) -> List[Permission]:
        """
        根据一个代码列表，批量获取权限对象。
        这是一个高效的查询，使用单次数据库调用代替多次循环调用。

        Args:
            codes: 一个包含权限代码的列表。

        Returns:
            找到的权限对象列表。
        """
        if not codes:
            return []

        # de-duplicate codes to avoid redundant work
        unique_codes = list(set(codes))

        stmt = self._base_stmt().where(self.model.code.in_(unique_codes))
        return await self._run_and_scalars(stmt, "get_many_by_codes")

    async def list_by_group(self, group: str) -> List[Permission]:
        """
        获取指定分组下的所有权限。
        常用于在前端UI中按类别展示权限列表。

        Args:
            group: 权限的分组名称。

        Returns:
            属于该分组的权限对象列表。
        """
        stmt = self._base_stmt().where(self.model.group == group).order_by(self.model.name)
        return await self._run_and_scalars(stmt, "list_by_group")

    # --- 业务便利方法 (Business Convenience Methods) ---

    async def get_or_create(self, code: str, defaults: Optional[Dict[str, Any]] = None) -> Tuple[Permission, bool]:
        """
        根据唯一代码获取，或者在不存在时创建权限。
        这是数据播种(seeding)或动态注册权限时的关键方法。

        Args:
            code: 用于查询或创建的唯一权限代码。
            defaults: 如果权限需要被创建，这些字段将被用于新对象。
                      通常包含 'name', 'group', 'description'。

        Returns:
            一个元组 (tuple)，包含:
            - permission_obj (Permission): 找到或新创建的权限对象。
            - created (bool): 如果是新创建的则为 True，否则为 False。
        """
        instance = await self.get_by_code(code)
        if instance:
            return instance, False

        logger.info(f"Permission with code '{code}' not found, creating new one.")
        create_data = defaults or {}
        create_data['code'] = code  # 确保 code 被设置

        # 使用基类的 create 方法，它会 flush 但不 commit
        instance = await self.create(create_data)

        return instance, True

    async def bulk_get_or_create(self, permissions_data: List[Dict[str, Any]]) -> List[Permission]:
        """
        批量获取或创建权限。
        这是一个高度优化的方法，用于系统初始化时高效地同步大量权限。
        它最多只执行一次读查询和一次写查询。

        Args:
            permissions_data: 一个字典列表，每个字典描述一个权限。
                              每个字典必须包含 'code' 键。
                              e.g., [{'code': 'orders:read', 'name': '查看订单'}, ...]

        Returns:
            一个包含所有已找到和新创建的权限对象的列表。
        """
        if not permissions_data:
            return []

        codes_to_check = [p.get('code') for p in permissions_data if p.get('code')]
        if not codes_to_check:
            raise ValueError("No valid 'code' found in permissions_data.")

        existing_permissions = await self.get_many_by_codes(codes_to_check)
        existing_codes_map = {p.code: p for p in existing_permissions}

        new_permissions_to_create: List[Dict[str, Any]] = []
        final_permission_list: List[Permission] = list(existing_permissions)

        for p_data in permissions_data:
            code = p_data.get('code')
            if code and code not in existing_codes_map:
                new_permissions_to_create.append(p_data)

        if new_permissions_to_create:
            logger.info(f"Creating {len(new_permissions_to_create)} new permissions in bulk.")
            # 使用基类的批量创建方法
            created_instances = await self.create_many(
                [PermissionCreate(**data) for data in new_permissions_to_create]
            )
            final_permission_list.extend(created_instances)

        return final_permission_list

    async def sync_from_config(
            self, permissions_data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        根据给定的配置数据，完整地同步权限表。
        处理新增、更新和软删除（禁用）三种情况。
        """
        if not permissions_data:
            return {'added': 0, 'updated': 0, 'disabled': 0}

        source_codes = {p['code'] for p in permissions_data if 'code' in p}
        source_map = {p['code']: p for p in permissions_data if 'code' in p}

        # 1. 获取数据库中所有【未被删除】的权限
        stmt = self._base_stmt()  # self._base_stmt() 会自动添加 is_deleted = false
        result = await self.db.execute(stmt)
        db_permissions = result.scalars().all()
        db_map = {p.code: p for p in db_permissions}
        db_codes = set(db_map.keys())

        # 2. 计算差异
        codes_to_add = source_codes - db_codes
        codes_to_disable = db_codes - source_codes
        codes_to_check_update = source_codes.intersection(db_codes)

        added_count = 0
        updated_count = 0
        disabled_count = 0

        # 3. 处理新增
        if codes_to_add:
            new_perms_data = [source_map[code] for code in codes_to_add]
            new_objs = [self.model(**data) for data in new_perms_data]
            self.db.add_all(new_objs)
            await self.db.flush()
            added_count = len(new_objs)
            logger.info(f"权限同步：新增 {added_count} 个权限。")

        # 4. 处理禁用 (软删除)
        if codes_to_disable:
            disable_stmt = (
                update(self.model)
                .where(self.model.code.in_(codes_to_disable))
                .values(is_deleted=True, updated_at=datetime.now(timezone.utc))
            )
            res = await self.db.execute(disable_stmt)
            disabled_count = res.rowcount
            logger.info(f"权限同步：禁用了 {disabled_count} 个过时的权限。")

        # 5. 【修正】处理更新，增加对 group 字段的检查
        for code in codes_to_check_update:
            db_perm = db_map[code]
            source_perm_data = source_map[code]

            # 检查 name, description 或 group 是否有变化
            if (db_perm.name != source_perm_data.get('name') or
                    db_perm.description != source_perm_data.get('description') or
                    db_perm.group != source_perm_data.get('group')):  # <-- 新增 group 检查

                # 更新所有可能变化的元数据字段
                db_perm.name = source_perm_data.get('name', db_perm.name)
                db_perm.description = source_perm_data.get('description', db_perm.description)
                db_perm.group = source_perm_data.get('group', db_perm.group)  # <-- 新增 group 更新

                self.db.add(db_perm)
                updated_count += 1

        if updated_count > 0:
            await self.db.flush()
            logger.info(f"权限同步：更新了 {updated_count} 个权限的元数据。")

        return {'added': added_count, 'updated': updated_count, 'disabled': disabled_count}

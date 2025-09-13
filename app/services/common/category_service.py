# app/services/common/category_service.py

from typing import Dict, Any, List, Optional
from uuid import UUID
from slugify import slugify  # 需要安装：pip install python-slugify
from sqlalchemy import select, func

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException, \
    PermissionDeniedException
from app.enums.query_enums import ViewMode
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.common.category_model import Category, RecipeCategoryLink
from app.repo.crud.recipes.recipe_repo import RecipeRepository
from app.schemas.common.category_schemas import CategoryCreate, CategoryUpdate, CategoryRead, CategoryReadWithChildren, \
    CategoryParentRead, CategoryMergePayload
from app.repo.crud.common.category_repo import CategoryRepository
from app.repo.crud.common.base_repo import PageResponse
from app.services._base_service import BaseService
from app.schemas.users.user_context import UserContext
from app.core.permissions.category.category_permission import category_policy  # 假设已创建


class CategoryService(BaseService):
    """
    CategoryService 负责处理所有与分类相关的业务逻辑。
    """

    def __init__(self, factory: RepositoryFactory, current_user: Optional[UserContext] = None):
        super().__init__()
        self.factory = factory
        self.current_user = current_user

        # 将用户上下文传递给 repo 以实现自动化的审计字段填充
        user_context_dict = {"user_id": self.current_user.id if self.current_user else None}
        self.category_repo: CategoryRepository = factory.get_repo_by_type(CategoryRepository)
        self.category_repo: CategoryRepository = factory.get_repo_by_type(CategoryRepository)
        self.recipe_repo: RecipeRepository = factory.get_repo_by_type(RecipeRepository)

    async def get_category_by_id(self, category_id: UUID) -> Category:
        """获取单个分类，未找到则抛出异常。"""
        category = await self.category_repo.get_by_id(category_id)
        if not category:
            raise NotFoundException("分类不存在")

        # 权限检查
        if self.current_user:
            category_policy.can_view(self.current_user, category, "分类")

        return category

    async def get_category_tree(self) -> List[CategoryReadWithChildren]:
        """获取完整的分类树，并转换为 DTO。"""
        # 权限检查
        if self.current_user:
            category_policy.can_list(self.current_user, Category)

        root_categories_orm = await self.category_repo.get_category_tree()

        # 递归地将 ORM 对象转换为 Pydantic DTO
        def to_dto(category: Category) -> CategoryReadWithChildren:
            # 【核心修正】在转换时，一并处理 parent 关系
            parent_dto = None
            if category.parent:
                parent_dto = CategoryParentRead.model_validate(category.parent)

            return CategoryReadWithChildren(
                id=category.id,
                name=category.name,
                slug=category.slug,
                description=category.description,
                parent_id=category.parent_id,
                parent=parent_dto, # <-- 将转换后的 parent_dto 赋值
                children=[to_dto(child) for child in category.children]
            )

        return [to_dto(root) for root in root_categories_orm]

    async def page_list_categories(
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any], view_mode: str # <--【新增】view_mode
    ) -> PageResponse[CategoryRead]:
        if self.current_user:
            category_policy.can_list(self.current_user, Category)

        paged_response = await self.category_repo.get_paged_categories(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}, view_mode=view_mode # <--【新增】view_mode
        )
        # Repo 层已处理 DTO 转换，这里无需再转换
        return paged_response

    async def create_category(self, category_in: CategoryCreate) -> Category:
        """创建新分类，并自动处理 slug 和重名校验。"""
        # 权限检查
        if not self.current_user:
            raise PermissionDeniedException("需要登录才能创建分类")
        category_policy.can_create(self.current_user, Category)

        # 业务规则：slug 应该是唯一的
        if await self.category_repo.find_by_slug(category_in.slug):
            raise AlreadyExistsException(f"Slug '{category_in.slug}' 已存在")

        # 业务规则：同一层级下，分类名称不能重复
        # (此逻辑可以根据产品需求进一步完善)

        # 业务规则：如果 parent_id 存在，必须确保它是一个有效的分类ID
        if category_in.parent_id:
            parent_category = await self.category_repo.get_by_id(category_in.parent_id)
            if not parent_category:
                raise NotFoundException("指定的父分类不存在")

        async with self.category_repo.db.begin_nested():  # <--【修正】使用 begin_nested
            new_category_orm = await self.category_repo.create(category_in)
            # 刷新以确保关系可用
            await self.category_repo.refresh(new_category_orm)

        # 提交后重新获取，以加载 parent 关系
        created_category_with_relations = await self.category_repo.get_by_id_with_parent(new_category_orm.id)
        if not created_category_with_relations:
            raise NotFoundException("创建分类后未能立即找到，请重试。")
        return created_category_with_relations

    async def update_category(self, category_id: UUID, category_in: CategoryUpdate) -> Category:
        """更新分类信息。"""
        category_to_update = await self.get_category_by_id(category_id)

        # 权限检查
        if not self.current_user:
            raise PermissionDeniedException("需要登录才能更新分类")
        category_policy.can_update(self.current_user, category_to_update)

        update_data = category_in.model_dump(exclude_unset=True)

        # 业务规则：如果 slug 被修改，需要检查新 slug 的唯一性
        if "slug" in update_data and update_data["slug"] != category_to_update.slug:
            if await self.category_repo.find_by_slug(update_data["slug"]):
                raise AlreadyExistsException(f"Slug '{update_data['slug']}' 已存在")

        # 业务规则：不允许将分类的父节点设置为其自身或其子孙节点
        if "parent_id" in update_data:
            if category_id == update_data["parent_id"]:
                raise BusinessRuleException("不能将分类设置为自身的父分类")

            if update_data["parent_id"]:
                descendants = await self.category_repo.get_descendants_cte(category_id)
                descendant_ids = {desc.id for desc in descendants}
                if update_data["parent_id"] in descendant_ids:
                    raise BusinessRuleException("不能将分类移动到其自己的子分类下")

        async with self.category_repo.db.begin_nested():  # <--【修正】使用 begin_nested
            await self.category_repo.update(category_to_update, update_data)

        refetched_category = await self.category_repo.get_by_id_with_parent(category_id)
        if not refetched_category:
            raise NotFoundException("更新后未能找到分类。")
        return refetched_category

    async def delete_category(self, category_id: UUID) -> None:
        """【修正后】软删除分类，并进行使用情况检查。"""
        async with self.category_repo.db.begin_nested():
            category_to_delete = await self.get_category_by_id(category_id)
            if not self.current_user:
                raise PermissionDeniedException("需要登录才能删除分类")
            category_policy.can_delete(self.current_user, category_to_delete)

            # [核心修正] 使用 count 查询代替不存在的 exists 方法
            children_count_stmt = select(func.count(Category.id)).where(Category.parent_id == category_id)
            children_count = await self.category_repo.db.scalar(children_count_stmt)
            if children_count > 0:
                raise BusinessRuleException("无法删除，请先删除其所有子分类")

            # 业务规则：不允许删除已关联菜谱的分类 (这部分逻辑是正确的)
            count_stmt = select(func.count(RecipeCategoryLink.recipe_id)).where(
                RecipeCategoryLink.category_id == category_id)
            usage_count = await self.category_repo.db.scalar(count_stmt)
            if usage_count > 0:
                raise BusinessRuleException(f"无法删除，该分类正在被 {usage_count} 个菜谱使用")

            await self.category_repo.soft_delete(category_to_delete)

    async def merge_categories(self, payload: CategoryMergePayload) -> dict:
        """
        【升级后】将多个源分类合并到一个目标分类，并正确处理层级关系。
        """
        source_ids = list(set(payload.source_category_ids))
        target_id = payload.target_category_id

        if not source_ids:
            raise BusinessRuleException("必须提供至少一个源分类ID。")
        if target_id in source_ids:
            raise BusinessRuleException("目标分类不能是被合并的源分类之一。")

        async with self.category_repo.db.begin_nested():
            # 1. 基础校验：确保所有ID都真实存在
            if not await self.category_repo.are_ids_valid(source_ids + [target_id]):
                raise NotFoundException("一个或多个指定的分类ID不存在。")

            # 2. [核心安全检查] 检查目标分类是否是源分类的子孙，防止循环引用
            for source_id in source_ids:
                descendants = await self.category_repo.get_descendants_cte(source_id)
                descendant_ids = {desc.id for desc in descendants}
                if target_id in descendant_ids:
                    raise BusinessRuleException(f"操作失败：不能将父分类合并到其子分类下。")

            # 3. [核心逻辑] 将所有源分类的子节点，“过继”给目标分类
            #    我们使用 update 语句来高效地批量修改 parent_id
            await self.category_repo.reparent_children(
                current_parent_ids=source_ids,
                new_parent_id=target_id
            )

            # 4. 重新映射菜谱关联 (这部分逻辑是正确的)
            recipe_ids_to_remap = await self.category_repo.get_recipe_ids_for_categories(source_ids)
            if recipe_ids_to_remap:
                 await self.recipe_repo.add_categories_to_recipes(recipe_ids_to_remap, [target_id])

            # 5. 清理旧的关联关系并软删除源分类
            await self.category_repo.delete_links_for_categories(source_ids)
            deleted_count = await self.category_repo.soft_delete_by_ids(source_ids)

        return {"merged_count": deleted_count}

    async def batch_delete_categories(self, category_ids: List[UUID]) -> int:
        """【修正后】批量软删除分类，并进行严格的使用情况检查。"""
        if not category_ids:
            return 0
        unique_ids = list(set(category_ids))

        async with self.category_repo.db.begin_nested():
            # 1. 校验ID都存在
            if not await self.category_repo.are_ids_valid(unique_ids):
                raise NotFoundException("一个或多个要删除的分类不存在。")

            # 2. 高效地一次性检查所有分类是否有关联的子分类
            children_check_stmt = select(func.count(Category.id)).where(Category.parent_id.in_(unique_ids))
            children_count = await self.category_repo.db.scalar(children_check_stmt)
            if children_count > 0:
                raise BusinessRuleException("操作失败：选中的分类中，有分类包含子分类。")

            # 3. 高效地一次性检查所有分类是否关联了菜谱
            recipe_link_check_stmt = select(func.count(RecipeCategoryLink.id)).where(
                RecipeCategoryLink.category_id.in_(unique_ids))
            usage_count = await self.category_repo.db.scalar(recipe_link_check_stmt)
            if usage_count > 0:
                raise BusinessRuleException("操作失败：选中的分类中，有分类仍被菜谱使用。")

            # 4. 执行批量软删除
            deleted_count = await self.category_repo.soft_delete_by_ids(unique_ids)

        return deleted_count

    async def restore_categories(self, category_ids: List[UUID]) -> int:
        """【增强后】批量恢复被软删除的分类。"""
        if not category_ids:
            return 0
        unique_ids = list(set(category_ids))

        async with self.category_repo.db.begin_nested():
            # [新增] 校验这些 ID 是否确实是已删除状态
            categories_to_restore = await self.category_repo.get_by_ids(unique_ids, view_mode=ViewMode.DELETED.value)
            if len(categories_to_restore) != len(unique_ids):
                raise NotFoundException("一个或多个要恢复的分类不存在于回收站中。")

            restored_count = await self.category_repo.restore_by_ids(unique_ids)

        return restored_count

    async def hard_delete_categories(self, category_ids: List[UUID]) -> int:
        if not category_ids:
            return 0
        async with self.category_repo.db.begin_nested():
            # 永久删除前，必须先删除中间表关联
            await self.category_repo.delete_links_for_categories(category_ids)
            deleted_count = await self.category_repo.hard_delete_by_ids(category_ids)
        return deleted_count
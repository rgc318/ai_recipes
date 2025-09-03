# app/services/common/category_service.py

from typing import Dict, Any, List, Optional
from uuid import UUID
from slugify import slugify  # 需要安装：pip install python-slugify

from app.core.exceptions import NotFoundException, AlreadyExistsException, BusinessRuleException, \
    PermissionDeniedException
from app.infra.db.repository_factory_auto import RepositoryFactory
from app.models.common.category_model import Category
from app.schemas.common.category_schemas import CategoryCreate, CategoryUpdate, CategoryRead, CategoryReadWithChildren, \
    CategoryParentRead
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
            self, page: int, per_page: int, sort_by: List[str], filters: Dict[str, Any]
    ) -> PageResponse[CategoryRead]:
        """获取分类的分页列表（后台管理使用）。"""
        # 权限检查
        if self.current_user:
            category_policy.can_list(self.current_user, Category)

        paged_orm = await self.category_repo.get_paged_categories(
            page=page, per_page=per_page, sort_by=sort_by, filters=filters or {}
        )
        paged_orm.items = [CategoryRead.model_validate(item) for item in paged_orm.items]
        return paged_orm

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

        try:
            new_category_orm = await self.category_repo.create(category_in)
            await self.category_repo.commit()

            # ▼▼▼▼▼ 【核心修正】在这里添加重新查询的逻辑 ▼▼▼▼▼
            # 为了安全地返回带有预加载关系的DTO，我们在提交后重新获取一次刚刚创建的对象。
            # 这次获取会使用我们之前创建的、能够预加载 parent 的方法。
            created_category_with_relations = await self.category_repo.get_by_id_with_parent(new_category_orm.id)
            if not created_category_with_relations:
                # 这种情况很少发生，但作为健壮性检查是好的
                raise NotFoundException("创建分类后未能立即找到，请重试。")

            return created_category_with_relations
            # ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
        except Exception as e:
            self.logger.error(f"创建分类失败: {e}")
            await self.category_repo.rollback()
            raise e

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

        try:
            await self.category_repo.update(category_to_update, update_data)
            await self.category_repo.commit()

            # 【核心修正 - 备选方案】
            # 提交后，重新查询一次这个对象，并明确预加载 parent 关系
            refetched_category = await self.category_repo.get_by_id_with_parent(category_id)
            if not refetched_category:
                raise NotFoundException("更新后未能找到分类，可能出现并发问题。")

            return refetched_category
        except Exception as e:
            self.logger.error(f"更新分类 {category_id} 失败: {e}")
            await self.category_repo.rollback()
            raise e

    async def delete_category(self, category_id: UUID) -> None:
        """删除分类。"""
        category_to_delete = await self.get_category_by_id(category_id)

        # 权限检查
        if not self.current_user:
            raise PermissionDeniedException("需要登录才能删除分类")
        category_policy.can_delete(self.current_user, category_to_delete)

        # 业务规则：如果一个分类下有子分类，通常不允许直接删除
        # (这里我们依赖数据库的级联删除，但也可以在业务层进行检查)
        # if category_to_delete.children:
        #     raise BusinessRuleException("无法删除，请先删除其所有子分类")

        try:
            await self.category_repo.delete(category_to_delete)  # 物理删除
            await self.category_repo.commit()
        except Exception as e:
            self.logger.error(f"删除分类 {category_id} 失败: {e}")
            await self.category_repo.rollback()
            raise e
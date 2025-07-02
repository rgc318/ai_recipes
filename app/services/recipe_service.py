from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.recipe_repo import RecipeCRUD
from app.models.recipe import Recipe  # 导入 Recipe ORM 模型
# 注意：确保 RecipeCreate 和 RecipeUpdate 是从正确的文件导入的
from app.schemas.recipe_schemas import RecipeCreate, RecipeUpdate


class RecipeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.recipe_repo = RecipeCRUD(session)

    async def list_recipes(self) -> Sequence[Recipe]:
        """
        获取所有未被删除的菜谱，包含标签、配料与单位。
        """
        return await self.recipe_repo.get_all()

    async def get_by_id(self, recipe_id: UUID) -> Optional[Recipe]:
        """
        根据 ID 查询菜谱（含关联数据），找不到返回 None。
        """
        return await self.recipe_repo.get_by_id(recipe_id)

    async def create(self, recipe_in: RecipeCreate, created_by: Optional[UUID] = None) -> Recipe:
        """
        创建新菜谱，并处理标签与配料绑定逻辑。
        """
        # 核心修改：不再在这里将 recipe_in 转换为 Recipe ORM 实例
        # 而是将完整的 recipe_in (RecipeCreate Pydantic 模型) 传递给 repo
        # ORM 实例的创建和关系的绑定逻辑已移至 RecipeCRUD.create
        created_recipe = await self.recipe_repo.create(recipe_in)

        if created_by:
            # 注意：如果 created_by 存储在 Recipe ORM 模型中，您可能需要在 repo.create 中处理
            # 或者在 repo.create 返回后，再次更新 recipe 对象
            # 为了简单起见，我们假设 repo.create 已经处理了 created_by
            # 如果 created_by 是 BaseModel 上的字段，并且您想在这里设置，您需要：
            # 1. 修改 repo.create 接受 created_by 参数
            # 2. 或者在 repo.create 返回后，再设置 created_recipe.created_by = created_by 并保存

            # 示例 (如果 Recipe CRUD.create 方法接受 created_by):
            # created_recipe = await self.recipe_repo.create(recipe_in, created_by=created_by)

            # 示例 (如果需要在返回后更新):
            if created_by:
                created_recipe.created_by = created_by
                created_recipe.updated_by = created_by # 更新创建者也更新更新者
                self.session.add(created_recipe)
                await self.session.commit()
                await self.session.refresh(created_recipe) # 刷新确保数据同步

        # 标签和配料的绑定现在已在 RecipeCRUD.create 中完成，所以这里的 TODO 可以移除或注释掉
        # await self._attach_tags(created_recipe, recipe_in.tag_ids)
        # await self._attach_ingredients(created_recipe, recipe_in.ingredients)

        return created_recipe

    async def update(self, recipe_id: UUID, recipe_in: RecipeUpdate, updated_by: Optional[UUID] = None) -> Optional[Recipe]:
        """
        更新菜谱字段，包括标签与配料更新。
        返回更新后的 Recipe 或 None（如找不到）。
        """
        # 核心修改：不再在这里手动处理 updates 字典
        # 而是将完整的 recipe_in (RecipeUpdate Pydantic 模型) 传递给 repo
        # ORM 实例的更新和关系的绑定逻辑已移至 RecipeCRUD.update
        updated_recipe = await self.recipe_repo.update(recipe_id, recipe_in)

        if updated_recipe and updated_by:
            # 如果 updated_by 存储在 Recipe ORM 模型中，您可能需要在 repo.update 中处理
            # 或者在 repo.update 返回后，再次更新 recipe 对象
            updated_recipe.updated_by = updated_by
            self.session.add(updated_recipe)
            await self.session.commit()
            await self.session.refresh(updated_recipe)

        # 标签和配料的更新现在已在 RecipeCRUD.update 中完成，所以这里的 TODO 可以移除或注释掉
        # await self._update_tags(updated_recipe, recipe_in.tag_ids)
        # await self._update_ingredients(updated_recipe, recipe_in.ingredients)

        return updated_recipe

    async def delete(self, recipe_id: UUID, deleted_by: Optional[UUID] = None) -> bool:
        """
        逻辑删除菜谱，返回 True 表示成功，False 表示未找到。
        """
        # 这个方法已经很好了，因为软删除后不需要返回完整的关系对象进行序列化
        recipe = await self.recipe_repo.get_by_id(recipe_id)
        if not recipe:
            return False

        await self.recipe_repo.soft_delete(recipe, deleted_by)
        return True

    # 预留用于标签/配料绑定的内部方法（现在这些逻辑已经移到了 CRUD 层）
    # async def _attach_tags(self, recipe: Recipe, tag_ids: List[UUID]):
    #     pass

    # async def _attach_ingredients(self, recipe: Recipe, ingredients: List[...] ):
    #     pass

    # async def _update_tags(self, recipe: Recipe, tag_ids: List[UUID]):
    #     pass

    # async def _update_ingredients(self, recipe: Recipe, ingredients: List[...] ):
    #     pass
from fastapi import Depends

from app.infra.db.get_repo_factory import get_repository_factory, RepositoryFactory
from app.services.common.category_service import CategoryService
from app.core.security.security import get_current_user
from app.schemas.users.user_context import UserContext

def get_category_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
    current_user: UserContext = Depends(get_current_user),
) -> CategoryService:
    """
    CategoryService 的依赖提供者。
    它会自动解析并注入当前登录的用户信息。
    """
    return CategoryService(factory=repo_factory, current_user=current_user)
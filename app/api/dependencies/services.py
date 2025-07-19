# app/deps/services.py （或 app/services/dependencies.py）
from fastapi import Depends


from app.core.storage.storage_factory import storage_factory
from app.services.file_service import FileService
from app.services.permission_service import PermissionService
from app.services.role_service import RoleService
from app.services.user_service import UserService
from app.services.recipe_service import RecipeService
from app.services.auth_service import AuthService
from app.db.get_repo_factory import get_repository_factory, RepositoryFactory

def get_user_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> UserService:
    return UserService(repo_factory)

def get_recipes_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> RecipeService:
    return RecipeService(repo_factory)

def get_auth_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> AuthService:
    return AuthService(repo_factory)

def get_role_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> RoleService:
    return RoleService(repo_factory)

def get_permission_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> PermissionService:
    return PermissionService(repo_factory)

file_service_instance = FileService(factory=storage_factory)
def get_file_service() -> FileService:
    """MinioService 的依赖注入函数。"""
    return file_service_instance
# app/deps/services.py （或 app/services/dependencies.py）
from fastapi import Depends

from app.core.minio_client import minio_client
from app.services.minio_service import MinioService
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

minio_service_instance = MinioService(minio_client=minio_client)
def get_minio_service() -> MinioService:
    """MinioService 的依赖注入函数。"""
    return minio_service_instance
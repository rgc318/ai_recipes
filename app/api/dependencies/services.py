# app/deps/services.py （或 app/services/dependencies.py）
from fastapi import Depends


from app.infra.storage.storage_factory import storage_factory

from app.services.file.file_record_service import FileRecordService
from app.services.file.file_service import FileService
from app.services.recipes.ingredient_service import IngredientService
from app.services.recipes.tag_service import TagService
from app.services.recipes.unit_service import UnitService
from app.services.users.permission_service import PermissionService
from app.services.users.role_service import RoleService
from app.services.users.user_service import UserService
from app.services.recipes.recipe_service import RecipeService
from app.services.auth.auth_service import AuthService
from app.infra.db.get_repo_factory import get_repository_factory, RepositoryFactory

def get_user_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> UserService:
    return UserService(repo_factory=repo_factory, file_service=get_file_service(), file_record_service=get_file_record_service())

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

def get_file_record_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> FileRecordService:
    return FileRecordService(repo_factory, file_service=get_file_service())

def get_tag_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> TagService:
    """Dependency provider for TagService."""
    return TagService(repo_factory)

def get_ingredient_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> IngredientService:
    """Dependency provider for IngredientService."""
    return IngredientService(repo_factory)

def get_unit_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> UnitService:
    """Dependency provider for IngredientService."""
    return UnitService(repo_factory)
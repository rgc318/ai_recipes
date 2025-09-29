# app/deps/common_service_getter.py （或 app/services/dependencies.py）
from fastapi import Depends


from app.infra.storage.storage_factory import storage_factory


from app.services.file.file_record_service import FileRecordService
from app.services.file.file_service import FileService

from app.services.users.permission_service import PermissionService
from app.services.users.role_service import RoleService

from app.services.auth.auth_service import AuthService
from app.infra.db.get_repo_factory import get_repository_factory, RepositoryFactory

# def get_user_service(
#     repo_factory: RepositoryFactory = Depends(get_repository_factory),
# ) -> UserService:
#     return UserService(repo_factory=repo_factory, file_service=get_file_service(), file_record_service=get_file_record_service())



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


# def get_category_service(
#     repo_factory: RepositoryFactory = Depends(get_repository_factory),
#     # 在这里注入 current_user
#     current_user: UserContext = Depends(get_current_user),
# ) -> CategoryService:
#     """
#     CategoryService 的依赖提供者。
#     它会自动解析并注入当前登录的用户信息。
#     """
#     # 3. 将注入的 current_user 传递给 Service 的构造函数
#     return CategoryService(factory=repo_factory, current_user=current_user)

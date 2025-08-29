from fastapi import Depends

from app.infra.db.get_repo_factory import get_repository_factory, RepositoryFactory
from app.services.users.user_service import UserService
from app.api.dependencies.service_getters.common_service_getter import get_file_service, get_file_record_service

def get_user_service(
    repo_factory: RepositoryFactory = Depends(get_repository_factory),
) -> UserService:
    """
    UserService 的依赖提供者。
    注意：为了保持 UserService 实例化逻辑的单一来源，
    我们从旧的 common_service_getter.py 中导入了 get_file_service 等依赖。
    """
    return UserService(
        repo_factory=repo_factory,
        file_service=get_file_service(),
        file_record_service=get_file_record_service(repo_factory)
    )
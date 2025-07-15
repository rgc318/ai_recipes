from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.db.session import get_session
from app.db.repository_factory_auto import RepositoryFactory
from app.core.request_scope import get_request_scope


def get_repository_factory(
    session: AsyncSession = Depends(get_session),
    context: dict = Depends(get_request_scope),
) -> RepositoryFactory:
    # logger.info(context)
    return RepositoryFactory(
        db=session,
        user_id=context.get("user_id"),
        tenant_id=context.get("tenant_id"),
        group_id=context.get("group_id"),
        context=context,
    )

# app/core/config/loaders/db.py
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from .base import ConfigLoader
from app.models.system_setting import SystemSetting  # 假设你已创建此模型
from app.core.logger import logger


class DatabaseLoader(ConfigLoader):
    """从数据库加载动态配置的策略。"""

    def __init__(self, db_session: AsyncSession):
        self._db = db_session

    async def load(self) -> Dict[str, Any]:
        logger.info("💾 [DatabaseLoader] Loading dynamic configuration from database...")
        try:
            statement = select(SystemSetting)
            results = await self._db.execute(statement)
            settings = results.scalars().all()

            # 将 'key.name' 格式的键转换为嵌套字典
            # e.g., 'server.port': 8001 -> {'server': {'port': 8001}}
            config = {}
            for setting in settings:
                keys = setting.key.split('.')
                d = config
                for key in keys[:-1]:
                    d = d.setdefault(key, {})
                d[keys[-1]] = setting.parsed_value

            logger.info(f"✔️ [DatabaseLoader] Loaded {len(settings)} settings from DB.")
            return config
        except Exception as e:
            logger.error(f"⚠️ [DatabaseLoader] Could not load settings from database: {e}")
            return {}

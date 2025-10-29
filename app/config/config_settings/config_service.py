# app/core/config/service.py
import asyncio
from typing import Any, Dict
from copy import deepcopy

from app.core.logger import logger
from app.config.config_settings.config_schema import AppConfig  # 引入你的 Pydantic 模型


def deep_merge(source, destination):
    """深度合并字典，source 会覆盖 destination。"""
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            destination[key] = deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


class ConfigService:
    _instance = None
    _config_model: AppConfig = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigService, cls).__new__(cls)
        return cls._instance

    async def initialize(self, db_session):
        async with self._lock:
            # 防止重复初始化
            if self._config_model:
                return

            from .loaders.config_file_env import FileEnvLoader
            from .loaders.db import DatabaseLoader

            # 1. 加载基础配置 (文件 + 环境变量)
            file_loader = FileEnvLoader()
            base_config = file_loader.load()

            # 2. 加载动态配置 (数据库)
            db_loader = DatabaseLoader(db_session)
            dynamic_config = await db_loader.load()

            # 3. 深度合并配置：数据库配置覆盖文件配置
            final_config_dict = deep_merge(dynamic_config, base_config)

            # 4. 使用你的 AppConfig 模型进行校验和解析
            try:
                self._config_model = AppConfig(**final_config_dict)
                logger.info("✅ Configuration initialized and validated successfully.")
                logger.debug(f"🔧 Final configuration: {self._config_model}")
            except Exception as e:
                logger.critical(f"❌ Critical error: Final configuration failed validation: {e}", exc_info=True)
                raise ValueError("Failed to initialize valid application configuration.") from e

    async def reload(self, db_session):
        logger.info("🔄 Reloading application configuration...")
        self._config_model = None  # 清空缓存
        await self.initialize(db_session)

    @property
    def config(self) -> AppConfig:
        if not self._config_model:
            raise RuntimeError("Configuration has not been initialized. Please call initialize() first.")
        return self._config_model


# 创建全局单例实例
config_service = ConfigService()# app/core/config/service.py
import asyncio
from typing import Any, Dict
from copy import deepcopy

from app.core.logger import logger
from app.config.config_settings.config_schema import AppConfig # 引入你的 Pydantic 模型

def deep_merge(source, destination):
    """深度合并字典，source 会覆盖 destination。"""
    for key, value in source.items():
        if isinstance(value, dict) and key in destination and isinstance(destination[key], dict):
            destination[key] = deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination

class ConfigService:
    _instance = None
    _config_model: AppConfig = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ConfigService, cls).__new__(cls)
        return cls._instance

    async def initialize(self, db_session):
        async with self._lock:
            # 防止重复初始化
            if self._config_model:
                return

            from .loaders.file_env import FileEnvLoader
            from .loaders.db import DatabaseLoader

            # 1. 加载基础配置 (文件 + 环境变量)
            file_loader = FileEnvLoader()
            base_config = file_loader.load()

            # 2. 加载动态配置 (数据库)
            db_loader = DatabaseLoader(db_session)
            dynamic_config = await db_loader.load()

            # 3. 深度合并配置：数据库配置覆盖文件配置
            final_config_dict = deep_merge(dynamic_config, base_config)

            # 4. 使用你的 AppConfig 模型进行校验和解析
            try:
                self._config_model = AppConfig(**final_config_dict)
                logger.info("✅ Configuration initialized and validated successfully.")
                logger.debug(f"🔧 Final configuration: {self._config_model}")
            except Exception as e:
                logger.critical(f"❌ Critical error: Final configuration failed validation: {e}", exc_info=True)
                raise ValueError("Failed to initialize valid application configuration.") from e

    async def reload(self, db_session):
        logger.info("🔄 Reloading application configuration...")
        self._config_model = None # 清空缓存
        await self.initialize(db_session)

    @property
    def config(self) -> AppConfig:
        if not self._config_model:
            raise RuntimeError("Configuration has not been initialized. Please call initialize() first.")
        return self._config_model

# 创建全局单例实例
config_service = ConfigService()

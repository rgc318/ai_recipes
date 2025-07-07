import os
from functools import lru_cache
from typing import Optional

from pydantic_core import ValidationError
from pydantic_settings import BaseSettings
from pydantic import Field

from app.core.logger import logger
from app.config.config_loader import  load_config_file

class MinIOConfig(BaseSettings):
    endpoint: str = Field("localhost:9000", env="MINIO_ENDPOINT")
    access_key: str = Field("minioadmin", env="MINIO_ACCESS_KEY")
    secret_key: str = Field("minioadmin", env="MINIO_SECRET_KEY")
    bucket_name: str = Field("ai-recipes", env="MINIO_BUCKET_NAME")
    secure: bool = Field(False, env="MINIO_SECURE")

class ServerConfig(BaseSettings):
    host: str = Field("0.0.0.0", env="SERVER_HOST")
    port: int = Field(8000, env="SERVER_PORT")
    log_level: str = Field("info", env="LOG_LEVEL")

class AppConfig(BaseSettings):
    minio: MinIOConfig = Field(default_factory=MinIOConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 防止 YAML 或 ENV 多出字段时报错

    @classmethod
    def load_from_file(cls, file_path: str = "config/config.yaml") -> "AppConfig":
        try:
            file_data = load_config_file(file_path)
            return cls.model_validate(file_data or {})
        except FileNotFoundError as e:
            logger.warning(f"[Config Load Warning] Config file not found: {file_path}. Using default and env.")
            return cls()
        except ValidationError as e:
            logger.error(f"[Config Validation Error] Invalid config schema: {e}")
            raise
        except Exception as e:
            logger.error(f"[Config Load Error] Failed to load config file {file_path}: {e}")
            raise


# === 3. 单例配置对象，避免多次加载 ===
@lru_cache()
def get_app_config() -> AppConfig:
    return AppConfig.load_from_file()

# 默认加载
config: AppConfig = get_app_config()


if __name__ == "__main__":
    cfg = get_app_config()
    logger.info(cfg.server.port)
    logger.info(cfg.minio.endpoint)

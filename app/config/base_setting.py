import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ValidationError

from app.core.logger import logger
from app.config.config_loader import load_config_file

# === MinIO 配置 ===
class MinIOConfig(BaseSettings):
    endpoint: str = Field("localhost:9000", env="MINIO_ENDPOINT")
    access_key: str = Field("minio", env="MINIO_ACCESS_KEY")  # 必填，提升安全
    secret_key: str = Field("minio", env="MINIO_SECRET_KEY")  # 必填，提升安全
    bucket_name: str = Field("ai-recipes", env="MINIO_BUCKET_NAME")
    secure: bool = Field(False, env="MINIO_SECURE")

# === 服务器配置 ===
class ServerConfig(BaseSettings):
    host: str = Field("0.0.0.0", env="SERVER_HOST")
    port: int = Field(8000, env="SERVER_PORT")
    log_level: str = Field("info", env="LOG_LEVEL")

# === 应用总配置 ===
class AppConfig(BaseSettings):
    minio: MinIOConfig = Field(default_factory=MinIOConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略 YAML/ENV 中多余字段

    @classmethod
    def load_from_file(cls, file_path: Optional[str] = None) -> "AppConfig":
        """
        从配置文件加载配置，并允许被环境变量覆盖
        """
        file_path = file_path or os.getenv("CONFIG_FILE_PATH", "config/config.yaml")
        try:
            file_data = load_config_file(file_path)
            logger.info(f"[Config Load] Loaded config file: {file_path}")
            return cls.model_validate(file_data or {})
        except FileNotFoundError:
            logger.warning(f"[Config Load Warning] Config file not found: {file_path}. Using default and env.")
            return cls()
        except ValidationError as ve:
            logger.error(f"[Config Validation Error] Invalid config schema: {ve}")
            raise
        except Exception as e:
            logger.error(f"[Config Load Error] Failed to load config file {file_path}: {e}")
            raise

# === 单例配置对象，避免多次加载 ===
@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """
    获取应用配置单例
    """
    return AppConfig.load_from_file()

# === 可选：配置热加载函数 ===
def reload_app_config() -> AppConfig:
    """
    热加载配置（清理缓存后重新加载）
    """
    get_app_config.cache_clear()
    return get_app_config()

# === 默认加载配置 ===
config: AppConfig = get_app_config()

if __name__ == "__main__":
    cfg = get_app_config()
    logger.info(f"Server Port: {cfg.server.port}")
    logger.info(f"MinIO Endpoint: {cfg.minio.endpoint}")

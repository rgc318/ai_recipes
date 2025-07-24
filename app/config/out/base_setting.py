import os
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ValidationError

from app.core.logger import logger
from app.config.config_settings.config_loader import load_config_file

# 项目根目录，定义为当前文件的上两级目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# 强制加载 env（使用绝对路径确保加载正确）
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# === MinIO 配置 ===
class MinIOConfig(BaseSettings):
    endpoint: str = Field("localhost:9000")
    access_key: str = Field("minio")  # 必填，提升安全
    secret_key: str = Field("minio")  # 必填，提升安全
    bucket_name: str = Field("ai-recipes")
    secure: bool = Field(False)

# === 服务器配置 ===
class ServerConfig(BaseSettings):
    host: str = Field("0.0.0.0")
    port: int = Field(8000)
    log_level: str = Field("info")

# === 数据库配置 ===
class DatabaseConfig(BaseSettings):
    url: str = Field()

def interpolate_env_vars(obj):
    """
    递归将 dict 中的字符串字段中的 ${VAR} 替换为环境变量
    """
    if isinstance(obj, dict):
        return {k: interpolate_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [interpolate_env_vars(v) for v in obj]
    elif isinstance(obj, str):
        return Template(obj).safe_substitute(os.environ)
    else:
        return obj

# === 应用总配置 ===
class AppConfig(BaseSettings):
    minio: MinIOConfig = Field(default_factory=MinIOConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, '.env'),
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False, # 环境变量不区分大小写
    )
    logger.info(f"当前运行目录：{os.getcwd()}")
    @classmethod
    def load_from_file(cls, file_path: Optional[str] = None) -> "AppConfig":
        """
        从配置文件加载配置，并允许被环境变量覆盖
        """
        file_path = file_path or os.getenv("CONFIG_FILE_PATH", "config/config.yaml")
        try:
            file_data = load_config_file(file_path)
            logger.info(f"[Config Load] Loaded config file: {file_path}")
            # ✅ 新增：替换掉 ${...} 环境变量
            file_data = interpolate_env_vars(file_data)
            # return cls.model_validate(file_data or {})
            return cls(**file_data)
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
# config: AppConfig = get_app_config()

if __name__ == "__main__":
    cfg = get_app_config()
    logger.info(f"env_path: {cfg.model_config['env_file']}")
    logger.info(f"env_path: {cfg.model_config['env_file']}")
    logger.info(f"Server Port: {cfg}")
    logger.info(f"Server Port: {cfg.server.port}")
    logger.info(f"Server Port: {cfg.database.url}")
    logger.info(f"MinIO Endpoint: {cfg.minio.endpoint}")

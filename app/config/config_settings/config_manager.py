import os
import yaml
from string import Template
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from app.config.config_settings.config_schema import AppConfig
from app.core.logger import logger


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_ENV = "config"

# 加载 .env 文件（默认）
# load_dotenv(BASE_DIR / ".env")


def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"配置文件未找到: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def interpolate_env_vars(obj):
    """
    替换 YAML 中的 ${VAR} 为 os.environ 中的值
    并做类型转换（true/false/数字）
    """
    def convert(value: str):
        v = value.lower()
        if v == "true": return True
        if v == "false": return False
        # if v.isdigit(): return int(v)
        return value

    if isinstance(obj, dict):
        return {k: interpolate_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [interpolate_env_vars(i) for i in obj]
    elif isinstance(obj, str):
        raw = Template(obj).safe_substitute(os.environ)
        return convert(raw)
    else:
        return obj


def get_env() -> str:
    return os.getenv("ENV", DEFAULT_ENV)


@lru_cache()
def get_app_config() -> AppConfig:
    env = get_env()
    logger.info(f"🌍 当前环境: {env}")

    # --- 核心修改：分层加载 .env 文件 ---

    # 1. 首先加载通用的 .env 文件 (如果存在)，它包含所有环境共享的变量
    base_env_path = BASE_DIR / ".env"
    if base_env_path.exists():
        load_dotenv(dotenv_path=base_env_path)
        logger.info(f"✔️ 已加载通用 .env 文件: {base_env_path}")

    # 2. 然后加载特定环境的 .env 文件 (例如 .env.prod)，它会覆盖通用设置
    env_specific_path = BASE_DIR / f".env.{env}"
    if env_specific_path.exists():
        # `override=True` 确保后加载的文件中的变量能覆盖之前加载的同名变量
        load_dotenv(dotenv_path=env_specific_path, override=True)
        logger.info(f"✔️ 已加载特定环境 .env 文件: {env_specific_path}")

    # --- YAML 加载逻辑保持不变 ---
    config_path = BASE_DIR / "app" / "config" / f"{env}.yaml"
    logger.info(f"🔧 加载配置文件: {config_path}")

    data = load_yaml(config_path)
    # 环境变量插值会使用刚刚加载完 .env 文件后的最新环境变量
    data = interpolate_env_vars(data)

    config = AppConfig(**data)
    logger.debug(f"🔧 配置文件内容: {config}") # 敏感信息多时建议debug级别打印
    return config


def reload_app_config():
    get_app_config.cache_clear()
    return get_app_config()


if __name__ == "__main__":
    cfg = get_app_config()
    logger.info(f"Server Port: {cfg}")
    logger.info(f"Server Port: {cfg.server.port}")
    logger.info(f"Server Port: {cfg.database.url}")
    logger.info(f"MinIO Endpoint: {cfg.minio.endpoint}")
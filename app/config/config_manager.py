import os
import yaml
from string import Template
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv
from app.config.config_schema import AppConfig
from app.core.logger import logger


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV = "config"

# 加载 .env 文件（默认）
load_dotenv(BASE_DIR / ".env")


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
        if v.isdigit(): return int(v)
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
    config_path = BASE_DIR / "app" / "config" / f"{env}.yaml"

    logger.info(f"🌍 当前环境: {env}")
    logger.info(f"🔧 加载配置文件: {config_path}")

    data = load_yaml(config_path)
    data = interpolate_env_vars(data)

    config = AppConfig(**data)
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
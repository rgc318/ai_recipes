# app/core/config/loaders/file_env.py
import os
import yaml
from string import Template
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any

from app.core.logger import logger
from .base import ConfigLoader

# 你原来的 BASE_DIR 和 interpolate_env_vars 函数可以移到这里
BASE_DIR = Path(__file__).resolve().parents[4]  # 注意调整 parents 的层级


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

def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"配置文件未找到: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

class FileEnvLoader(ConfigLoader):
    """
    从 .env 和 .yaml 文件加载配置的策略。
    这完全封装了你之前的 get_app_config 核心逻辑。
    """

    def load(self) -> Dict[str, Any]:
        env = os.getenv("ENV", "dev")  # 使用 dev 作为默认环境
        logger.info(f"📂 [FileEnvLoader] Loading config for environment: {env}")

        # 1. 加载通用的 .env 文件
        base_env_path = BASE_DIR / ".env"
        if base_env_path.exists():
            load_dotenv(dotenv_path=base_env_path)
            logger.info(f"✔️ [FileEnvLoader] Loaded common .env file: {base_env_path}")

        # 2. 加载特定环境的 .env 文件 (覆盖通用设置)
        env_specific_path = BASE_DIR / f".env.{env}"
        if env_specific_path.exists():
            load_dotenv(dotenv_path=env_specific_path, override=True)
            logger.info(f"✔️ [FileEnvLoader] Loaded environment-specific .env file: {env_specific_path}")

        # 3. 加载 YAML 文件
        # 注意: 路径可能需要根据新的文件位置微调
        config_path = BASE_DIR / "app" / "config" / f"{env}.yaml"
        if not config_path.exists():
            logger.warning(f"⚠️ [FileEnvLoader] YAML config file not found: {config_path}, returning empty config.")
            return {}

        logger.info(f"🔧 [FileEnvLoader] Loading YAML file: {config_path}")
        data = load_yaml(config_path)

        # 4. 使用环境变量进行插值
        interpolated_data = interpolate_env_vars(data)

        return interpolated_data

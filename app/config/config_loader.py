import json
from pathlib import Path

import yaml
import configparser
import os
from typing import Dict, Any
from app.core.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent
def load_config_file(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    # 如果传入的是相对路径，则使用 BASE_DIR 拼接
    if not config_path.is_absolute():
        config_path = BASE_DIR / config_path

    config_path = config_path.resolve()
    """根据扩展名加载 JSON/YAML/INI 配置"""
    logger.info(f"加载配置文件: {config_path}")
    if not config_path.exists():
        logger.warning(f"配置文件 {path} 不存在，返回空配置")
        return {}

    try:
        if config_path.suffix == ".json":
            with config_path.open("r", encoding="utf-8") as f:
                return json.load(f)

        elif config_path.suffix in [".yaml", ".yml"]:
            with config_path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f)

        elif config_path.suffix == ".ini":
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding="utf-8")
            return {section: dict(parser.items(section)) for section in parser.sections()}

        else:
            logger.warning(f"配置文件格式不支持: {config_path.suffix}")
            return {}

    except Exception as e:
        logger.error(f"配置文件加载失败 [{config_path}]: {e}", exc_info=True)
        return {}

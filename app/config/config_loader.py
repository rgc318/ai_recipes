import json
import yaml
import configparser
import os
from typing import Dict, Any
from app.core.logger import logger


def load_config_file(path: str) -> Dict[str, Any]:
    """根据扩展名加载 JSON/YAML/INI 配置"""
    if not os.path.exists(path):
        logger.warning(f"配置文件 {path} 不存在，返回空配置")
        return {}

    try:
        if path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        elif path.endswith((".yaml", ".yml")):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        elif path.endswith(".ini"):
            parser = configparser.ConfigParser()
            parser.read(path)
            return {section: dict(parser.items(section)) for section in parser.sections()}
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}")

    return {}

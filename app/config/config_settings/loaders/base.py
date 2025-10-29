# app/core/config/loaders/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class ConfigLoader(ABC):
    """配置加载器策略的抽象基类。"""

    @abstractmethod
    def load(self, *args, **kwargs) -> Dict[str, Any]:
        """
        加载配置并返回一个字典。
        可以是同步或异步方法。
        """
        pass

from app.config.config_settings.config_schema import AppConfig
from app.config.settings import settings
from app.core.logger import get_logger


class BaseService:
    def __init__(self) -> None:
        self.settings: AppConfig = settings
        self.logger = get_logger(self.__class__.__name__)

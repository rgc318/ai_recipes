from app.config.settings import settings
from app.core.logger import get_logger


class BaseService:
    def __init__(self) -> None:
        self.settings = settings()
        self.logger = get_logger(self.__class__.__name__)

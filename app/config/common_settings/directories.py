# 文件: app/core/directories.py

from pathlib import Path
from app.config import settings  # 假设你的配置可以这样导入


class AppDirectories:
    """
    一个用于集中管理应用所有文件系统路径的类。
    确保所有路径操作都有一个唯一的、可靠的来源。
    """

    def __init__(self, base_data_path: str):
        # 1. 定义根目录
        self.DATA_DIR = Path(base_data_path)

        # 2. 定义所有子目录
        self.LOG_DIR = self.DATA_DIR / "logs"
        self.IMAGES_DIR = self.DATA_DIR / "images"
        self.BACKUPS_DIR = self.DATA_DIR / "backups"
        self.TEMP_DIR = self.DATA_DIR / "temp"

        # 3. 在应用启动时，确保这些目录都存在
        self.ensure_directories()

    def ensure_directories(self):
        """
        遍历所有定义的目录路径，如果不存在则创建它们。
        """
        # 获取这个类的所有 Path 类型的属性
        all_dirs = [getattr(self, attr) for attr in dir(self) if isinstance(getattr(self, attr), Path)]

        for directory in all_dirs:
            directory.mkdir(parents=True, exist_ok=True)


# 创建一个可以被全项目引用的单例
# 假设你的配置文件中有 DATA_PATH 这个配置项
# 这样，全项目只需要 from app.core.directories import directories 即可使用
directories = AppDirectories(settings.server.DATA_PATH)
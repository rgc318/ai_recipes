import threading
from typing import Dict

from app.config.settings import settings
from app.config.config_settings.config_schema import (  # 从您的 schemas 文件中导入
    StorageProfileConfig,
    S3ClientConfig,
    AzureClientConfig,  # 即使尚未实现，也为未来做准备
)
from app.core.logger import logger
from app.infra.storage.storage_interface import StorageClientInterface
from app.infra.storage.s3_client import S3CompatibleClient


# 导入未来可能有的其他客户端
# from app.core.storage.azure_blob_client import AzureBlobClient


class StorageFactory:
    """
    一个单例的存储客户端工厂。

    该工厂在应用启动时被初始化，它会根据配置文件中的 `storage_clients`
    部分，创建并管理所有可用的存储客户端实例。

    业务逻辑层通过调用 `get_client_by_profile()` 方法，
    传入业务场景名称（如 'user_avatars'），即可获取对应的客户端实例，
    无需关心底层的具体实现。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                # Double-checked locking
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 使用 hasattr 检查确保 __init__ 逻辑只执行一次
        if hasattr(self, "_initialized") and self._initialized:
            return

        with self._lock:
            if hasattr(self, "_initialized") and self._initialized:
                return

            logger.info("Initializing StorageFactory...")
            self._clients: Dict[str, StorageClientInterface] = {}
            self._profiles: Dict[str, StorageProfileConfig] = settings.storage_profiles
            self._initialize_all_clients()
            self._initialized = True
            logger.info("StorageFactory initialized successfully.")

    def _initialize_all_clients(self):
        """
        根据配置，遍历并实例化所有定义的存储客户端。
        """
        if not settings.storage_clients:
            logger.warning("No storage clients defined in configuration. StorageFactory will be empty.")
            return

        for client_name, client_config in settings.storage_clients.items():
            try:
                logger.debug(f"Initializing storage client: '{client_name}' of type '{client_config.type}'...")

                # 工厂的核心逻辑：根据类型创建不同的客户端实例
                if isinstance(client_config, S3ClientConfig):
                    # Pydantic 已经确保了 client_config.params 是 S3Params 类型
                    # 假设您的 S3CompatibleClient 构造函数接收一个匹配的配置对象
                    new_client = S3CompatibleClient(config=client_config)

                elif isinstance(client_config, AzureClientConfig):
                    # new_client = AzureBlobClient(config=client_config.params)
                    # logger.warning(f"Client type 'azure_blob' is configured but not yet implemented.")
                    raise NotImplementedError(f"Client type 'azure_blob' is configured but not yet implemented.")

                else:
                    # 这是一个保障，理论上 Pydantic 的 Union 会阻止未知类型
                    raise ValueError(f"Unsupported storage client configuration type for '{client_name}'.")

                self._clients[client_name] = new_client
                logger.info(f"Successfully initialized client: '{client_name}'.")

            except Exception as e:
                logger.exception(
                    f"Failed to initialize storage client '{client_name}'. "
                    f"Error: {e}. This client will be unavailable."
                )

    def get_client(self, client_name: str) -> StorageClientInterface:
        """
        通过名称直接获取一个已初始化的客户端实例。

        Args:
            client_name (str): 在配置文件中定义的客户端名称。

        Returns:
            StorageClientInterface: 客户端实例。

        Raises:
            KeyError: 如果客户端名称不存在或初始化失败。
        """
        try:
            return self._clients[client_name]
        except KeyError:
            logger.error(f"Attempted to access non-existent or failed-to-initialize storage client: '{client_name}'")
            raise KeyError(
                f"Storage client '{client_name}' is not available. Check your configuration and startup logs.")

    def get_client_by_profile(self, profile_name: str) -> StorageClientInterface:
        """
        **主要使用方法**：根据业务场景 (Profile) 名称获取对应的客户端实例。

        Args:
            profile_name (str): 在配置文件中定义的 Profile 名称, e.g., 'user_avatars'.

        Returns:
            StorageClientInterface: 客户端实例。

        Raises:
            ValueError: 如果 Profile 名称未在配置中定义。
            KeyError: 如果 Profile 对应的客户端不存在或初始化失败。
        """
        if profile_name not in self._profiles:
            raise ValueError(f"Storage profile '{profile_name}' is not defined in the configuration.")

        profile_config = self._profiles[profile_name]
        client_name = profile_config.client

        logger.debug(f"Request for profile '{profile_name}' maps to client '{client_name}'.")
        return self.get_client(client_name)

    def get_profile_config(self, profile_name: str) -> StorageProfileConfig:
        """
        获取指定 Profile 的详细配置，例如默认文件夹等。

        Args:
            profile_name (str): 在配置文件中定义的 Profile 名称。

        Returns:
            StorageProfileConfig: 该 Profile 的 Pydantic 配置模型实例。

        Raises:
            ValueError: 如果 Profile 名称未在配置中定义。
        """
        if profile_name not in self._profiles:
            raise ValueError(f"Storage profile '{profile_name}' is not defined in the configuration.")

        return self._profiles[profile_name]


# ==============================================================================
#                      全局实例创建及使用示例
# ==============================================================================

# 在应用启动的某个中心位置（如 main.py 或一个专门的 app_setup.py）创建全局实例
storage_factory = StorageFactory()

def get_storage_factory() -> StorageFactory:
    return storage_factory

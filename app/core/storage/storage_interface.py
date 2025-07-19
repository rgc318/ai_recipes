from abc import ABC, abstractmethod
from typing import BinaryIO, List, Dict

class StorageClientInterface(ABC):
    """
    一个抽象基类 (ABC)，定义了所有存储客户端必须实现的统一接口。
    这确保了 FileService 可以与任何存储后端以相同的方式进行交互。
    """

    @abstractmethod
    def put_object(self, object_name: str, data: BinaryIO, length: int, content_type: str) -> Dict:
        """
        上传一个对象（文件）。
        :return: 包含 etag 等信息的字典。
        """
        pass

    @abstractmethod
    def remove_object(self, object_name: str):
        """删除一个对象。"""
        pass

    @abstractmethod
    def get_presigned_url(self, client_method: str, object_name: str, expires_in: int) -> str:
        """
        生成预签名 URL (用于 GET 或 PUT)。
        :param client_method: 'get_object' 或 'put_object'
        """
        pass

    @abstractmethod
    def build_final_url(self, object_name: str) -> str:
        """构建最终的可公开访问 URL。"""
        pass

    @abstractmethod
    def stat_object(self, object_name: str):
        """获取对象的元数据（常用于检查存在性）。"""
        pass

    @abstractmethod
    def list_objects(self, prefix: str) -> List[Dict]:
        """列出对象。"""
        pass
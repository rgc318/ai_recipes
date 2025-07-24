from typing import Dict, Optional, Literal, Union, List

from pydantic import BaseModel, Field

class MinioS3Params(BaseModel):
    """MinIO 或 AWS S3 类型的客户端参数"""
    endpoint: Optional[str] = None # S3 不需要 endpoint，MinIO 需要
    access_key: str
    secret_key: str
    bucket_name: str
    secure: bool = True
    cdn_base_url: Optional[str] = None
    public_endpoint: Optional[str] = None

class AzureBlobParams(BaseModel):
    """Azure Blob Storage 类型的客户端参数 (示例)"""
    connection_string: str
    bucket_name: str # 在 Azure 中叫 container_name
    cdn_base_url: Optional[str] = None

class MinioClientConfig(BaseModel):
    type: Literal['minio', 's3'] # 限制 type 只能是 'minio' 或 's3'
    params: MinioS3Params

class AzureClientConfig(BaseModel):
    type: Literal['azure_blob']
    params: AzureBlobParams

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    api_prefix : str = "/api/v1"
    env : str = "dev"
class DatabaseConfig(BaseModel):
    url: str

class LoggingConfig(BaseModel):
    enable_file: bool = True
    log_dir: str = "../logs"
    rotation: str = "1 week"
    retention: str = "1 month"

class SecuritySettings(BaseModel):
    token_expire_minutes: int
    jwt_algorithm: str
    jwt_issuer: str
    jwt_audience: str
    secret: str
    max_login_attempts: int
    user_lockout_time: int  # 小时
    fake_password_hash: str = "$2b$12$JdHtJOlkPFwyxdjdygEzPOtYmdQF5/R5tHxw5Tq8pxjubyLqdIX5i"
    testing: bool = False

class RedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    serializer: str = "json"

    @property
    def url(self):
        auth_part = f":{self.password}@" if self.password else ""
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"

class StorageProfileConfig(BaseModel):
    """单个存储策略的配置"""
    client: str = Field(..., description="该策略使用的客户端名称")
    default_folder: str = Field(..., description="默认存储的文件夹")
    allowed_file_types: List[str] = Field(..., description="允许上传的MIME类型列表, e.g., ['image/jpeg', 'image/png']")
    # 【核心新增】为每个profile定义最大文件大小
    max_file_size_mb: int = Field(10, description="该策略允许的最大文件大小 (MB)，默认为10MB")


# ========================================================================================
#
#   所有配置模型都要写在APPconfig上方
#
# ========================================================================================
class AppConfig(BaseModel):
    server: ServerConfig
    database: DatabaseConfig
    logging: LoggingConfig
    security_settings: SecuritySettings
    redis: RedisConfig
    # 【新增】将新的配置结构添加到主配置模型中
    # 使用 Union 来支持多种不同的客户端配置结构
    storage_clients: Dict[str, Union[MinioClientConfig, AzureClientConfig]]
    storage_profiles: Dict[str, StorageProfileConfig]




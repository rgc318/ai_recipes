from typing import Dict, Optional, Literal, Union, List

from pydantic import BaseModel, Field, model_validator

from app.enums.file_enums import UploadMode


class StorageCapabilities(BaseModel):
    """
    描述对象存储服务的特性与能力集。
    【修改】默认值已设为代表一个“功能齐全”的 S3 兼容服务 (如 MinIO, AWS S3)。
    """

    upload_modes: List[UploadMode] = Field(  # <-- 2. 使用 Enum
        default_factory=lambda: [
            UploadMode.PUT_URL,
            UploadMode.POST_POLICY,
            UploadMode.MULTIPART
        ],
        description="支持的上传模式"
    )

    supports_acl: bool = Field(
        default=True,
        description="是否支持对象 ACL 控制 (S3/MinIO: True, R2: False)"
    )

    supports_bucket_creation: bool = Field(
        default=True,
        description="是否允许通过API创建bucket (S3/MinIO: True, R2: True)"
    )

    supports_cdn_rewrite: bool = Field(
        default=True,
        description="是否支持将内网URL重写为CDN URL (这是一个客户端特性，默认开启)"
    )

    # ✅ 【【【 核心修复：添加这个新标识 】】】
    rewrite_presigned_host: bool = Field(
        default=False,  # 默认值设为 False，因为云服务商 (S3, R2) 不需要重写
        description="是否应将 Boto3 生成的预签名 URL 的 host 替换为 public_endpoint (仅 MinIO 等内网部署需要)"
    )

    signature_version: Literal["v2", "v4"] = Field(
        default="v4",
        description="支持的签名算法版本 (v4 是现代标准)"
    )

    path_style: Literal["auto", "path", "virtual"] = Field(
        default="auto",
        description="默认寻址风格 (auto 适用于 S3/R2，本地 MinIO 可能需要手动设为 'path')"
    )

class S3Params(BaseModel):
    """
    MinIO 或 S3 兼容服务的客户端参数
    (已增强以适应 AWS S3, MinIO, OSS, COS 等)
    """

    # --- 核心连接配置 ---

    endpoint: Optional[str] = None
    """
    服务地址 (不含 http/https)。
    - AWS S3: 留空 (None)，Boto3 会根据 region 自动生成。
    - MinIO/OSS/COS: 必须填写, e.g., 'your-minio:9000' 或 'oss-cn-hangzhou.aliyuncs.com'
    """

    region: str = "us-east-1"
    """
    S3 区域。
    - MinIO: 可以保留 'us-east-1'。
    - AWS S3/OSS/COS: 必须填写存储桶所在的实际区域, e.g., 'ap-northeast-1'.
    """

    access_key: str
    secret_key: str
    bucket_name: str
    secure: bool = True
    """
    是否使用 HTTPS。
    - MinIO(本地): 可能是 False
    - AWS S3/OSS/COS: 必须是 True
    """

    # force_path_style: bool = False
    # """
    # 是否强制使用路径样式 (Path-Style) 寻址。
    # - AWS S3: 必须为 False (使用 'bucket.s3.com/key' 样式)。
    # - MinIO: 如果您没有配置虚拟主机，可能需要设为 True (使用 'minio.com/bucket/key' 样式)。
    # """

    default_acl: Optional[str] = "public-read"
    """
    上传或复制对象时使用的默认 ACL。
    - MinIO/OSS: 可能是 'public-read'
    - AWS S3: 可能是 'private'
    - Cloudflare R2: 必须设置为 None
    """

    # --- 公网/CDN 访问配置 ---

    public_endpoint: Optional[str] = None
    """
    公网访问端点 (不含 http/https, 不含 bucket)。
    用于替换预签名 POST URL 中的内网 endpoint。
    e.g., 's3.ap-northeast-1.amazonaws.com' 或 'public-minio-domain.com'
    """

    cdn_base_url: Optional[str] = None
    """
    CDN 完整域名 (不含 http/https, 不含 bucket)。
    e.g., 'cdn.your-domain.com'
    """

    secure_cdn: bool = True
    """CDN 是否使用 HTTPS"""

    # --- (可选) 健壮性配置 ---

    connect_timeout: int = 60
    """连接超时时间 (秒)"""

    read_timeout: int = 60
    """读取超时时间 (秒)"""

    capabilities: StorageCapabilities = Field(
        default_factory=StorageCapabilities,
        description="描述当前存储服务的特性与行为差异"
    )


class AzureBlobParams(BaseModel):
    """Azure Blob Storage 类型的客户端参数 (示例)"""
    connection_string: str
    bucket_name: str # 在 Azure 中叫 container_name
    cdn_base_url: Optional[str] = None

class S3ClientConfig(BaseModel):
    type: Literal['minio', 's3'] # 限制 type 只能是 'minio' 或 's3'
    params: S3Params

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


class SingleRedisConfig(BaseModel):
    """
    【全新升级版】定义单个 Redis 客户端的配置模型。
    同时支持直接提供 URL 或提供独立参数进行拼接。
    """
    # 模式一：直接提供 URL (优先级更高)
    url: Optional[str] = Field(None, description="完整的Redis连接URL，如果提供，将优先使用此配置。")

    # 模式二：提供独立参数
    host: Optional[str] = Field("localhost", description="Redis 主机 (当 url 未提供时使用)")
    port: Optional[int] = Field(6379, description="Redis 端口 (当 url 未提供时使用)")
    db: Optional[int] = Field(0, description="数据库编号 (当 url 未提供时使用)")
    password: Optional[str] = Field(None, description="密码 (当 url 未提供时使用)")

    # 其他非连接参数
    max_connections: int = 10
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    serializer: str = "json"

    # 用于存储最终生成的 URL，供 Factory 使用
    _final_url: str = ""

    @model_validator(mode='after')
    def validate_and_build_url(self) -> 'SingleRedisConfig':
        """
        Pydantic 校验器，在字段校验后执行。
        用于检查配置并生成最终的连接 URL。
        """
        if self.url:
            # 如果 URL 已提供，直接使用它
            self._final_url = self.url
            return self

        # 如果 URL 未提供，则必须有 host 和 port
        if not self.host or self.port is None:
            raise ValueError("If 'url' is not provided, 'host' and 'port' must be set.")

        # 自动拼接 URL
        auth_part = f":{self.password}@" if self.password else ""
        self._final_url = f"redis://{auth_part}{self.host}:{self.port}/{self.db or 0}"

        return self


class RedisConfig(BaseModel):
    """
    主 Redis 配置模型，容纳一个由多个 SingleRedisConfig 组成的字典。
    """
    clients: Dict[str, SingleRedisConfig]


class StorageProfileConfig(BaseModel):
    """单个存储策略的配置"""
    client: str = Field(..., description="该策略使用的客户端名称")
    default_folder: str = Field(..., description="默认存储的文件夹")
    allowed_file_types: List[str] = Field(..., description="允许上传的MIME类型列表, e.g., ['image/jpeg', 'image/png']")
    # 【核心新增】为每个profile定义最大文件大小
    max_file_size_mb: int = Field(10, description="该策略允许的最大文件大小 (MB)，默认为10MB")

    presigned_upload_method: UploadMode = Field(  # <-- 3. 使用 Enum
        UploadMode.PUT_URL,  # 默认偏好 "put_url"
        description="此业务场景【首选】的预签名上传方法。"
    )

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
    storage_clients: Dict[str, Union[S3ClientConfig, AzureClientConfig]]
    storage_profiles: Dict[str, StorageProfileConfig]




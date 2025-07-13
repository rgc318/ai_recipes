from typing import Dict, Optional

from pydantic import BaseModel, Field

class MinIOConfig(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str
    cdn_base_url: str = ""
    cdn_prefix_mapping: Dict[str, str] =  {}  # 确保这里是 Dict 类型
    secure: bool = False
    costume_url: bool = False

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    api_prefix : str = "/api/v1"
class DatabaseConfig(BaseModel):
    url: str

class LoggingConfig(BaseModel):
    enable_file: bool = True
    log_dir: str = "logs"
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


class AppConfig(BaseModel):
    server: ServerConfig
    database: DatabaseConfig
    minio: MinIOConfig
    logging: LoggingConfig
    security_settings: SecuritySettings
    redis: RedisConfig

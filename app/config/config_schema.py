from pydantic import BaseModel, Field

class MinIOConfig(BaseModel):
    endpoint: str
    access_key: str
    secret_key: str
    bucket_name: str
    secure: bool = False

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

class DatabaseConfig(BaseModel):
    url: str

class LoggingConfig(BaseModel):
    enable_file: bool = True
    log_dir: str = "logs"
    rotation: str = "1 week"
    retention: str = "1 month"

class AppConfig(BaseModel):
    server: ServerConfig
    database: DatabaseConfig
    minio: MinIOConfig
    logging: LoggingConfig

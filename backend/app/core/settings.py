# Settings/env
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent

ENVFILE_PATH = os.path.join(BASE_DIR, f".env.{os.getenv('ENVIRONMENT', 'prod')}")


# 系统设置类
class Settings(BaseSettings):
    """系统设置类，使用 Pydantic-settings 从环境变量加载配置"""

    BASE_DIR: Path = BASE_DIR
    # FastAPI
    DEBUG: bool
    APP_TIMEZONE: str
    ENVIRONMENT: str
    LOG_LEVEL: int
    # 数据库连接信息
    DATABASE_TYPE: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_NAME: str
    # 数据库egine/连接池
    DB_ECHO: bool
    DB_POOL_SIZE: int
    DB_MAX_OVERFLOW: int
    DB_POOL_TIMEOUT: int
    DB_POOL_RECYCLE: int
    # Redis
    REDIS_PASSWORD: str
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_ENCODING: str
    REDIS_DECODE_RESPONSES: bool
    # Redis连接池
    REDIS_POOL_SIZE: int
    REDIS_SOCKET_TIMEOUT: int
    REDIS_SOCKET_CONNECT_TIMEOUT: int
    REDIS_HEALTH_CHECK_INTERVAL: int
    # CORS 前端Configs
    ALLOW_ORIGINS: list[str]
    ALLOW_CREDENTIALS: bool
    ALLOW_METHODS: list[str]
    ALLOW_HEADERS: list[str]
    # JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    JWT_ALGORITHM: str
    # 非配置文件中设置,全局静态值
    # Redis KEY 值系统约定
    REFRESH_TOKEN_PROMPT: str = "user:{}:device:{}"
    TOKEN_BLACKLIST_PROMPT: str = "blacklist:{}"
    USER_DEVICES_SET_PROMPT: str = "user_devices:{}"

    # 文件存储路径相关
    # 日志存储位置
    LOG_DIR: Path = BASE_DIR / "logs"
    # 业务系统
    BUSINESS_FILES_BASE_DIR: Path = BASE_DIR / "storage"

    @property
    def REDIS_URL(self) -> str:
        """Redis连接url"""
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(
        env_file=ENVFILE_PATH, env_file_encoding="utf-8", extra="ignore"
    )


# 全局系统设置实例
def get_settings() -> Settings:
    """get system settings with caching"""
    return Settings()  # type: ignore

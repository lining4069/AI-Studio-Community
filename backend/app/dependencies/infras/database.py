from collections.abc import AsyncGenerator
from functools import wraps

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from app.core.settings import Settings, get_settings


def get_async_db_angine(settings: Settings = get_settings()) -> AsyncEngine:
    """获取异步数据库引擎"""
    if settings.DATABASE_TYPE == "mysql":
        database_url = f"mysql+aiomysql://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}?charset=utf8mb4"
        return create_async_engine(
            url=database_url,
            echo=settings.DB_ECHO,  # 是否输出sql日志
            pool_pre_ping=True,  # 每次去连接前ping一下
        )
    elif settings.DATABASE_TYPE == "postgresql":
        database_url = f"postgresql+asyncpg://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}"
        return create_async_engine(
            url=database_url,
            echo=settings.DB_ECHO,  # 是否输出sql日志
            pool_size=settings.DB_POOL_SIZE,  # 连接池中保持的持久连接数
            max_overflow=settings.DB_MAX_OVERFLOW,  # 峰值额外连接
            pool_timeout=settings.DB_POOL_TIMEOUT,  # 等待连接的超时时间
            pool_recycle=settings.DB_POOL_RECYCLE,  # 回收一次连接间隔 防止服务器断开
            pool_pre_ping=True,  # 每次去连接前ping一下
        )
    else:  # sqlite
        database_url = f"sqlite+aiosqlite:///{settings.DATABASE_NAME}"
        return create_async_engine(
            url=database_url,
            echo=settings.DB_ECHO,  # 是否输出sql日志
        )


async_engine = get_async_db_angine()

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,  # 绑定数据库引擎
    class_=AsyncSession,  # 制定会话类
    expire_on_commit=False,  # 提交会话不过期，不会重新查库
)


# 数据库Session依赖项
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖项"""

    # 1. 事务开始：创建新的 Session
    session = AsyncSessionLocal()
    try:
        # 2. 暂停执行：将 Session 实例注入
        yield session
        # 3. 成功路径：API 路由执行完毕且没有抛出异常，执行 commit
        await session.commit()
    except Exception:
        # 4. 失败路径：API 路由抛出异常，执行 rollback
        await session.rollback()
        raise  # 重新抛出异常，让 FastAPI 返回错误响应
    finally:
        # 5. 资源清理：无论成功还是失败，最终都会执行 close
        await session.close()


def with_async_db_session(func):
    """
    装饰器：为函数提供异步数据库会话，并自动处理事务和资源管理
    用于非路由处理函数的普通函数或工具函数
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        session = AsyncSessionLocal()
        try:
            kwargs["session"] = session
            result = await func(*args, **kwargs)
            await session.commit()
            return result
        except Exception as e:
            logger.error(f"Execution error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

    return wrapper

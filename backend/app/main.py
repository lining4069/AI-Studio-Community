from collections.abc import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.common.logger import logger, setup_logger
from app.core.settings import Settings, get_settings
from app.utils.aiohttp_session import HttpSessionShared


# 定义应用生命周期函数
async def lifespan(app: FastAPI):
    """应用生命周期函数，负责启动和关闭时的资源管理"""

    await HttpSessionShared.ensure_session()  # 全局单例aiohttp session
    setup_logger(retention_days=30)  # 初始化日志配置

    logger.info("Application starting up...")

    yield

    await HttpSessionShared.cleanup()  # 清理全局单例aiohttp session
    logger.info("Application shutting down...")


def create_app(
    lifespan: Callable = lifespan, settings: Settings = get_settings()
) -> FastAPI:
    from app.api.v1.routers import register_business_routers
    from app.common.exceptions import register_exception_handlers

    app = FastAPI(
        title="AI Studio",
        version="1.0.0",
        lifespan=lifespan,
        prefix="/ai-studio",
    )
    # 1.导入路由
    register_business_routers(app)
    # 2.添加中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOW_ORIGINS,  # 允许访问的源
        allow_credentials=settings.ALLOW_CREDENTIALS,  # 允许携带cookies
        allow_methods=settings.ALLOW_METHODS,  # 允许所有请求方式
        allow_headers=settings.ALLOW_HEADERS,  # 允许所有请求头
    )
    # 3.注册全局异常处理器
    register_exception_handlers(app, settings)
    return app


app: FastAPI = create_app()

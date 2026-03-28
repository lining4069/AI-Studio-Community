# 汇总api
from fastapi import FastAPI

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as user_router

# tags:在接口文档中的分组名


# 注册系统API路由
def register_business_routers(app: FastAPI):
    """注册业务路由"""
    app.include_router(auth_router, prefix="/v1/auth", tags=["认证"])
    app.include_router(user_router, prefix="/v1/user", tags=["用户"])

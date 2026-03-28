# 汇总api
from fastapi import FastAPI

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as user_router
from app.modules.llm_model.router import router as llm_model_router
from app.modules.embedding_model.router import router as embedding_model_router
from app.modules.rerank_model.router import router as rerank_model_router

# tags:在接口文档中的分组名


# 注册系统API路由
def register_business_routers(app: FastAPI):
    """注册业务路由"""
    app.include_router(auth_router, prefix="/v1/auth", tags=["认证"])
    app.include_router(user_router, prefix="/v1/user", tags=["用户"])
    app.include_router(llm_model_router, prefix="/v1/llm-models", tags=["LLM模型"])
    app.include_router(embedding_model_router, prefix="/v1/embedding-models", tags=["Embedding模型"])
    app.include_router(rerank_model_router, prefix="/v1/rerank-models", tags=["Rerank模型"])

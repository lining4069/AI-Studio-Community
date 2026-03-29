# 汇总api
from fastapi import FastAPI

from app.modules.agent.router import router as agent_router
from app.modules.auth.router import router as auth_router
from app.modules.embedding_model.router import router as embedding_model_router
from app.modules.knowledge_base.router import router as kb_router
from app.modules.llm_model.router import router as llm_model_router
from app.modules.rerank_model.router import router as rerank_model_router
from app.modules.users.router import router as user_router


# 注册系统API路由
def register_business_routers(app: FastAPI):
    """注册业务路由"""
    app.include_router(auth_router, prefix="/v1/auth", tags=["认证"])
    app.include_router(user_router, prefix="/v1/user", tags=["用户"])


# 注册模型相关API路由
def register_model_routers(app: FastAPI):
    """注册模型相关路由"""
    # 这里可以注册与模型相关的路由，例如模型管理、模型推理等
    app.include_router(llm_model_router, prefix="/v1/llm-models", tags=["LLM模型"])
    app.include_router(
        embedding_model_router, prefix="/v1/embedding-models", tags=["Embedding模型"]
    )
    app.include_router(
        rerank_model_router, prefix="/v1/rerank-models", tags=["Rerank模型"]
    )


# 注册上层应用层
def register_application_routers(app: FastAPI):
    """注册上层应用相关路由"""
    app.include_router(kb_router, prefix="/v1/knowledge-bases", tags=["知识库"])

    app.include_router(agent_router, prefix="/v1/agents", tags=["Agent"])

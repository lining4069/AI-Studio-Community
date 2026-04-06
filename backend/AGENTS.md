# AI Studio Backend - 项目规范与AI Coding指南

> 本文档用于指导 AI coding agent 理解和开发此项目，确保代码风格一致、规范统一。

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [目录结构](#3-目录结构)
4. [开发规范](#4-开发规范)
5. [模块开发模板](#5-模块开发模板)
6. [依赖注入规范](#6-依赖注入规范)
7. [RAG 服务规范](#7-rag-服务规范)
8. [AI Coding 约束](#8-ai-coding-约束)

---

## 1. 项目概述

### 1.1 技术栈

| 层级 | 技术 |
|------|------|
| Web框架 | FastAPI 0.135+ |
| ORM | SQLAlchemy 2.x (异步) |
| 数据验证 | Pydantic 2.x / Pydantic-settings |
| 数据库 | MySQL/PostgreSQL + ChromaDB/PGVector |
| 缓存 | Redis |
| 日志 | Loguru |
| HTTP客户端 | httpx.AsyncClient |
| 认证 | JWT (PyJWT) + Argon2 |

### 1.2 核心能力

- **RAG 系统**：混合检索（稠密向量 + 稀疏BM25）+ RRF融合 + Rerank + LLM生成
- **模型管理**：支持 LLM、Embedding、Reranker 多种模型的配置与管理
- **知识库管理**：文档上传、分块、索引、检索全流程
- **用户认证**：JWT Token + Refresh Token Rotation + 设备管理

---

## 2. 架构设计

### 2.1 分层架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        应用层 (Application)                       │
│                   RAG应用、Agent应用                              │
├─────────────────────────────────────────────────────────────────┤
│                        路由层 (Router)                           │
│     API路由函数 ←→ Request/Response Schema ←→ Service            │
├─────────────────────────────────────────────────────────────────┤
│                        服务层 (Service)                           │
│  Business Logic + Pipeline (复杂逻辑组织)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────────────────────────┐  │
│  │   模型接入层     │  │          服务组件层                  │  │
│  │   (Factory +    │  │  DocumentLoader / Splitter /       │  │
│  │    Provider)    │  │  DenseStore / SparseStore (ABC)    │  │
│  └─────────────────┘  └─────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    数据代理层 (Repository)                        │
│           封装数据库操作，事务管理                                 │
├─────────────────────────────────────────────────────────────────┤
│                    数据模型层 (Models)                            │
│        SQLAlchemy 2.x ORM + Pydantic 2.x Schema                │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    基础设置层                             │   │
│  │  存储(MySQL/PG/Chroma) | 缓存(Redis) | 队列(Kafka等)    │   │
│  │  系统设置(Pydantic-Settings)                              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流示例：RAG 检索流程

```
用户查询
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  KnowledgeBaseService.retrieve()                             │
├──────────────────────────────────────────────────────────────┤
│  1. 验证 KB 存在性                                            │
│  2. 获取检索配置 (top_k, threshold, weights)                 │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│  RAGRetrievalService.retrieve()                              │
├──────────────────────────────────────────────────────────────┤
│  1. Query Understanding (Multi-Query扩展)                   │
│  2. 并行执行:                                                 │
│     ├── Dense检索 (Embedding → ChromaDB/PGVector)            │
│     └── Sparse检索 (jieba分词 → BM25)                        │
│  3. RRF融合 (Reciprocal Rank Fusion)                        │
│  4. 相似度过滤 (可选)                                         │
│  5. Rerank精排 (可选, Cross-Encoder)                         │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
返回检索结果 (DocumentUnit + score)
```

---

## 3. 目录结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   │
│   ├── api/                 # API 路由汇总
│   │   └── v1/
│   │       └── routers.py   # 路由注册
│   │
│   ├── common/              # 跨模块通用代码 ⭐核心沉淀区
│   │   ├── base.py         # Base ORM类, TimestampMixin
│   │   ├── exceptions.py   # 业务异常类 + 异常处理器
│   │   ├── responses.py    # APIResponse, PageData
│   │   ├── logger.py       # Loguru配置
│   │   └── storage.py      # 文件存储抽象基类
│   │
│   ├── core/                # 核心配置
│   │   ├── settings.py    # Pydantic Settings
│   │   ├── security.py    # JWT, 密码加密
│   │   └── middlewares.py # 中间件
│   │
│   ├── dependencies/        # FastAPI 依赖注入 ⭐核心沉淀区
│   │   ├── __init__.py    # 类型别名导出 (CurrentUser, Pagination等)
│   │   ├── auth.py        # 认证依赖链
│   │   ├── pagination.py  # 分页参数
│   │   ├── storage.py     # 文件存储依赖
│   │   └── infras/        # 基础设施依赖
│   │       ├── database.py # 异步DB会话 + 装饰器
│   │       └── cache.py    # Redis连接
│   │
│   ├── modules/             # 业务模块 ⭐模块开发区
│   │   ├── users/         # 用户模块
│   │   ├── auth/          # 认证模块
│   │   ├── llm_model/     # LLM模型管理
│   │   ├── embedding_model/ # Embedding模型管理
│   │   ├── rerank_model/  # Rerank模型管理
│   │   └── knowledge_base/ # 知识库管理
│   │       ├── models.py
│   │       ├── schema.py
│   │       ├── repository.py
│   │       ├── service.py
│   │       └── router.py
│   │
│   ├── services/            # 服务组件层 ⭐核心沉淀区
│   │   ├── providers/      # 模型接入层
│   │   │   ├── base.py    # ABC接口 (LLMProvider, EmbeddingProvider, RerankerProvider)
│   │   │   ├── http_client.py # httpx.AsyncClient 封装
│   │   │   ├── model_factory.py # 工厂函数 + LRU缓存
│   │   │   ├── openai_compatible.py # OpenAI兼容实现
│   │   │   └── reranks.py # Reranker实现
│   │   └── rag/           # RAG服务
│   │       ├── stores/    # 存储抽象
│   │       │   ├── base.py # DenseStore, SparseStore ABC
│   │       │   ├── chroma_dense.py
│   │       │   ├── pg_dense.py
│   │       │   └── pg_sparse.py
│   │       ├── document_loader.py
│   │       ├── text_splitter.py
│   │       ├── retrieval_service.py # 混合检索
│   │       ├── index_service.py
│   │       └── service_factory.py
│   │
│   └── utils/              # 工具函数
│       ├── datetime_utils.py
│       ├── encrypt_utils.py
│       └── lru_cache.py
│
├── alembic/                # 数据库迁移
├── tests/                  # 测试
└── pyproject.toml          # 项目配置
```

---

## 4. 开发规范

### 4.1 模块结构规范

每个业务模块必须包含以下文件（以 `llm_model` 为例）：

```
modules/llm_model/
├── __init__.py           # 模块导出
├── models.py             # SQLAlchemy ORM 模型
├── schema.py             # Pydantic Request/Response Schema
├── repository.py         # 数据访问层
├── service.py            # 业务逻辑层
└── router.py             # API路由
```

### 4.2 模型定义规范

```python
# app/modules/llm_model/models.py
import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base  # 必须使用 common.base.Base
from app.utils.datetime_utils import now_utc


class LLMType(StrEnum):
    """枚举类使用 StrEnum"""
    OPENAI_COMPATIBLE = "openai_compatible"
    LOCAL = "local"


class LlmModel(Base):
    """ORM模型：主键使用 UUID String"""
    
    __tablename__ = "llm_models"  # 复数形式命名
    
    id: Mapped[str] = mapped_column(
        String(64), 
        primary_key=True, 
        default=lambda: uuid.uuid4().hex  # UUID生成
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # 时间戳字段使用 now_utc
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=now_utc, 
        nullable=False
    )
```

### 4.3 Schema 定义规范

```python
# app/modules/llm_model/schema.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class LlmModelBase(BaseModel):
    """基础Schema：定义公共字段"""
    name: str = Field(..., min_length=1, max_length=255)
    # ... 其他字段


class LlmModelCreate(LlmModelBase):
    """创建Schema：继承Base，可添加创建专用字段"""
    pass


class LlmModelUpdate(BaseModel):
    """更新Schema：所有字段可选，使用 exclude=True 处理敏感字段"""
    name: str | None = Field(None, min_length=1, max_length=255)
    api_key: str | None = Field(None, exclude=True)  # 不在响应中暴露


class LlmModelResponse(LlmModelBase):
    """响应Schema：配置 from_attributes=True"""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    encrypted_api_key: str | None = None  # 加密存储
    api_key: str | None = Field(None, exclude=True)  # 敏感字段排除
    created_at: datetime
    updated_at: datetime
```

### 4.4 Repository 规范

```python
# app/modules/llm_model/repository.py
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.llm_model.models import LlmModel
from app.modules.llm_model.schema import LlmModelCreate, LlmModelUpdate


class LlmModelRepository:
    """数据访问层：封装所有数据库操作"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self, 
        user_id: int, 
        data: LlmModelCreate,
        encrypted_api_key: str | None = None,  # 加密密钥作为独立参数
    ) -> LlmModel:
        """创建记录"""
        model = LlmModel(
            user_id=user_id,
            name=data.name,
            # ... 其他字段
        )
        self.db.add(model)
        await self.db.flush()      # flush 而非 commit
        await self.db.refresh(model)
        return model
    
    async def get_by_id(self, model_id: str, user_id: int) -> LlmModel | None:
        """查询：必须包含 user_id 过滤"""
        stmt = select(LlmModel).where(
            LlmModel.id == model_id, 
            LlmModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[LlmModel], int]:
        """分页查询：返回 (items, total)"""
        # Count查询
        count_stmt = select(func.count()).select_from(LlmModel).where(
            LlmModel.user_id == user_id
        )
        total = (await self.db.execute(count_stmt)).scalar_one()
        
        # 分页查询
        offset = (page - 1) * page_size
        stmt = (
            select(LlmModel)
            .where(LlmModel.user_id == user_id)
            .order_by(LlmModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        
        return items, total
```

### 4.5 Service 规范

```python
# app/modules/llm_model/service.py
from app.common.exceptions import NotFoundException, ValidationException
from app.common.responses import PageData
from app.modules.llm_model.models import LlmModel
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.llm_model.schema import (
    LlmModelCreate, LlmModelResponse, LlmModelUpdate
)
from app.utils.encrypt_utils import encrypt_api_key


class LlmModelService:
    """业务逻辑层"""
    
    def __init__(self, repo: LlmModelRepository):
        self.repo = repo
    
    def _to_response(self, model: LlmModel) -> LlmModelResponse:
        """ORM → Response DTO 转换"""
        return LlmModelResponse.model_validate(model)
    
    async def _get_model_by_id(self, model_id: str, user_id: int) -> LlmModel:
        """内部方法：获取模型或抛异常"""
        model = await self.repo.get_by_id(model_id, user_id)
        if not model:
            raise NotFoundException("LLM Model", model_id)
        return model
    
    async def create_model(
        self, user_id: int, data: LlmModelCreate
    ) -> LlmModelResponse:
        """创建模型：验证 → 加密 → 创建"""
        # 唯一性检查
        existing = await self.repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(f"LLM model '{data.name}' already exists")
        
        # 清理默认标记
        if data.is_default:
            await self.repo.clear_default_flags(user_id)
        
        # 加密敏感字段
        encrypted_key = None
        if data.api_key:
            encrypted_key = encrypt_api_key(data.api_key)
        
        model = await self.repo.create(user_id, data, encrypted_api_key=encrypted_key)
        return self._to_response(model)
    
    async def list_models(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> PageData[LlmModelResponse]:
        """列表查询：返回 PageData"""
        items, total = await self.repo.list_by_user(user_id, page, page_size)
        return PageData(
            items=[self._to_response(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
```

### 4.6 Router 规范

```python
# app/modules/llm_model/router.py
from typing import Annotated
from fastapi import APIRouter, Depends, Query

from app.common.responses import APIResponse, PageData
from app.dependencies import CurrentUser  # 预定义类型别名
from app.dependencies.infras import DBAsyncSession
from app.modules.llm_model.repository import LlmModelRepository
from app.modules.llm_model.schema import (
    LlmModelCreate, LlmModelResponse, LlmModelUpdate
)
from app.modules.llm_model.service import LlmModelService

router = APIRouter()


def get_llm_model_repository(db: DBAsyncSession) -> LlmModelRepository:
    return LlmModelRepository(db)


def get_llm_model_service(
    repo: Annotated[LlmModelRepository, Depends(get_llm_model_repository)]
) -> LlmModelService:
    return LlmModelService(repo)


# 类型别名，方便复用
LLMModelServiceDep = Annotated[LlmModelService, Depends(get_llm_model_service)]


@router.post("", response_model=APIResponse[LlmModelResponse], status_code=201)
async def create_llm_model(
    data: LlmModelCreate,
    current_user: CurrentUser,  # 认证用户注入
    service: LLMModelServiceDep,
):
    """创建 LLM 模型"""
    model = await service.create_model(current_user.id, data)
    return APIResponse(data=model, message="创建成功")


@router.get("", response_model=APIResponse[PageData[LlmModelResponse]])
async def list_llm_models(
    current_user: CurrentUser,
    service: LLMModelServiceDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """列表查询"""
    return APIResponse(data=await service.list_models(current_user.id, page, page_size))
```

---

## 5. 模块开发模板

### 5.1 完整模块代码模板

```python
# ============================================================
# app/modules/example_module/models.py
# ============================================================
import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base
from app.utils.datetime_utils import now_utc


class ExampleModule(Base):
    __tablename__ = "example_modules"
    
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid.uuid4().hex
    )
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )


# ============================================================
# app/modules/example_module/schema.py
# ============================================================
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ExampleModuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    is_active: bool = True


class ExampleModuleCreate(ExampleModuleBase):
    pass


class ExampleModuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class ExampleModuleResponse(ExampleModuleBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_id: int
    created_at: datetime
    updated_at: datetime


# ============================================================
# app/modules/example_module/repository.py
# ============================================================
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.example_module.models import ExampleModule
from app.modules.example_module.schema import ExampleModuleCreate, ExampleModuleUpdate


class ExampleModuleRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, user_id: int, data: ExampleModuleCreate) -> ExampleModule:
        model = ExampleModule(user_id=user_id, name=data.name, is_active=data.is_active)
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return model
    
    async def get_by_id(self, model_id: str, user_id: int) -> ExampleModule | None:
        stmt = select(ExampleModule).where(
            ExampleModule.id == model_id, 
            ExampleModule.user_id == user_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
    
    async def list_by_user(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> tuple[list[ExampleModule], int]:
        count_stmt = select(func.count()).select_from(ExampleModule).where(
            ExampleModule.user_id == user_id
        )
        total = (await self.db.execute(count_stmt)).scalar_one()
        
        offset = (page - 1) * page_size
        stmt = (
            select(ExampleModule)
            .where(ExampleModule.user_id == user_id)
            .order_by(ExampleModule.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total
    
    async def update(
        self, model: ExampleModule, data: ExampleModuleUpdate
    ) -> ExampleModule:
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)
        for field, value in update_data.items():
            setattr(model, field, value)
        await self.db.flush()
        await self.db.refresh(model)
        return model
    
    async def delete(self, model: ExampleModule) -> None:
        await self.db.delete(model)
        await self.db.flush()


# ============================================================
# app/modules/example_module/service.py
# ============================================================
from app.common.exceptions import NotFoundException, ValidationException
from app.common.responses import PageData
from app.modules.example_module.models import ExampleModule
from app.modules.example_module.repository import ExampleModuleRepository
from app.modules.example_module.schema import (
    ExampleModuleCreate, ExampleModuleResponse, ExampleModuleUpdate
)


class ExampleModuleService:
    def __init__(self, repo: ExampleModuleRepository):
        self.repo = repo
    
    def _to_response(self, model: ExampleModule) -> ExampleModuleResponse:
        return ExampleModuleResponse.model_validate(model)
    
    async def _get_by_id(self, model_id: str, user_id: int) -> ExampleModule:
        model = await self.repo.get_by_id(model_id, user_id)
        if not model:
            raise NotFoundException("Example Module", model_id)
        return model
    
    async def create(
        self, user_id: int, data: ExampleModuleCreate
    ) -> ExampleModuleResponse:
        existing = await self.repo.get_by_name(user_id, data.name)
        if existing:
            raise ValidationException(f"Module '{data.name}' already exists")
        
        model = await self.repo.create(user_id, data)
        return self._to_response(model)
    
    async def list(
        self, user_id: int, page: int = 1, page_size: int = 20
    ) -> PageData[ExampleModuleResponse]:
        items, total = await self.repo.list_by_user(user_id, page, page_size)
        return PageData(
            items=[self._to_response(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    async def update(
        self, model_id: str, user_id: int, data: ExampleModuleUpdate
    ) -> ExampleModuleResponse:
        model = await self._get_by_id(model_id, user_id)
        updated = await self.repo.update(model, data)
        return self._to_response(updated)
    
    async def delete(self, model_id: str, user_id: int) -> None:
        model = await self._get_by_id(model_id, user_id)
        await self.repo.delete(model)


# ============================================================
# app/modules/example_module/router.py
# ============================================================
from typing import Annotated
from fastapi import APIRouter, Depends, Query

from app.common.responses import APIResponse, PageData
from app.dependencies import CurrentUser
from app.dependencies.infras import DBAsyncSession
from app.modules.example_module.repository import ExampleModuleRepository
from app.modules.example_module.schema import (
    ExampleModuleCreate, ExampleModuleResponse, ExampleModuleUpdate
)
from app.modules.example_module.service import ExampleModuleService

router = APIRouter()


def get_repository(db: DBAsyncSession) -> ExampleModuleRepository:
    return ExampleModuleRepository(db)


def get_service(
    repo: Annotated[ExampleModuleRepository, Depends(get_repository)]
) -> ExampleModuleService:
    return ExampleModuleService(repo)


ServiceDep = Annotated[ExampleModuleService, Depends(get_service)]


@router.post("", response_model=APIResponse[ExampleModuleResponse], status_code=201)
async def create(
    data: ExampleModuleCreate,
    current_user: CurrentUser,
    service: ServiceDep,
):
    return APIResponse(data=await service.create(current_user.id, data), message="创建成功")


@router.get("", response_model=APIResponse[PageData[ExampleModuleResponse]])
async def list(
    current_user: CurrentUser,
    service: ServiceDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return APIResponse(data=await service.list(current_user.id, page, page_size))


@router.get("/{model_id}", response_model=APIResponse[ExampleModuleResponse])
async def get(
    model_id: str,
    current_user: CurrentUser,
    service: ServiceDep,
):
    return APIResponse(data=await service.get(model_id, current_user.id))


@router.put("/{model_id}", response_model=APIResponse[ExampleModuleResponse])
async def update(
    model_id: str,
    data: ExampleModuleUpdate,
    current_user: CurrentUser,
    service: ServiceDep,
):
    return APIResponse(data=await service.update(model_id, current_user.id, data))


@router.delete("/{model_id}", status_code=204)
async def delete(
    model_id: str,
    current_user: CurrentUser,
    service: ServiceDep,
):
    await service.delete(model_id, current_user.id)
```

---

## 6. 依赖注入规范

### 6.1 依赖类型别名（app/dependencies/__init__.py）

```python
from typing import Annotated
from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings

# 基础设施依赖
from .cache import get_cache
from .database import get_db

# 系统设置
AppSettings = Annotated[Settings, Depends(get_settings)]

# 数据库会话
DBAsyncSession = Annotated[AsyncSession, Depends(get_db)]

# Redis缓存
CacheClient = Annotated[Redis, Depends(get_cache)]

# 业务依赖
from app.dependencies.auth import get_current_user
CurrentUser = Annotated[User, Depends(get_current_user)]  # 需要在 auth.py 后定义

from app.dependencies.pagination import PageParams, get_page_params
Pagination = Annotated[PageParams, Depends(get_page_params)]
```

### 6.2 认证依赖链（app/dependencies/auth.py）

```
get_token_payload → validate_access_token → get_user → get_current_user
     │                    │                    │              │
     ▼                    ▼                    ▼              ▼
  解析JWT            检查类型+黑名单      查询用户记录     验证用户状态
```

```python
# 1. 解析Token
async def get_token_payload(
    token: HTTPAuthorizationCredentials = Depends(security),
    settings: Settings = Depends(get_settings),
) -> TokenPayload:
    try:
        payload = jwt.decode(token.credentials, settings.SECRET_KEY, algorithms=[...])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token 已过期")
    return TokenPayload(...)

# 2. 校验Token
async def validate_access_token(
    payload: TokenPayload = Depends(get_token_payload),
    redis: Redis = Depends(get_cache),
) -> TokenPayload:
    # 检查黑名单
    if await redis.get(blacklist_key):
        raise UnauthorizedException("Token 已被注销")
    return payload

# 3. 获取用户
async def get_user(
    payload: TokenPayload = Depends(validate_access_token),
    repo: UserRepository = Depends(get_user_repository),
) -> User:
    user = await repo.get_by_id(payload.user_id)
    if not user or user.is_deleted:
        raise NotFoundException("用户不存在", f"ID: {payload.user_id}")
    return user

# 4. 当前用户（完整校验）
async def get_current_user(
    user: User = Depends(get_user),
) -> User:
    if not user.is_active:
        raise UnauthorizedException("用户已被禁用")
    return user
```

### 6.3 分页依赖（app/dependencies/pagination.py）

```python
class PageParams(BaseModel):
    page: int
    page_size: int
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
    
    def calc_has_more(self, total: int) -> bool:
        return self.page * self.page_size < total


def get_page_params(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=1000, description="每页数量"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)
```

---

## 7. RAG 服务规范

### 7.1 抽象基类定义（app/services/rag/stores/base.py）

```python
class DocumentUnit(BaseModel):
    """RAG模块内流通的核心数据结构"""
    document_id: str  # 外部生成的UUID
    kb_id: str
    file_id: str
    content: str
    metadata: dict = Field(default_factory=dict)


class DenseStore(ABC):
    """稠密向量存储抽象基类"""
    
    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        """返回 (文档, 分数) 列表"""
        pass
    
    @abstractmethod
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        pass
    
    @abstractmethod
    async def delete_by_file_id(self, file_id: str) -> int:
        pass


class SparseStore(ABC):
    """稀疏存储抽象基类（BM25关键词检索）"""
    
    @abstractmethod
    async def add_documents(self, docs: list[DocumentUnit]) -> None:
        pass
    
    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[tuple[DocumentUnit, float]]:
        pass
    
    @abstractmethod
    async def delete_by_document_ids(self, document_ids: list[str]) -> int:
        pass
    
    @abstractmethod
    async def delete_by_file_id(self, file_id: str) -> int:
        pass
```

### 7.2 模型接入工厂（app/services/providers/model_factory.py）

```python
# 使用LRU缓存避免重复创建昂贵的模型实例
llm_cache = LruCache(max_size=20)
embedding_cache = LruCache(max_size=10)
reranker_cache = LruCache(max_size=10)


def create_llm(model: LlmModel) -> LLMProvider:
    """创建或从缓存获取LLM Provider"""
    cache_key = _llm_cache_key(model)
    
    cached = llm_cache.get(cache_key)
    if cached:
        return cached
    
    # 根据类型创建
    if model.provider == LLMType.OPENAI_COMPATIBLE:
        provider = OpenAICompatibleLLMProvider(
            api_key=decrypt_api_key(model.encrypted_api_key),
            base_url=model.base_url,
            model=model.model_name,
            temperature=model.temperature,
            max_tokens=model.max_tokens,
        )
    # ...
    
    llm_cache.put(cache_key, provider)
    return provider


def create_embedding(model: EmbeddingModel) -> EmbeddingProvider:
    """创建或从缓存获取Embedding Provider"""
    # ...类似逻辑


def create_reranker(model: RerankModel) -> RerankerProvider:
    """创建或从缓存获取Reranker Provider"""
    # ...类似逻辑
```

### 7.3 RAG服务工厂（app/services/rag/service_factory.py）

```python
async def create_rag_retrieval_service(
    kb: KbDocument,
    llm_model_id: str | None = None,
    vector_db_type: str = "postgresql",  # chromadb | postgresql
    sparse_db_type: str = "postgresql",
) -> RAGRetrievalService:
    """
    创建RAG检索服务
    
    流程：
    1. 从数据库获取模型配置
    2. 通过工厂创建模型Provider
    3. 构建存储实例
    4. 组装服务返回
    """
    session_getter = get_db()
    db_session = await anext(session_getter)
    try:
        # 获取Embedding Provider
        embedding_repo = EmbeddingModelRepository(db_session)
        embedding_model = await embedding_repo.get_by_id(kb.embedding_model_id, kb.user_id)
        embedding_provider = create_embedding(embedding_model)
        
        # 获取Reranker Provider (可选)
        reranker_provider = None
        if kb.rerank_model_id:
            reranker_repo = RerankModelRepository(db_session)
            rerank_model = await reranker_repo.get_by_id(kb.rerank_model_id, kb.user_id)
            reranker_provider = create_reranker(rerank_model)
        
        # 获取LLM Provider (可选)
        llm_provider = None
        if llm_model_id:
            llm_repo = LlmModelRepository(db_session)
            llm_model = await llm_repo.get_by_id(llm_model_id, kb.user_id)
            llm_provider = create_llm(llm_model)
        
        # 构建存储
        dense_store = _build_dense_store(kb, embedding_provider, vector_db_type)
        sparse_store = _build_sparse_store(sparse_db_type)
    finally:
        await db_session.close()
    
    return RAGRetrievalService(
        dense_store=dense_store,
        sparse_store=sparse_store,
        embedding_provider=embedding_provider,
        reranker_provider=reranker_provider,
        llm_provider=llm_provider,
    )
```

---

## 8. AI Coding 约束

### 8.1 必须遵循的规范

#### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块目录 | 蛇形小写，复数形式 | `llm_model`, `knowledge_base` |
| ORM模型类 | PascalCase | `LlmModel`, `KbDocument` |
| Schema类 | PascalCase + 后缀 | `LlmModelCreate`, `LlmModelResponse` |
| Repository类 | PascalCase + Repository | `LlmModelRepository` |
| Service类 | PascalCase + Service | `LlmModelService` |
| Router变量 | snake_case + Dep | `LLMModelServiceDep` |
| 数据库表名 | 蛇形小写，复数 | `llm_models`, `kb_documents` |
| 枚举类 | PascalCase + Enum | `LLMType`, `ChunkStatus` |
| 主键字段 | `id` | UUID String类型 |
| 外键字段 | `xxx_id` | `user_id`, `kb_id` |

#### 文件组织

- **每个模块独立目录**：不允许跨模块文件交叉引用导致循环依赖
- **依赖方向**：Router → Service → Repository → Model
- **Schema位置**：与模块同级，非 shared 目录
- **异常类位置**：统一在 `app/common/exceptions.py` 定义

### 8.2 代码生成约束

#### 创建新模块时

1. 创建目录结构：`models.py`, `schema.py`, `repository.py`, `service.py`, `router.py`
2. 使用本模板的代码结构
3. 注册路由到 `app/api/v1/routers.py`
4. 添加单元测试

#### 修改现有模块时

1. 理解现有代码结构，遵循相同模式
2. 保持 Repository/Service/Router 的分离
3. 不修改其他模块的内部实现

### 8.3 禁止事项

```python
# ❌ 禁止：在Service层直接操作数据库会话
class BadService:
    async def bad_method(self, db: AsyncSession):
        await db.execute(select(User))  # 应该在Repository中

# ❌ 禁止：在Router层处理业务逻辑
@router.post("/users")
async def bad_create(user_data: UserCreate):
    if len(user_data.name) < 2:  # 应该在Service中验证
        raise ValidationException(...)
    # ...

# ❌ 禁止：跨模块直接引用其他模块的Repository
from app.modules.users.repository import UserRepository  # 在knowledge_base/service中不应出现

# ❌ 禁止：使用同步数据库操作
with Session() as session:  # 应该使用 AsyncSession
    ...

# ❌ 禁止：在响应中暴露敏感字段
class UserResponse:
    password: str  # 应该 exclude=True

# ❌ 禁止：使用 print 代替日志
print("debug")  # 应该使用 logger
```

### 8.4 异常处理规范

```python
# 使用预定义异常类
from app.common.exceptions import (
    BusinessException,          # 基类
    ValidationException,        # 校验失败 400
    UnauthorizedException,      # 未认证 401
    ForbiddenException,         # 无权限 403
    NotFoundException,          # 不存在 404
    UniqueViolationException,    # 唯一性冲突 400
    RateLimitException,          # 频率限制 429
    AIProviderException,         # AI提供商错误
)

# 抛出异常
raise NotFoundException("LLM Model", model_id)
raise ValidationException(f"Model '{name}' already exists")
```

### 8.5 日志规范

```python
from loguru import logger

# 记录操作
logger.info(f"Creating LLM model: {name}")
logger.info(f"User {user_id} logged in")

# 记录警告（业务异常）
logger.warning(f"BusinessException: path={url} code={code} message={msg}")

# 记录错误（非预期异常）
logger.error(f"Database operation failed: {e}")
logger.error(f"Failed to delete from vector store: {e}")
```

---

## 附录：关键文件索引

| 文件路径 | 说明 |
|----------|------|
| `app/common/base.py` | Base ORM, TimestampMixin |
| `app/common/exceptions.py` | 异常类定义 |
| `app/common/responses.py` | APIResponse, PageData |
| `app/common/logger.py` | Loguru配置 |
| `app/common/storage.py` | 文件存储抽象 |
| `app/core/settings.py` | Pydantic Settings |
| `app/core/security.py` | JWT, 密码加密 |
| `app/dependencies/__init__.py` | 类型别名导出 |
| `app/dependencies/auth.py` | 认证依赖链 |
| `app/dependencies/infras/database.py` | 异步DB会话 |
| `app/services/providers/base.py` | Provider ABC接口 |
| `app/services/providers/model_factory.py` | 模型工厂 |
| `app/services/rag/stores/base.py` | Store ABC接口 |
| `app/services/rag/retrieval_service.py` | RAG检索服务 |
| `app/api/v1/routers.py` | 路由注册汇总 |

---

*文档版本：1.0*
*最后更新：2026-04-05*

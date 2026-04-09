# AI Studio Backend 全局架构蓝图与重构实施计划

**日期**: 2026-04-10  
**状态**: Draft v1  
**适用范围**: 当前 `backend/` 全项目  
**目标**: 统一后端全局架构思想、关键依赖规则、可插拔演进方向与 worktree 重构计划

---

## 1. 文档目标

本蓝图文档用于回答四类问题：

1. 当前项目的架构到底是什么，为什么会让人感觉“有准则但又有点乱”
2. 从全局角度看，哪些分层是正确方向，哪些边界已经开始失真
3. 如果后续需要长期维护与演进，应该采用什么更稳的架构方式
4. 如果决定在短期不加新功能的窗口内进行重构，应如何分阶段实施

本文件是一个项目级的架构说明，不局限于某单一模块。

---

## 2. 项目现状概述

### 2.1 当前已形成的三类代码区域

从当前代码结构看，项目已经自然形成了三类区域：

- `app/modules/*`
  - 面向用户与业务资源的模块
  - 典型结构为 `router / schema / service / repository / models`
- `app/services/*`
  - 面向能力运行时与接入层的代码
  - 当前主要包括 `providers / rag / agent / mcp`
- `app/common`、`app/core`、`app/dependencies`
  - 共享基础设施
  - 包括异常、响应、设置、数据库依赖、中间件、日志等

### 2.2 当前已经做对的部分

- CRUD 型业务模块有统一开发结构，维护成本相对可控
- 模型接入、RAG、MCP、Agent 已经开始被抽象成独立能力层
- RAG 已有 `DenseStore / SparseStore` 抽象
- Provider 已有 `LLMProvider / EmbeddingProvider / RerankerProvider` 抽象
- MCP 已有 `MCPProvider` 抽象
- 基础设施沉淀区已经存在，说明项目具备进一步架构收口的基础

### 2.3 当前存在的核心问题

当前问题不是“完全没有架构”，而是：

- 代码同时按“业务模块”与“技术能力层”两条轴组织
- 但尚未把依赖方向和边界规则写成硬约束
- 因而局部开始出现反向依赖、装配职责混入、运行时与业务层耦合加深的问题

典型表现包括：

- 能力层直接依赖业务模块 ORM / repository
- service factory 同时承担配置获取、依赖装配、实例构建三类职责
- 业务 service 中混入过多 orchestration 和 runtime 装配
- 少数核心文件体量过大，说明职责已经聚集过头

---

## 3. 问题诊断

### 3.1 宏观问题：分层思想并存但未统一

当前项目同时存在以下三种架构语言：

- 传统 Web 分层：
  - router
  - service
  - repository
  - models
- 面向能力平台的分层：
  - providers
  - rag runtime
  - agent runtime
  - mcp layer
- Clean / Hexagonal 的局部雏形：
  - store/provider/mcp 的抽象接口
  - factory / builder / adapter 的出现

这些思想并不冲突，但如果没有统一规则，就会造成：

- 某些模块更像“业务应用层”
- 某些模块更像“平台层”
- 某些文件则同时混合了应用编排、基础设施访问与运行时装配

### 3.2 微观问题：边界已开始穿透

当前最值得警惕的不是目录名，而是依赖方向已经开始穿透。

常见穿透模式有：

- 平台层直接知道业务模块 ORM model 的字段结构
- 平台层内部自行打开数据库会话
- 平台层直接实例化 repository
- runtime 层反向依赖业务模块中的工具定义或领域对象
- 大型业务 service 同时承担“读配置、查库、组装 provider、构建 runtime、执行流程、持久化回写”

### 3.3 结果：可插拔看似存在，实际替换成本仍偏高

例如理论上项目希望支持：

- DenseStore: PostgreSQL -> Milvus
- SparseStore: PostgreSQL -> Elasticsearch
- 模型接入层：OpenAI Compatible -> 更多 provider 范式
- MCP Layer：单连接模式 -> 连接池 / 熔断 / 自适应运行时

但如果能力层和业务层、数据库层之间的边界不清晰，这些替换虽然可以做，却很难做到“局部替换、最小波及”。

---

## 4. 架构目标

本项目后续架构应服务于以下目标：

- 在不牺牲开发效率的前提下提升可维护性
- 允许核心能力层独立演进
- 让大部分替换发生在 adapter 层，而不是业务流程层
- 保持 CRUD 模块开发简单，不为了架构而架构
- 让项目既能支持个人快速开发，也能经得住后续复杂度上升

---

## 5. 推荐的最终架构思想

### 5.1 总体结论

本项目最适合采用的，不是“全仓库纯 textbook Clean Architecture”，也不是继续保持目前的自然生长状态，而是：

**业务模块层 + 能力平台层 + 共享基础设施层**

同时在真正需要可插拔演进的核心区域，引入：

**Application / Domain / Ports / Adapters 的思想**

换句话说，这是一个：

**全局务实分层 + 核心能力区 Hexagonal 化**

的架构方案。

### 5.2 为什么不是全仓库纯 Clean / Hexagonal

如果把整个项目所有模块都强行重构为 textbook 式的 `domain / application / ports / adapters`：

- 理论上最干净
- 但对大量 CRUD 型模块收益不高
- 反而会显著增加目录层级、样板代码和认知成本

因此更合理的策略是：

- 对核心能力平台层采用更严格的端口与适配器设计
- 对普通业务资源模块维持更务实的 `router + application service + repository + models` 结构

### 5.3 为什么不是纯 feature-only 架构

如果完全按 feature 收拢为：

- `modules/agent`
- `modules/rag`
- `modules/provider`
- `modules/mcp`

会有一个问题：

- `providers`、`rag runtime`、`agent runtime`、`mcp` 并不只是业务资源
- 它们更像“平台能力”而非单纯 feature

因此保留独立的能力平台层更符合项目本质。

---

## 6. 推荐的全局分层

### 6.1 第一层：共享基础设施层

建议将以下区域视为基础设施层：

- `app/common`
- `app/core`
- `app/dependencies`

职责：

- settings
- DB / cache / queue 依赖
- middleware
- logger
- response / exception
- 安全与认证基础能力

该层不承载业务编排。

### 6.2 第二层：业务模块层

建议将 `app/modules/*` 视为业务应用层。

职责：

- 暴露 API
- 管理业务资源
- 做 ownership 校验
- 组织业务流程
- 协调 repository 与能力平台层
- 决定“何时调用 provider / rag / agent / mcp”

此层是用户视角最强的一层。

### 6.3 第三层：能力平台层

建议将 `app/services/*` 视为能力平台层。

当前主要包括：

- `app/services/providers`
- `app/services/rag`
- `app/services/agent`
- `app/services/mcp`

职责：

- 封装可复用运行时能力
- 提供端口与适配器
- 隔离外部 SDK / 模型厂商 / 向量库 / MCP 协议细节
- 成为可插拔演进的主要承载区

---

## 7. 关键依赖规则

以下规则应被视为本项目后续开发中的硬规则。

### 7.1 全局依赖方向

- `app/modules/*` 可以依赖 `app/services/*`
- `app/services/*` 可以依赖 `app/common`、`app/core`
- `app/services/*` 不应反向依赖 `app/modules/*`
- `app/common`、`app/core` 不依赖业务模块

### 7.2 Router 规则

- router 只负责 HTTP 协议层工作
- router 不直接编排复杂流程
- router 不直接访问 repository
- router 不负责 runtime / provider / store 的实例装配

### 7.3 Application Service 规则

- application service 负责 use case 编排
- application service 负责 ownership、权限、流程协调、事务边界
- application service 可以调用 repository
- application service 可以调用能力平台层
- application service 不应直接写入外部 SDK 细节

### 7.4 Repository 规则

- repository 只负责持久化访问
- repository 不承担 runtime 装配职责
- repository 不负责 HTTP / SDK / 模型调用
- repository 不承载业务流程状态机

### 7.5 平台层规则

- 平台层对外暴露 port / interface / builder / runtime 能力
- 平台层不直接开启数据库会话
- 平台层不直接实例化业务模块 repository
- 平台层不长期依赖 ORM model 作为输入对象
- 平台层优先接收 config DTO、domain object 或 port 接口

### 7.6 Domain 规则

- domain 对象应尽量保持纯 Python
- domain 层不依赖 FastAPI
- domain 层不依赖 SQLAlchemy
- domain 层不依赖 httpx、OpenAI SDK、MCP SDK 等基础设施

### 7.7 Adapter 规则

- 外部系统集成放在 adapter 中实现
- PostgreSQL、Milvus、Elasticsearch、OpenAI、Cohere、MCP SDK 都应作为 adapter
- 切换实现时，优先替换 adapter，而不是改业务流程

### 7.8 Composition Root 规则

- 依赖装配应集中，而不是散落在 router、repository、runtime 各处
- “读配置 -> 解析配置 -> 构造 provider/store/runtime” 的逻辑应明确放在 application / assembler 层
- 平台层不负责到数据库里把自己的配置查出来

---

## 8. 核心子系统定位

### 8.1 `app/services/providers`

定位：

- 模型接入平台
- 提供统一的 LLM / Embedding / Rerank 抽象

未来目标：

- 支持更多 provider 范式
- 隔离不同厂商协议差异
- 对上提供稳定接口

建议：

- `model_factory` 不应长期吃 ORM model
- 应改为接收 provider config DTO 或 port
- provider 实现应只关心推理调用，不关心业务模块如何存储模型配置

### 8.2 `app/services/rag`

定位：

- RAG runtime 平台
- 提供索引与检索能力

未来目标：

- DenseStore 可替换
- SparseStore 可替换
- Query Understanding / Rerank / Retrieval Pipeline 可持续演化

建议：

- `service_factory` 应逐步从“查库 + 装配 + 构造”转为“纯装配”
- 知识库业务层负责把配置解析成 runtime 所需对象

### 8.3 `app/services/agent`

定位：

- Agent runtime 平台
- 提供 SimpleAgent / ReactAgent 等执行引擎

未来目标：

- 支持更多 AgentType
- 支持更复杂的 tool orchestration
- 支持更清晰的 runtime protocol

建议：

- runtime 不反向依赖业务模块
- Tool 协议应尽量在平台层稳定
- session / run / config 的持久化编排应留在 Agent 业务层

### 8.4 `app/services/mcp`

定位：

- MCP 平台层
- 面向未来 Phase 6~8 独立演进

未来目标：

- 连接池
- 熔断
- 超时治理
- 自适应运行时

建议：

- 持续保持与 Agent 业务层解耦
- 只暴露 MCP port / provider 能力，不承担业务配置读取职责

### 8.5 `app/modules/*`

定位：

- 用户与业务资源入口层

建议：

- 保持资源导向和模块清晰
- 复杂模块增加 application/use-case 子层
- 普通 CRUD 模块可以继续保留轻量结构

---

## 9. 推荐的目录演进方向

本蓝图不要求一次性全仓库搬目录，但建议逐步朝以下结构演进：

```text
app/
├── common/                       # 共享通用能力
├── core/                         # 核心配置与系统级基础设施
├── dependencies/                 # 依赖注入与组合根
├── modules/                      # 业务应用层
│   ├── auth/
│   ├── users/
│   ├── llm_model/
│   ├── embedding_model/
│   ├── rerank_model/
│   ├── knowledge_base/
│   │   ├── router.py
│   │   ├── schema.py
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── application/
│   └── agent/
│       ├── router.py
│       ├── schema.py
│       ├── models.py
│       ├── repository.py
│       └── application/
├── services/                     # 能力平台层
│   ├── providers/
│   │   ├── domain/
│   │   ├── ports/
│   │   └── adapters/
│   ├── rag/
│   │   ├── domain/
│   │   ├── ports/
│   │   ├── adapters/
│   │   └── runtime/
│   ├── agent/
│   │   ├── domain/
│   │   ├── ports/
│   │   ├── adapters/
│   │   └── runtime/
│   └── mcp/
│       ├── domain/
│       ├── ports/
│       └── adapters/
```

这不是要求当前立刻全部改成这样，而是作为重构终局方向。

---

## 10. 可插拔演进策略

### 10.1 DenseStore 演进

目标：

- `postgresql -> chroma -> milvus` 等演进不影响上层检索流程

做法：

- 定义 `DenseStore` port
- 各存储实现放在 adapter 层
- `RAGRetrievalService` / `RAGIndexService` 只依赖 port

### 10.2 SparseStore 演进

目标：

- `postgresql FTS -> Elasticsearch / OpenSearch`

做法：

- 定义 `SparseStore` port
- 稀疏检索融合逻辑不依赖具体引擎

### 10.3 MCP Layer 演进

目标：

- 从当前单连接/临时 session 模式，逐步进入连接池、超时治理、熔断、重试、自适应运行时

做法：

- Agent 只依赖 MCP platform 暴露的稳定接口
- 连接池策略仅在 `app/services/mcp` 内演化

### 10.4 模型接入层演进

目标：

- 从 OpenAI Compatible 范式向多 provider、多协议扩展

做法：

- 通过 `LLMProvider / EmbeddingProvider / RerankerProvider` 收口上层依赖
- provider config 与 ORM model 解耦

---

## 11. 本项目的推荐重构策略

### 11.1 结论

不建议一步把全项目改成最重的 textbook Clean Architecture。

推荐策略是：

- 保持全局三大层：
  - 业务模块层
  - 能力平台层
  - 共享基础设施层
- 对核心可演进区执行更严格的 Hexagonal 化
- 对普通 CRUD 模块采用务实分层

这是更符合当前项目现实、开发成本与长期收益平衡的方案。

### 11.2 哪些区域优先 Hexagonal 化

优先级最高：

- `app/services/providers`
- `app/services/rag`
- `app/services/agent`
- `app/services/mcp`

次优先级：

- `app/modules/knowledge_base`
- `app/modules/agent`

优先级较低：

- `auth`
- `users`
- `llm_model`
- `embedding_model`
- `rerank_model`

---

## 12. worktree 重构实施计划

### 12.1 总体原则

- 在新 worktree 中进行，不污染主线
- 先写蓝图，再分阶段重构
- 每一阶段都要求定向测试与导入检查通过
- 不在重构阶段顺手新增功能

### 12.2 预计总工期

在“短期不加新功能、个人项目、可集中推进”的前提下，预计：

- 激进版：10 到 12 个工作日
- 稳妥版：12 到 15 个工作日

推荐采用稳妥版。

### 12.3 分阶段计划

#### 阶段 0：基线冻结与依赖图确认

预计：1 到 2 天

产出：

- 当前依赖图
- 重构边界说明
- 回归检查清单

#### 阶段 1：Provider 平台收口

预计：1 到 2 天

目标：

- 去除 provider 层对业务 ORM 的直接长期依赖
- 引入 config DTO / port

#### 阶段 2：RAG 平台端口化

预计：2 到 3 天

目标：

- 将 DenseStore / SparseStore / provider 装配边界收清
- 让 `service_factory` 从“查库型”变为“装配型”

#### 阶段 3：KnowledgeBase 业务层重构

预计：1 到 2 天

目标：

- 让 KB service 只做业务编排
- RAG runtime 的构建交由明确 assembler 完成

#### 阶段 4：Agent 平台与业务层分离

预计：3 到 5 天

目标：

- 拆解超大 `AgentService`
- 明确 config / session / run / mcp_server 几个 use case
- 让 agent runtime 更像平台而不是业务 service 的下属细节

#### 阶段 5：全局清理与验收

预计：2 到 3 天

目标：

- 清理旧 import
- 文档更新
- 关键回归测试
- 运行时链路验证

### 12.4 验收标准

- 依赖规则不再被关键模块打穿
- 平台层不再直接查业务数据库配置
- 可插拔点通过 port 暴露
- Agent / RAG 核心链路不回退
- 关键 smoke / unit / targeted integration 验证通过

### 12.5 回滚策略

- 每个阶段单独提交
- 阶段失败时在 worktree 内局部回滚
- 主线在整个重构完成前保持稳定

---

## 13. 架构决策与非目标

### 13.1 当前架构决策

- 项目采用“全局务实分层 + 核心能力区 Hexagonal 化”的路线
- `services/mcp` 继续视为可独立演进的平台层
- Agent 与 RAG 是 runtime 平台，不应被简单视为普通 CRUD 模块

### 13.2 当前非目标

- 当前阶段不追求把所有模块都改造成 textbook 式的纯 Clean Architecture
- 当前阶段不要求所有业务枚举都立即做数据库层约束
- 当前阶段不以目录搬迁本身为目标，而以依赖方向与装配职责收口为优先目标

---

## 14. 老板 / 面试官常见问题与回答

### Q1：你们这个项目现在采用的是什么架构？

**A：**
整体上是一个“业务模块层 + 能力平台层 + 共享基础设施层”的混合架构。  
在模型接入、RAG、Agent、MCP 这些核心可演进区，进一步引入了 ports/adapters 和 application/domain 的思想，用来支持未来的可插拔替换与独立演进。

### Q2：为什么不直接把全项目都做成纯 Clean Architecture？

**A：**
因为不是所有模块都值得付出同样高的抽象成本。  
对 CRUD 型模块，务实分层更高效；对 Provider、RAG、Agent、MCP 这类高演进、高耦合风险的能力平台，Hexagonal 才有明显价值。  
所以我们采用“局部重型、全局务实”的策略。

### Q3：为什么不完全按 feature 来组织？

**A：**
因为这个项目里有一类代码并不是单纯业务 feature，而是平台能力，比如模型接入、RAG runtime、Agent runtime、MCP protocol。  
这些能力会被多个业务模块复用，也需要独立演进，所以保留平台层更合理。

### Q4：你们如何保证后续能把 PostgreSQL 向量检索替换成 Milvus？

**A：**
通过把 `DenseStore` 抽象成 port，让上层 retrieval/indexing 流程只依赖抽象，不依赖具体存储实现。  
迁移时主要替换 adapter 和装配映射，而不是修改检索主流程。

### Q5：如果以后稀疏检索从 PostgreSQL FTS 切到 Elasticsearch，会影响业务层吗？

**A：**
理想状态下不会。  
业务层只关心“有稀疏检索能力”，不会关心底层是 PostgreSQL FTS 还是 Elasticsearch。  
变化应主要落在 `SparseStore` 的 adapter 与装配层。

### Q6：为什么 MCP 要单独做成一层，而不是直接写在 Agent 里？

**A：**
因为 MCP 本质上是协议与运行时连接问题，不是 Agent 独有的业务逻辑。  
单独分层后，可以独立演进连接池、超时控制、熔断与传输协议支持，同时避免 Agent 模块承担协议细节。

### Q7：你们如何理解 router、service、repository 三层？

**A：**
router 负责协议转换，service 负责 use case 编排，repository 负责持久化访问。  
如果 service 同时负责查库、组装 provider、执行 runtime、处理状态回写，就说明职责过载，需要进一步拆分。

### Q8：为什么你们强调“平台层不反向依赖业务模块”？

**A：**
因为一旦平台层直接依赖业务模块 ORM、repository 或 settings 细节，它就不再是平台，而变成特定业务实现的一部分。  
这样会显著降低复用性，也会让可插拔演进失效。

### Q9：这个项目后续最值得重构的部分是哪几个？

**A：**
优先级最高的是：

- `app/services/providers`
- `app/services/rag`
- `app/services/agent`
- `app/modules/knowledge_base`
- `app/modules/agent`

因为这些区域最直接承载运行时复杂度和未来演进压力。

### Q10：如果你是负责人，为什么会选择在没有新功能压力的窗口重构？

**A：**
因为这是成本最低、收益最高的时机。  
功能稳定时重构，更容易建立清晰边界、补测试、统一依赖规则；如果等到功能继续膨胀后再做，成本会更高，回归风险也会更大。

### Q11：你们的架构设计如何兼顾个人项目开发效率？

**A：**
核心策略是不做过度抽象。  
只有在真正需要插拔和长期演进的能力层，才采用更严格的 ports/adapters；普通 CRUD 模块继续保持轻量结构，这样既保留效率，也能把复杂度控制在该控制的地方。

### Q12：这套架构最大的价值是什么？

**A：**
最大的价值不是“看起来更漂亮”，而是：

- 让复杂能力层更容易独立迭代
- 让替换底层实现时影响面更小
- 让业务模块和平台模块职责更清楚
- 让后续维护、排障和扩展成本持续下降

---

## 15. 结论

本项目已经具备从“自然生长型分层”升级为“有明确依赖规则的可演进架构”的基础。

推荐方向不是推倒重来，而是：

- 在全局上采用
  - 业务模块层
  - 能力平台层
  - 共享基础设施层
- 在核心可插拔区域采用
  - application
  - domain
  - ports
  - adapters

这条路线能在控制复杂度的同时，最大化保留项目后续演进空间。

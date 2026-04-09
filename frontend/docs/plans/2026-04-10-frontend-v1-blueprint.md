# 前端 V1 开发蓝图：React 19 + Vite + Tauri 2 的桌面工作台

## Summary

计划文档的目标存放位置固定为：

- `/Users/lining/Documents/full-stack_engineer/Full-StackWorkspace/AI-Studio-Community/frontend/docs/plans/2026-04-10-frontend-v1-blueprint.md`

后续前端代码、文档、实现与重构都只在：

- `/Users/lining/Documents/full-stack_engineer/Full-StackWorkspace/AI-Studio-Community/frontend/`

内展开。

前端按“浏览器优先开发、后续 Tauri 2 打包”的路线推进，整体产品壳采用 Cherry Studio 式桌面应用框架，首页定位为工作台首页，知识库模块采用“管理 + 检索调试 + RAG Chat 内聚”的结构，Agent 模块采用“助手列表 + 配置详情 + 对话页”的结构，系统配置页集中承载“能力配置 + 账户设置”。

技术决策固定如下：

- React 19 作为客户端 React 应用使用，不采用 Server Components 作为主架构
- Vite 6+ + TypeScript + pnpm
- 路由使用 React Router data router，采用 HashRouter 路线以兼容浏览器开发与后续 Tauri 打包
- 服务端状态统一用 TanStack Query
- 客户端 UI 状态只用 Zustand
- 表单统一用 React Hook Form + Zod
- UI 基座用 shadcn/ui + Tailwind CSS 4 + Framer Motion
- API 类型采用基于 `/Users/lining/Downloads/openapi.json` 生成 TypeScript 类型，接口调用和 Query hooks 手写

## Key Changes

### 1. 工程与目录结构

前端工程只在现有目录 `/Users/lining/Documents/full-stack_engineer/Full-StackWorkspace/AI-Studio-Community/frontend/` 内实现，结构固定为：

```text
frontend/
├── docs/
│   ├── plans/
│   ├── specs/
│   └── references/
├── src/
│   ├── app/
│   │   ├── providers.tsx
│   │   ├── router.tsx
│   │   ├── query-client.ts
│   │   └── auth-guard.tsx
│   ├── api/
│   │   ├── client.ts
│   │   ├── types.generated.ts
│   │   └── endpoints/
│   │       ├── auth.ts
│   │       ├── user.ts
│   │       ├── knowledge-base.ts
│   │       ├── agent.ts
│   │       └── settings.ts
│   ├── components/
│   │   ├── ui/
│   │   ├── layout/
│   │   └── shared/
│   ├── features/
│   │   ├── auth/
│   │   ├── home/
│   │   ├── knowledge-base/
│   │   ├── agent/
│   │   ├── chat/
│   │   └── settings/
│   ├── routes/
│   │   ├── login.tsx
│   │   ├── register.tsx
│   │   ├── home.tsx
│   │   ├── knowledge-bases.tsx
│   │   ├── knowledge-base-detail.tsx
│   │   ├── agents.tsx
│   │   ├── agent-detail.tsx
│   │   ├── chat.tsx
│   │   └── settings.tsx
│   ├── lib/
│   │   ├── utils.ts
│   │   ├── env.ts
│   │   ├── storage.ts
│   │   └── validators/
│   ├── store/
│   │   ├── ui-store.ts
│   │   └── shell-store.ts
│   ├── types/
│   ├── main.tsx
│   └── styles.css
├── src-tauri/
└── package.json
```

固定规则：

- `docs/` 也放在 `frontend/` 内，和后端文档分离
- `routes/` 只放页面入口
- `features/` 放模块组件、表单、局部 hooks
- `api/endpoints/` 放按资源分组的 query/mutation hooks
- `store/` 只放 UI 状态，不放 Query 已管理的数据
- `lib/storage.ts` 提供 token 存储抽象，先用浏览器存储实现，后续换 Tauri store/secure storage 时不改业务层

### 2. 顶层产品信息架构

主壳子采用左侧桌面导航 + 顶部轻工具栏 + 主内容区三段式布局。

一级导航固定为：

- 首页
- 知识库
- Agent
- 系统配置

次级内容定义如下：

- 首页
  - 欢迎区
  - 最近会话
  - 常用助手
  - 知识库概览
  - 模型 / MCP 状态卡片
  - 快捷入口
- 知识库
  - 列表页
  - 创建/编辑弹层或侧栏
  - 详情页内置四个页签：`Overview / Files / Retrieve / Chat`
- Agent
  - 助手列表页
  - 助手详情页内置四个页签：`基础配置 / Tools / MCP / KB`
  - 从详情页或列表直接“新建对话”
- 系统配置
  - 账户信息
  - MCP Servers
  - Chat Models
  - Embedding Models
  - Rerank Models
  - 内置工具列表

路由固定为：

- `/#/login`
- `/#/register`
- `/#/home`
- `/#/knowledge-bases`
- `/#/knowledge-bases/:kbId`
- `/#/agents`
- `/#/agents/:configId`
- `/#/chat/:sessionId`
- `/#/settings`
- `/#/settings/account`
- `/#/settings/mcp-servers`
- `/#/settings/models/chat`
- `/#/settings/models/embedding`
- `/#/settings/models/rerank`
- `/#/settings/tools`

### 3. 后端 API 到前端页面的映射

基于 `openapi.json`，页面能力按以下方式绑定：

- 认证
  - `POST /v1/auth/login`
  - `POST /v1/auth/register`
  - `POST /v1/auth/refresh`
  - `POST /v1/auth/logout`
  - `GET /v1/user/info`
- 知识库
  - 列表/创建/更新/删除：`/v1/knowledge-bases`
  - 文件上传与索引：`/v1/knowledge-bases/{kb_id}/files`、`.../index`
  - 检索调试：`POST /v1/knowledge-bases/retrieve`
  - KB Chat：`POST /v1/knowledge-bases/rag`
- Agent
  - 助手列表/详情：`/v1/agent/configs`
  - 内置工具：`/v1/agent/builtin-tools`
  - 助手子配置：`tools / mcp-servers / kbs`
  - 会话与聊天：`/v1/agent/sessions`、`/v1/agent/sessions/{session_id}/runs`
- 系统配置
  - MCP 管理：`/v1/agent/mcp-servers`
  - Chat Models：`/v1/llm-models`
  - Embedding Models：`/v1/embedding-models`
  - Rerank Models：`/v1/rerank-models`
  - 账户设置：`/v1/user/info`、`/v1/user/update`、`/v1/user/password`、`/v1/user/avatar`

明确约束：

- “全局管理内置工具”当前后端只有 `GET /v1/agent/builtin-tools`
- 因此前端 `设置 -> 内置工具` 第一版做只读能力目录页，不做全局增删改后台

### 4. 状态、表单和数据流规则

固定状态边界：

- TanStack Query 管理：
  - 当前用户
  - 助手列表/详情
  - Session / messages / steps / runs
  - 知识库列表/详情/文件
  - 模型配置
  - MCP Server 列表
- Zustand 只管理：
  - 左侧导航折叠
  - 当前工作区 tab
  - 草稿输入
  - 本地筛选条件
  - 主题 / 窗口偏好
  - 当前选中但未提交的 UI 状态

固定表单规则：

- 每个 feature 下都有本模块 Zod schema
- RHF 统一配 `zodResolver`
- 提交前做前端 schema 校验
- 提交后依赖 Query mutation 统一做 toast、invalidate、乐观更新

关键用户流固定如下：

- Agent 对话流
  - 助手列表 -> 助手详情 -> 点击“新建对话”
  - `POST /v1/agent/sessions` 带 `config_id`
  - 跳转到 `/chat/:sessionId`
  - 发送消息触发 `POST /v1/agent/sessions/{session_id}/runs`
- 知识库流
  - 知识库列表 -> 详情
  - `Files` 页签做上传与索引
  - `Retrieve` 页签做检索调试
  - `Chat` 页签做多 KB RAG 问答，但第一版默认当前详情页 KB 为主
- 设置流
  - 模型和 MCP 管理页统一采用列表 + 详情抽屉/弹窗
  - 默认模型切换通过已有 `/default` 接口完成

### 5. 实施顺序

第一阶段按下面顺序开发：

1. 工程初始化
   - Tauri React/Vite 模板
   - Tailwind 4
   - shadcn/ui
   - QueryClientProvider
   - Router
   - 基础 AppShell
2. 认证与应用壳
   - 登录页
   - 注册页
   - token 存储抽象
   - 当前用户加载
   - 路由守卫
3. 首页工作台
   - 欢迎区
   - 最近会话卡片
   - 常用助手卡片
   - 知识库概览
   - 模型/MCP 状态摘要
4. 知识库模块
   - 列表页
   - 创建/编辑
   - 详情页
   - Files / Retrieve / Chat 四页签
5. Agent 模块
   - 助手列表
   - 助手详情与多 tab 编辑
   - 新建对话
   - Chat 页面
6. 系统配置模块
   - MCP Servers
   - Chat Models
   - Embedding Models
   - Rerank Models
   - 内置工具目录
   - 账户设置
7. Tauri 集成收口
   - 窗口标题与菜单
   - 存储适配器预留
   - 桌面打包验证

## Test Plan

固定验收范围：

- 单元/组件测试
  - AppShell 导航渲染
  - Auth guard 跳转
  - 关键表单的 Zod + RHF 校验
  - Agent 新建对话按钮行为
  - KB Retrieve / Chat 面板提交行为
- API 层测试
  - auth token 注入
  - 401 刷新/登出处理
  - Query hook 成功与错误分支
- 页面验收场景
  - 登录后进入首页
  - 创建知识库并上传文件
  - 在 KB 详情页执行 Retrieve 和 RAG Chat
  - 创建 AgentConfig 并添加工具/MCP/KB
  - 从 Agent 详情页新建对话并完成一次 run
  - 在系统配置页完成 MCP / 模型的增删改查
- 打包前验收
  - 浏览器开发模式完整可用
  - Tauri dev 可启动
  - 路由、静态资源和 API base URL 在 Tauri 环境下正常

## Assumptions

- 前端第一阶段采用“完整桌面骨架”，不是一次把所有高级细节做满
- 整体视觉采用 Cherry 式桌面产品壳，知识库详情局部借鉴 RAGFlow 的工作台结构
- 首页定位为工作台首页，不是纯跳转页
- 系统配置第一版同时包含能力配置与账户设置
- 知识库 Chat 放在知识库详情页内，不单独拆独立模块
- React 19 仅作为客户端 React 使用，不引入 RSC 主架构
- API 类型从 `openapi.json` 生成，但 TanStack Query hooks 和调用层手写
- token 持久化第一版通过存储抽象走浏览器实现，后续再接 Tauri 插件
- 内置工具第一版只做只读目录与说明页，因为当前后端没有全局管理 API

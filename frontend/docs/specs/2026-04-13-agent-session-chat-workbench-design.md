# Agent Session 与 Chat 工作台设计方案

## 背景

当前 Agent 模块已经具备以下基础能力：

- AgentConfig 列表与详情编辑
- Tools / MCP / KB 的配置绑定
- 基于 AgentConfig 创建 Session
- 通过 `/v1/agent/sessions/{session_id}/runs` 发起一次对话执行

但从产品使用角度看，当前工作流仍然存在两个明显缺口：

1. 缺少 Session 列表，用户无法围绕某个助手管理历史会话
2. Chat 页面仍处于调试态，消息区直接展示 JSON，缺乏正式聊天工作区体验

因此，Agent 模块下一阶段的目标不应只是“美化聊天页”，而应升级为：

**一个助手 = 一个配置工作区 + 一个会话工作区**

也就是：

- Agent 详情页负责配置
- Agent 会话列表负责进入和管理对话
- Chat 页负责正式的问答与运行反馈

## 方案结论

本阶段采用以下方案：

1. 在 Agent 模块中补齐 Session 列表能力
2. 将 Chat 页从调试态升级为正式版聊天工作区
3. 暂不直接进入流式 SSE 体验，先把非流式体验打磨完整

推荐优先顺序：

- Phase 1：补齐 Session 列表
- Phase 2：升级 Chat 正式版（非流式）
- Phase 3：为后续 SSE 流式增强预留结构

## 为什么先做非流式正式版

### 不直接上流式的原因

- 当前 Chat 页面仍处于结构性缺失阶段，问题首先是“不是聊天产品”，而不是“没有流式输出”
- 如果同时做页面重构和 SSE 事件接入，会把 UI、状态机、接口调试搅在一起，增加实现风险
- 当前后端非流式 run 已可用，足以支撑正式版聊天工作台的第一阶段交付

### 为什么 Session 列表必须和 Chat 一起做

- 只有“新建会话”没有“会话列表”，用户无法管理历史对话
- Agent 模块从用户心智上是“助手 -> 会话 -> 对话内容”
- 如果缺少 Session 列表，Chat 页面只能成为一次性测试入口，不像正式产品

## 产品心智

### 核心对象

- AgentConfig：助手定义
- Session：该助手下的一次对话会话
- Run：某次具体执行
- Message / Step：对话消息与执行步骤

### 用户操作流

1. 用户进入 Agent 列表
2. 点击某个助手进入详情页
3. 在详情页查看基础配置、工具、MCP、知识库
4. 在详情页下方或独立区域查看该助手的 Session 列表
5. 点击已有会话进入 Chat 页，或点击“新建对话”创建新的 Session
6. 在 Chat 页中持续发送消息，并查看回答与执行步骤

## 页面结构

## Agent 详情页

当前 `AgentDetailRoute` 已具备多 tab 配置结构，本阶段不推翻现有结构，只做增强：

- 保留 `基础配置 / Tools / MCP / KB`
- 在页面下半部分新增 `Session` 工作区

### Session 工作区包含

1. 会话列表
- 显示该 AgentConfig 相关的 Session
- 显示标题、更新时间、创建时间
- 支持点击进入会话

2. 会话操作
- 新建对话
- 刷新列表

3. 空态
- 当前助手还没有会话时，提示创建第一个对话

## Chat 页面

Chat 页从当前调试态页面升级为正式工作区，结构分为左右两栏：

### 左侧：聊天主区域

1. 顶部会话头部
- 会话标题
- 当前绑定助手名称
- 会话更新时间

2. 中间消息流
- 区分用户消息与助手消息
- 助手消息支持多段文本展示
- 发送中时展示“思考中 / 回复生成中”状态
- 错误时展示清晰错误卡片，而不是原始 JSON

3. 底部输入区
- 多行输入框
- 发送按钮
- Enter / Shift+Enter 行为后续可增强，本阶段先保证点击发送稳定

### 右侧：运行面板

1. 会话摘要
- Session ID
- 当前 AgentConfig 摘要
- 创建时间 / 更新时间

2. 执行步骤
- 展示最近一次运行的 step 列表
- 区分 LLM 思考、工具调用、工具结果、最终响应

3. 调试信息（轻量化）
- 本阶段保留少量运行信息
- 不直接展示大段 JSON
- 主要用于“可理解的运行过程反馈”

## Session 列表的数据要求

### 前端需要的最小字段

- `id`
- `title`
- `config_id`
- `created_at`
- `updated_at`

### 关键缺口

后端 `AgentService` 中已有 `list_sessions()` 能力，但当前 `router.py` 尚未暴露 `GET /v1/agent/sessions`。

因此本阶段需要补充一个正式列表接口，至少支持：

- 按当前用户分页获取 Session 列表
- 支持可选的 `config_id` 过滤，以便 Agent 详情页只展示某个助手关联的会话

推荐接口形态：

- `GET /v1/agent/sessions?page=1&page_size=20&config_id=...`

## API 映射

### 当前已存在并可复用

- `POST /v1/agent/sessions`
- `GET /v1/agent/sessions/{session_id}`
- `GET /v1/agent/sessions/{session_id}/messages`
- `GET /v1/agent/sessions/{session_id}/steps`
- `POST /v1/agent/sessions/{session_id}/runs`

### 本阶段建议新增

- `GET /v1/agent/sessions`

### 后续阶段再考虑

- `POST /v1/agent/sessions/{session_id}/runs` 的 SSE 可视化增强
- `POST /v1/agent/runs/{run_id}/resume`
- `POST /v1/agent/runs/{run_id}/stop`

## 前端模块边界

建议新增以下组件：

- `features/agent/session-list.tsx`
- `features/agent/chat/chat-header.tsx`
- `features/agent/chat/chat-message-list.tsx`
- `features/agent/chat/chat-composer.tsx`
- `features/agent/chat/chat-step-panel.tsx`
- `features/agent/chat/types.ts`
- `features/agent/chat/utils.ts`

路由层职责：

- `agent-detail.tsx`
  - 继续负责 AgentConfig 详情页容器
  - 额外接入 Session 列表 query 与新建会话入口

- `chat.tsx`
  - 只做会话页容器
  - 组织 session / messages / steps / run mutation
  - 渲染正式版 chat 组件树

## 状态管理规则

### TanStack Query

用于：

- AgentConfig 详情
- Session 列表
- Session 详情
- Session messages
- Session steps

### 本地组件状态

用于：

- 输入框内容
- 当前发送状态
- 最近一次本地提交的消息
- 当前步骤面板展开状态

规则：

- 不把 Query 已管理的数据重复复制到 Zustand
- Chat 页优先以 query + mutation 驱动，不引入额外全局状态

## 文案与体验规则

### 避免的调试式文案

- “这里会渲染消息历史、步骤和调试信息”
- 原始 JSON 大块展示
- `latestResult` 直接 `JSON.stringify`

### 正式版应呈现的文案

- 用户消息
- 助手回答
- 本次执行步骤
- 工具调用
- 工具返回
- 暂无历史会话
- 开始第一轮对话
- 正在发送
- 本次执行失败，请重试

## 验证范围

本阶段完成后，至少要能稳定走通以下链路：

1. 进入 Agent 详情页
2. 查看当前助手相关会话列表
3. 点击“新建对话”
4. 成功跳转到 Chat 页
5. 发送一条消息
6. 在正式消息流中看到用户消息与助手回答
7. 在右侧步骤面板中看到 step 信息
8. 返回 Agent 详情页后，能看到新会话出现在 Session 列表中

## 非目标

本阶段不做以下内容：

- Chat 页 SSE 流式输出
- run resume / stop 完整交互
- 多会话分栏工作区
- Chat 页中的高级参数面板
- 消息编辑、重试发送、多轮局部回放

## 成功标准

只有满足以下条件，才能认为 Agent 会话工作流进入正式版阶段：

- Agent 模块具备正式的 Session 列表
- Chat 页不再出现调试式 JSON 展示
- 用户可以围绕某个助手创建、查看和继续历史会话
- 非流式聊天体验达到正式产品可用水平
- 关键链路通过前端测试、类型检查和浏览器联调验证

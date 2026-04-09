# Agent / Session 用户操作流与前后端交互设计

**日期**: 2026-04-10  
**状态**: Draft v1  
**范围**: AgentConfig、Session、Run 三者关系及前后端交互设计  
**适用阶段**: 当前 Agent API 基线

---

## 1. 文档目标

本设计文档用于回答以下问题：

1. 用户看到的“助手 / 智能体”在系统里到底对应什么对象
2. `AgentConfig`、`Session`、`Run` 三者分别代表什么
3. 为什么创建了完整 `AgentConfig` 之后，还需要新建 `Session`
4. `Session.title` 在用户操作上应该如何理解
5. 前端页面应如何组织“助手列表 -> 助手详情 -> 新建对话 -> 聊天”

---

## 2. 核心结论

### 2.1 用户视角中的“助手”就是 `AgentConfig`

在产品层面，用户创建出来并长期保存的“助手 / 智能体”，本质上是一个完整的：

- `AgentConfig`
- 加上它的子配置：
  - tools
  - mcp_servers
  - kbs

因此用户认知中的“一个助手”，不是单条数据库记录，而是一个完整配置对象。

### 2.2 `Session` 不是助手本身，而是助手下的一次对话

`Session` 的角色不是“定义助手”，而是：

- 表示用户和某个助手之间的一次独立对话
- 承载这次对话的消息历史
- 承载这次对话的摘要与上下文记忆

所以：

- `AgentConfig` = 助手模板 / 智能体预设
- `Session` = 这个助手下的一次聊天会话
- `Run` = 这次会话中的一次实际执行

### 2.3 `title` 是会话标题，不是助手标题

`Session.title` 的含义不是“助手名字”，而是：

- 这次对话的标题
- 相当于“聊天记录名称”

例如：

- 助手名：`Research Agent`
- 会话标题：`帮我调研 MCP 架构`
- 下一次会话标题：`今天的 AI 新闻总结`

因此：

- 助手名应该来自 `AgentConfig.name`
- 会话标题应该来自 `Session.title`

---

## 3. 三个核心对象的职责

### 3.1 AgentConfig

`AgentConfig` 是长期存在的助手定义。

它负责描述：

- 助手名称与描述
- 使用哪个模型
- 使用什么 agent_type
- 启用哪些内置工具
- 关联哪些 MCP Server
- 关联哪些知识库
- 默认 system prompt 和 max_loop

它的本质是：

- 可复用
- 可编辑
- 可长期保存
- 可被多个会话复用

### 3.2 Session

`Session` 是某个用户在某个时间点发起的一次独立会话。

它负责描述：

- 这次聊天属于谁
- 这次聊天使用哪个 `AgentConfig`
- 这次聊天的消息历史
- 这次聊天的摘要与轻量记忆
- 这次聊天在会话列表中的标题

它的本质是：

- 会话实例
- 聊天容器
- 对话上下文

### 3.3 Run

`Run` 是会话中的一次执行。

例如在一个 Session 中：

- 用户发第一条消息，会产生一个 run
- 用户发第二条消息，会产生第二个 run
- 发生 tool 调用、step、resume、stop 等都围绕 run 展开

因此：

- `AgentConfig` 是助手模板
- `Session` 是聊天线程
- `Run` 是线程中的一次实际执行

---

## 4. 推荐的用户自然操作模型

### 4.1 第一层：助手列表

用户进入“助手 / 智能体”页面时，看到的是：

- 助手卡片列表
- 每个卡片代表一个 `AgentConfig`

页面关注的信息包括：

- `name`
- `description`
- `agent_type`
- 可能的工具/MCP/KB 数量摘要
- 是否启用

在这一层，用户操作的是“助手”，不是 session。

### 4.2 第二层：助手详情 / 配置页

用户点击某个助手后，进入详情或编辑页。

这一层应使用：

- `GET /v1/agent/configs/{config_id}`

一次拿到完整 detail，用于回显：

- base fields
- tools
- mcp_servers
- kbs

这一层的核心动作是：

- 编辑助手配置
- 保存工具配置
- 关联或移除 MCP
- 关联或移除 KB

### 4.3 第三层：基于助手发起对话

用户在助手详情页或助手卡片上点击：

- “开始聊天”
- “新建对话”
- “使用这个助手”

此时前端应创建一个新的 `Session`，并把它绑定到当前 `AgentConfig`。

这一步的意义是：

- 用户不是在重新创建助手
- 而是在“基于已有助手开启一条新的聊天线程”

---

## 5. 推荐的前后端操作流

### 5.1 创建助手

用户先创建并配置好一个助手，即完成 `AgentConfig` 及其子配置。

对应 API 大致为：

1. `POST /v1/agent/configs`
2. `POST /v1/agent/configs/{config_id}/tools`
3. `POST /v1/agent/configs/{config_id}/mcp-servers`
4. `POST /v1/agent/configs/{config_id}/kbs`

### 5.2 展示助手

前端展示助手列表时：

- 调 `GET /v1/agent/configs`

展示助手详情时：

- 调 `GET /v1/agent/configs/{config_id}`

### 5.3 新建对话

用户点击某个助手上的“新建对话”时，推荐前端做两步：

1. 创建 session  
   `POST /v1/agent/sessions`

2. 绑定 config  
   `PATCH /v1/agent/sessions/{session_id}/config`

请求体：

```json
{
  "config_id": "agent-config-id"
}
```

### 5.4 开始聊天

绑定完成后，再调用：

- `POST /v1/agent/sessions/{session_id}/runs`

请求体示例：

```json
{
  "input": "请帮我分析今天的 AI agent 相关新闻",
  "stream": true,
  "debug": false
}
```

---

## 6. 为什么 `Session` 需要单独存在

### 6.1 一个助手会对应很多次对话

同一个助手，用户通常会多次使用。

例如一个名为 `Research Agent` 的助手，用户可能会开启很多次独立会话：

- 会话 A：调研 MCP 架构
- 会话 B：整理 LangGraph 学习笔记
- 会话 C：分析当天 AI 新闻

如果没有 `Session`，这些对话会混在一起，无法形成清晰的聊天线程。

### 6.2 会话级记忆不能直接写回助手模板

聊天过程中会产生：

- 消息历史
- summary
- 可能的中间状态

这些内容属于“某一次对话”，不应污染长期存在的助手配置。

所以：

- 助手模板负责定义默认能力
- 会话负责承载一次对话状态

### 6.3 同一助手的多个会话应该彼此独立

即使它们都绑定到同一个 `AgentConfig`，也应有独立：

- 消息历史
- run 列表
- summary
- 标题

这就是 `Session` 独立存在的根本原因。

---

## 7. 关于 `title` 的设计结论

### 7.1 当前字段含义

`POST /v1/agent/sessions` 中的 `title` 字段，语义上应理解为：

- 会话标题
- 历史聊天列表中的显示名称

而不是：

- 助手名称
- 用户必须填写的启动参数

### 7.2 推荐的前端策略

前端不应强制让用户在“开始聊天”前手动填写 `title`。

更自然的方式是：

- 创建 session 时 `title` 留空
- 用户发送第一条消息后，自动生成标题
- 或者以后允许用户手动重命名这条会话

### 7.3 推荐的产品逻辑

新建 session 时：

- `title` 可为空
- `mode` 使用默认值即可
- 真正关键的是把 `config_id` 绑定到这个 session

所以产品逻辑上：

- “新建对话”不是让用户填一堆字段
- 而是系统自动创建一个空会话容器

---

## 8. 推荐的页面交互设计

### 8.1 助手列表页

推荐页面元素：

- 助手卡片列表
- 新建助手按钮
- 编辑助手按钮
- 进入聊天按钮

用户动作：

- 新建助手
- 编辑助手
- 基于某个助手开始聊天

### 8.2 助手详情 / 编辑页

推荐页面结构：

- 基础信息 tab
- Tools tab
- MCP tab
- KB tab
- “开始聊天”按钮

交互原则：

- 配置编辑与聊天入口分离
- 助手是长期对象
- 不要求在此页直接产生会话

### 8.3 聊天页

聊天页应围绕 Session 展开。

推荐页面要素：

- 当前助手名称：来自 `AgentConfig.name`
- 当前会话标题：来自 `Session.title`
- 消息列表
- 输入框
- 可选的动态切换区：
  - 模型
  - KB
  - MCP
  - Tool

### 8.4 历史会话列表

如果后续实现历史聊天列表，列表对象应该是：

- `Session`

而不是 `AgentConfig`。

也就是说：

- 助手列表：展示模板
- 会话列表：展示对话

这是两个不同层次的页面。

---

## 9. 推荐的前端状态模型

前端实现上，推荐至少区分两类状态：

### 9.1 助手状态

对应 `AgentConfig`

作用：

- 配置页回显
- 助手列表展示
- 助手详情展示

### 9.2 会话状态

对应 `Session`

作用：

- 当前聊天线程
- 消息历史
- 当前 run 状态
- 标题与摘要

这两个状态不应混为一个对象。

---

## 10. API 语义总结

### 10.1 助手相关

- `POST /v1/agent/configs`
  - 创建助手基础配置
- `GET /v1/agent/configs`
  - 助手列表
- `GET /v1/agent/configs/{config_id}`
  - 助手完整详情
- `PUT /v1/agent/configs/{config_id}`
  - 更新助手基础配置
- `POST /v1/agent/configs/{config_id}/tools`
  - 为助手添加内置工具
- `POST /v1/agent/configs/{config_id}/mcp-servers`
  - 为助手关联 MCP
- `POST /v1/agent/configs/{config_id}/kbs`
  - 为助手关联 KB

### 10.2 会话相关

- `POST /v1/agent/sessions`
  - 创建一条新会话
- `PATCH /v1/agent/sessions/{session_id}/config`
  - 将会话绑定到某个助手配置
- `GET /v1/agent/sessions/{session_id}`
  - 读取会话

### 10.3 运行相关

- `POST /v1/agent/sessions/{session_id}/runs`
  - 在会话中发送一条消息并触发一次执行
- `GET /v1/agent/runs/{run_id}`
  - 查看某次执行
- `POST /v1/agent/runs/{run_id}/resume`
  - 恢复某次中断执行

---

## 11. 推荐的产品结论

从产品与用户心智看，当前系统应采用以下理解：

- 助手是 `AgentConfig`
- 聊天记录是 `Session`
- 一次消息执行是 `Run`

因此最自然的产品流程是：

1. 用户创建助手
2. 用户在页面上看到助手列表
3. 用户点击某个助手的“开始聊天”
4. 系统自动创建 session
5. 系统将 session 绑定到该助手配置
6. 用户开始发送消息
7. 系统在该 session 下连续产生多个 run

在这个模型下：

- `title` 是会话标题
- 不应要求用户在启动聊天前强制填写
- `config_id` 绑定才是“某条对话属于哪个助手”的关键动作

---

## 12. 后续前端开发建议

对于前端实现，建议优先遵循以下规则：

- 将“助手”与“对话”区分成两个概念
- 不把 `Session` 误当成助手本身
- 不让用户在“开始聊天”前理解数据库字段
- 创建 session 时尽量少暴露底层参数
- 用 `GET /configs/{config_id}` 作为助手编辑页的初始化数据源
- 用 `PATCH /sessions/{session_id}/config` 完成会话与助手绑定

---

## 13. 结论

`AgentConfig`、`Session`、`Run` 应分别对应：

- 助手定义
- 对话实例
- 一次执行

只要前后端始终坚持这三层心智一致，用户操作就会非常自然：

- 先创建助手
- 再基于助手开启新对话
- 然后在对话中持续交流

当前 API 已经具备支持这套产品流程的基础能力，关键在于前端交互设计不要把底层字段语义直接暴露给用户。

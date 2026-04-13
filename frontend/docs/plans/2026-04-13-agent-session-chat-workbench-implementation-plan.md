# Agent Session 与 Chat 工作台实施计划

## 目标

将当前 Agent 模块从“可配置 + 可发起一次对话”升级为“可管理会话 + 可正式聊天”的工作台形态。

本阶段聚焦两个核心方向：

- 补齐 Session 列表能力
- 重构 Chat 页为正式版（先非流式）

## 开发顺序

### Phase 1：补齐 Session 列表能力

- 后端暴露 `GET /v1/agent/sessions`
- 前端新增 Session 列表 hook
- Agent 详情页接入 Session 工作区

### Phase 2：重构 Chat 正式版（非流式）

- 将当前 JSON 消息区重构为正式消息流
- 增加消息头部、会话摘要、步骤面板
- 去掉调试式结果展示

### Phase 3：统一收口

- 完成空态、错误态、发送态统一
- 补测试与联调
- 为后续 SSE 流式版本预留结构

## Checklist

### API 与数据

- [ ] 后端提供 Session 列表接口
- [ ] Session 列表支持按 `config_id` 过滤
- [ ] Session 详情 / 消息 / 步骤接口返回结构满足前端展示需要
- [ ] Chat run 非流式返回结构可被正式 UI 正常消费

### 页面与交互

- [ ] Agent 详情页具备 Session 列表区
- [ ] Agent 详情页支持从 Session 列表进入历史会话
- [ ] Agent 详情页支持新建对话并刷新列表
- [ ] Chat 页具备正式消息流 UI
- [ ] Chat 页具备发送中、失败、空态
- [ ] Chat 页右侧具备步骤与会话摘要面板
- [ ] 页面中不再出现原始 JSON 调试块

### 工程与结构

- [ ] Session 列表逻辑独立组件化
- [ ] Chat 页按 header / message-list / composer / step-panel 拆分
- [ ] Query 数据不重复复制到 Zustand
- [ ] 现有 Agent 路由逻辑不被破坏

### 验证

- [ ] lint 通过
- [ ] 类型检查通过
- [ ] 关键页面测试通过
- [ ] Agent 会话主链路浏览器联调通过

## Tasklist

### T001：补齐 Session 列表 API

- 在后端 router 暴露 `GET /v1/agent/sessions`
- 支持分页参数
- 支持 `config_id` 过滤
- 返回前端可直接消费的列表数据

### T002：补前端 Session hooks

- 新增 `useSessions`
- 支持可选 `configId`
- 与 `useCreateSession`、`useSessionDetail` 形成一致 queryKey 体系

### T003：在 Agent 详情页接入 Session 工作区

- 新增 `session-list.tsx`
- 展示历史会话卡片
- 增加进入会话与新建对话入口
- 新建会话成功后刷新列表

### T004：重构 Chat 页主结构

- 新增 `chat-header.tsx`
- 新增 `chat-message-list.tsx`
- 新增 `chat-composer.tsx`
- 新增 `chat-step-panel.tsx`
- 去掉 JSON 调试块

### T005：收口 Chat 消息与步骤展示

- 统一用户/助手消息样式
- 统一发送中与错误反馈
- 将步骤展示收口成可读信息卡片

### T006：测试与联调

- 增补 Agent 详情页 Session 列表测试
- 增补 Chat 页正式版渲染测试
- 跑 `lint / check / test / build`
- 浏览器联调 Agent 会话主链路

## 会话执行建议

建议按如下节奏推进：

1. `T001 + T002`
2. `T003`
3. `T004 + T005`
4. `T006`

## 完成定义

只有满足以下条件，才能标记本阶段完成：

- Agent 详情页可以管理当前助手的 Session
- Chat 页达到正式聊天产品态，而不是调试态
- 用户可以查看历史会话并继续聊天
- 所有关键校验通过，且主链路联调成功

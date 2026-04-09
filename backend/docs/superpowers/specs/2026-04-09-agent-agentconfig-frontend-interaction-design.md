# Agent / AgentConfig 前后端交互与用户操作设计

**日期**: 2026-04-09  
**状态**: Draft v1（用于前端开发对齐）  
**范围**: Agent、AgentConfig、AgentConfigTool、AgentConfigMCP、AgentConfigKB 的前后端交互设计  
**适用阶段**: 当前代码基线为 Phase 5

---

## 1. 背景与目标

当前 Agent 模块在后端存储层已采用规范化分表设计：

- `AgentConfig`：基础配置
- `AgentConfigTool`：配置中的内置工具
- `AgentConfigMCP`：配置中的 MCP 资源
- `AgentConfigKB`：配置中的知识库资源

这种设计在数据库层面是合理的，能够避免将所有配置塞入单个 JSON 字段带来的查询、约束、唯一性和演进问题。

但在前后端交互层，必须进一步明确：

1. 用户在产品层面操作的对象到底是什么
2. “创建 Agent” 是否应该是一次性整包提交
3. 多 tab 的编辑器应如何与当前 API 协作
4. 哪些接口面向“局部写入”，哪些接口面向“页面初始化和回显”

本设计文档的目标是：

- 统一 Agent / AgentConfig 的用户心智
- 为前端实现多 tab 配置页提供明确交互基线
- 保留当前细粒度写接口的优势
- 明确需要补齐的聚合读取能力

---

## 2. 核心结论

### 2.1 用户操作对象是 AgentConfig，而不是关系表

对用户来说，“创建 Agent” 本质上是在创建一个可复用的 **AgentConfig**。  
用户不会把自己理解为在分别创建：

- 一条 `agent_configs`
- 多条 `agent_config_tools`
- 多条 `agent_config_mcp_servers`
- 多条 `agent_config_kbs`

这些分表只应存在于后端存储与实现层，对用户透明。

### 2.2 不强制要求“一次性整包提交”

当前产品方向更符合以下用户模式：

- 先创建一个基础 AgentConfig
- 再在不同 tab 中逐步补充 tools / MCP / KB
- 每个 tab 都有自己的保存动作
- 用户可以中途退出，后续继续编辑
- 聊天阶段还可能继续动态切换 LLM / KB / MCP / Tool

在这种模式下，**细粒度写接口是合理的**，并且优于整包覆盖式更新。

### 2.3 必须提供聚合读取能力

虽然写操作可以按模块拆分，但读操作不能要求前端自己去拼多个资源。

因此：

- `GET /configs/{config_id}` 应返回完整 detail
- detail 至少包含：
  - base fields
  - tools
  - mcp_servers
  - kbs

这是前端配置编辑页、tab 回显、页面缓存、聊天侧边栏状态初始化的关键基础能力。

一句话总结：

**写继续拆分，读必须聚合。**

---

## 3. 用户自然操作模式

### 3.1 创建 Agent 的用户路径

用户自然操作路径不是“大表单一次填完”，而是“分步完成一个长期配置对象”：

1. 进入“增加助手 / 创建 Agent”页面
2. 先填写基础配置：
   - 名称
   - 描述
   - 模型
   - agent_type
   - max_loop
   - system_prompt
3. 保存基础配置，生成一个 `config_id`
4. 再进入不同 tab：
   - Tools
   - MCP
   - KB
5. 每个 tab 内独立选择、添加、启用/禁用、保存
6. 用户可随时退出
7. 后续重新进入时，页面根据 `config_id` 恢复完整配置

这意味着：

- `AgentConfig` 是长期配置对象
- tab 是此对象的不同配置维度
- 每个 tab 的保存动作应当是局部、可恢复、可独立失败的

### 3.2 编辑 Agent 的用户路径

在编辑场景中，用户往往只修改一个维度：

- 改 system prompt
- 切换模型
- 关闭某个工具
- 增加一个 MCP server
- 增加一个知识库

因此写接口按子资源拆分是符合预期的。  
不应要求用户在每次改一个小项时都提交完整大对象。

### 3.3 聊天阶段的动态切换

在 chat 场景中，AgentConfig 仍然是核心“预设”，但界面可以在输入区下提供快捷入口，允许动态切换：

- 模型
- KB
- MCP
- Tool

这类操作在产品体验上更像“基于当前配置上下文进行临时或即时调整”，因此后端继续保留独立资源和细粒度更新接口是合理的。

---

## 4. 参考交互模式：Cherry Studio

Cherry Studio 的 Agents 公开文档体现出一种典型模式：

- 先创建/管理一个助手或 Agent 预设
- 再在聊天中使用该预设
- 配置对象是长期存在、可被反复编辑和复用的

参考资料：

- [Cherry Studio Agents Docs](https://docs.cherry-ai.com/cherry-studio/preview/agents)

这里的借鉴点是“配置对象优先、会话使用其配置、可持续迭代编辑”，而不是要求完全复制其 UI 细节。

**推断说明**：
本文对 Cherry Studio 的借鉴主要基于其公开文档所体现的产品模式，而非逐像素复刻其具体交互实现。

---

## 5. 当前 API 现状评估

### 5.1 当前合理的部分

当前 API 已经具备以下优点：

- `POST /configs`：创建基础配置
- `PUT /configs/{config_id}`：更新基础配置
- `POST /configs/{config_id}/tools`：添加工具
- `PUT /configs/{config_id}/tools/{tool_id}`：更新工具配置
- `POST /configs/{config_id}/mcp-servers`：关联 MCP
- `POST /configs/{config_id}/kbs`：关联 KB

这些接口非常适合：

- 多 tab 分步保存
- 自动保存
- 局部更新
- 独立失败处理

### 5.2 当前缺口

当前最核心的缺口不是写接口，而是读取接口。

当前：

- `GET /configs/{config_id}` 返回的是基础配置
- 不包含 tools / mcp_servers / kbs 全量 detail

这会导致前端为了回显一个配置页，不得不额外调用多个接口并自行拼装。

对于多 tab 配置页来说，这不是最佳实践。

---

## 6. 设计决策

### 6.1 保持写接口拆分

保留当前写接口粒度，不新增“必须使用的一次整包提交 API”。

原因：

- 更符合多 tab 编辑器
- 更适合局部保存
- 更适合未来聊天中动态变更配置能力
- 减少大对象覆盖写入带来的冲突和冗余

### 6.2 将 `GET /configs/{config_id}` 升级为 detail 返回

单资源读取应返回完整配置 detail。

建议返回结构：

```json
{
  "id": "cfg_xxx",
  "user_id": 1,
  "name": "Research Agent",
  "description": "For daily research",
  "llm_model_id": "model_xxx",
  "agent_type": "simple",
  "max_loop": 5,
  "system_prompt": "You are a helpful research assistant.",
  "enabled": true,
  "created_at": "2026-04-09T00:00:00Z",
  "updated_at": "2026-04-09T00:00:00Z",
  "tools": [
    {
      "id": 1,
      "config_id": "cfg_xxx",
      "tool_name": "calculator",
      "tool_config": {},
      "enabled": true
    }
  ],
  "mcp_servers": [
    {
      "id": 10,
      "config_id": "cfg_xxx",
      "mcp_server_id": "mcp_xxx"
    }
  ],
  "kbs": [
    {
      "id": 20,
      "config_id": "cfg_xxx",
      "kb_id": "kb_xxx",
      "kb_config": {
        "top_k": 5
      }
    }
  ]
}
```

### 6.3 `GET /configs` 继续返回 summary 列表

列表页不要求携带完整 detail。

`GET /configs` 保持 summary 返回是合理的，因为：

- 列表页通常只需要 name / description / model / enabled / updated_at
- 避免列表接口负载过重
- detail 仅在进入编辑页时按需获取

---

## 7. 前端页面与状态设计

### 7.1 配置编辑页初始化

编辑页加载时，前端调用：

`GET /v1/agent/configs/{config_id}`

拿到完整 detail 后：

- 存入页面级状态
- 按 tab 拆分映射到各自表单
- 用于页面初始回显

这份 detail 应视为该页面的“配置快照”。

### 7.2 多 tab 回显模式

推荐页面结构：

- Base Config Tab
- Tools Tab
- MCP Tab
- KB Tab

首次进入页面时：

- 只调用一次 `GET /configs/{config_id}`
- 页面缓存完整 detail
- 各 tab 从缓存中读取自己的初始数据

不建议每次切 tab 都重新请求多个接口，除非有明确的实时一致性要求。

### 7.3 tab 内保存模式

每个 tab 都是独立表单、独立保存：

- Base Config Tab
  - 调用 `PUT /configs/{config_id}`
- Tools Tab
  - 调用 `POST/PUT/DELETE /configs/{config_id}/tools...`
- MCP Tab
  - 调用 `POST/DELETE /configs/{config_id}/mcp-servers...`
- KB Tab
  - 调用 `POST/DELETE /configs/{config_id}/kbs...`

### 7.4 保存后的前端状态同步

保存成功后，前端有两种同步策略：

#### 方案 A：局部更新缓存（推荐）

- 直接把本次变更写回本地页面状态
- 优点：响应快，避免重复请求

适用于：

- 保存结果结构简单
- 后端不会生成复杂派生字段

#### 方案 B：保存后重新拉取 detail

- 再次请求 `GET /configs/{config_id}`
- 优点：状态最稳，完全以后端返回为准

适用于：

- 关联关系较复杂
- 希望页面状态绝对一致
- MVP 阶段优先保证正确性

建议：

- MVP 可先采用方案 B
- 交互成熟后再优化为方案 A

---

## 8. 前端所需辅助列表接口

为了支持下拉选择和资源关联，前端需要从各模块获取资源列表：

- LLM 模型列表
- Builtin tools 列表
- MCP servers 列表
- KB 列表

因此典型交互链路是：

1. 进入 AgentConfig 编辑页
2. 调 `GET /configs/{config_id}` 取当前 detail
3. 并行调用：
   - `GET /builtin-tools`
   - `GET /mcp-servers`
   - `GET /kbs`（由 KB 模块提供）
   - `GET /llm-models`（由模型模块提供）
4. 用 detail 做回显，用列表数据做下拉选项

---

## 9. 推荐 API 语义

### 9.1 读取

#### `GET /v1/agent/configs`

用途：

- 列表页
- 配置选择弹窗
- 会话绑定配置时的下拉列表

返回：

- summary 列表

#### `GET /v1/agent/configs/{config_id}`

用途：

- 配置编辑页初始化
- tab 回显
- 页面缓存初始化
- 聊天侧边栏展示配置详情

返回：

- detail
- base fields + tools + mcp_servers + kbs

### 9.2 写入

#### `POST /v1/agent/configs`

用途：

- 新建基础配置
- 创建成功后拿到 `config_id`

不要求同时提交 tools / mcp / kb。

#### `PUT /v1/agent/configs/{config_id}`

用途：

- 更新基础配置
- 仅修改基础字段

#### `POST /v1/agent/configs/{config_id}/tools`

用途：

- 添加工具

#### `PUT /v1/agent/configs/{config_id}/tools/{tool_id}`

用途：

- 更新工具配置

#### `DELETE /v1/agent/configs/{config_id}/tools/{tool_id}`

用途：

- 删除工具

#### `POST /v1/agent/configs/{config_id}/mcp-servers`

用途：

- 关联 MCP server

#### `DELETE /v1/agent/configs/{config_id}/mcp-servers/{link_id}`

用途：

- 解除 MCP 关联

#### `POST /v1/agent/configs/{config_id}/kbs`

用途：

- 关联知识库

#### `DELETE /v1/agent/configs/{config_id}/kbs/{link_id}`

用途：

- 解除知识库关联

---

## 10. 聊天场景中的 Agent / Config 关系

### 10.1 Session 绑定 Config

当前会话通过：

`PATCH /v1/agent/sessions/{session_id}/config`

将一个 `config_id` 绑定到 session。

这意味着：

- `AgentConfig` 是可复用的配置模板
- `Session` 是对话容器
- `Run` 是单次执行

### 10.2 聊天中的动态切换

在聊天页面里，可以在输入框下方提供动态配置入口：

- 选择模型
- 选择 KB
- 选择 MCP
- 选择 Tool

这些入口在产品上应被理解为“当前对话上下文的配置变更”，而不是要求用户回到统一大表单中一次性编辑所有内容。

因此当前细粒度配置模型与聊天场景是兼容的。

---

## 11. 非目标

本设计当前不要求：

- 新增“一次整包提交”的 `create/update full config API`
- 将所有关联写入合并成单次请求
- 在本阶段重构底层分表模型
- 在本阶段改变 MCP / KB / Tool 的独立资源属性

---

## 12. 建议的后续实现顺序

1. 将 `GET /configs/{config_id}` 升级为 detail 返回
2. 前端配置编辑页改为“单次 detail 拉取 + tab 局部保存”
3. 页面缓存采用“保存后局部更新”或“保存后重拉 detail”
4. 聊天输入区下方再逐步补充动态切换入口

---

## 13. 验收标准

- [ ] `GET /v1/agent/configs/{config_id}` 返回完整 detail
- [ ] 编辑页只需一次 detail 请求即可完成 tab 回显
- [ ] 各 tab 能独立保存，不依赖整包提交
- [ ] 保存失败仅影响当前 tab，不破坏其他已保存配置
- [ ] 聊天页面可以消费 `AgentConfig` 作为长期预设对象
- [ ] 后端分表结构继续保持对前端透明

---

## 14. 最终结论

当前系统最合理的设计收敛不是“新增一次性整包提交接口”，而是：

- **保持写接口细粒度拆分**
- **把 `GET /configs/{config_id}` 升级为完整 detail**

这既保留了当前模型在多 tab、自动保存、动态切换场景下的优势，也让前端能以更自然的方式完成页面初始化、tab 回显和后续开发。

# Agent System API 验证操作实例

**基于**: Agent模块架构与设计.md
**日期**: 2026-04-09
**Phase**: Phase 1-5 完整流程

---

## 概述

### Phase 5 核心变更

| 变更项 | Phase 4 | Phase 5 |
|--------|---------|---------|
| MCP SDK | langchain-mcp-adapters | MCP Python Native SDK |
| 传输协议 | streamable_http / sse | **+ stdio** |
| 工具发现超时 | **无** | 30s (`asyncio.wait_for`) |
| 内置工具 | calculator / datetime / websearch | **+ rag_retrieval** |
| stdio CRUD | **不可用** | 完整链路可用 |

### API 调用顺序图

```
时间轴 →

[MCP Server CRUD] ──────────────────────────── 必选（stdio/HTTP/SSE）
        │
[AgentConfig CRUD] ───┬── 添加工具
        │             └── 关联 MCP
        │
[Session CRUD] ───────┴── 绑定 Config
        │
[发起 Run] ───────────┬── SSE 事件流
        │             ├── 查看 Run
        │             ├── 查看 Steps
        │             └── 查看 Messages
        │
[Resume/Stop] ────────┴── 可选
```

---

## Step 1: MCP Server CRUD（必选）

### 1.1 创建 HTTP/SSE 传输的 MCP Server

```bash
# streamable_http 传输
curl -X POST 'http://127.0.0.1:8000/v1/agent/mcp-servers' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "github-mcp",
    "transport": "streamable_http",
    "url": "https://mcp.github.com/sse",
    "headers": {"Authorization": "Bearer xxx"},
    "enabled": true
  }'

# Response:
# {
#   "id": "mcp_xxx",
#   "name": "github-mcp",
#   "transport": "streamable_http",
#   "url": "https://mcp.github.com/sse",
#   "command": null,
#   "args": null,
#   "env": null,
#   "cwd": null,
#   ...
# }
```

### 1.2 创建 stdio 传输的 MCP Server（Phase 5 新增）

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/mcp-servers' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "filesystem-mcp",
    "transport": "stdio",
    "command": "uv",
    "args": ["--directory", "/project", "run", "mcp-server-fs"],
    "env": {"API_KEY": "xxx"},
    "cwd": "/project",
    "enabled": true
  }'

# Response:
# {
#   "id": "mcp_xxx",
#   "name": "filesystem-mcp",
#   "transport": "stdio",
#   "url": null,
#   "command": "uv",
#   "args": ["--directory", "/project", "run", "mcp-server-fs"],
#   "env": {"API_KEY": "xxx"},
#   "cwd": "/project",
#   ...
# }
```

### 1.3 测试 MCP Server 连接（Phase 5：30s 超时保护）

```bash
# 正常连接
curl -X POST 'http://127.0.0.1:8000/v1/agent/mcp-servers/<server_id>/test' \
  -H 'Authorization: Bearer <token>'

# Response (成功):
# {"success": true, "message": "Connection successful", "tools_count": 12}

# Response (连接超时 - Phase 5 新增):
# {"success": false, "message": "Connection timeout after 30s", "tools_count": 0}

# Response (连接失败):
# {"success": false, "message": "Connection failed: connection refused", "tools_count": 0}
```

### 1.4 列出 MCP Servers

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/mcp-servers' \
  -H 'Authorization: Bearer <token>'

# Response:
# {
#   "data": [
#     {
#       "id": "mcp_xxx",
#       "name": "github-mcp",
#       "transport": "streamable_http",
#       "url": "https://mcp.github.com/sse",
#       "command": null,
#       "args": null,
#       "env": null,
#       "cwd": null,
#       "enabled": true,
#       ...
#     }
#   ],
#   "total": 1
# }
```

### 1.5 更新 MCP Server

```bash
curl -X PUT 'http://127.0.0.1:8000/v1/agent/mcp-servers/<server_id>' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "github-mcp-updated",
    "transport": "stdio",
    "command": "python",
    "args": ["-m", "mcp_server"],
    "env": {"DEBUG": "true"},
    "cwd": "/workspace"
  }'
```

---

## Step 2: AgentConfig CRUD

### 2.1 创建 AgentConfig

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "数学助手",
    "description": "专门处理数学计算的助手",
    "agent_type": "simple",
    "max_loop": 5,
    "system_prompt": "你是一个数学助手，请仔细计算"
  }'

# Response:
# {
#   "id": "config_xxx",
#   "name": "数学助手",
#   "agent_type": "simple",
#   "max_loop": 5,
#   ...
# }
```

### 2.2 添加工具

```bash
# 添加工具 - calculator（Phase 5 内置 MCP 工具）
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/tools' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "calculator",
    "tool_config": {}
  }'

# 添加工具 - datetime（Phase 5 内置 MCP 工具）
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/tools' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "datetime",
    "tool_config": {}
  }'

# 添加工具 - rag_retrieval（Phase 5 内置 MCP 工具，需要 KB 关联）
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/tools' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "rag_retrieval",
    "tool_config": {}
  }'

# 添加工具 - websearch（需要 API key）
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/tools' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "tool_name": "websearch",
    "tool_config": {
      "api_key": "tvly-xxx",
      "search_depth": "basic"
    }
  }'

# Response（成功）:
# {"id": 1, "config_id": "config_xxx", "tool_name": "calculator", "enabled": true, ...}
```

### 2.3 关联 MCP Server（Phase 5：支持 stdio/HTTP/SSE）

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/mcp-servers' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"mcp_server_id": "mcp_xxx"}'

# Response: {"id": 1, "config_id": "config_xxx", "mcp_server_id": "mcp_xxx", ...}
```

### 2.4 验证工具配置（关键调试端点）

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/resolved-tools' \
  -H 'Authorization: Bearer <token>'

# Response (成功):
# {
#   "data": {
#     "tools": [
#       {"name": "calculator", "description": "...", "enabled": true},
#       {"name": "datetime", "description": "...", "enabled": true},
#       {"name": "websearch", "description": "...", "enabled": true},
#       {"name": "github_repo_info", "description": "...", "enabled": true},  ← MCP 工具
#       {"name": "github_file_read", "description": "...", "enabled": true}   ← MCP 工具
#     ],
#     "warnings": []
#   }
# }

# 有警告时的 Response（Phase 5 超时示例）:
# {
#   "data": {
#     "tools": [...],
#     "warnings": [
#       "mcp:github-mcp connection failed: MCP server github-mcp list_tools() timeout after 30s"
#     ]
#   }
# }
```

### 2.5 列出所有内置工具（Phase 5 新增 rag_retrieval）

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/builtin-tools' \
  -H 'Authorization: Bearer <token>'

# Response:
# {
#   "tools": [
#     {
#       "name": "calculator",
#       "description": "Mathematical calculator for arithmetic expressions",
#       "has_config": false,
#       "input_schema": {"type": "object", "properties": {"expression": ...}, "required": ["expression"]}
#     },
#     {
#       "name": "datetime",
#       "description": "Get current date and time",
#       "has_config": false,
#       "input_schema": {"type": "object", "properties": {}}
#     },
#     {
#       "name": "rag_retrieval",
#       "description": "Knowledge base retrieval for finding relevant documents",
#       "has_config": false,
#       "input_schema": {"type": "object", "properties": {"query": ...}, "required": ["query"]}
#     }
#   ]
# }
```

### 2.6 Config CRUD

```bash
# 列出当前用户的所有 Config
curl -X GET 'http://127.0.0.1:8000/v1/agent/configs' \
  -H 'Authorization: Bearer <token>'

# 获取 Config 详情
curl -X GET 'http://127.0.0.1:8000/v1/agent/configs/config_xxx' \
  -H 'Authorization: Bearer <token>'

# 更新 Config
curl -X PUT 'http://127.0.0.1:8000/v1/agent/configs/config_xxx' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "新名称",
    "max_loop": 10,
    "system_prompt": "更新后的提示词"
  }'

# 删除 Config
curl -X DELETE 'http://127.0.0.1:8000/v1/agent/configs/config_xxx' \
  -H 'Authorization: Bearer <token>'
```

---

## Step 3: 创建 Session 并绑定 Config

### 3.1 创建 Session（绑定 Config）

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/sessions' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"config_id": "config_xxx"}'

# Response:
# {
#   "id": "session_xxx",
#   "config_id": "config_xxx",
#   "summary": null,
#   ...
# }
```

### 3.2 更新 Session 绑定的 Config

```bash
curl -X PATCH 'http://127.0.0.1:8000/v1/agent/sessions/session_xxx/config' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"config_id": "config_yyy"}'
```

---

## Step 4: 发起 Run（流式执行）

### 4.1 Calculator 工具调用

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/sessions/session_xxx/runs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input": "计算 1+2*3", "stream": true}'

# SSE 事件流示例:
#
# event: step_start
# data: {"step_id": "step_001", "step_index": 0, "type": "llm_decision", "name": "openai", "status": "running"}
#
# event: tool_call
# data: {"tool": "calculator", "arguments": {"expression": "1+2*3"}, "step_id": "step_001", "step_index": 0}
#
# event: tool_result
# data: {"tool": "calculator", "result": {"result": 7.0}, "step_id": "step_002", "step_index": 1}
#
# event: step_end
# data: {"step_id": "step_001", "status": "success", "output": {"result": 7.0}, "latency_ms": 12}
#
# event: run_end
# data: {"status": "success", "output": "1+2*3 = 7", "steps_count": 2}
```

### 4.2 DateTime 工具调用

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/sessions/session_xxx/runs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input": "现在几点了？", "stream": true}'

# SSE:
# event: tool_result
# data: {"tool": "datetime", "result": {
#   "date": "2026-04-09T15:30:00.123456",
#   "timestamp": 1744205400.12,
#   "year": 2026, "month": 4, "day": 9,
#   "hour": 15, "minute": 30, "second": 0
# }}
```

### 4.3 MCP 外部工具调用（Phase 5 Native SDK）

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/sessions/session_xxx/runs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input": "帮我查一下 github.com/anthropics/claude-code 的 star 数量", "stream": true}'

# SSE:
# event: tool_call
# data: {"tool": "github_repo_info", "arguments": {"owner": "anthropics", "repo": "claude-code"}, ...}
#
# event: tool_result
# data: {"tool": "github_repo_info", "result": {"stars": 12400, " forks": 1200, ...}, ...}
```

### 4.4 查看 Run 详情

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/runs/run_xxx' \
  -H 'Authorization: Bearer <token>'

# Response:
# {
#   "id": "run_xxx",
#   "session_id": "session_xxx",
#   "status": "success",
#   "input": "计算 1+2*3",
#   "output": "1+2*3 = 7",
#   "config_snapshot": {
#     "id": "config_xxx",
#     "tools": [...],
#     "mcp_servers": [...],
#     ...
#   },
#   ...
# }
```

### 4.5 查看 Run 的 Steps

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/runs/run_xxx/steps' \
  -H 'Authorization: Bearer <token>'

# Response:
# {
#   "steps": [
#     {
#       "id": "step_001",
#       "step_index": 0,
#       "type": "llm_decision",
#       "name": "openai",
#       "input": {"messages": [...]},
#       "output": {"decision": {"type": "tool_call", "tool": "calculator", ...}},
#       "status": "success",
#       "latency_ms": 123
#     },
#     {
#       "id": "step_002",
#       "step_index": 1,
#       "type": "tool",
#       "name": "calculator",
#       "input": {"arguments": {"expression": "1+2*3"}},
#       "output": {"result": 7.0},
#       "status": "success",
#       "latency_ms": 5
#     }
#   ]
# }
```

### 4.6 查看 Session 的 Messages

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/sessions/session_xxx/messages' \
  -H 'Authorization: Bearer <token>'

# Response:
# {
#   "messages": [
#     {"id": "msg_001", "role": "user", "content": "计算 1+2*3", ...},
#     {"id": "msg_002", "role": "assistant", "content": "我来计算...", "tool_calls": [...]},
#     {"id": "msg_003", "role": "tool", "content": "{\"result\": 7.0}", ...}
#   ]
# }
```

---

## Step 5: Resume / Stop（可选）

### 5.1 Resume（恢复中断的 Run）

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/runs/run_xxx/resume' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"stream": true}'

# Resume 流程：
# 1. 获取原始 Run 成功的 steps
# 2. 重建状态（messages + tool_results）
# 3. 从 last_step_index + 1 继续执行
# 4. 创建新 Run（原始 Run 标记为 interrupted）
```

### 5.2 Stop（停止 Run）

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/runs/run_xxx/stop' \
  -H 'Authorization: Bearer <token>'

# Response:
# {"id": "run_xxx", "status": "interrupted", "message": "Run stopped"}
```

---

## 完整流程示例

### 示例 1：使用内置 MCP 工具（calculator）

```bash
# 1. 创建 Config
CONFIG_RESP=$(curl -s -X POST 'http://127.0.0.1:8000/v1/agent/configs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"name": "数学助手", "agent_type": "simple"}')
CONFIG_ID=$(echo $CONFIG_RESP | jq -r '.id')

# 2. 添加 calculator 工具
curl -s -X POST "http://127.0.0.1:8000/v1/agent/configs/${CONFIG_ID}/tools" \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"tool_name": "calculator"}' | jq

# 3. 创建 Session
SESSION_RESP=$(curl -s -X POST 'http://127.0.0.1:8000/v1/agent/sessions' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d "{\"config_id\": \"${CONFIG_ID}\"}")
SESSION_ID=$(echo $SESSION_RESP | jq -r '.id')

# 4. 发起 Run
curl -X POST "http://127.0.0.1:8000/v1/agent/sessions/${SESSION_ID}/runs" \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input": "计算 (10 + 5) * 2 / 4", "stream": false}'
# Response: {"session_id": "...", "run_id": "...", "output": "结果是 7.5", "steps": [...]}
```

### 示例 2：使用 stdio 传输的 MCP Server（Phase 5）

```bash
# 1. 创建 stdio MCP Server
MCP_RESP=$(curl -s -X POST 'http://127.0.0.1:8000/v1/agent/mcp-servers' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "filesystem-mcp",
    "transport": "stdio",
    "command": "uv",
    "args": ["run", "mcp-filesystem"],
    "cwd": "/workspace"
  }')
MCP_ID=$(echo $MCP_RESP | jq -r '.id')

# 2. 测试连接
curl -X POST "http://127.0.0.1:8000/v1/agent/mcp-servers/${MCP_ID}/test" \
  -H 'Authorization: Bearer <token>'
# Response: {"success": true, "message": "Connection successful", "tools_count": 5}

# 3. 创建 Config 并关联
CONFIG_RESP=$(curl -s -X POST 'http://127.0.0.1:8000/v1/agent/configs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"name": "文件系统助手", "agent_type": "simple"}')
CONFIG_ID=$(echo $CONFIG_RESP | jq -r '.id')

curl -s -X POST "http://127.0.0.1:8000/v1/agent/configs/${CONFIG_ID}/mcp-servers" \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d "{\"mcp_server_id\": \"${MCP_ID}\"}" | jq

# 4. 创建 Session 并执行
SESSION_RESP=$(curl -s -X POST 'http://127.0.0.1:8000/v1/agent/sessions' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d "{\"config_id\": \"${CONFIG_ID}\"}")
SESSION_ID=$(echo $SESSION_RESP | jq -r '.id')

curl -X POST "http://127.0.0.1:8000/v1/agent/sessions/${SESSION_ID}/runs" \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input": "列出当前目录的文件", "stream": false}'
```

---

## 错误处理示例

### MCP Server 连接超时（Phase 5 新增）

```bash
# MCP Server 响应过慢
curl -X POST 'http://127.0.0.1:8000/v1/agent/mcp-servers/<slow_server_id>/test' \
  -H 'Authorization: Bearer <token>'

# Response: {"success": false, "message": "Connection timeout after 30s", "tools_count": 0}
```

### stdio 传输缺少必需参数（Phase 5 新增）

```bash
# 创建 stdio MCP Server 但缺少 command
curl -X POST 'http://127.0.0.1:8000/v1/agent/mcp-servers' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "bad-mcp",
    "transport": "stdio",
    "args": ["--help"]
  }'

# Response: HTTP 422
# {"detail": [{"type": "missing", "loc": ["body", "command"], "msg": "Field required", ...}]}
```

### 409 Conflict - 重复添加工具

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/tools' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"tool_name": "calculator"}'

# Response: HTTP 409
# {"detail": "Tool calculator already exists in config"}
```

### 404 Not Found - 资源不存在

```bash
curl -X GET 'http://127.0.0.1:8000/v1/agent/configs/nonexistent' \
  -H 'Authorization: Bearer <token>'

# Response: HTTP 404
# {"detail": "Config not found"}
```

### MCP Server 不可用时的 warnings（Phase 5 超时信息）

```bash
# resolved-tools 端点查看
curl -X GET 'http://127.0.0.1:8000/v1/agent/configs/config_xxx/resolved-tools' \
  -H 'Authorization: Bearer <token>'

# Response:
# {
#   "data": {
#     "tools": [
#       {"name": "calculator", ...},
#       {"name": "datetime", ...}
#     ],
#     "warnings": [
#       "mcp:broken-mcp connection failed: MCP server broken-mcp list_tools() timeout after 30s"
#     ]
#   }
# }
```

### Run 超时 / Max Loop

```bash
curl -X POST 'http://127.0.0.1:8000/v1/agent/sessions/session_xxx/runs' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  -d '{"input": "复杂的多步计算", "stream": true}'

# SSE:
# event: run_end
# data: {"status": "success", "output": "Max iterations reached without final response."}
```

---

## 验证清单

| # | 验证项 | 预期结果 |
|---|--------|----------|
| **Phase 5 新增** | | |
| 1 | 创建 stdio MCP Server（command + args） | ✅ 成功，返回完整字段 |
| 2 | 创建 stdio MCP Server（缺少 command） | ✅ 422 验证错误 |
| 3 | 更新 stdio MCP Server（改 transport 为 sse） | ✅ 成功，command/args 保留 |
| 4 | test_mcp_server 连接 stdio 服务器 | ✅ success=true 或 timeout |
| 5 | list_tools 超时（30s） | ✅ warnings 包含 timeout 信息 |
| 6 | 内置工具 rag_retrieval | ✅ 出现在 builtin-tools 列表 |
| 7 | 关联 stdio MCP Server 到 Config | ✅ 成功 |
| 8 | stdio MCP Server 工具被正确加载 | ✅ resolved-tools 显示 MCP 工具 |
| **Phase 1-4 回归** | | |
| 9 | 创建 Config，添加 calculator + datetime | ✅ 成功，无 warnings |
| 10 | 重复添加同名 tool | ✅ 409 Conflict |
| 11 | 关联 HTTP MCP Server，再创建 Run | ✅ config_snapshot 有内容 |
| 12 | 修改 Config，重新 Run | ✅ 新 Run 快照反映修改 |
| 13 | 某个 MCP server 不通 | ✅ 其他工具正常加载，warnings 记录错误 |
| 14 | agent_type="react" | ✅ ReactAgent 被调用 |
| 15 | 用不同 user token 访问 MCP Servers | ✅ 403 Forbidden |
| 16 | Session 绑定 config，发起 Run | ✅ Run 使用该 Config 的工具 |
| 17 | Resume 中断的 Run | ✅ 从上次中断处继续 |
| 18 | Stop 正在运行的 Run | ✅ status=interrupted |

---

## 附录：Phase 5 错误消息对照表

| 场景 | 错误消息 |
|------|----------|
| `list_tools()` 超时（tool_builder） | `mcp:{name} connection failed: MCP server {name} list_tools() timeout after 30s` |
| `list_tools()` 超时（test_mcp_server） | `Connection timeout after 30s` |
| `call_tool()` 超时（MCPTool.run） | `Tool {tool_name} timeout after 10s` |
| transport=stdio 缺少 command | `transport=stdio requires 'command' and 'args'` |
| transport=stdio 缺少 args | `transport=stdio requires 'command' and 'args'` |
| transport=sse 缺少 url | `transport=sse requires 'url'` |
| MCP 连接失败 | `Connection failed: {原因}` |
| MCP 协议错误 | `Protocol error: {原因}` |

# Agent MCP Test Checklist

**日期**: 2026-04-09  
**范围**: Agent Phase 5 当前 MCP 操作流验证  
**目标**: 覆盖 MCP 三种 transport、Agent 接入链路、关键失败场景与回归检查点

## 1. 当前已验证主链路

这些链路已经完成验证，可作为当前 Phase 5 的基础通过项。

| 编号 | 场景 | Transport | 启动方式 | 目标 | 当前状态 | 备注 |
|---|---|---|---|---|---|---|
| A1 | Tavily 远程 MCP 成功连通 | `streamable_http` | 远程 URL + Bearer Header | 验证远程 MCP endpoint、握手、工具发现 | `已通过` | 最终正确 URL 为 `https://mcp.tavily.com/mcp/` |
| A2 | Tavily 本地 MCP 成功连通 | `stdio` | `npx tavily-mcp` | 验证本地进程启动、握手、工具发现 | `已通过` | 依赖本机可执行 `npx` 与有效 `TAVILY_API_KEY` |
| A3 | 仓库内 mock Python MCP 成功连通 | `stdio` | `./.venv/bin/python mock_stdio_server.py` | 验证本地 Python 脚本、握手、工具发现 | `已通过` | 固定回归样例：`echo` / `add` |
| A4 | 官方 Git MCP 成功连通 | `stdio` | `uvx mcp-server-git --repository <repo>` | 验证 uvx 启动链路、仓库访问、工具发现 | `已通过` | 推荐作为 `uvx` 标准回归样例 |

## 2. 推荐最小测试矩阵

| 编号 | 场景 | Transport | 启动方式 | 主要验证点 | 优先级 | 当前状态 |
|---|---|---|---|---|---|---|
| M1 | Tavily 远程 MCP 成功 | `streamable_http` | 远程 URL | 远程握手、`list_tools`、headers 生效 | P0 | `已通过` |
| M2 | Tavily 远程 MCP 错误 URL | `streamable_http` | 错误 endpoint | 404 诊断是否清晰 | P0 | `已覆盖诊断修复，建议补手测记录` |
| M3 | Tavily 远程 MCP 错误 API key | `streamable_http` | 错误 Bearer | 401/403 诊断是否清晰 | P0 | `待测试` |
| M4 | Tavily 本地 MCP 成功 | `stdio` | `npx tavily-mcp` | 本地进程启动、握手、`list_tools` | P0 | `已通过` |
| M5 | Python MCP 成功 | `stdio` | `./.venv/bin/python mock_stdio_server.py` | 本地 Python 脚本、`cwd/env`、工具调用 | P0 | `已通过` |
| M6 | uvx MCP 成功 | `stdio` | `uvx mcp-server-git --repository <repo>` | uv 生态兼容性、仓库访问、工具发现 | P1 | `已通过` |
| M7 | command 不存在 | `stdio` | 错误 command | 启动失败错误是否清晰 | P0 | `待测试` |
| M8 | 缺失 env | `stdio` | 正确 command / 错误 env | 本地 server 初始化失败是否可诊断 | P1 | `待测试` |
| M9 | 本地 server 超时 | `stdio` | 故意 sleep | timeout 是否正确返回 | P1 | `待测试` |
| M10 | SSE 成功 | `sse` | 可用 SSE MCP server | 第三种 transport 可用性 | P1 | `待测试` |
| M11 | Agent 真实 run 使用单 MCP tool | `streamable_http` / `stdio` | 任一可用 MCP | 不只是 `/test` 成功，而是真实 `call_tool` | P0 | `待测试` |
| M12 | Agent 真实 run 使用多工具源 | 混合 | builtin + MCP | 工具合并、命名冲突、构建链路 | P1 | `待测试` |
| M13 | `stream=true` 流式运行 | 混合 | 任一可用 MCP | SSE 事件流下 tool call 正常 | P1 | `待测试` |
| M14 | `resume_agent` 使用 MCP | 混合 | 任一可用 MCP | resume 时配置/步骤恢复正确 | P2 | `待测试` |

## 3. 建议优先补测顺序

1. `stdio + 自定义本地 Python MCP`
2. `streamable_http + 错误 API key`
3. `stdio + command 不存在`
4. `Agent run + 单 MCP tool`
5. `stdio + uvx`
6. `sse`
7. `多工具源 / stream=true / resume_agent`

## 4. 建议保留的长期回归样例

### 4.1 远程 MCP 样例

- Tavily `streamable_http`
- 用于验证：
  - 正确 endpoint
  - header 鉴权
  - 远程 `list_tools`

### 4.2 本地第三方 MCP 样例

- Tavily `stdio`
- 用于验证：
  - 外部本地进程可启动
  - `env` 注入有效
  - Node/npm/npx 生态兼容

### 4.3 本地自定义 MCP 样例

建议后续补一个仓库内最小 mock server，例如：

- 路径建议：`tests/fixtures/mcp/mock_stdio_server.py`
- 建议提供工具：
  - `echo(text: str)`
  - `add(a: int, b: int)`
- 用于验证：
  - `./.venv/bin/python` 启动
  - 相对/绝对路径
  - `cwd`
  - `env`
  - schema discovery
  - tool execution
  - timeout / 异常注入

### 4.4 本地 uvx MCP 样例

- 官方 reference server：`mcp-server-git`
- 启动方式：`uvx mcp-server-git --repository <repo-path>`
- 用于验证：
  - `uvx` 可执行
  - Python MCP 包生态兼容
  - 本地仓库路径访问
  - schema discovery
  - Git 工具调用

## 5. 每次回归建议至少通过的基线

- [x] 一条 `streamable_http` 成功链路
- [x] 一条 `stdio` 成功链路
- [x] 一条 `stdio` 本地 Python 自定义 server 链路
- [x] 一条 `stdio` 基于 `uvx` 的 Python MCP 链路
- [ ] 一条远程 MCP 鉴权失败链路
- [ ] 一条本地 command 启动失败链路
- [ ] 一条真实 Agent `run_agent` 调用 MCP tool 链路

## 6. 当前已知结论

- `streamable_http` Tavily 成功与否高度依赖正确的 MCP endpoint
- Tavily 远程 URL 配错时，表象可能是 `Session terminated`，现在服务端已补充二次诊断逻辑
- `stdio` Tavily 已验证通过，说明当前本地进程拉起链路是通的
- 仓库内 mock Python `stdio` MCP server 已验证通过，可作为稳定回归样例
- `uvx mcp-server-git` 已验证通过，可作为 `uvx` 标准回归样例

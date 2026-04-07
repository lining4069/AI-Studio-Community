# Agent System Phase 2 — 设计决策过程记录

**Date:** 2026-04-07
**Purpose:** 供技术面试 / 架构评审 / 团队知识传承使用
**Context:** 从 Phase 1 完成到 Phase 2 设计定稿的完整决策链路

---

## 一、Phase 2 从哪里开始？（背景）

### Q: Phase 1 已经完成了什么？Phase 2/3 的目标是什么？

**Phase 1 完成内容：**
- DB 表：`agent_sessions`, `agent_messages`, `agent_steps`
- Tool ABC + Registry（本地工具注册）
- 内置工具：Calculator, DateTime, RAG
- SimpleAgent（1-loop 执行）
- SSE 流式响应
- Memory（summary 摘要记忆）
- Repository + Service + Router 三层架构

**Phase 2 目标（6 个 feature）：**
1. `agent_runs` 表 — 运行记录，支撑 replay 和 debug
2. `mcp_servers` 表 — MCP 配置（后续迭代）
3. MCP Adapter — 外部工具生态（后续迭代）
4. ToolSpec 标准化 — provider-agnostic 工具 schema
5. Memory 分层 — summary + recent + recall
6. Run 恢复机制 — Agent.run 中断/恢复能力

**Phase 3 目标：**
- Full ReAct Planner
- Embedding-based Recall
- Multi-step Planning

---

## 二、Phase 2 迭代顺序选择

### Q: Phase 2 有 6 个 feature，应该先做哪个？

**三个选项：**
- A. MCP 工具生态优先 — 先做 MCP Adapter + mcp_servers 表
- B. Run 可观测性优先 — 先做 agent_runs 表 + steps 关联
- C. Memory 增强优先 — 先做 recent messages 分层 + embedding recall

**A: ❌ 不选**
MCP 接入在没有可观测性的情况下会变成黑盒。工具失败不知道哪里错，无法复现问题，debug 成本极高。

**C: ❌ 不选**
Memory 增强无法验证效果。recall 是否命中？summary 是否影响回答？token 使用是否优化？没数据无法优化。

**B: ✅ 选择 Run 可观测性**

**核心理由：Run 是"地基能力"，不是 feature。**

没有 Run 可观测性，后面会遇到：
- MCP 接入（A）会变成黑盒
- Memory 增强（C）无法验证效果
- ReAct/Planning 无法 debug

**B 做完立刻获得的能力：**
1. **Replay** — 还原完整执行链路
2. **Debug** — 每一步 input/output、latency、token
3. **分析能力** — 哪个 tool 最慢？哪一步最容易失败？
4. **Run 恢复** — 为 Phase 2 Feature 6 铺路

**一句话：** Phase 2 先解决"看得见"，再解决"变更强"。

---

## 三、Run 粒度设计

### Q: 一次 Run 指的是什么？

**三个选项：**
- A. 一次完整的 API 请求（从用户发起到收到最终 response）
- B. 一次 LLM 调用（包括 tool 调用）
- C. 一次 tool 执行（LLM call + tool execution）

**A: ✅ 选择 A（一次完整 API 请求）**

**B: ❌ 不选（LLM 调用级别太细）**
- run 数量爆炸（一次请求可能 2~5 个 LLM call）
- 无法表达"完整任务"
- replay 变得毫无意义

**C: ❌ 不选（tool 执行级别语义错误）**
- tool 只是 Step 的一种
- 会破坏统一抽象（Step 已经覆盖 tool）
- 数据模型会变得混乱

**A 的语义干净：**
```
Run = "一次任务执行实例"
Run 是一个完整闭环：input → reasoning → tool → output
Step = "执行过程"
Step 是 Run 内部的轨迹
Session = "长期对话"
Session 包含多个 Run
```

**数据量可控：**
- 1 个用户请求 = 1 run
- 每个 run ~ 2–6 steps
- 比 B 少一个数量级

---

## 四、Resume 粒度设计

### Q: Run 被中断时，恢复的粒度是什么？

**三个选项：**
- A. 完整重放（Replay Only）— 不支持中断恢复，只支持从头 replay
- B. 从最近 Step 恢复（Step-level Resume）— 从最后一个成功 step 继续
- C. 完整状态恢复（State-level Resume）— 存储完整 AgentState 快照

**A: ❌ 不选（太弱）**
- 无法处理中断（网络/服务重启）
- 长任务直接废掉

**C: ❌ 不选（过度设计）**
1. **状态不可信** — snapshot ≠ 真实执行结果，memory 可能变化，tool 外部状态变化
2. **存储爆炸** — messages + scratchpad + tool_results JSON 巨大
3. **Debug 困难** — 看到一个 snapshot 而不是一步步执行轨迹

**B: ✅ 选择 Step-level Resume**

**核心原则：Single Source of Truth（唯一可信来源 = agent_steps）**

**B 的本质优势：**
- **单一数据源** — 没有 snapshot，没有缓存 state，没有双写问题
- **天然支持 replay + resume** — replay = 从头 rebuild，resume = 从中间继续
- **幂等天然成立** — step.status = success → 不再执行
- **存储成本低** — 只存 step input/output 和状态

**不要存状态，要存事实；不要恢复状态，要重建状态。**

---

## 五、Run 创建时机

### Q: agent_runs 记录何时创建？

**三个选项：**
- A. 请求开始时立即创建
- B. 请求结束时创建
- C. 首次 Step 创建时延迟创建

**A: ✅ 选择 A（请求开始时创建）**

**B: ❌ 不选（直接废掉一半能力）**
- 执行过程中 DB 没记录
- 无法 resume
- 无法实时观察
- 崩溃数据丢失

**C: ❌ 不选（看似折中，其实坑）**
- 如果 LLM 还没返回 step 就挂了，run 不存在
- 生命周期不清晰

**正确的 Run 生命周期：**
```
POST /runs
   ↓
create run(status=running) ✅
   ↓
开始执行 Agent
   ↓
持续写 steps
   ↓
完成 → status=success
失败 → status=error
中断 → status=running（或 interrupted）
```

**Run 必须在执行前存在，否则无法证明"这次执行发生过"。**

---

## 六、Run 与 Message 的关系（最关键的架构分水岭）

### Q: Run 执行过程中产生的 Message，应该归属到哪里？

**两个选项：**
- A. Message 归属 Session（当前设计）
- B. Message 归属 Run（解耦设计）

**A: ❌ 不选**
```
Session
  └── Messages (session_id)
  └── Runs
        └── Steps (session_id, 无 run_id)
```
- replay 依赖 session.messages
- session 在变化，replay 结果不稳定
- 多 Agent 支持困难

**B: ✅ 选择 B（Run-owned Messages + Session Summary）**

**但不是纯 B，而是"轻量混合版"：**

```
Session
  └── summary（长期记忆） ✅

  └── Runs
        ├── messages（本次输入输出） ✅
        └── steps（执行轨迹） ✅
```

**Session 不再存完整 messages，只存"压缩后的记忆（summary）"。**

**为什么必须选 B？**

1. **Run 必须是"自包含"的** — replay(run) = 完整快照 ✅，而不是依赖 session.messages ❌
2. **Resume 才是"确定性"的** — state = run.messages + steps ✅，而不是 session 可能已变 ❌
3. **多 Agent / 多策略天然支持** — Run1 (agent A), Run2 (agent B) 完全隔离 ✅
4. **Debug / Replay 体验质变** — 直接返回 run.messages + steps ✅，而不是拼 session messages ❌

**Message 分层（非常关键）：**
```
Message = 事实（本次执行输入 + 输出）
Memory = 抽象（summary / long-term memory）
```

**Prompt 构建方式（核心变化）：**
```
Phase 1: prompt = session.messages
Phase 2: prompt = session.summary + recent run messages + 当前输入
```

---

## 七、ToolSpec 标准化时机

### Q: ToolSpec 标准化是否在本次 Phase 2 范围内？

**两个选项：**
- A. 包含在本次 — 趁 agent_runs 设计时同步完成
- B. 本次不含 + 接口预留

**A: ❌ 不选（现在不该做）**

1. **主线是"执行可靠性"，不是"工具生态"** — Run/Step/Resume/幂等 = 执行引擎稳定性，ToolSpec = Integration Layer
2. **ToolSpec 设计依赖 MCP / Provider 认知** — 还没真正接入 MCP，强行标准化容易设计错
3. **当前 Tool 使用方式不稳定** — SimpleAgent（1-loop）→ ReAct/Plan-Execute/Multi-step，现在定死 schema 高风险

**B: ✅ 选择 B（不做 + 接口预留）**

**正确做法：做"薄抽象"，不做"重标准"**

```
Phase 2（现在）做：
  Tool Runtime Interface（运行时接口）
  - Tool ABC 定义 ✅
  - ToolRegistry ✅
  - 基础 schema（弱约束）✅
  - to_llm_tool() 隔离点 ✅

Phase 2.5（下一步）做：
  ToolSpec 标准化：
  - JSON Schema 完整定义
  - provider mapping

Phase 3（未来）做：
  MCP Adapter：动态 tool discovery + remote tools
```

**判断标准（用于未来决策）：**
> 这个抽象是否被 2+ 个真实实现同时需要？
> ToolSpec 当前：只有本地 Tool 在用 ❌，MCP 还没接 ❌ → 不应该标准化

---

## 八、最终确认的 Phase 2 设计决策

| # | 决策 | 选择 | 核心理由 |
|---|------|------|---------|
| 1 | Run 粒度 | A：一次完整 API 请求 | 语义清晰，数据量可控 |
| 2 | Resume 粒度 | B：Step-level Resume | SSOT = agent_steps，幂等天然 |
| 3 | Run 创建时机 | A：请求开始时立即创建 | 支持 resume + 实时可观测性 |
| 4 | Run 与 Message 关系 | B：Run-owned + Session Summary | 自包含，支持多 Agent |
| 5 | ToolSpec | B：不做 + 接口预留 | MCP 未接入，不锁死 schema |

---

## 九、Phase 2 最终范围

```
1. agent_runs 表（Run 实体 + 状态管理）

2. agent_messages 扩展
   - 增加 run_id（Run-owned）

3. agent_steps 扩展
   - 增加 run_id
   - 增加 step_index
   - 增加 status + idempotency_key

4. Run API
   - GET /runs/{id}
   - GET /runs/{id}/steps
   - POST /runs/{id}/resume
   - POST /runs/{id}/stop

5. Replay / Resume 机制
   - replay：重建 state
   - resume：从 step-level 恢复

6. Tool 接口预留
   - to_llm_tool()
   - provider 解耦点

7. Step 状态机（执行协议）
   - pending → running → success / error

8. Run 状态机
   - running → success / error / interrupted

9. 执行顺序保证
   - step_index + UNIQUE(run_id, step_index)
```

---

## 十、Phase 2 架构演进图

```
Phase 1:
  Tool → ToolRegistry (本地硬编码)
  Memory → summary only
  Run → 无状态，单次执行
  Messages → Session 共享

Phase 2:
  Tool → ToolRegistry + to_llm_tool() 隔离点
  Memory → summary（Session 层）
  Run → agent_runs 表持久化
  Messages → Run-owned（自包含）
  Resume → Step-level（SSOT = agent_steps）

Phase 3:
  Tool → MCP Adapter (动态加载)
  Memory → summary + recent + recall (embedding)
  Run → 完整 ReAct 多步推理
```

---

## 十一、关键设计原则（面试可引用）

### 1. SSOT（Single Source of Truth）
> 不要存状态，要存事实；不要恢复状态，要重建状态。

### 2. Run 自包含（Self-Contained）
> Run 必须能独立 replay。依赖外部状态（session messages）会导致 replay 结果不稳定。

### 3. 渐进式抽象（Evolutionary Abstraction）
> 这个抽象是否被 2+ 个真实实现同时需要？如果不是，不应该标准化。

### 4. 地基优先（Foundation First）
> Phase 2 先解决"看得见"，再解决"变更强"。没有可观测性，工具接入和 Memory 增强都是盲人摸象。

### 5. 幂等天然（Idempotency by Design）
> step.status = success → 不再执行。状态机设计让幂等自然而然成立，不需要额外补偿逻辑。

---

## 十二、文档参考

- Phase 1 设计文档：`docs/superpowers/specs/2026-04-06-agent-system-phase1-design.md`
- Phase 2 设计文档：`docs/superpowers/specs/2026-04-07-agent-system-phase2-design.md`
- Phase 1 Brainstorm：`agent-system-brainstorm.md`（记忆文件）

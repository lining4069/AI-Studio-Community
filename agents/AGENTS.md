# AGENTS.md — AI Coding Operating System (AgentOS)

> 主控文件：定义 Agent 行为 + 上下文加载策略 + 执行流程

---

# 🧠 Agent身份

你是“轮班工程师 Agent”：

- ❌ 无长期记忆
- ✅ 依赖文件恢复上下文
- ✅ 每次只完成一个功能
- ✅ 必须保证系统可运行 + 可测试 + 可提交

---

# ⚠️ 全局规则（最高优先级）

1. 系统必须始终可运行
2. 必须先测试再实现（TDD）
3. 每次只做一个功能
4. 必须通过端到端验证（E2E）
5. 必须提交 + 更新进度

---

# 🔄 标准执行流程

## Step 1：恢复上下文

读取：

- `claude-progress.txt`
- `feature_list.json`
- `git log -20`

---

## Step 2：环境验证

启动项目 + 执行测试：

失败 → ❗必须优先修复

---

## Step 3：选择任务

只允许：

- 一个 `passes=false` 的功能

---

## Step 4：加载上下文（动态）

### Backend开发

加载：

- `/agents/architecture/backend.md`
- `/agents/coding/python.md`
- `/agents/coding/naming.md`

涉及RAG：

- `/agents/ai/rag.md`

工程规范强约束（必须遵守）

必须遵守：

- 分层架构：Router → Service → Repository
- 禁止跨层调用
- 禁止跨模块 Repository 引用
- 必须使用依赖注入（Depends）
- 必须使用 Pydantic Schema
- Service 层组织所有业务逻辑

违反 = ❌ 任务失败

📚 示例代码使用规则

必须参考：

- /agents/examples/backend/*

禁止：

- 风格漂移

---

### 测试开发

加载：

- `/agents/testing/strategy.md`
- `/agents/testing/patterns.md`

---

### AI开发

加载：

- `/agents/ai/rag.md`
- `/agents/ai/llm_provider.md`
- `/agents/ai/agent.md`

---

### 前端开发

加载：

- `/agents/architecture/frontend.md`
- `/agents/coding/typescript.md`

---

## Step 5：TDD开发

1. 写测试（失败）
2. 实现功能
3. 测试通过
4. 重构

---

## Step 6：验证

必须执行：

- Integration 或 E2E测试

---

## Step 7：提交

```bash
git commit -m "feat(Fxxx): description"
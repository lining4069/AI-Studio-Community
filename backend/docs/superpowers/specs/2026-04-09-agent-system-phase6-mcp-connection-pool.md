# Agent System Phase 6 — MCP Connection Pool

**日期**: 2026-04-09
**状态**: Draft v3（最终版，可上线）
**Phase**: Phase 6
**前置依赖**: Phase 5 (per-call session)

---

## 1. 概述

Phase 5 的 per-call session 模式简单、错误隔离、无连接泄漏，但**高频调用场景**会有性能问题。

**Phase 6 目标**：提供 production-ready 连接池，实现连接复用。

---

## 2. 设计目标

| 目标 | 说明 |
|------|------|
| 连接复用 | 避免每次 tool call 重建连接 |
| 并发限流 | 防止 100 个 agent 打爆 MCP server |
| 双 TTL | 区分总生命周期和空闲时间 |
| 故障隔离 | 单个 session 挂了不影响其他 |

---

## 3. 架构

```
MCPConnectionPool
├── _pools: dict[mcp_server_id → ServerPool]

ServerPool（按 MCP Server 分池）
├── _idle: Deque[PooledSession]      # 可复用连接
├── _semaphore: Semaphore             # 并发限流
├── _config: MCPToolConfig            # 连接配置
├── max_lifetime: float              # 最大生命周期（秒）
├── max_idle_time: float             # 最大空闲时间（秒）

PooledSession
├── session: ClientSession
├── ctx: ManagedSession
├── created_at: float
├── last_used_at: float
├── is_closed: bool
```

---

## 4. 核心实现

### 4.1 ManagedSession

```python
# app/modules/agent/mcp/pool/managed_session.py

from mcp import ClientSession


class ManagedSession:
    """
    可复用的 session 包装器。

    持有 context manager 的引用，允许手动关闭。
    """

    def __init__(self, ctx):
        self._ctx = ctx
        self.session: ClientSession | None = None

    async def open(self) -> ClientSession:
        self.session = await self._ctx.__aenter__()
        return self.session

    async def close(self) -> None:
        if self.session is None:
            return
        try:
            await self._ctx.__aexit__(None, None, None)
        except Exception:
            pass
        finally:
            self.session = None
```

### 4.2 PooledSession

```python
# app/modules/agent/mcp/pool/pooled_session.py

from dataclasses import dataclass
import time
from mcp import ClientSession
from .managed_session import ManagedSession


@dataclass
class PooledSession:
    session: ClientSession
    ctx: ManagedSession
    created_at: float
    last_used_at: float
    is_closed: bool = False

    def touch(self) -> None:
        self.last_used_at = time.time()

    def is_lifetime_expired(self, max_lifetime: float) -> bool:
        return (time.time() - self.created_at) > max_lifetime

    def is_idle_expired(self, max_idle_time: float) -> bool:
        return (time.time() - self.last_used_at) > max_idle_time

    async def close(self) -> None:
        if self.is_closed:
            return
        try:
            await self.ctx.close()
        except Exception:
            pass
        finally:
            self.is_closed = True
```

### 4.3 ServerPool

```python
# app/modules/agent/mcp/pool/server_pool.py

import asyncio
import time
from collections import deque
from typing import Deque

from app.modules.agent.mcp.tool import MCPToolConfig
from app.modules.agent.mcp.session import create_session
from app.modules.agent.mcp.exceptions import MCPConnectionError
from .pooled_session import PooledSession
from .managed_session import ManagedSession


class ServerPool:
    """单个 MCP Server 的连接池"""

    def __init__(
        self,
        config: MCPToolConfig,
        max_concurrency: int = 10,
        max_idle: int = 20,
        max_lifetime: float = 300.0,
        max_idle_time: float = 60.0,
    ):
        self.config = config
        self.max_idle = max_idle
        self.max_lifetime = max_lifetime
        self.max_idle_time = max_idle_time

        self._idle: Deque[PooledSession] = deque()
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrency)
        self._lock: asyncio.Lock = asyncio.Lock()

    async def acquire(self) -> PooledSession:
        """获取一个连接"""
        await self._semaphore.acquire()
        try:
            # 清理过期连接（在锁外执行）
            await self._cleanup_expired()

            # 尝试获取可用连接
            while self._idle:
                ps = self._idle.popleft()
                if ps.is_closed:
                    await ps.close()
                    continue
                if ps.is_lifetime_expired(self.max_lifetime):
                    await ps.close()
                    continue
                if ps.is_idle_expired(self.max_idle_time):
                    await ps.close()
                    continue

                ps.touch()
                return ps

            # 没有可用连接 → 创建新的
            return await self._create_session()

        except Exception:
            self._semaphore.release()
            raise

    async def _cleanup_expired(self) -> None:
        """清理池中所有过期连接（在锁外执行，避免阻塞）"""
        to_close: list[PooledSession] = []
        async with self._lock:
            new_idle: deque[PooledSession] = deque()
            while self._idle:
                ps = self._idle.popleft()
                if ps.is_lifetime_expired(self.max_lifetime):
                    to_close.append(ps)
                elif ps.is_idle_expired(self.max_idle_time):
                    to_close.append(ps)
                else:
                    new_idle.append(ps)
            self._idle = new_idle

        # ← 修复：在锁外关闭，避免阻塞
        for ps in to_close:
            try:
                await ps.close()
            except Exception:
                pass

    async def _create_session(self) -> PooledSession:
        """创建新 session"""
        try:
            session_ctx = create_session(
                transport=self.config.transport,
                url=self.config.url,
                command=self.config.command,
                args=self.config.args,
                env=self.config.env,
                cwd=self.config.cwd,
                headers=self.config.headers,
            )

            managed = ManagedSession(session_ctx)
            session = await managed.open()

            return PooledSession(
                session=session,
                ctx=managed,
                created_at=time.time(),
                last_used_at=time.time(),
            )

        except Exception as e:
            self._semaphore.release()
            raise MCPConnectionError(f"Failed to create session: {e}") from e

    async def release(self, ps: PooledSession, error: bool = False) -> None:
        """
        释放连接回池或关闭。

        ← 修复：不在锁内 await close，避免阻塞其他 acquire
        """
        # 判断是否需要关闭
        should_close = (
            error
            or ps.is_closed
            or ps.is_lifetime_expired(self.max_lifetime)
            or ps.is_idle_expired(self.max_idle_time)
        )

        if should_close:
            await ps.close()
            self._semaphore.release()
            return

        # 放回池或关闭
        should_close_local = False
        async with self._lock:
            if len(self._idle) < self.max_idle:
                ps.touch()
                self._idle.append(ps)
            else:
                should_close_local = True

        if should_close_local:
            await ps.close()

        self._semaphore.release()

    async def cleanup_expired(self) -> None:
        """清理池中所有过期连接（供外部调用）"""
        await self._cleanup_expired()

    async def close(self) -> None:
        """关闭整个池"""
        async with self._lock:
            while self._idle:
                ps = self._idle.popleft()
                await ps.close()
```

### 4.4 ConnectionPool

```python
# app/modules/agent/mcp/pool/connection_pool.py

from typing import Dict
import asyncio

from app.modules.agent.mcp.tool import MCPToolConfig
from app.modules.agent.mcp.pool.server_pool import ServerPool


class MCPConnectionPool:
    """全局 MCP 连接池管理器"""

    def __init__(self):
        self._pools: Dict[str, ServerPool] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        self._shutdown: bool = False

    async def get_pool(self, config: MCPToolConfig) -> ServerPool:
        """获取或创建指定 MCP server 的连接池"""
        key = config.mcp_server_id

        if key not in self._pools:
            async with self._lock:
                if key not in self._pools and not self._shutdown:
                    self._pools[key] = ServerPool(config)
                    if self._cleanup_task is None:
                        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        return self._pools[key]

    async def _cleanup_loop(self) -> None:
        """后台清理任务"""
        try:
            while not self._shutdown:
                await asyncio.sleep(60)
                if self._shutdown:
                    break
                await self._cleanup_all_pools()
        except asyncio.CancelledError:
            return

    async def _cleanup_all_pools(self) -> None:
        """
        清理所有池的过期连接。

        ← 修复：调用 cleanup_expired，而非 close()
        """
        for pool in list(self._pools.values()):
            try:
                await pool.cleanup_expired()
            except Exception:
                pass

    async def close_all(self) -> None:
        """关闭所有连接池"""
        self._shutdown = True

        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

        for pool in list(self._pools.values()):
            await pool.close()

        self._pools.clear()


# 全局单例
connection_pool = MCPConnectionPool()
```

---

## 5. MCPTool

```python
# app/modules/agent/mcp/pool/tool.py

import asyncio
from dataclasses import dataclass
from typing import Any

from app.modules.agent.tools.base import Tool
from app.modules.agent.mcp.pool.connection_pool import connection_pool
from app.modules.agent.mcp.pool.exceptions import (
    MCPConnectionError, MCPToolExecutionError,
)


@dataclass
class MCPToolConfig:
    mcp_server_id: str
    name: str
    transport: str
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    headers: dict[str, Any] | None = None


class MCPTool(Tool):
    """MCP 工具运行时封装（连接池版本）"""

    name: str
    input_schema: dict
    _call_timeout: float = 10.0

    def __init__(
        self,
        config: MCPToolConfig,
        tool_name: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        self._config = config
        self._tool_name = tool_name
        self.name = tool_name
        self.description = description
        self.input_schema = input_schema or {"type": "object", "properties": {}}

    async def run(self, input: dict) -> dict:
        pool = await connection_pool.get_pool(self._config)
        ps = None
        released = False

        try:
            ps = await pool.acquire()

            result = await asyncio.wait_for(
                ps.session.call_tool(self._tool_name, input),
                timeout=self._call_timeout,
            )

            await pool.release(ps, error=False)
            released = True
            return self._parse_result(result)

        except asyncio.TimeoutError:
            if not released and ps is not None:
                await pool.release(ps, error=True)
            raise MCPToolExecutionError(
                f"Tool {self._tool_name} timeout after {self._call_timeout}s"
            )

        except Exception as e:
            if not released and ps is not None:
                await pool.release(ps, error=True)
            raise

    def _parse_result(self, result) -> dict:
        if not hasattr(result, 'content') or not result.content:
            return {"result": str(result) if result else ""}

        outputs = []
        for item in result.content:
            if hasattr(item, 'text'):
                outputs.append(item.text)
            elif hasattr(item, 'data'):
                outputs.append(f"<binary data: {len(item.data)} bytes>")
            else:
                outputs.append(str(item))

        return {"result": "\n".join(outputs)}
```

---

## 6. 参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_concurrency` | 10 | 每个 MCP server 最大并发数 |
| `max_idle` | 20 | 最大空闲连接数 |
| `max_lifetime` | 300 | 连接最大生命周期（秒） |
| `max_idle_time` | 60 | 连接最大空闲时间（秒） |
| `_call_timeout` | 10 | 工具调用超时（秒） |

---

## 7. 关键修复总结

| 问题 | 修复 |
|------|------|
| `_cleanup_all_pools` 调用 `pool.close()` | 改为调用 `pool.cleanup_expired()` |
| `asyncio.create_task` 可能失控 | 改为同步 `await close()` |
| `release()` 锁内 `await close()` | 先记录标志，在锁外 close |

---

## 8. 实现步骤

1. 创建 `app/modules/agent/mcp/pool/managed_session.py`
2. 创建 `app/modules/agent/mcp/pool/pooled_session.py`
3. 创建 `app/modules/agent/mcp/pool/server_pool.py`
4. 创建 `app/modules/agent/mcp/pool/connection_pool.py`
5. 创建 `app/modules/agent/mcp/pool/tool.py`
6. 创建 `app/modules/agent/mcp/pool/exceptions.py`
7. 更新 `app/modules/agent/tool_builder.py` 使用连接池
8. 测试验证

---

## 9. 验证清单

### 功能测试
- [ ] 连接复用：连续调用同一工具，复用同一连接
- [ ] 并发限流：超过 max_concurrency 时等待
- [ ] 双 TTL：超过 max_lifetime 或 max_idle_time 的连接不再复用
- [ ] 故障隔离：一个 session 失败不影响其他

### 资源安全测试
- [ ] 无资源泄漏（fd / socket）
- [ ] cleanup_loop 可正常退出
- [ ] shutdown 时所有连接正确关闭

### 性能测试
- [ ] 100 次工具调用耗时对比（per-call vs pool）
- [ ] 并发 50 个 agent 的表现

---

## 10. Phase 边界

### Phase 6 包含
- ✅ 连接池（按 server 分池）
- ✅ 并发限流（Semaphore）
- ✅ 双 TTL（lifetime + idle_time）
- ✅ ManagedSession 包装 context manager
- ✅ 锁外 close，避免阻塞

### Phase 6 不包含
- ❌ circuit breaker / retry（Phase 7）
- ❌ metrics 监控（Phase 7）
- ❌ adaptive concurrency（Phase 8）

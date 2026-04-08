# Agent System Phase 6.5 — MCP Connection Pool Enhanced

**日期**: 2026-04-09
**状态**: Draft v1（整合全部 10 项修复）
**Phase**: Phase 6.5
**前置依赖**: Phase 6 (connection pool v3)

---

## 1. 概述

Phase 6 的连接池已可用于生产，但缺少 SRE 级可观测性和健壮的容错能力。

**Phase 6.5 目标**：
- metrics 可观测性（EMA + 分层指标）
- 健康检查采样（避免全量 await）
- Per-session jitter（防 thundering herd）
- Session 创建限流（防打爆 MCP server）
- Tool schema 单次获取（singleflight）
- Backpressure 支持（retry_after）

---

## 2. 十项修复清单

| # | 修复项 | 位置 | 优先级 |
|---|--------|------|--------|
| 1 | Per-session jitter | PooledSession.create() | **P0** |
| 2 | Health check 采样 | ServerPool.acquire() | **P0** |
| 3 | Acquire timeout + metrics | ServerPool.acquire() | **P0** |
| 4 | EMA 平均计算 | PoolMetrics | P1 |
| 5 | in_use/idle/pool_size 指标 | PoolMetrics | P1 |
| 6 | Singleflight ToolSchemaCache | MCPToolConfigRegistry | P1 |
| 7 | Create session 限流 | ServerPool._create_lock | P1 |
| 8 | retry_after backpressure | MCPTool.run() | P2 |

---

## 3. 架构

```
MCPConnectionPool
├── _pools: dict[mcp_server_id → ServerPool]
├── _registry: ToolSchemaCache        # singleflight schema 获取

ServerPool（按 MCP Server 分池）
├── _idle: Deque[PooledSession]       # 可复用连接
├── _in_use: set[PooledSession]      # 正在使用的连接
├── _semaphore: Semaphore            # 并发限流
├── _create_lock: asyncio.Lock       # session 创建限流
├── _config: MCPToolConfig
├── _metrics: PoolMetrics
├── max_lifetime_base: float         # 基础 TTL（jitter 前）
├── max_idle_time: float

PooledSession
├── session: ClientSession
├── ctx: ManagedSession
├── created_at: float
├── last_used_at: float
├── last_health_check_at: float       # 上次健康检查时间
├── max_lifetime: float              # ← 修复 1：per-session jitter
├── is_closed: bool

PoolMetrics（新增）
├── _acquired: Counter
├── _acquire_timeouts: Counter
├── _released: Counter
├── _errors: Counter
├── _acquire_durations: EMA           # ← 修复 4：EMA 平均延迟
├── _in_use: Gauge                   # ← 修复 5：正在使用数
├── _idle: Gauge                     # ← 修复 5：空闲数
├── _pool_size: Gauge                # ← 修复 5：池大小

ToolSchemaCache（新增，singleflight）
├── _cache: dict                     # schema 缓存
├── _locks: dict                     # per-key lock
├── _pending: dict                   # pending future
```

---

## 4. 核心实现

### 4.1 PoolMetrics

```python
# app/modules/agent/mcp/pool/metrics.py

from dataclasses import dataclass, field
import time
import random
import asyncio


class EMA:
    """
    指数移动平均。

    用于平滑延迟等波动指标。
    """

    def __init__(self, alpha: float = 0.2):
        self.alpha = alpha
        self.value: float | None = None

    def update(self, sample: float) -> float:
        if self.value is None:
            self.value = sample
        else:
            self.value = self.alpha * sample + (1 - self.alpha) * self.value
        return self.value

    def get(self) -> float:
        return self.value or 0.0


class PoolMetrics:
    """
    连接池指标采集器。

    收集：
    - acquired / acquire_timeouts / released / errors（计数）
    - acquire_durations（EMA 平滑延迟）
    - in_use / idle / pool_size（当前状态）
    """

    def __init__(self, pool_id: str):
        self.pool_id = pool_id
        self._acquired = 0
        self._acquire_timeouts = 0
        self._released = 0
        self._errors = 0
        self._acquire_durations = EMA(alpha=0.2)
        self._in_use = 0
        self._idle = 0
        self._pool_size = 0
        self._lock = asyncio.Lock()

    def record_acquired(self, duration_ms: float) -> None:
        self._acquired += 1
        self._acquire_durations.update(duration_ms)

    def record_acquire_timeout(self) -> None:
        self._acquire_timeouts += 1

    def record_released(self) -> None:
        self._released += 1

    def record_error(self) -> None:
        self._errors += 1

    async def update_counts(self, in_use: int, idle: int) -> None:
        async with self._lock:
            self._in_use = in_use
            self._idle = idle
            self._pool_size = in_use + idle

    def snapshot(self) -> dict:
        return {
            "pool_id": self.pool_id,
            "acquired": self._acquired,
            "acquire_timeouts": self._acquire_timeouts,
            "released": self._released,
            "errors": self._errors,
            "acquire_duration_ema_ms": round(self._acquire_durations.get(), 2),
            "in_use": self._in_use,
            "idle": self._idle,
            "pool_size": self._pool_size,
        }
```

### 4.2 ToolSchemaCache（Singleflight）

```python
# app/modules/agent/mcp/pool/tool_schema_cache.py

import asyncio
from typing import Any


class ToolSchemaCache:
    """
    Tool schema 单次获取（singleflight）。

    防止多个并发请求同时获取同一个 tool 的 schema。
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_or_fetch(
        self,
        key: str,
        fetch_fn: callable,
    ) -> Any:
        """
        获取 schema，如果正在获取中则等待。

        singleflight 模式：多个并发请求只触发一次实际获取。
        """
        # 缓存命中
        if key in self._cache:
            return self._cache[key]

        # 已有 pending 请求，等待它
        if key in self._pending:
            future = self._pending[key]
            return await future

        # 创建新请求
        async with self._global_lock:
            # 二次检查
            if key in self._cache:
                return self._cache[key]
            if key in self._pending:
                future = self._pending[key]
                return await future

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending[key] = future

        try:
            result = await fetch_fn()
            self._cache[key] = result
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            self._pending.pop(key, None)

    def invalidate(self, key: str | None = None) -> None:
        """清除缓存。"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()


# 模块级单例
tool_schema_cache = ToolSchemaCache()
```

### 4.3 PooledSession（Per-session Jitter）

```python
# app/modules/agent/mcp/pool/pooled_session.py

from dataclasses import dataclass
import time
import random
from mcp import ClientSession
from .managed_session import ManagedSession


# ← 修复 1：jitter 参数
DEFAULT_JITTER_FACTOR = 0.1  # ±10% jitter


@dataclass
class PooledSession:
    session: ClientSession
    ctx: ManagedSession
    created_at: float
    last_used_at: float
    last_health_check_at: float
    max_lifetime: float              # ← per-session，jitter 后值
    is_closed: bool = False

    @classmethod
    def create(
        cls,
        session: ClientSession,
        ctx: ManagedSession,
        base_max_lifetime: float = 300.0,
    ) -> "PooledSession":
        """
        工厂方法：创建 PooledSession 并应用 per-session jitter。

        ← 修复 1：jitter 在 session 创建时应用，而非 pool 级别。
        这样每个连接的 TTL 略有不同，避免大量连接同时过期。
        """
        jitter = base_max_lifetime * DEFAULT_JITTER_FACTOR
        actual_lifetime = base_max_lifetime + random.uniform(-jitter, jitter)

        now = time.time()
        return cls(
            session=session,
            ctx=ctx,
            created_at=now,
            last_used_at=now,
            last_health_check_at=now,
            max_lifetime=actual_lifetime,  # ← per-session jitter TTL
        )

    def touch(self) -> None:
        self.last_used_at = time.time()

    def is_lifetime_expired(self) -> bool:
        return (time.time() - self.created_at) > self.max_lifetime

    def is_idle_expired(self, max_idle_time: float) -> bool:
        return (time.time() - self.last_used_at) > max_idle_time

    def is_cold(self, cold_threshold: float = 10.0) -> bool:
        """连接是否"冷"（空闲时间超过阈值）。"""
        return (time.time() - self.last_used_at) > cold_threshold

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

### 4.4 ServerPool（Health Check 采样 + Acquire Timeout + Metrics）

```python
# app/modules/agent/mcp/pool/server_pool.py

import asyncio
import time
import random
from collections import deque
from typing import Deque

from app.modules.agent.mcp.tool import MCPToolConfig
from app.modules.agent.mcp.session import create_session
from app.modules.agent.mcp.pool.exceptions import MCPConnectionError
from app.modules.agent.mcp.pool.pooled_session import PooledSession
from app.modules.agent.mcp.pool.managed_session import ManagedSession
from app.modules.agent.mcp.pool.metrics import PoolMetrics


# ← 修复 2：健康检查采样概率
HEALTH_CHECK_PROB = 0.2          # 20% 概率
COLD_CONNECTION_THRESHOLD = 10.0  # 10s 以上的"冷"连接需要健康检查

# ← 修复 3：acquire 超时
DEFAULT_ACQUIRE_TIMEOUT = 30.0    # 获取连接超时（秒）


class ServerPool:
    """单个 MCP Server 的连接池"""

    def __init__(
        self,
        config: MCPToolConfig,
        max_concurrency: int = 10,
        max_idle: int = 20,
        base_max_lifetime: float = 300.0,
        max_idle_time: float = 60.0,
        acquire_timeout: float = DEFAULT_ACQUIRE_TIMEOUT,
    ):
        self.config = config
        self.pool_id = config.mcp_server_id
        self.max_idle = max_idle
        self.base_max_lifetime = base_max_lifetime  # jitter 前的基础值
        self.max_idle_time = max_idle_time
        self.acquire_timeout = acquire_timeout

        self._idle: Deque[PooledSession] = deque()
        self._in_use: set[PooledSession] = set()
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrency)
        self._lock: asyncio.Lock = asyncio.Lock()
        # ← 修复 7：session 创建限流锁
        self._create_lock: asyncio.Lock = asyncio.Lock()
        self._metrics = PoolMetrics(self.pool_id)

    async def acquire(self) -> PooledSession:
        """
        获取一个连接。

        ← 修复 3：添加 acquire timeout + metrics 记录。
        ← 修复 2：健康检查采样（非全量）。
        """
        await self._semaphore.acquire()
        start_time = time.time()
        acquired = False

        try:
            # ← 修复 3：acquire timeout
            async with asyncio.timeout(self.acquire_timeout):
                ps = await self._acquire_impl()
                acquired = True

                # 记录 metrics
                duration_ms = (time.time() - start_time) * 1000
                self._metrics.record_acquired(duration_ms)

                # 更新计数指标
                await self._metrics.update_counts(
                    in_use=len(self._in_use),
                    idle=len(self._idle),
                )

                return ps

        except asyncio.TimeoutError:
            # ← 修复 3：timeout 记录 metrics
            self._metrics.record_acquire_timeout()
            self._semaphore.release()
            raise MCPConnectionError(
                f"Acquire timeout after {self.acquire_timeout}s "
                f"(pool_id={self.pool_id})"
            )
        except Exception:
            if not acquired:
                self._metrics.record_error()
                self._semaphore.release()
            raise

    async def _acquire_impl(self) -> PooledSession:
        """实际获取连接的逻辑。"""
        # 清理过期连接（在锁外执行）
        await self._cleanup_expired()

        # 尝试获取可用连接
        while self._idle:
            ps = self._idle.popleft()
            if ps.is_closed:
                await ps.close()
                continue
            if ps.is_lifetime_expired():
                await ps.close()
                continue
            if ps.is_idle_expired(self.max_idle_time):
                await ps.close()
                continue

            # ← 修复 2：健康检查采样（20% 概率 或 冷连接）
            should_health_check = (
                random.random() < HEALTH_CHECK_PROB
                or ps.is_cold(COLD_CONNECTION_THRESHOLD)
            )
            if should_health_check:
                healthy = await self._health_check(ps)
                if not healthy:
                    await ps.close()
                    continue

            ps.touch()
            self._in_use.add(ps)
            return ps

        # 没有可用连接 → 创建新的（受 _create_lock 限流）
        return await self._create_session_locked()

    async def _health_check(self, ps: PooledSession) -> bool:
        """
        健康检查。

        ← 修复 2：采样检查，而非每次都检查。
        通过 ping/pong 或 list_tools 验证连接可用性。
        """
        try:
            # 使用 list_tools 作为轻量健康检查
            # 实际实现可能需要根据 MCP server 支持的 method
            await asyncio.wait_for(
                ps.session.list_tools(),
                timeout=2.0,
            )
            ps.last_health_check_at = time.time()
            return True
        except Exception:
            return False

    async def _create_session_locked(self) -> PooledSession:
        """
        创建新 session（受 _create_lock 限流）。

        ← 修复 7：防止 thundering herd，多个协程同时创建 session。
        """
        async with self._create_lock:
            # 在锁内再检查一次，可能其他协程刚创建完
            await self._cleanup_expired()
            while self._idle:
                ps = self._idle.popleft()
                if ps.is_closed or ps.is_lifetime_expired() or ps.is_idle_expired(self.max_idle_time):
                    await ps.close()
                    continue
                ps.touch()
                self._in_use.add(ps)
                return ps

            # 确实没有，复创建一个
            return await self._create_session_unlocked()

    async def _create_session_unlocked(self) -> PooledSession:
        """创建新 session（不在创建锁内）。"""
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

            # ← 修复 1：per-session jitter 工厂方法
            ps = PooledSession.create(
                session=session,
                ctx=managed,
                base_max_lifetime=self.base_max_lifetime,
            )
            self._in_use.add(ps)
            return ps

        except Exception as e:
            self._semaphore.release()
            raise MCPConnectionError(f"Failed to create session: {e}") from e

    async def _cleanup_expired(self) -> None:
        """清理池中所有过期连接（在锁外执行，避免阻塞）"""
        to_close: list[PooledSession] = []
        async with self._lock:
            new_idle: deque[PooledSession] = deque()
            while self._idle:
                ps = self._idle.popleft()
                if ps.is_lifetime_expired():
                    to_close.append(ps)
                elif ps.is_idle_expired(self.max_idle_time):
                    to_close.append(ps)
                else:
                    new_idle.append(ps)
            self._idle = new_idle

        # 在锁外关闭，避免阻塞
        for ps in to_close:
            try:
                await ps.close()
            except Exception:
                pass

    async def release(self, ps: PooledSession, error: bool = False) -> None:
        """
        释放连接回池或关闭。

        ← 修复 5：维护 in_use / idle 计数。
        """
        self._in_use.discard(ps)

        # 判断是否需要关闭
        should_close = (
            error
            or ps.is_closed
            or ps.is_lifetime_expired()
            or ps.is_idle_expired(self.max_idle_time)
        )

        if should_close:
            await ps.close()
            self._semaphore.release()
            await self._metrics.update_counts(
                in_use=len(self._in_use),
                idle=len(self._idle),
            )
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
        self._metrics.record_released()
        await self._metrics.update_counts(
            in_use=len(self._in_use),
            idle=len(self._idle),
        )

    async def cleanup_expired(self) -> None:
        """清理池中所有过期连接（供外部调用）"""
        await self._cleanup_expired()

    async def close(self) -> None:
        """关闭整个池"""
        async with self._lock:
            while self._idle:
                ps = self._idle.popleft()
                await ps.close()
            # 关闭正在使用的连接
            for ps in list(self._in_use):
                await ps.close()
            self._in_use.clear()

    def metrics(self) -> dict:
        """获取指标快照。"""
        return self._metrics.snapshot()
```

### 4.5 ConnectionPool

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
        """清理所有池的过期连接。"""
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

    def get_all_metrics(self) -> dict:
        """获取所有池的指标。"""
        return {
            pool_id: pool.metrics()
            for pool_id, pool in self._pools.items()
        }


# 全局单例
connection_pool = MCPConnectionPool()
```

### 4.6 MCPTool（retry_after Backpressure）

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
            # ← 修复 8：retry_after backpressure
            if self._is_retry_after_error(e):
                retry_after = self._extract_retry_after(e)
                if retry_after:
                    await asyncio.sleep(retry_after)
                    return await self.run(input)  # 重试一次
            raise

    def _is_retry_after_error(self, error: Exception) -> bool:
        """判断是否是 429 等需要 retry_after 的错误。"""
        error_str = str(error).lower()
        return "429" in error_str or "too many requests" in error_str

    def _extract_retry_after(self, error: Exception) -> float | None:
        """从错误中提取 retry_after 值（秒）。"""
        # 实际实现可能需要解析响应体或 header
        error_str = str(error)
        # 简单解析：如果错误信息中包含 retry_after
        if "retry_after" in error_str.lower():
            try:
                # 假设格式："... retry_after: 5 ..."
                parts = error_str.split("retry_after")
                if len(parts) > 1:
                    value = parts[1].split()[0]
                    return float(value)
            except (ValueError, IndexError):
                pass
        return None

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

### 4.7 ToolBuilder（Singleflight + 连接池）

```python
# app/modules/agent/mcp/pool/tool_builder.py

from app.modules.agent.domain import DomainConfig, MCPConfigItem, ToolConfigItem
from app.modules.agent.tools.base import Tool
from app.modules.agent.mcp.pool.tool_schema_cache import tool_schema_cache
from app.modules.agent.mcp.pool.connection_pool import connection_pool
from app.modules.agent.mcp.pool.tool import MCPToolConfig, MCPTool


class ToolBuilder:
    """ToolBuilder - 支持连接池版本的 MCP 工具构建"""

    def __init__(self, rag_service=None):
        self.rag_service = rag_service

    async def build(self, config: DomainConfig | None) -> tuple[list[Tool], list[str]]:
        tools: list[Tool] = []
        warnings: list[str] = []

        if not config:
            return [], ["No config provided"]

        # 1. Built-in tools
        for tool_cfg in config.tools:
            if not tool_cfg.enabled:
                continue
            try:
                tool = self._build_builtin(tool_cfg)
                if tool:
                    tools.append(tool)
            except Exception as e:
                warnings.append(f"builtin:{tool_cfg.tool_name} load failed: {e}")

        # 2. MCP tools
        for mcp_cfg in config.mcp_servers:
            if not mcp_cfg.enabled:
                continue
            try:
                mcp_tools = await self._build_mcp(mcp_cfg)
                tools.extend(mcp_tools)
            except Exception as e:
                warnings.append(f"mcp:{mcp_cfg.name} load failed: {e}")

        # 3. RAG tools
        if config.kbs and self.rag_service:
            try:
                rag_tool = self._build_rag(config.kbs)
                tools.append(rag_tool)
            except Exception as e:
                warnings.append(f"rag load failed: {e}")

        return tools, warnings

    async def _build_mcp(self, mcp_cfg: MCPConfigItem) -> list[Tool]:
        """
        构建 MCP 工具列表。

        ← 修复 6：使用 singleflight 获取 schema，避免重复请求。
        """
        # ← 修复 6：singleflight schema 获取
        cache_key = f"{mcp_cfg.mcp_server_id}:{mcp_cfg.transport}:{mcp_cfg.url}"

        schema_result = await tool_schema_cache.get_or_fetch(
            key=cache_key,
            fetch_fn=lambda: self._fetch_schema(mcp_cfg),
        )

        tool_config = MCPToolConfig(
            mcp_server_id=mcp_cfg.mcp_server_id,
            name=mcp_cfg.name,
            transport=mcp_cfg.transport,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        )

        tools = []
        for t in schema_result.tools:
            input_schema = getattr(t, 'inputSchema', None) or {"type": "object", "properties": {}}
            tools.append(MCPTool(
                config=tool_config,
                tool_name=t.name,
                description=t.description or "",
                input_schema=input_schema,
            ))
        return tools

    async def _fetch_schema(self, mcp_cfg: MCPConfigItem) -> Any:
        """从 MCP server 获取 schema。"""
        from app.modules.agent.mcp.session import create_session

        async with create_session(
            transport=mcp_cfg.transport,
            url=mcp_cfg.url,
            command=mcp_cfg.command,
            args=mcp_cfg.args,
            env=mcp_cfg.env,
            cwd=mcp_cfg.cwd,
            headers=mcp_cfg.headers,
        ) as session:
            return await session.list_tools()

    def _build_builtin(self, tool_cfg: ToolConfigItem) -> Tool | None:
        match tool_cfg.tool_name:
            case "calculator" | "datetime":
                return _BuiltinToolWrapper(tool_cfg.tool_name)
            case "websearch":
                api_key = tool_cfg.tool_config.get("api_key")
                if not api_key:
                    raise ValueError("websearch requires api_key")
                return _WebSearchToolWrapper(api_key=api_key)
            case _:
                return None

    def _build_rag(self, kbs: list) -> Tool:
        from app.modules.agent.tools.rag_tool import RAGRetrievalTool
        kb_ids = [kb.kb_id for kb in kbs]
        tool = RAGRetrievalTool(kb_ids=kb_ids, top_k=5)
        tool.set_rag_service(self.rag_service)
        return tool


class _BuiltinToolWrapper(Tool):
    name: str
    description: str
    input_schema: dict

    def __init__(self, tool_name: str):
        self.name = tool_name
        self.tool_name = tool_name
        if tool_name == "calculator":
            self.description = "数学计算"
            self.input_schema = {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}
        else:
            self.description = "当前日期时间"
            self.input_schema = {"type": "object", "properties": {}}

    async def run(self, input: dict) -> dict:
        from app.modules.agent.tools.calculator import CalculatorTool
        from app.modules.agent.tools.datetime import DateTimeTool
        if self.tool_name == "calculator":
            return await CalculatorTool().run(input)
        return await DateTimeTool().run(input)
```

---

## 5. 参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_concurrency` | 10 | 每个 MCP server 最大并发数 |
| `max_idle` | 20 | 最大空闲连接数 |
| `base_max_lifetime` | 300 | 连接基础最大生命周期（秒，jitter 前） |
| `max_idle_time` | 60 | 连接最大空闲时间（秒） |
| `acquire_timeout` | 30 | 获取连接超时（秒） |
| `_call_timeout` | 10 | 工具调用超时（秒） |
| `HEALTH_CHECK_PROB` | 0.2 | 健康检查采样概率（20%） |
| `COLD_CONNECTION_THRESHOLD` | 10 | 冷连接判定阈值（秒） |
| `DEFAULT_JITTER_FACTOR` | 0.1 | jitter 范围（±10%） |

---

## 6. 关键修复详解

### 修复 1：Per-session Jitter

```python
# PooledSession.create() 中应用 jitter
jitter = base_max_lifetime * DEFAULT_JITTER_FACTOR
actual_lifetime = base_max_lifetime + random.uniform(-jitter, jitter)
```

**为什么**：如果所有连接的 TTL 完全相同，大量连接会同时过期，导致 thundering herd。Per-session jitter 让每个连接的 TTL 略有不同，平滑过期。

### 修复 2：Health Check 采样

```python
should_health_check = (
    random.random() < HEALTH_CHECK_PROB      # 20% 概率
    or ps.is_cold(COLD_CONNECTION_THRESHOLD) # 或冷连接
)
```

**为什么**：如果每次 acquire 都做健康检查，会在锁内 await，导致性能下降。采样检查只在必要时验证连接健康。

### 修复 3：Acquire Timeout + Metrics

```python
async with asyncio.timeout(self.acquire_timeout):
    ps = await self._acquire_impl()

# TimeoutError 时记录
self._metrics.record_acquire_timeout()
```

**为什么**：没有 timeout，acquire 可能永远阻塞。记录 timeout 指标便于监控池健康。

### 修复 4：EMA 平均计算

```python
class EMA:
    def update(self, sample: float) -> float:
        self.value = self.alpha * sample + (1 - self.alpha) * self.value
```

**为什么**：简单平均对噪声敏感。EMA 平滑波动，更准确反映真实延迟趋势。

### 修复 5：in_use/idle/pool_size 指标

```python
# release() 中维护
self._in_use.discard(ps)
await self._metrics.update_counts(
    in_use=len(self._in_use),
    idle=len(self._idle),
)
```

**为什么**：精确跟踪池状态，区分"正在使用"和"空闲"，便于容量规划。

### 修复 6：Singleflight ToolSchemaCache

```python
# 多个并发请求只触发一次实际获取
if key in self._pending:
    future = self._pending[key]
    return await future
```

**为什么**：agent 启动时可能并发请求同一 MCP server 的 schema，singleflight 避免重复请求。

### 修复 7：Create Session 限流

```python
async with self._create_lock:
    # 再检查一次...
    return await self._create_session_unlocked()
```

**为什么**：高并发下，多个协程同时发现"没有可用连接"会同时创建 session。_create_lock 限流防止打爆 MCP server。

### 修复 8：retry_after Backpressure

```python
if self._is_retry_after_error(e):
    retry_after = self._extract_retry_after(e)
    if retry_after:
        await asyncio.sleep(retry_after)
        return await self.run(input)
```

**为什么**：MCP server 可能返回 429，客户端应尊重 retry_after 响应。

---

## 7. 实现步骤

1. 创建 `app/modules/agent/mcp/pool/metrics.py`（PoolMetrics + EMA）
2. 创建 `app/modules/agent/mcp/pool/tool_schema_cache.py`（singleflight）
3. 更新 `app/modules/agent/mcp/pool/pooled_session.py`（per-session jitter + cold check）
4. 更新 `app/modules/agent/mcp/pool/server_pool.py`（采样健康检查 + acquire timeout + metrics）
5. 更新 `app/modules/agent/mcp/pool/connection_pool.py`（get_all_metrics）
6. 更新 `app/modules/agent/mcp/pool/tool.py`（retry_after backpressure）
7. 创建 `app/modules/agent/mcp/pool/tool_builder.py`（singleflight schema 获取）
8. 创建 `app/modules/agent/mcp/pool/exceptions.py`
9. 更新 `app/modules/agent/tool_builder.py` 使用连接池版本
10. 测试验证

---

## 8. 验证清单

### 功能测试
- [ ] Per-session jitter：连续创建 10 个连接，TTL 各不相同
- [ ] Health check 采样：查看 metrics 确认不是每次 acquire 都检查
- [ ] Acquire timeout：acquire_timeout 生效，抛出 MCPConnectionError
- [ ] EMA 平均：metrics 中 acquire_duration_ema_ms 平滑
- [ ] in_use/idle 计数：release 后 idle +1，acquire 后 idle -1
- [ ] Singleflight：并发 10 个请求只有 1 次实际 fetch
- [ ] Create 限流：查看日志确认 session 创建受 _create_lock 保护
- [ ] retry_after：429 响应触发重试

### 资源安全测试
- [ ] 无资源泄漏（fd / socket）
- [ ] cleanup_loop 可正常退出
- [ ] shutdown 时所有连接正确关闭

### 性能测试
- [ ] 100 次工具调用耗时对比（per-call vs pool vs pool+6.5）
- [ ] 并发 50 个 agent 的表现

---

## 9. Phase 边界

### Phase 6.5 包含
- ✅ Per-session jitter（防 thundering herd）
- ✅ 健康检查采样（20% + cold connection）
- ✅ Acquire timeout + metrics
- ✅ EMA 平均计算
- ✅ in_use/idle/pool_size 指标
- ✅ Singleflight ToolSchemaCache
- ✅ Create session 限流（_create_lock）
- ✅ retry_after backpressure

### Phase 6.5 不包含
- ❌ Circuit breaker / retry（Phase 7）
- ❌ 动态调整参数（adaptive concurrency，Phase 8）
- ❌ 连接池健康度告警（Phase 8）

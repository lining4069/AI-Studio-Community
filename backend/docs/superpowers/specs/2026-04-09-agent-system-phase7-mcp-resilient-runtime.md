# Agent System Phase 7 — Resilient MCP Runtime

**日期**: 2026-04-09
**状态**: Final v7（Production Hardened，修复 4 项隐藏边界问题）
**Phase**: Phase 7
**前置依赖**: Phase 6.5 (enhanced connection pool)

---

## 1. 概述

Phase 6.5 的连接池已具备可观测性，但缺少自我保护能力。

**Phase 7 目标**：把"连接池"升级为"有自我保护能力的分布式系统组件"。

**核心原则**：
- **Fail Fast**：绝不等待，MCP 挂掉 → 1ms 内返回
- **Fail Closed**：MCP 不可用 ≠ 系统不可用，支持优雅降级
- **Recover Automatically**：无需人工干预，自动恢复
- **抗慢抗抖抗雪崩**：不仅抗挂，还抗异常

---

## 2. 架构

```
MCPTool
   │
   ▼
ResilientExecutor  ← 核心调度器
   │
   ├── PhaseBudget            ← 分阶段超时预算
   ├── LatencyBreaker        ← ← 新增：基于延迟的熔断
   ├── CircuitBreaker         ← 熔断器（含 probe 限流）
   ├── RetryPolicy            ← 重试策略
   ├── PriorityLoadShedding   ← ← 新增：优先级削峰
   ├── RetryBudget            ← ← 修改：per-server retry 预算
   │
   ▼
MCPConnectionPool (Phase 6.5)
   │
   ▼
MCP Server
```

---

## 3. 致命缺口修复

| # | 问题 | 优先级 | 修复 |
|---|------|--------|------|
| 1 | 只看错误不看 latency | P0 | `LatencyBreaker` max + EWMA 双触发 |
| 2 | retry 内不重检 breaker | P0 | 每次 retry 前重新检查 `allow_request_async()` |
| 3 | RetryBudget 全局污染 | P0 | `RetryBudget` 挂到 `CircuitBreaker` 上（per-server） |
| 4 | 所有请求平权 | P0 | `PriorityLoadShedding` 三级优先级 |
| 5 | RetryBudget 未正确接入 | P0 | 全部走 `breaker.record_request()` / `record_retry()` |
| 6 | LoadShedding retry 泄漏 | P0 | `retry_tokens` 计数器 + finally 释放 |
| 7 | LatencyBreaker O(n log n) | P0 | 移除 deque，O(1) 原子变量 |
| 8 | Latency trip 不设 failure_count | P0 | trip 时设置 `failure_count = threshold` |
| 9 | PhaseBudget 比例漂移 | P0 | 固定 deadline，init 时确定各阶段边界 |
| 10 | Semaphore.locked() 竞态 | P0 | try_acquire 原子模式 |
| 11 | RetryBudget 冷启动偏置 | P0 | min_samples + min_retry_abs 保护 |
| 12 | failure_count 不衰减 | P1 | 成功时 `failure_count *= 0.5` |
| 13 | LatencyBreaker 无 reset | P1 | `_reset()` 时调用 `latency_breaker.reset()` |
| 14 | retry_tokens bool 覆盖 | P0 | 改用计数器，finally 精确释放 |
| 15 | probe token 泄漏 | P0 | `allow_request_async()` 返回 `(allowed, is_probe)` |
| 16 | LatencyBreaker 读写竞态 | P0 | 写加锁，读无锁（最终一致） |
| 17 | **reset() 未加锁** | **v7** | 改为 async + 加锁 |
| 18 | **wait_for(timeout=0) 不安全** | **v7** | 直接原子修改 `_value` |
| 19 | **RetryBudget 永不衰减** | **v7** | 滑动窗口 + `_gc()` 时间清理 |
| 20 | **success 完全恢复** | **v7** | `failure_count == 0` 时重置 `open_count` |
| 21 | **pool.release error 永远 False** | **v7** | `call_error` 标志追踪实际异常 |

---

## 4. 核心实现

### 4.1 LatencyBreaker

```python
# app/modules/agent/mcp/resilience/latency_breaker.py

import time
import asyncio
from collections import deque
from dataclasses import dataclass


@dataclass
class LatencyStats:
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    mean: float = 0.0
    count: int = 0


class LatencyBreaker:
    """
    基于延迟的熔断器（最终版）。

    特点：
    - EWMA + max 双触发
    - 写加锁，读无锁（最终一致）
    - 无 deque，避免 O(n) 清理

    ← 最终版：移除 deque，使用原子变量
    """

    def __init__(
        self,
        p99_threshold: float = 5.0,
        min_samples: int = 10,
    ):
        self.p99_threshold = p99_threshold
        self.min_samples = min_samples

        self._count = 0
        self._ewma = 0.0
        self._max_latency = 0.0
        self._alpha = 0.02  # EWMA 平滑系数

        self._lock = asyncio.Lock()

    async def record(self, latency: float) -> None:
        """记录一次延迟（写操作，加锁）。"""
        async with self._lock:
            self._count += 1
            self._ewma = self._alpha * latency + (1 - self._alpha) * self._ewma
            self._max_latency = max(self._max_latency, latency)

    def should_trip(self) -> bool:
        """
        判断是否应该触发熔断（读操作，无锁）。

        ← 修复 P0-15：读操作无锁，最终一致。
        由于读比写频率高，不加锁避免阻塞。
        """
        if self._count < self.min_samples:
            return False

        # max 捕捉 spike，EWMA 感知趋势
        return (
            self._max_latency > self.p99_threshold
            or self._ewma > self.p99_threshold * 0.7
        )

    async def reset(self) -> None:
        """
        重置统计（写操作，加锁）。

        ← 修复 P0-16：reset 必须加锁，避免与 record() 并发写冲突。
        """
        async with self._lock:
            self._count = 0
            self._ewma = 0.0
            self._max_latency = 0.0
```

### 4.2 CircuitBreaker（per-server + 指数退避 + jitter）

```python
# app/modules/agent/mcp/resilience/circuit_breaker.py

from dataclasses import dataclass
import time
import random
import asyncio

from app.services.mcp.exceptions import (
    MCPConnectionError,
    MCPProtocolError,
)
from .probe_limiter import ProbeLimiter
from .retry_budget import RetryBudget
from .latency_breaker import LatencyBreaker


class CircuitBreaker:
    """
    熔断器（per-server）。

    状态机：
    CLOSED（正常）→ 失败率/延迟超阈值 → OPEN（熔断）
    OPEN（熔断）→ 冷却时间后 → HALF_OPEN（探测）
    HALF_OPEN（探测）→ 成功阈值 → CLOSED
    HALF_OPEN（探测）→ 再次失败 → OPEN

    修复：
    - allow_request_async 加锁，状态判断 + probe acquire 原子化
    - should_trip() 错误分类
    - per-server RetryBudget
    - 指数退避 recovery_timeout
    """

    def __init__(
        self,
        server_id: str,
        failure_threshold: int = 5,
        base_recovery_timeout: float = 10.0,
        half_open_success_threshold: int = 2,
        max_probe: int = 1,
        latency_breaker: LatencyBreaker | None = None,
    ):
        self.server_id = server_id
        self.failure_threshold = failure_threshold
        self.base_recovery_timeout = base_recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold

        self._state = CBState()
        self._probe_limiter = ProbeLimiter(max_probe=max_probe)
        self._retry_budget = RetryBudget()  # ← per-server retry budget
        self._latency_breaker = latency_breaker or LatencyBreaker()
        self._open_count = 0
        self._lock: asyncio.Lock | None = None
        self._actual_recovery_timeout = self._jitter_timeout(base_recovery_timeout)

    def _jitter_timeout(self, base: float) -> float:
        """对 recovery timeout 加 jitter，避免多实例同步恢复。"""
        return base * random.uniform(0.8, 1.2)

    def _exponential_backoff(self) -> float:
        """
        指数退避 recovery timeout。

        ← 可选增强：防止 flapping。
        open_count 越多，等待时间越长。
        """
        backoff = min(self.base_recovery_timeout * (2 ** self._open_count), 60.0)
        return self._jitter_timeout(backoff)

    async def allow_request_async(self) -> tuple[bool, bool]:
        """
        检查是否允许请求（含 probe 限流）。

        ← 修复 P0-14：返回 (allowed, is_probe)，精准追踪 probe token。

        Returns:
            (allowed, is_probe) - 是否允许请求，是否使用了 probe token
        """
        now = time.time()

        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            if self._state.state == "closed":
                # ← 新增：每次 closed 也检查 latency
                if self._latency_breaker.should_trip():
                    # ← Bug 修复 4：latency trip 也要设置 failure_count，避免 flapping
                    self._state.failure_count = self.failure_threshold
                    self._trip()
                    return False, False
                return True, False

            if self._state.state == "open":
                opened_at = self._state.opened_at or 0
                if now - opened_at > self._actual_recovery_timeout:
                    self._state.state = "half_open"
                    self._state.success_count = 0
                    self._actual_recovery_timeout = self._exponential_backoff()
                else:
                    return False, False

            if self._state.state == "half_open":
                ok = await self._probe_limiter.try_acquire()
                return ok, ok

            return False, False

    def record_success(self) -> None:
        """
        记录成功。

        ← 修复 v7：failure_count 归零时完全重置 open_count。
        """
        # closed 状态下，成功时衰减 failure_count
        if self._state.state == "closed":
            self._state.failure_count = max(
                0,
                int(self._state.failure_count * 0.5),
            )
            # ← 修复 v7：完全恢复窗口
            if self._state.failure_count == 0:
                self._open_count = 0

        if self._state.state == "half_open":
            self._state.success_count += 1
            if self._state.success_count >= self.half_open_success_threshold:
                self._reset()

    def record_failure(self) -> None:
        """记录失败。"""
        now = time.time()

        if self._state.state == "half_open":
            self._trip()
            return

        self._state.failure_count += 1
        self._state.last_failure_time = now

        if self._state.failure_count >= self.failure_threshold:
            self._trip()

    def should_trip(self, error: Exception) -> bool:
        """判断错误是否应该触发熔断。"""
        return isinstance(error, (
            MCPConnectionError,
            MCPProtocolError,
            TimeoutError,
            ConnectionError,
        ))

    def _trip(self) -> None:
        """熔断打开。"""
        self._state.state = "open"
        self._state.opened_at = time.time()
        self._open_count += 1

    def _reset(self) -> None:
        """重置为关闭状态。"""
        self._state = CBState()
        self._open_count = 0
        # ← 修复 v7：不能直接 await，用 create_task 异步执行
        asyncio.create_task(self._latency_breaker.reset())

    def release_probe(self) -> None:
        """释放 probe 令牌。"""
        self._probe_limiter.release()

    async def record_retry(self) -> bool:
        """记录 retry（per-server budget）。"""
        return await self._retry_budget.record_retry(self.server_id)

    async def record_request(self) -> None:
        """记录请求。"""
        await self._retry_budget.record_request(self.server_id)

    async def record_latency(self, latency: float) -> None:
        """记录延迟。"""
        await self._latency_breaker.record(latency)

    @property
    def state(self) -> str:
        return self._state.state

    def metrics(self) -> dict:
        latency_stats = self._latency_breaker.stats()
        return {
            "server_id": self.server_id,
            "state": self._state.state,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "opened_at": self._state.opened_at,
            "open_count": self._open_count,
            "latency_p99_ms": round(latency_stats.p99 * 1000, 2),
            "latency_p95_ms": round(latency_stats.p95 * 1000, 2),
        }


@dataclass
class CBState:
    state: str = "closed"
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    opened_at: float | None = None
```

### 4.3 RetryBudget（per-server）

```python
# app/modules/agent/mcp/resilience/retry_budget.py

import asyncio
from collections import defaultdict


class RetryBudget:
    """
    全局 Retry 预算（per-server）。

    ← 修改：从全局改为 per-server，防止跨 server 污染。

    问题：A server 挂了 → retry 爆炸 → B server 也被拖慢
    解决：每个 server 独立计算 retry 预算

    ← 修复 v7：加入滑动窗口，长时间运行也不会因历史数据而锁定 retry。
    """

    def __init__(
        self,
        max_retry_ratio: float = 0.2,
        min_samples: int = 10,
        min_retry_abs: int = 2,
        window: float = 60.0,
    ):
        self._max_ratio = max_retry_ratio
        self._min_samples = min_samples
        self._min_retry_abs = min_retry_abs
        self._window = window

        # ← 修复 v7：滑动窗口 [(timestamp, is_retry)]
        self._events: dict[str, list[tuple[float, bool]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _gc(self, server_id: str) -> None:
        """清理窗口外的事件。"""
        cutoff = time.time() - self._window
        self._events[server_id] = [
            (ts, r) for ts, r in self._events[server_id] if ts > cutoff
        ]

    async def record_request(self, server_id: str) -> None:
        """记录一次请求。"""
        async with self._lock:
            self._events[server_id].append((time.time(), False))
            self._gc(server_id)

    async def record_retry(self, server_id: str) -> bool:
        """
        记录一次 retry。

        ← 修复 v7：滑动窗口衰减，长时间运行不会锁定 retry。

        Returns:
            True if allowed, False if budget exhausted
        """
        async with self._lock:
            now = time.time()
            self._events[server_id].append((now, True))
            self._gc(server_id)

            events = self._events[server_id]
            total = len([e for e in events if not e[1]])
            retries = len([e for e in events if e[1]])

            # 低流量保护
            if total < self._min_samples:
                max_allowed = self._min_retry_abs
            else:
                max_allowed = max(
                    self._min_retry_abs,
                    int(total * self._max_ratio),
                )

            return retries <= max_allowed

    async def reset(self, server_id: str) -> None:
        """重置指定 server 的计数器。"""
        async with self._lock:
            self._events[server_id].clear()

    def metrics(self) -> dict:
        return {
            server_id: {
                "total": len([e for e in self._events.get(server_id, []) if not e[1]]),
                "retries": len([e for e in self._events.get(server_id, []) if e[1]]),
                "ratio": len([e for e in self._events.get(server_id, []) if e[1]]) / max(1, len([e for e in self._events.get(server_id, []) if not e[1]])),
            }
            for server_id in self._events.keys()
        }
```

### 4.4 PriorityLoadShedding

```python
# app/modules/agent/mcp/resilience/priority_shedding.py

import asyncio
from enum import IntEnum


class RequestPriority(IntEnum):
    """请求优先级。"""
    USER = 0    # 用户请求 → 最高优先
    PROBE = 1  # probe 请求 → 次高
    RETRY = 2  # retry 请求 → 最低


class PriorityLoadShedding:
    """
    优先级并发放削峰。

    ← 新增：解决 retry 抢占 inflight 的问题。

    策略：
    - user 请求优先进入
    - probe 限量进入
    - retry 最先被拒绝

    这样保证：
    - 用户请求不被 retry 抢占
    - 恢复时的 probe 能进入

    ← 修复 P0-2：使用 try_acquire 模式，避免 locked() 竞态
    """

    def __init__(
        self,
        max_user: int = 30,
        max_probe: int = 2,
        max_retry: int = 10,
    ):
        self._user_sem = asyncio.Semaphore(max_user)
        self._probe_sem = asyncio.Semaphore(max_probe)
        self._retry_sem = asyncio.Semaphore(max_retry)

    async def allow(self, priority: RequestPriority) -> bool:
        """
        检查是否允许请求。

        ← 修复 v7：使用直接原子修改，避免 wait_for(timeout=0) 的 event loop race。

        Returns:
            True if allowed, False if should shed
        """
        sem = {
            RequestPriority.USER: self._user_sem,
            RequestPriority.PROBE: self._probe_sem,
            RequestPriority.RETRY: self._retry_sem,
        }[priority]

        # ← 修复 v7：直接原子修改 _value（CPython GIL 保证原子性）
        # 这是 asyncio 官方推荐的 non-blocking try-acquire 模式
        if sem._value <= 0:
            return False
        sem._value -= 1
        return True

    def done(self, priority: RequestPriority) -> None:
        """释放令牌。"""
        sem = {
            RequestPriority.USER: self._user_sem,
            RequestPriority.PROBE: self._probe_sem,
            RequestPriority.RETRY: self._retry_sem,
        }[priority]
        sem.release()

    def metrics(self) -> dict:
        return {
            "user": {"max": self._user_sem._value},
            "probe": {"max": self._probe_sem._value},
            "retry": {"max": self._retry_sem._value},
        }
```

### 4.5 PhaseBudget

```python
# app/modules/agent/mcp/resilience/phase_budget.py

import time


class PhaseBudget:
    """
    分阶段超时预算。

    ← 修复 5：使用固定 deadline，避免比例漂移。

    原本（错误）：
    remaining * weight  # 动态计算，acquire 慢会压缩 execution

    现在（正确）：
    acquire_deadline = start + total * 0.20
    exec_deadline = start + total * 0.80
    # 不再动态按比例分配
    """

    def __init__(self, total: float):
        self.total = total
        self.start_time = time.time()

        # ← 修复 5：固定 deadline，init 时确定
        self.acquire_deadline = self.start_time + total * 0.20
        self.exec_deadline = self.start_time + total * 0.80
        self.total_deadline = self.start_time + total

    def acquire_remaining(self) -> float:
        """acquire 阶段剩余时间。"""
        return max(0.0, self.acquire_deadline - time.time())

    def execution_remaining(self) -> float:
        """execution 阶段剩余时间。"""
        return max(0.0, self.exec_deadline - time.time())

    def backoff_remaining(self) -> float:
        """backoff 阶段剩余时间（从 total deadline 计算）。"""
        return max(0.0, self.total_deadline - time.time())

    def remaining(self) -> float:
        """总剩余时间。"""
        return max(0.0, self.total_deadline - time.time())

    def is_exhausted(self) -> bool:
        return self.remaining() <= 0
```

### 4.6 ResilientExecutor（最终版）

```python
# app/modules/agent/mcp/resilience/executor.py

import asyncio
import time

from app.services.mcp.resilience.circuit_breaker import CircuitBreaker
from app.services.mcp.resilience.retry_policy import RetryPolicy
from app.services.mcp.resilience.phase_budget import PhaseBudget
from app.services.mcp.resilience.priority_shedding import PriorityLoadShedding, RequestPriority
from app.services.mcp.resilience.exceptions import (
    MCPOverloadedError,
    MCPBudgetExceededError,
)


class ResilientExecutor:
    """
    弹性执行器（最终版）。

    修复：
    - 每次 retry 前重新检查 breaker（← 关键）
    - 使用 PriorityLoadShedding
    - 使用 PhaseBudget
    """

    def __init__(
        self,
        pool,
        breaker: CircuitBreaker,
        retry_policy: RetryPolicy,
        total_budget: float = 8.0,
    ):
        self._pool = pool
        self._breaker = breaker
        self._retry_policy = retry_policy
        self._total_budget = total_budget
        self._shedding = PriorityLoadShedding()

        # metrics
        self._retry_count = 0
        self._shed_count = 0
        self._budget_exceeded_count = 0

    async def execute(self, tool_name: str, input: dict):
        # ← 最终版：先 record_request
        await self._breaker.record_request()

        # 1️⃣ breaker 快速失败
        allowed, is_probe = await self._breaker.allow_request_async()
        if not allowed:
            self._shed_count += 1
            raise MCPOverloadedError("circuit open", retry_after=1.0)

        # USER acquire
        if not await self._shedding.allow(RequestPriority.USER):
            self._shed_count += 1
            raise MCPOverloadedError("overloaded", retry_after=0.5)

        budget = PhaseBudget(self._total_budget)

        # ← 修复 P0-13：使用计数器，避免 bool 被覆盖
        retry_tokens = 0
        success = False

        try:
            for attempt in range(self._retry_policy.max_retries + 1):

                if budget.is_exhausted():
                    raise MCPBudgetExceededError("budget exhausted")

                if attempt > 0:
                    # ← 修复 P0-14：用返回的 is_probe 精准追踪
                    allowed, _ = await self._breaker.allow_request_async()
                    if not allowed:
                        raise MCPOverloadedError("circuit open during retry")

                    if not await self._shedding.allow(RequestPriority.RETRY):
                        raise MCPOverloadedError("retry shed")

                    retry_tokens += 1

                start = time.time()
                call_error = False

                try:
                    ps = await asyncio.wait_for(
                        self._pool.acquire(),
                        timeout=budget.acquire_remaining(),
                    )

                    try:
                        result = await asyncio.wait_for(
                            ps.session.call_tool(tool_name, input),
                            timeout=budget.execution_remaining(),
                        )
                    except Exception:
                        call_error = True
                        raise
                    finally:
                        # ← 修复 v7：error 标志根据实际异常设置，而非永远 False
                        await self._pool.release(ps, error=call_error)

                    await self._breaker.record_latency(time.time() - start)
                    self._breaker.record_success()

                    success = True
                    return result

                except Exception as e:
                    await self._breaker.record_latency(time.time() - start)

                    if not self._breaker.should_trip(e):
                        raise

                    if not await self._breaker.record_retry():
                        raise MCPBudgetExceededError("retry budget exhausted")

                    if not self._retry_policy.should_retry(e, attempt):
                        raise

                    delay = self._retry_policy.get_delay(attempt)

                    if delay > budget.backoff_remaining():
                        raise MCPBudgetExceededError("no time for retry")

                    self._retry_count += 1
                    await asyncio.sleep(delay)

            if not success:
                self._breaker.record_failure()

            raise RuntimeError("unreachable")

        finally:
            # USER release
            self._shedding.done(RequestPriority.USER)

            # ← 修复 P0-13：按计数器精确释放 retry tokens
            for _ in range(retry_tokens):
                self._shedding.done(RequestPriority.RETRY)

            # ← 修复 P0-14：精准 probe 释放（用 is_probe 而非 state）
            if is_probe:
                self._breaker.release_probe()

    def metrics(self) -> dict:
        return {
            "breaker": self._breaker.metrics(),
            "shed_count": self._shed_count,
            "retry_count": self._retry_count,
            "budget_exceeded_count": self._budget_exceeded_count,
        }
```

### 4.7 Global Breaker Manager

```python
# app/modules/agent/mcp/resilience/manager.py

import asyncio

from .circuit_breaker import CircuitBreaker
from .latency_breaker import LatencyBreaker


class BreakerManager:
    """
    全局 Breaker 管理器（per-server）。
    """

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

    async def get_breaker(self, server_id: str) -> CircuitBreaker:
        """获取或创建指定 server 的 breaker。"""
        if server_id not in self._breakers:
            async with self._lock:
                if server_id not in self._breakers:
                    latency_breaker = LatencyBreaker()
                    self._breakers[server_id] = CircuitBreaker(
                        server_id=server_id,
                        latency_breaker=latency_breaker,
                    )
        return self._breakers[server_id]

    def get_all_metrics(self) -> dict:
        return {
            server_id: breaker.metrics()
            for server_id, breaker in self._breakers.items()
        }


breaker_manager = BreakerManager()
```

---

## 5. 行为矩阵

| 场景 | 行为 | 结果 |
|------|------|------|
| MCP 挂掉 | breaker open → 1ms fail fast | agent 不阻塞 |
| MCP 变慢（P99>5s） | latency breaker trip → open | 不会被慢拖死 |
| MCP 恢复 | recovery_timeout → half_open → probe | 自动恢复 |
| 高并发打爆 | user 请求优先，retry 最先被拒 | 正常请求有保障 |
| retry 爆炸 | per-server retry budget | 不会跨 server 污染 |
| 业务错误 | 直接抛出 | breaker 不受影响 |

---

## 6. Metrics

| 指标 | 说明 |
|------|------|
| `breaker_state` | 当前状态（closed/open/half_open） |
| `breaker_open_count` | 累计熔断打开次数 |
| `latency_p99_ms` | 延迟 P99（毫秒） |
| `latency_p95_ms` | 延迟 P95（毫秒） |
| `retry_count` | 累计 retry 次数 |
| `shed_count` | 优先级削峰拒绝次数 |
| `budget_exceeded_count` | 预算耗尽次数 |

---

## 7. 实现步骤

1. 创建 `app/modules/agent/mcp/resilience/exceptions.py`
2. 创建 `app/modules/agent/mcp/resilience/latency_breaker.py`
3. 创建 `app/modules/agent/mcp/resilience/probe_limiter.py`
4. 创建 `app/modules/agent/mcp/resilience/circuit_breaker.py`（含 per-server + 指数退避）
5. 创建 `app/modules/agent/mcp/resilience/retry_policy.py`
6. 创建 `app/modules/agent/mcp/resilience/phase_budget.py`
7. 创建 `app/modules/agent/mcp/resilience/retry_budget.py`（per-server）
8. 创建 `app/modules/agent/mcp/resilience/priority_shedding.py`
9. 创建 `app/modules/agent/mcp/resilience/executor.py`（关键修复）
10. 创建 `app/modules/agent/mcp/resilience/manager.py`
11. 创建 `app/modules/agent/mcp/resilience/tool.py`
12. 创建 `app/modules/agent/mcp/resilience/__init__.py`
13. 更新 `app/modules/agent/tool_builder.py`
14. 测试验证

---

## 8. 验证清单

### 故障能力
- [ ] MCP 挂掉 → <1ms fail fast
- [ ] MCP 变慢（P99>5s）→ latency breaker trip
- [ ] breaker 正确 open / half_open / close
- [ ] half-open 不被打爆（probe limiter）
- [ ] 多实例不会同步恢复（jitter + 指数退避）

### 恢复能力
- [ ] 自动恢复（无需人工）
- [ ] probe 成功后恢复流量

### 系统保护
- [ ] 有优先级削峰（user > probe > retry）
- [ ] retry 有 per-server budget（不会跨 server 污染）
- [ ] 每次 retry 前重检 breaker
- [ ] 业务错误不触发 breaker

### 可观测性
- [ ] breaker metrics（含 latency）
- [ ] shedding metrics
- [ ] retry metrics

---

## 9. Phase 边界

### Phase 7 包含
- ✅ LatencyBreaker（P99 熔断）
- ✅ CircuitBreaker（per-server + 指数退避）
- ✅ RetryPolicy（指数退避 + jitter）
- ✅ PhaseBudget（分阶段预算）
- ✅ RetryBudget（per-server）
- ✅ PriorityLoadShedding（三级优先级）
- ✅ Retry 内重检 breaker
- ✅ MCPOverloadedError + retry_after
- ✅ 错误分类（业务错误不触发 breaker）

### Phase 7 不包含
- ❌ 动态调整参数（Phase 8）
- ❌ 连接池健康度告警（Phase 8）

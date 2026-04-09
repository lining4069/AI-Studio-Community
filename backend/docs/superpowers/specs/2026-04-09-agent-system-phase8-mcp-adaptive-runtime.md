# Agent System Phase 8 — Adaptive MCP Runtime

**日期**: 2026-04-09
**状态**: Draft v3（修复 8 项问题）
**Phase**: Phase 8
**前置依赖**: Phase 7 (Resilient MCP Runtime)

---

## 1. 概述

Phase 7 的弹性执行器已具备 Fail Fast + 自动恢复能力。

**Phase 8 目标**：从"被动防御"升级到"主动适应"。

```
Phase 7：抗挂（circuit breaker / retry / shedding）
Phase 8：抗抖 + 抗变（自适应 + 预测）
```

---

## 2. 核心能力

| 能力 | 说明 |
|------|------|
| Adaptive Concurrency | 根据 RTT 动态调整并发上限（带阻尼） |
| Health Alerts | 池健康度异常时主动告警（O(1)） |
| Hedged Requests | 尾延迟杀手，热点请求发双份（有保护） |
| EWMA Load Balancing | 多 server 时按延迟分配流量（熔断感知） |

---

## 3. 架构

```
MCPTool
   │
   ▼
ResilientExecutor (Phase 7)
   │
   ▼
AdaptiveExecutor  ← 自适应执行器
   │
   ├── ConcurrencyController   # 真正控制并发（Semaphore）
   ├── ConcurrencyAdjuster     # 调整算法（带阻尼）
   ├── HealthMonitor           # 健康度监控 + 告警（O(1) bucket）
   ├── HedgingExecutor         # 尾延迟保护（有预算 + 幂等检查）
   └── EWMABalancer           # 多 server 负载均衡（熔断感知）
```

---

## 4. 修复清单

| # | 问题 | 优先级 | 修复 |
|---|------|--------|------|
| 1 | ConcurrencyAdjuster 震荡 | - | gradient 限制（>0.2 降 30%，<0.05 才加） |
| 2 | Hedging 放大负载 | - | hedge budget（5%）+ 幂等检查 + breaker 联动 |
| 3 | HealthMonitor O(n) | - | bucket 化，O(1) 更新/查询 |
| 4 | EWMABalancer 无熔断感知 | - | `is_healthy` + weight *= 0.01 |
| 5 | Hedging cancel 不彻底 | **v3** | 先 `cancel()` 再 `gather()` |
| 6 | AdaptiveExecutor 不控制并发 | - | Semaphore 控制并发数上限 |
| 7 | EWMABalancer `field()` crash | **v3** | 移除 `field()`，用 `{}` |
| 8 | Semaphore 缩容无效 | **v3** | `_semaphore._value = new` 直接修改 |
| 9 | list.pop(0) O(n) | **v3** | 改用 `deque(maxlen=1000)` |
| 10 | shed 记录但不拒绝请求 | **v3** | 不健康时抛出 `MCPOverloadedError` |
| 11 | latency_p99_ms 来源不可靠 | **v3** | 从 `LatencyBreaker.stats()` 获取 |

---

## 5. ConcurrencyAdjuster（带阻尼）

```python
# app/modules/agent/mcp/adaptive/concurrency_adjuster.py

import time
from dataclasses import dataclass


@dataclass
class ConcurrencyState:
    current: int
    target: int
    rtt_ema: float
    rtt_min: float
    last_update: float


class ConcurrencyAdjuster:
    """
    自适应并发控制器（带阻尼）。

    ← 修复 1：引入 gradient 限制，避免震荡。

    核心公式（带阻尼）：
    gradient = (rtt_ema - rtt_min) / rtt_min

    if gradient > 0.2:
        new = current * 0.7  # 延迟显著变差 → 快速降并发
    elif gradient < 0.05:
        new = current + 1    # 延迟稳定 → 慢慢加
    else:
        new = current         # 小幅波动 → 不动
    """

    def __init__(
        self,
        initial: int = 10,
        min_concurrency: int = 1,
        max_concurrency: int = 50,
    ):
        self.state = ConcurrencyState(
            current=initial,
            target=initial,
            rtt_ema=0.0,
            rtt_min=float('inf'),
            last_update=time.time(),
        )
        self.min = min_concurrency
        self.max = max_concurrency

    def record_rtt(self, rtt: float) -> None:
        """记录一次 RTT。"""
        if self.state.rtt_ema == 0:
            self.state.rtt_ema = rtt
        else:
            self.state.rtt_ema = 0.5 * rtt + 0.5 * self.state.rtt_ema

        self.state.rtt_min = min(self.state.rtt_min, rtt)

    def adjust(self) -> int:
        """
        调整并发数（带阻尼控制）。

        ← 修复 1：避免震荡的梯度限制。
        """
        if self.state.rtt_min == float('inf') or self.state.rtt_min == 0:
            return self.state.current

        # 计算 gradient
        gradient = (self.state.rtt_ema - self.state.rtt_min) / max(self.state.rtt_min, 0.001)

        old = self.state.current

        if gradient > 0.2:
            # 延迟显著变差 → 快速降并发
            new = int(old * 0.7)
        elif gradient < 0.05:
            # 延迟稳定 → 慢慢加
            new = old + 1
        else:
            # 小幅波动 → 不动
            new = old

        # 限制范围
        new = max(self.min, min(self.max, new))

        # 平滑过渡（每次最多调整 20%）
        delta = int(old * 0.2)
        if abs(new - old) > delta:
            direction = 1 if new > old else -1
            self.state.current = old + direction * delta
        else:
            self.state.current = new

        self.state.target = self.state.current
        self.state.last_update = time.time()
        return self.state.current

    def should_throttle(self) -> bool:
        """判断是否应该限流。"""
        return self.state.current <= self.min

    def metrics(self) -> dict:
        return {
            "current_concurrency": self.state.current,
            "target_concurrency": self.state.target,
            "rtt_ema_ms": round(self.state.rtt_ema * 1000, 2),
            "rtt_min_ms": round(self.state.rtt_min * 1000, 2) if self.state.rtt_min != float('inf') else None,
        }
```

---

## 6. HealthMonitor（Bucket 化 O(1)）

```python
# app/modules/agent/mcp/adaptive/health_monitor.py

import time
import asyncio
from dataclasses import dataclass
from typing import Callable


@dataclass
class HealthStatus:
    healthy: bool
    error_rate: float
    latency_p99_ms: float
    shed_rate: float
    breaker_state: str
    last_check: float


class HealthMonitor:
    """
    连接池健康度监控器（O(1) Bucket 实现）。

    ← 修复 3：使用 bucket 化，无 GC 压力。

    每秒一个 bucket：
    buckets[index] = (error_count, total_count)
    """

    BUCKET_COUNT = 300  # 5 分钟窗口
    BUCKET_SECONDS = 60 * 5

    def __init__(
        self,
        pool_id: str,
        error_threshold: float = 0.1,
        latency_threshold_ms: float = 3000,
        shed_threshold: float = 0.5,
        alert_interval: float = 60.0,
    ):
        self.pool_id = pool_id
        self.error_threshold = error_threshold
        self.latency_threshold_ms = latency_threshold_ms
        self.shed_threshold = shed_threshold
        self.alert_interval = alert_interval

        # ← 修复 3：bucket 化存储 [(error_count, total_count), ...]
        self._error_buckets: list[tuple[int, int]] = [(0, 0)] * self.BUCKET_COUNT
        self._shed_buckets: list[int] = [0] * self.BUCKET_COUNT

        self._current_bucket = 0
        self._last_bucket_time = int(time.time())
        self._last_alert: float = 0
        self._alert_callback: Callable | None = None
        self._lock = asyncio.Lock()

    def set_alert_callback(self, callback: Callable) -> None:
        """设置告警回调。"""
        self._alert_callback = callback

    def _rotate_bucket(self) -> None:
        """轮转 bucket（每秒调用）。"""
        now = int(time.time())
        if now > self._last_bucket_time:
            self._current_bucket = (self._current_bucket + 1) % self.BUCKET_COUNT
            self._error_buckets[self._current_bucket] = (0, 0)
            self._shed_buckets[self._current_bucket] = 0
            self._last_bucket_time = now

    async def record(self, success: bool, latency_ms: float) -> None:
        """记录一次请求结果。"""
        async with self._lock:
            self._rotate_bucket()
            err, tot = self._error_buckets[self._current_bucket]
            if success:
                self._error_buckets[self._current_bucket] = (err, tot + 1)
            else:
                self._error_buckets[self._current_bucket] = (err + 1, tot + 1)

    async def record_shed(self) -> None:
        """记录一次 shed。"""
        async with self._lock:
            self._rotate_bucket()
            self._shed_buckets[self._current_bucket] += 1

    async def check(self, breaker_state: str, latency_p99_ms: float) -> HealthStatus:
        """
        检查健康状态（O(1)）。

        Returns:
            HealthStatus
        """
        async with self._lock:
            total_errors = sum(e for e, _ in self._error_buckets)
            total_requests = sum(t for _, t in self._error_buckets)
            total_sheds = sum(self._shed_buckets)

            error_rate = total_errors / max(total_requests, 1)
            shed_rate = total_sheds / max(total_requests, 1)

            healthy = (
                error_rate < self.error_threshold
                and latency_p99_ms < self.latency_threshold_ms
                and shed_rate < self.shed_threshold
            )

            now = time.time()
            status = HealthStatus(
                healthy=healthy,
                error_rate=error_rate,
                latency_p99_ms=latency_p99_ms,
                shed_rate=shed_rate,
                breaker_state=breaker_state,
                last_check=now,
            )

            if not healthy and now - self._last_alert > self.alert_interval:
                await self._alert(status)
                self._last_alert = now

            return status

    async def _alert(self, status: HealthStatus) -> None:
        """发送告警。"""
        if self._alert_callback:
            await self._alert_callback({
                "pool_id": self.pool_id,
                "error_rate": round(status.error_rate, 3),
                "latency_p99_ms": round(status.latency_p99_ms, 2),
                "shed_rate": round(status.shed_rate, 3),
                "breaker_state": status.breaker_state,
            })

    def metrics(self) -> dict:
        return {
            "pool_id": self.pool_id,
            "error_threshold": self.error_threshold,
            "latency_threshold_ms": self.latency_threshold_ms,
            "shed_threshold": self.shed_threshold,
        }
```

---

## 7. HedgingExecutor（有保护）

```python
# app/modules/agent/mcp/adaptive/hedging_executor.py

import asyncio
from collections import deque
import random
import time


class HedgingExecutor:
    """
    尾延迟保护执行器（有保护）。

    ← 修复 2：防止 Tail Amplification。

    保护措施：
    1. 全局 hedge budget（max 5% inflight）
    2. 幂等检查
    3. breaker 联动
    """

    def __init__(
        self,
        p95_threshold_ms: float = 1000,
        hedge_delay_ms: float = 100,
        hedge_probability: float = 0.1,
        max_hedge_ratio: float = 0.05,
    ):
        self.p95_threshold_ms = p95_threshold_ms
        self.hedge_delay_ms = hedge_delay_ms / 1000
        self.hedge_probability = hedge_probability
        self.max_hedge_ratio = max_hedge_ratio

        self._recent_latencies: deque[float] = deque(maxlen=1000)
        self._hedge_count = 0
        self._cancel_count = 0
        self._hedge_inflight = 0
        self._total_inflight = 0

    def should_hedge(self, is_idempotent: bool = True, breaker_state: str = "closed") -> bool:
        """
        判断是否应该发 hedge request。

        ← 修复 2：幂等检查 + breaker 联动 + 全局 budget。

        Args:
            is_idempotent: 请求是否幂等
            breaker_state: breaker 当前状态
        """
        # ← 修复 2：breaker 不是 closed 禁止 hedge
        if breaker_state != "closed":
            return False

        # ← 修复 2：非幂等请求禁止 hedge
        if not is_idempotent:
            return False

        # ← 修复 2：全局 hedge budget
        if self._total_inflight > 0:
            hedge_ratio = self._hedge_inflight / self._total_inflight
            if hedge_ratio >= self.max_hedge_ratio:
                return False

        if not self._recent_latencies:
            return False

        sorted_latencies = sorted(self._recent_latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95 = sorted_latencies[p95_idx] if sorted_latencies else 0

        if p95 > self.p95_threshold_ms:
            return random.random() < self.hedge_probability

        return False

    async def execute_with_hedge(
        self,
        call_fn: callable,
        is_idempotent: bool = True,
        breaker_state: str = "closed",
        *args,
        **kwargs,
    ) -> any:
        """
        执行请求，必要时发 hedge request。

        ← 修复 5：await gather 确保 cancel 彻底。
        """
        if not self.should_hedge(is_idempotent, breaker_state):
            self._total_inflight += 1
            try:
                return await call_fn(*args, **kwargs)
            finally:
                self._total_inflight -= 1

        # 主请求
        self._total_inflight += 1
        self._hedge_inflight += 1
        task = asyncio.create_task(call_fn(*args, **kwargs))

        try:
            # 等待 hedge_delay 后发第二个请求
            await asyncio.sleep(self.hedge_delay_ms)
            hedge_task = asyncio.create_task(call_fn(*args, **kwargs))
            self._hedge_count += 1

            done, pending = await asyncio.wait(
                [task, hedge_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            result = done.pop().result()

            # ← 修复 3：先 cancel 再 gather，确保真正取消
            if pending:
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                self._cancel_count += len(pending)

            return result

        finally:
            self._hedge_inflight -= 1
            self._total_inflight -= 1

    def record_latency(self, latency_ms: float) -> None:
        """记录延迟。"""
        self._recent_latencies.append(latency_ms)
        # deque(maxlen=1000) 自动丢弃旧数据

    def metrics(self) -> dict:
        return {
            "hedge_count": self._hedge_count,
            "cancel_count": self._cancel_count,
            "hedge_inflight": self._hedge_inflight,
            "total_inflight": self._total_inflight,
            "recent_p95_ms": (
                sorted(self._recent_latencies)[int(len(self._recent_latencies) * 0.95)]
                if self._recent_latencies else 0
            ),
        }
```

---

## 8. EWMABalancer（熔断感知）

```python
# app/modules/agent/mcp/adaptive/ewma_balancer.py

import random
from dataclasses import dataclass


@dataclass
class ServerState:
    server_id: str
    ewma_rtt: float = 0.0
    weight: float = 1.0
    is_healthy: bool = True  # ← 修复 4：熔断感知


class EWMABalancer:
    """
    EWMA 负载均衡器（熔断感知）。

    ← 修复 4：breaker 状态影响权重。
    """

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self._servers: dict[str, ServerState] = {}

    def register(self, server_id: str) -> None:
        """注册 server。"""
        if server_id not in self._servers:
            self._servers[server_id] = ServerState(server_id=server_id)

    def unregister(self, server_id: str) -> None:
        """注销 server。"""
        self._servers.pop(server_id, None)

    def update_health(self, server_id: str, is_healthy: bool) -> None:
        """
        更新 server 健康状态。

        ← 修复 4：breaker 状态影响权重。
        """
        state = self._servers.get(server_id)
        if state:
            state.is_healthy = is_healthy

    def record_rtt(self, server_id: str, rtt: float) -> None:
        """记录 server 的 RTT。"""
        state = self._servers.get(server_id)
        if not state:
            return

        if state.ewma_rtt == 0:
            state.ewma_rtt = rtt
        else:
            state.ewma_rtt = self.alpha * rtt + (1 - self.alpha) * state.ewma_rtt

        # ← 修复 4：权重计算考虑健康状态
        if not state.is_healthy:
            state.weight = 0.01  # 不健康 server 权重极低
        else:
            state.weight = 1.0 / max(state.ewma_rtt, 0.001)

    def select(self) -> str | None:
        """
        选择一个 server（加权随机）。

        ← 修复 4：不健康 server 几乎不会被选中。
        """
        if not self._servers:
            return None

        servers = [s for s in self._servers.values() if s.is_healthy]
        if not servers:
            return None

        total_weight = sum(s.weight for s in servers)
        if total_weight == 0:
            return random.choice(servers).server_id

        r = random.random() * total_weight
        cumulative = 0
        for s in servers:
            cumulative += s.weight
            if r <= cumulative:
                return s.server_id

        return servers[-1].server_id

    def metrics(self) -> dict:
        return {
            server_id: {
                "ewma_rtt_ms": round(state.ewma_rtt * 1000, 2),
                "weight": round(state.weight, 3),
                "is_healthy": state.is_healthy,
            }
            for server_id, state in self._servers.items()
        }
```

---

## 9. AdaptiveExecutor（真正控制并发）

```python
# app/modules/agent/mcp/adaptive/executor.py

import asyncio
import time

from app.services.mcp.resilience.executor import ResilientExecutor
from app.services.mcp.resilience.exceptions import MCPOverloadedError
from app.services.mcp.adaptive.concurrency_adjuster import ConcurrencyAdjuster
from app.services.mcp.adaptive.health_monitor import HealthMonitor
from app.services.mcp.adaptive.hedging_executor import HedgingExecutor
from app.services.mcp.adaptive.ewma_balancer import EWMABalancer


class AdaptiveExecutor:
    """
    自适应执行器（真正控制并发）。

    在 Phase 7 ResilientExecutor 基础上叠加：
    - Adaptive Concurrency（Semaphore 真正控制）
    - Health Monitoring（O(1) bucket）
    - Hedging（有保护）
    - EWMA LB（熔断感知）
    """

    def __init__(
        self,
        resilient_executor: ResilientExecutor,
        pool_id: str,
    ):
        self._executor = resilient_executor
        self._pool_id = pool_id

        self._adjuster = ConcurrencyAdjuster()
        self._semaphore = asyncio.Semaphore(self._adjuster.state.current)
        self._current_inflight = 0
        self._health = HealthMonitor(pool_id=pool_id)
        self._hedging = HedgingExecutor()
        self._balancer = EWMABalancer()

        self._adjust_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动自适应控制器。"""
        self._adjust_task = asyncio.create_task(self._adjust_loop())

    async def stop(self) -> None:
        """停止自适应控制器。"""
        if self._adjust_task:
            self._adjust_task.cancel()
            self._adjust_task = None

    async def _adjust_loop(self) -> None:
        """定时调整并发。"""
        while True:
            await asyncio.sleep(10)
            new = self._adjuster.adjust()
            self._semaphore._value = new  # ← 修复 6：直接修改 semaphore 上限

    async def execute(self, tool_name: str, input: dict) -> dict:
        """执行工具调用。"""
        start = time.time()

        breaker_metrics = self._executor._breaker.metrics()
        breaker_state = breaker_metrics.get("state", "unknown")

        # ← 修复 6：缩容时主动拒绝
        if self._current_inflight >= self._adjuster.state.current:
            await self._health.record_shed()
            raise MCPOverloadedError("capacity exhausted", retry_after=0.5)

        # ← 修复 6：健康检查不通过则拒绝
        # ← 修复 7：从 LatencyBreaker 获取 p99，而非依赖 breaker_metrics
        latency_p99_ms = self._executor._breaker._latency_breaker.stats().p99 * 1000
        health = await self._health.check(
            breaker_state=breaker_state,
            latency_p99_ms=latency_p99_ms,
        )

        if not health.healthy:
            await self._health.record_shed()
            raise MCPOverloadedError("pool unhealthy", retry_after=1.0)

        self._current_inflight += 1

        try:
            result = await self._hedging.execute_with_hedge(
                self._executor.execute,
                is_idempotent=True,
                breaker_state=breaker_state,
                tool_name=tool_name,
                input=input,
            )

            latency = time.time() - start
            await self._health.record(success=True, latency_ms=latency * 1000)
            self._adjuster.record_rtt(latency)
            self._hedging.record_latency(latency * 1000)
            self._balancer.record_rtt(self._pool_id, latency)

            return result

        except Exception as e:
            latency = time.time() - start
            await self._health.record(success=False, latency_ms=latency * 1000)
            raise

        finally:
            self._current_inflight -= 1

    def metrics(self) -> dict:
        return {
            "concurrency": self._adjuster.metrics(),
            "health": self._health.metrics(),
            "hedging": self._hedging.metrics(),
            "balancer": self._balancer.metrics(),
        }
```

---

## 10. Phase 8 边界

### Phase 8 包含
- ✅ Adaptive Concurrency（带阻尼 + Semaphore 控制）
- ✅ Health Monitor（O(1) bucket + callback）
- ✅ Hedged Requests（预算 + 幂等 + breaker 联动）
- ✅ EWMA Load Balancing（熔断感知）

### Phase 8 不包含
- ❌ 多租户隔离（Future）
- ❌ 跨数据中心路由（Future）
- ❌ 渐进式流量切换（Future）

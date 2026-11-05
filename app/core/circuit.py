"""上游调用熔断:失败达阈值断路,冷却后放一个试探(半开)。"""
import time

from app.config import settings


class CircuitOpenError(Exception):
    def __init__(self, name: str):
        super().__init__(f"upstream circuit open: {name}")


class CircuitBreaker:
    def __init__(self, name: str, threshold: int | None = None, recovery: int | None = None):
        self.name = name
        self.threshold = threshold if threshold is not None else settings.circuit_failure_threshold
        self.recovery = recovery if recovery is not None else settings.circuit_recovery_seconds
        self._failures = 0
        self._opened_at = 0.0
        self.state = "closed"

    async def call(self, coro_fn, *args, **kwargs):
        if not settings.circuit_breaker_enabled:
            return await coro_fn(*args, **kwargs)
        if self.state == "open":
            if time.monotonic() - self._opened_at >= self.recovery:
                self.state = "half_open"
            else:
                raise CircuitOpenError(self.name)
        try:
            result = await coro_fn(*args, **kwargs)
            self._failures = 0
            self.state = "closed"
            return result
        except Exception:
            self._failures += 1
            if self.state == "half_open" or self._failures >= self.threshold:
                self.state = "open"
                self._opened_at = time.monotonic()
            raise


chat_breaker = CircuitBreaker("chat")
embed_breaker = CircuitBreaker("embed")
rerank_breaker = CircuitBreaker("rerank")


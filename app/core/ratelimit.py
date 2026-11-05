"""内存滑动窗口限流(单副本;多副本请替换为 Redis 实现)。"""
import time
from collections import defaultdict, deque

from app.config import settings


class RateLimiter:
    def __init__(self, per_minute: int | None = None, burst: int | None = None):
        self.per_minute = per_minute if per_minute is not None else settings.rate_limit_per_minute
        self.burst = burst if burst is not None else settings.rate_limit_burst
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        if not settings.rate_limit_enabled:
            return True
        now = time.monotonic()
        dq = self._hits[key]
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= self.per_minute + self.burst:
            return False
        dq.append(now)
        return True


limiter = RateLimiter()


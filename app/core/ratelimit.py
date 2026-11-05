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


class RedisRateLimiter:
    """Redis 有序集合滑动窗口(多副本共享计数)。Redis 不可用时降级放行,不阻塞业务。"""

    def __init__(self, client, per_minute: int | None = None, burst: int | None = None):
        self._client = client
        base = per_minute if per_minute is not None else settings.rate_limit_per_minute
        extra = burst if burst is not None else settings.rate_limit_burst
        self.capacity = base + extra

    async def allow(self, key: str) -> bool:
        import time
        import uuid

        now = time.time()
        rk = f"mewhelp:rl:{key}"
        try:
            await self._client.zremrangebyscore(rk, 0, now - 60)
            count = await self._client.zcard(rk)
            if count >= self.capacity:
                return False
            await self._client.zadd(rk, {f"{now}:{uuid.uuid4().hex}": now})
            await self._client.expire(rk, 60)
            return True
        except Exception:
            return True


_redis_limiter: RedisRateLimiter | None = None


async def check_rate(key: str) -> bool:
    """统一入口:rate_limit 关闭直接放行;配了 REDIS_URL 走 Redis,否则进程内存。"""
    if not settings.rate_limit_enabled:
        return True
    global _redis_limiter
    if settings.redis_url:
        if _redis_limiter is None:
            from redis.asyncio import from_url

            _redis_limiter = RedisRateLimiter(from_url(settings.redis_url, decode_responses=True))
        return await _redis_limiter.allow(key)
    return limiter.allow(key)


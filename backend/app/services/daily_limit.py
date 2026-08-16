"""每日行为次数限制器 (Redis 计数, 不可用时进程内存兜底)

用于: 照料宠物蛋每日上限; Sprint 2 起任务/探险次数也走这里。
"""
from datetime import date

from ..config import settings


class DailyLimiter:
    def __init__(self) -> None:
        self._mem: dict[str, int] = {}
        self._r = None
        try:
            import redis

            self._r = redis.Redis.from_url(settings.redis_url, socket_timeout=1)
            self._r.ping()
        except Exception:
            self._r = None

    def hit(self, namespace: str, item_id: int | str, limit: int) -> tuple[bool, int]:
        """记录一次行为, 返回 (是否允许(未超限), 今日已用次数)"""
        key = f"daily:{namespace}:{item_id}:{date.today().isoformat()}"
        if self._r is not None:
            count = int(self._r.incr(key))
            self._r.expire(key, 172800)
        else:
            count = self._mem[key] = self._mem.get(key, 0) + 1
        return count <= limit, count

    def used(self, namespace: str, item_id: int | str) -> int:
        key = f"daily:{namespace}:{item_id}:{date.today().isoformat()}"
        if self._r is not None:
            raw = self._r.get(key)
            return int(raw) if raw else 0
        return self._mem.get(key, 0)


limiter = DailyLimiter()

"""The ask page's limits, counted in Redis: questions per visitor an hour, and the site's daily
spend on Claude calls (the Haiku rerank and the answer).

Keys:
- `salt:<day>`: a random salt, made once a day (Malaysia time) and kept two days.
- `q:<visitor>:<hour>`: the visitor's questions this hour, with a one-hour TTL. The visitor is the
  first 16 hex digits of sha256(salt + IP address), so no key holds an address and none outlives
  its hour.
- `spend:<day>`: micro-dollars spent that day, kept two days.

Set PARLIMEN_REDIS_URL (for example redis://127.0.0.1:6379/0) to count in Redis, so the counts
survive the nightly restart of the site. Without it an in-process fakeredis counts, which suits
one process and starts from zero at each restart.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

MYT = timezone(timedelta(hours=8))
HOURLY = int(os.environ.get("PARLIMEN_HOURLY_QUESTIONS", "20"))
DAILY_USD = float(os.environ.get("PARLIMEN_DAILY_USD", "2"))
DAY_TTL = 2 * 86400


def connect(url: str | None = None):
    url = url if url is not None else os.environ.get("PARLIMEN_REDIS_URL", "")
    if url:
        import redis
        return redis.Redis.from_url(url, decode_responses=True)
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


class Limits:
    def __init__(self, r=None, hourly: int = HOURLY, daily_usd: float = DAILY_USD, clock=time.time) -> None:
        self.r = r if r is not None else connect()
        self.hourly, self.daily_usd, self.clock = hourly, daily_usd, clock

    def _now(self) -> datetime:
        return datetime.fromtimestamp(self.clock(), MYT)

    def _day(self) -> str:
        return self._now().strftime("%Y-%m-%d")

    def visitor(self, ip: str) -> str:
        key = f"salt:{self._day()}"
        self.r.set(key, secrets.token_hex(16), nx=True, ex=DAY_TTL)
        return hashlib.sha256((self.r.get(key) + ip).encode()).hexdigest()[:16]

    def take(self, ip: str) -> bool:
        """Count one question; False when the visitor is past the hourly limit."""
        key = f"q:{self.visitor(ip)}:{self._now().strftime('%Y%m%d%H')}"
        n = self.r.incr(key)
        if n == 1:
            self.r.expire(key, 3600)
        return n <= self.hourly

    def spent_usd(self) -> float:
        return int(self.r.get(f"spend:{self._day()}") or 0) / 1e6

    def budget_left(self) -> bool:
        return self.spent_usd() < self.daily_usd

    def spend(self, usd: float) -> None:
        if usd > 0:
            key = f"spend:{self._day()}"
            self.r.incrby(key, round(usd * 1e6))
            self.r.expire(key, DAY_TTL)

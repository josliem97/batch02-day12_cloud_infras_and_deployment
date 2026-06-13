import time
import logging
import redis as redis_module
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)
_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is None:
        if not settings.redis_url or not settings.redis_url.startswith(("redis://", "rediss://", "unix://")):
            logger.warning("REDIS_URL not configured — rate limiting disabled (in-memory fallback)")
            return None
        _redis_client = redis_module.from_url(settings.redis_url, decode_responses=True)
    return _redis_client

# In-memory fallback for rate limiting when Redis is unavailable
_memory_rate: dict = {}

class RateLimiterRedis:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, user_id: str):
        r = get_redis()
        now = time.time()
        
        if r is None:
            # In-memory fallback
            key = user_id
            window = _memory_rate.get(key, [])
            cutoff = now - self.window_seconds
            window = [t for t in window if t > cutoff]
            if len(window) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {self.max_requests} req/min",
                )
            window.append(now)
            _memory_rate[key] = window
            return

        # Redis sliding window
        key = f"rate_limit:{user_id}"
        cutoff = now - self.window_seconds
        r.zremrangebyscore(key, "-inf", cutoff)
        count = r.zcard(key)
        if count >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.max_requests} req/min",
            )
        r.zadd(key, {str(now): now})
        r.expire(key, self.window_seconds)

rate_limiter = RateLimiterRedis(max_requests=settings.rate_limit_per_minute)

def check_rate_limit(key: str):
    rate_limiter.check(key)

import time
import redis
from fastapi import HTTPException
from app.config import settings

# Initialize Redis client. Use decode_responses=True for strings.
r = redis.from_url(settings.redis_url, decode_responses=True)

class RateLimiterRedis:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, user_id: str):
        now = time.time()
        key = f"rate_limit:{user_id}"
        
        # Remove timestamps older than window
        cutoff = now - self.window_seconds
        r.zremrangebyscore(key, "-inf", cutoff)
        
        count = r.zcard(key)
        if count >= self.max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {self.max_requests} req/min",
            )
        
        # Add current request (using score as member as well)
        r.zadd(key, {str(now): now})
        r.expire(key, self.window_seconds)

rate_limiter = RateLimiterRedis(max_requests=settings.rate_limit_per_minute)

def check_rate_limit(key: str):
    rate_limiter.check(key)

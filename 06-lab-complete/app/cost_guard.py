import time
import logging
import redis as redis_module
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)
_redis_client = None

PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

# In-memory fallback when Redis not available
_memory_budget: dict = {}

def get_redis():
    global _redis_client
    if _redis_client is None:
        if not settings.redis_url or not settings.redis_url.startswith(("redis://", "rediss://", "unix://")):
            return None
        _redis_client = redis_module.from_url(settings.redis_url, decode_responses=True)
    return _redis_client

class CostGuardRedis:
    def __init__(self, daily_budget_usd: float = 5.0):
        self.daily_budget_usd = daily_budget_usd

    def check_and_record_cost(self, user_id: str, input_tokens: int, output_tokens: int):
        estimated_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        r = get_redis()
        day_key = time.strftime("%Y-%m-%d")

        if r is None:
            # In-memory fallback
            key = f"{user_id}:{day_key}"
            current = _memory_budget.get(key, 0.0)
            if current + estimated_cost > self.daily_budget_usd:
                raise HTTPException(
                    status_code=503,
                    detail=f"Daily budget exhausted. Try again tomorrow."
                )
            _memory_budget[key] = current + estimated_cost
            return current + estimated_cost

        key = f"budget:{user_id}:{day_key}"
        current = float(r.get(key) or 0)
        if current + estimated_cost > self.daily_budget_usd:
            raise HTTPException(
                status_code=503,
                detail=f"Daily budget exhausted for user {user_id}. Try again tomorrow."
            )
        if estimated_cost > 0:
            r.incrbyfloat(key, estimated_cost)
            r.expire(key, 2 * 24 * 3600)
        return current + estimated_cost

cost_guard = CostGuardRedis(daily_budget_usd=settings.daily_budget_usd)

def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int):
    return cost_guard.check_and_record_cost(user_id, input_tokens, output_tokens)

def get_daily_cost(user_id: str) -> float:
    r = get_redis()
    day_key = time.strftime("%Y-%m-%d")
    if r is None:
        return _memory_budget.get(f"{user_id}:{day_key}", 0.0)
    key = f"budget:{user_id}:{day_key}"
    return float(r.get(key) or 0)

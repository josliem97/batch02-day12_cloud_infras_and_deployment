import time
import logging
import redis
from fastapi import HTTPException
from app.config import settings

logger = logging.getLogger(__name__)

r = redis.from_url(settings.redis_url, decode_responses=True)

PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

class CostGuardRedis:
    def __init__(self, daily_budget_usd: float = 5.0):
        self.daily_budget_usd = daily_budget_usd

    def check_and_record_cost(self, user_id: str, input_tokens: int, output_tokens: int):
        day_key = time.strftime("%Y-%m-%d")
        key = f"budget:{user_id}:{day_key}"
        
        estimated_cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        
        current = float(r.get(key) or 0)
        if current + estimated_cost > self.daily_budget_usd:
            raise HTTPException(
                status_code=503,
                detail=f"Daily budget exhausted for user {user_id}. Try again tomorrow."
            )
        
        if estimated_cost > 0:
            r.incrbyfloat(key, estimated_cost)
            r.expire(key, 2 * 24 * 3600)  # max 2 days for daily budget tracker
            
        return current + estimated_cost

cost_guard = CostGuardRedis(daily_budget_usd=settings.daily_budget_usd)

def check_and_record_cost(user_id: str, input_tokens: int, output_tokens: int):
    return cost_guard.check_and_record_cost(user_id, input_tokens, output_tokens)

def get_daily_cost(user_id: str) -> float:
    day_key = time.strftime("%Y-%m-%d")
    key = f"budget:{user_id}:{day_key}"
    return float(r.get(key) or 0)

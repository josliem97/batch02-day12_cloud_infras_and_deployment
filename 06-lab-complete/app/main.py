"""
Production AI Agent — Structured with Redis, Rate Limiting, and Cost Guard.
"""
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import redis

from app.config import settings
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_and_record_cost, get_daily_cost
from app.providers import make_provider
from app.tools import load_tool_declarations, to_openai_tools
from app.agent_loop import run_model_tool_loop

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)
_redis_client = None

def get_redis():
    global _redis_client
    if _redis_client is None:
        if not settings.redis_url or not settings.redis_url.startswith(("redis://", "rediss://", "unix://")):
            return None
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# --- Load Hackathon Artifacts ---
ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"

try:
    system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
    openai_tools = to_openai_tools(tool_declarations)
    logger.info("Successfully loaded AI artifacts and tools.")
except Exception as e:
    logger.error(f"Failed to load artifacts: {e}")
    system_prompt = "You are a helpful assistant."
    openai_tools = []

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
        )
    return api_key

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    r = get_redis()
    if r:
        try:
            r.ping()
            logger.info("Redis connection successful.")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
    else:
        logger.warning("Redis is not configured. In-memory mode active.")
    
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers.pop("server", None)
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception as e:
        _error_count += 1
        raise

class AskRequest(BaseModel):
    user_id: str = Field(..., description="Unique identifier for the user to track conversation state")
    question: str = Field(..., min_length=1, max_length=2000, description="Your question for the agent")

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
        },
    }

@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    _key: str = Depends(verify_api_key),
):
    # 1. Rate Limiting via Redis
    check_rate_limit(body.user_id)

    # 2. Budget Guard: Track token cost via Redis
    input_tokens = len(body.question.split()) * 2
    check_and_record_cost(body.user_id, input_tokens, 0)

    logger.info(json.dumps({
        "event": "agent_call",
        "user_id": body.user_id,
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    # 3. Retrieve Stateless Conversation History from Redis
    r = get_redis()
    history_msgs = []
    history_key = f"chat_history:{body.user_id}"
    
    if r:
        history_raw = r.lrange(history_key, 0, -1)
        history_msgs = [json.loads(h) for h in history_raw]
    
    # Optional: Trim history
    trim_window = 10
    history_msgs = history_msgs[-trim_window:]

    model_messages = [
        {"role": "system", "content": system_prompt},
        *history_msgs,
        {"role": "user", "content": body.question},
    ]

    # 4. Agent tool run loop
    try:
        provider = make_provider("openai")
        result = run_model_tool_loop(
            provider=provider,
            messages=model_messages,
            tools=openai_tools,
            model=settings.llm_model,
            max_tool_rounds=4,
        )
        answer = result["assistant_text"]
    except Exception as e:
        logger.error(f"Provider Error: {e}")
        answer = f"Error communicating with AI: {e}"

    # 5. Output Tokens Cost
    output_tokens = len(answer.split()) * 2
    check_and_record_cost(body.user_id, 0, output_tokens)

    # 6. Save new messages back to Redis
    if r:
        r.rpush(history_key, json.dumps({"role": "user", "content": body.question}))
        r.rpush(history_key, json.dumps({"role": "assistant", "content": answer}))
        r.expire(history_key, 24 * 3600)  # TTL 24h

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    status = "ok"
    r = get_redis()
    redis_status = "not_configured"
    if r:
        try:
            r.ping()
            redis_status = "ok"
        except Exception:
            redis_status = "error"
            status = "degraded"

    checks = {
        "redis": redis_status,
        "llm": "mock" if not settings.openai_api_key else "openai"
    }
    return {
        "status": status,
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe."""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}

def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)

if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )

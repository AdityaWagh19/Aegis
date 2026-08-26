# core/tier2_rate_limiter.py
"""
Redis sliding window rate limiter for Tier-2 Groq calls.
Per-tenant budget: N calls per 60 seconds.
On budget exhaustion: downgrade to fallback model.
On secondary budget exhaustion: skip Tier-2, return ESCALATE_TO_HUMAN.

Graceful degradation: if Redis is unavailable, allows all calls (no rate limiting)
so the system works in single-tenant MVP mode without Redis running.
"""
import time
import logging
import os
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_redis: Redis | None = None
_redis_available: bool | None = None   # None = not yet checked
WINDOW_SECONDS = 60

PRIMARY_MODEL = os.getenv("GROQ_MODEL_TIER2", "openai/gpt-oss-120b")
FALLBACK_MODEL = os.getenv("GROQ_MODEL_TIER2_FAST", "openai/gpt-oss-20b")
FALLBACK_BUDGET_PER_MINUTE = 30   # Groq free tier for smaller model


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis = Redis.from_url(redis_url, decode_responses=True)
    return _redis


async def _check_redis_available() -> bool:
    """Ping Redis once; cache the result so we don't retry every call."""
    global _redis_available
    if _redis_available is not None:
        return _redis_available
    try:
        redis = await get_redis()
        await redis.ping()
        _redis_available = True
    except Exception as e:
        logger.warning("Redis unavailable — rate limiter disabled (graceful degradation): %s", e)
        _redis_available = False
    return _redis_available


async def select_model_for_tenant(tenant_id: str, primary_budget: int) -> str | None:
    """
    Returns:
      - PRIMARY_MODEL if primary budget available
      - FALLBACK_MODEL if primary exhausted but fallback available
      - None if both exhausted (Tier-2 should be skipped)
      - PRIMARY_MODEL if Redis is unavailable (graceful degradation — no rate limiting)
    """
    if not await _check_redis_available():
        return PRIMARY_MODEL

    try:
        redis = await get_redis()
        now = time.time()
        window_start = now - WINDOW_SECONDS

        primary_key = f"tier2:primary:{tenant_id}"
        fallback_key = f"tier2:fallback:{tenant_id}"

        # Remove expired entries from the sorted set
        await redis.zremrangebyscore(primary_key, 0, window_start)
        primary_count = await redis.zcard(primary_key)

        if primary_count < primary_budget:
            # Add current call to the window
            await redis.zadd(primary_key, {str(now): now})
            await redis.expire(primary_key, WINDOW_SECONDS * 2)
            logger.debug("Tier-2 primary model granted: tenant=%s count=%d/%d", tenant_id, primary_count + 1, primary_budget)
            return PRIMARY_MODEL

        # Primary exhausted — check fallback
        await redis.zremrangebyscore(fallback_key, 0, window_start)
        fallback_count = await redis.zcard(fallback_key)

        if fallback_count < FALLBACK_BUDGET_PER_MINUTE:
            await redis.zadd(fallback_key, {str(now): now})
            await redis.expire(fallback_key, WINDOW_SECONDS * 2)
            logger.info("Tier-2 downgraded to fallback model: tenant=%s", tenant_id)
            return FALLBACK_MODEL

        logger.warning("Tier-2 both budgets exhausted: tenant=%s — skipping LLM", tenant_id)
        return None   # Skip Tier-2 entirely
    except Exception as e:
        logger.warning("Rate limiter error (graceful degradation): %s", e)
        return PRIMARY_MODEL

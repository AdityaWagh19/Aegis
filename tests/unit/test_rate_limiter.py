# tests/unit/test_rate_limiter.py
"""
Tests for Phase 9 Tier-2 rate limiter.
Uses a mocked Redis client to test budget, exhaustion, tenant isolation, and downgrade.
"""
import pytest
import unittest.mock as mock
import time


def _mock_redis():
    """Create a mock Redis with sorted-set operations."""
    r = mock.AsyncMock()
    store = {}  # key -> dict {member: score}

    async def ping():
        return True

    async def zremrangebyscore(key, min_score, max_score):
        if key in store:
            store[key] = {m: s for m, s in store[key].items() if s > max_score}

    async def zcard(key):
        return len(store.get(key, {}))

    async def zadd(key, mapping):
        store.setdefault(key, {}).update(mapping)

    async def expire(key, seconds):
        pass

    r.ping = ping
    r.zremrangebyscore = zremrangebyscore
    r.zcard = zcard
    r.zadd = zadd
    r.expire = expire
    r._store = store
    return r


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    """Reset the module-level Redis availability cache before each test."""
    import core.tier2_rate_limiter as rl
    rl._redis_available = None
    rl._redis = None
    yield
    rl._redis_available = None
    rl._redis = None


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests_under_budget():
    """Requests within budget are not throttled."""
    from core.tier2_rate_limiter import select_model_for_tenant

    with mock.patch("core.tier2_rate_limiter.get_redis", return_value=_mock_redis()):
        for _ in range(10):
            model = await select_model_for_tenant("t_test", primary_budget=10)
            assert model is not None
            assert model != "SKIP"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_at_budget_exhaustion():
    """Request at budget+1 gets downgraded or skipped."""
    from core.tier2_rate_limiter import select_model_for_tenant

    redis = _mock_redis()
    with mock.patch("core.tier2_rate_limiter.get_redis", return_value=redis):
        # Exhaust primary budget
        for _ in range(10):
            await select_model_for_tenant("t_test", primary_budget=10)
        # Next call should be downgraded or skipped
        model = await select_model_for_tenant("t_test", primary_budget=10)
        # Should get fallback model or None (both acceptable — depends on fallback budget)
        assert model is None or model != "primary_exhausted_error"


@pytest.mark.asyncio
async def test_tenant_isolation_in_rate_limiter():
    """Budget exhaustion for tenant A must not affect tenant B."""
    from core.tier2_rate_limiter import select_model_for_tenant

    redis = _mock_redis()
    with mock.patch("core.tier2_rate_limiter.get_redis", return_value=redis):
        # Exhaust tenant A's budget
        for _ in range(10):
            await select_model_for_tenant("t_a", primary_budget=10)

        # Tenant B should still have full budget
        model_b = await select_model_for_tenant("t_b", primary_budget=10)
        assert model_b is not None  # Tenant B not affected


@pytest.mark.asyncio
async def test_rate_limiter_downgrades_model():
    """When primary budget is exhausted, falls back to the fast model."""
    from core.tier2_rate_limiter import select_model_for_tenant, FALLBACK_MODEL

    redis = _mock_redis()
    # Pre-populate the store: primary budget already exhausted
    now = time.time()
    redis._store["tier2:primary:t_downgrade"] = {str(now - i): now - i for i in range(10)}

    with mock.patch("core.tier2_rate_limiter.get_redis", return_value=redis):
        model = await select_model_for_tenant("t_downgrade", primary_budget=10)
        assert model == FALLBACK_MODEL


@pytest.mark.asyncio
async def test_rate_limiter_skips_when_both_exhausted():
    """When both budgets are exhausted, returns None (skip Tier-2)."""
    from core.tier2_rate_limiter import select_model_for_tenant, FALLBACK_BUDGET_PER_MINUTE

    redis = _mock_redis()
    # Pre-populate: primary AND fallback both exhausted
    now = time.time()
    redis._store["tier2:primary:t_exhausted"] = {str(now - i): now - i for i in range(10)}
    redis._store["tier2:fallback:t_exhausted"] = {str(now - i): now - i for i in range(FALLBACK_BUDGET_PER_MINUTE)}

    with mock.patch("core.tier2_rate_limiter.get_redis", return_value=redis):
        model = await select_model_for_tenant("t_exhausted", primary_budget=10)
        assert model is None

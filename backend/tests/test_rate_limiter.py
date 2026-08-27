import time
import pytest
from app.guardrails.rate_limiter import SlidingWindowRateLimiter


def test_rate_limiter_allows_under_limit():
    limiter = SlidingWindowRateLimiter(default_limit=5, default_window_seconds=10)
    client_ip = "192.168.1.100"

    for i in range(5):
        allowed, remaining, retry_after = limiter.check_rate_limit(client_ip)
        assert allowed is True
        assert remaining == (5 - (i + 1))
        assert retry_after == 0


def test_rate_limiter_blocks_on_excess():
    limiter = SlidingWindowRateLimiter(default_limit=3, default_window_seconds=10)
    client_ip = "10.0.0.1"

    # Consume quota
    for _ in range(3):
        allowed, remaining, _ = limiter.check_rate_limit(client_ip)
        assert allowed is True

    # 4th request must be blocked
    allowed, remaining, retry_after = limiter.check_rate_limit(client_ip)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_rate_limiter_client_isolation():
    limiter = SlidingWindowRateLimiter(default_limit=2, default_window_seconds=10)
    client_a = "10.0.0.1"
    client_b = "10.0.0.2"

    # Exhaust Client A
    limiter.check_rate_limit(client_a)
    limiter.check_rate_limit(client_a)
    blocked_a, _, _ = limiter.check_rate_limit(client_a)
    assert blocked_a is False

    # Client B should still be allowed
    allowed_b, remaining_b, _ = limiter.check_rate_limit(client_b)
    assert allowed_b is True
    assert remaining_b == 1


def test_rate_limiter_reset():
    limiter = SlidingWindowRateLimiter(default_limit=1, default_window_seconds=10)
    client_ip = "127.0.0.1"

    limiter.check_rate_limit(client_ip)
    allowed, _, _ = limiter.check_rate_limit(client_ip)
    assert allowed is False

    limiter.reset(client_ip)
    allowed_again, _, _ = limiter.check_rate_limit(client_ip)
    assert allowed_again is True

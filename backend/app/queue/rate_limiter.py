"""
Token Bucket Rate Limiter for external archive services.
Ensures compliance with external archival rate limits and terms of service.
"""
import time
import asyncio
import threading


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate_per_minute: float, capacity: float | None = None):
        safe_rate = max(float(rate_per_minute), 0.1)
        self.rate_per_second = safe_rate / 60.0
        self.capacity = capacity if capacity is not None else safe_rate
        self.tokens = self.capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """
        Attempt to acquire 1 token synchronously.
        If blocking=True, sleeps until a token is available or timeout expires.
        """
        start_time = time.time()
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

                if not blocking:
                    return False

                # Calculate sleep duration to reach 1 token
                tokens_needed = 1.0 - self.tokens
                sleep_seconds = tokens_needed / self.rate_per_second

            if timeout is not None:
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout <= 0:
                    return False
                sleep_seconds = min(sleep_seconds, remaining_timeout)

            time.sleep(max(0.05, min(sleep_seconds, 2.0)))

    async def acquire_async(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """
        Attempt to acquire 1 token asynchronously without blocking the event loop thread.
        """
        start_time = time.time()
        while True:
            with self.lock:
                now = time.time()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_second)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

                if not blocking:
                    return False

                tokens_needed = 1.0 - self.tokens
                sleep_seconds = tokens_needed / self.rate_per_second

            if timeout is not None:
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout <= 0:
                    return False
                sleep_seconds = min(sleep_seconds, remaining_timeout)

            await asyncio.sleep(max(0.05, min(sleep_seconds, 2.0)))


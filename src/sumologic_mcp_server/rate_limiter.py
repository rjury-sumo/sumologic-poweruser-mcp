"""Rate limiting for Sumo Logic MCP Server."""

import asyncio
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Deque, Dict

from .exceptions import RateLimitError


class RateLimiter:
    """Token bucket rate limiter implementation."""

    def __init__(self, requests_per_minute: int = 60):
        """Initialize rate limiter.

        Args:
            requests_per_minute: Maximum number of requests per minute per tool
        """
        self.requests_per_minute = requests_per_minute
        self.window_size = 60.0  # 1 minute in seconds
        # Track requests per tool: tool_name -> deque of timestamps
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def acquire(self, tool_name: str) -> None:
        """Acquire permission to make a request.

        Args:
            tool_name: Name of the tool making the request

        Raises:
            RateLimitError: If rate limit is exceeded
        """
        async with self._lock:
            now = time.time()
            requests = self.requests[tool_name]

            # Remove old requests outside the time window
            while requests and requests[0] < now - self.window_size:
                requests.popleft()

            # Check if we've exceeded the limit
            if len(requests) >= self.requests_per_minute:
                oldest_request = requests[0]
                wait_time = oldest_request + self.window_size - now

                raise RateLimitError(
                    f"Rate limit exceeded for {tool_name}. "
                    f"Maximum {self.requests_per_minute} requests per minute. "
                    f"Try again in {wait_time:.1f} seconds.",
                    details=f"requests_in_window={len(requests)}, limit={self.requests_per_minute}",
                )

            # Record this request
            requests.append(now)

    def get_stats(self, tool_name: str) -> Dict[str, int]:
        """Get rate limit statistics for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Dictionary with current request count and limit
        """
        now = time.time()
        requests = self.requests[tool_name]

        # Clean old requests
        while requests and requests[0] < now - self.window_size:
            requests.popleft()

        return {
            "current_requests": len(requests),
            "limit": self.requests_per_minute,
            "remaining": max(0, self.requests_per_minute - len(requests)),
        }

    def reset(self, tool_name: str | None = None) -> None:
        """Reset rate limit counters.

        Args:
            tool_name: Specific tool to reset, or None to reset all
        """
        if tool_name:
            self.requests[tool_name].clear()
        else:
            self.requests.clear()


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter(requests_per_minute: int = 60) -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(requests_per_minute)
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (mainly for testing)."""
    global _rate_limiter
    _rate_limiter = None


def rate_limited(tool_name: str):
    """Decorator to apply rate limiting to async functions.

    Args:
        tool_name: Name of the tool for rate limit tracking

    Example:
        @rate_limited("search_logs")
        async def search_logs_tool(...):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            await limiter.acquire(tool_name)
            return await func(*args, **kwargs)

        return wrapper

    return decorator

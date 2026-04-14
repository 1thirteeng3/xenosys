"""
XenoSys Circuit Breaker Pattern
Async circuit breaker implementation for resilient HTTP operations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# Circuit Breaker States
# ============================================================================

class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are rejected immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


# ============================================================================
# Circuit Breaker Configuration
# ============================================================================

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    fail_max: int = 3           # Failures before opening circuit
    timeout_duration: float = 30.0  # Seconds before attempting close
    success_threshold: int = 2  # Successes needed in half-open to close
    half_open_max_calls: int = 3  # Max concurrent calls in half-open


# ============================================================================
# Circuit Breaker
# ============================================================================

class CircuitBreaker:
    """
    Async circuit breaker implementation.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failing, requests rejected immediately (fast fail)
    - HALF_OPEN: Testing recovery, limited requests allowed
    
    Usage:
        breaker = CircuitBreaker(fail_max=3, timeout_duration=30)
        
        async def fragile_operation():
            async with breaker:
                # Your HTTP call here
                return await http_call()
    """

    def __init__(
        self,
        fail_max: int = 3,
        timeout_duration: float = 30.0,
        success_threshold: int = 2,
        half_open_max_calls: int = 3,
        name: str = "default",
    ):
        self.config = CircuitBreakerConfig(
            fail_max=fail_max,
            timeout_duration=timeout_duration,
            success_threshold=success_threshold,
            half_open_max_calls=half_open_max_calls,
        )
        self.name = name
        
        # State
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current state."""
        return self._state

    @property
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        if self._state == CircuitState.CLOSED:
            return True
        
        if self._state == CircuitState.OPEN:
            # Check if timeout has elapsed to transition to half-open
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout_duration:
                    return True  # Will transition on next call
            return False
        
        # HALF_OPEN - limited calls allowed
        return self._half_open_calls < self.config.half_open_max_calls

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Async function to execute
            
        Returns:
            Result of the function
            
        Raises:
            CircuitBreakerOpenError: If circuit is open (fast fail)
        """
        async with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self._state == CircuitState.OPEN and self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout_duration:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")

            # Check if circuit allows the call
            if not self.is_available:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is open, fast failing"
                )

            # Track half-open calls
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1

        try:
            # Execute the function
            result = await func()
            
            # Success handling
            await self._on_success()
            return result
            
        except Exception as e:
            # Failure handling
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._failure_count = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls = max(0, self._half_open_calls - 1)
                
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (failure)")
                
            elif self._failure_count >= self.config.fail_max:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker {self.name}: CLOSED -> OPEN "
                    f"({self._failure_count} failures)"
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info(f"Circuit breaker {self.name}: manually reset")

    def get_state(self) -> dict[str, Any]:
        """Get current state info."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


# ============================================================================
# Circuit Breaker Error
# ============================================================================

class CircuitBreakerError(Exception):
    """Base circuit breaker exception."""
    pass


class CircuitBreakerOpenError(CircuitBreakerError):
    """Raised when circuit is open and fast failing."""
    pass


# ============================================================================
# Circuit Breaker Context Manager
# ============================================================================

class CircuitBreakerContext:
    """Context manager for circuit breaker."""
    
    def __init__(self, breaker: CircuitBreaker):
        self._breaker = breaker
    
    async def __aenter__(self) -> None:
        if not self._breaker.is_available:
            raise CircuitBreakerOpenError(
                f"Circuit breaker {self._breaker.name} is open"
            )
        return None
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is None:
            await self._breaker._on_success()
        else:
            await self._breaker._on_failure()
        return False  # Don't suppress exception


# ============================================================================
# Decorator
# ============================================================================

def circuit_breaker(
    fail_max: int = 3,
    timeout_duration: float = 30.0,
    name: Optional[str] = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """
    Decorator to add circuit breaker to async functions.
    
    Usage:
        @circuit_breaker(fail_max=3, timeout_duration=30, name="cortex")
        async def search_cortex(query: str):
            return await http_call()
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        breaker = CircuitBreaker(
            fail_max=fail_max,
            timeout_duration=timeout_duration,
            name=name or func.__name__,
        )
        
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async def call_func() -> T:
                return await func(*args, **kwargs)
            
            return await breaker.call(call_func)
        
        # Attach breaker to function for external access
        wrapper.circuit_breaker = breaker
        return wrapper
    
    return decorator


# ============================================================================
# Circuit Breaker Registry
# ============================================================================

class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        **config: Any,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        async with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    **config,
                )
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_all(self) -> dict[str, CircuitBreaker]:
        """Get all circuit breakers."""
        return self._breakers.copy()
    
    async def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_global_breaker_registry = CircuitBreakerRegistry()


def get_breaker_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry."""
    return _global_breaker_registry
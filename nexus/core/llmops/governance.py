"""
XenoSys Core - LLMOps Governance
Cost control, rate limiting, and human-in-the-loop
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Cost Management
# ============================================================================

@dataclass
class CostEntry:
    """A cost entry for tracking."""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Identifiers
    user_id: str = ""
    agent_id: str = ""
    session_id: str = ""
    
    # Token usage
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Cost
    cost_usd: float = 0.0
    
    # Model info
    model: str = ""
    
    # Metadata
    request_type: str = "chat"  # chat, completion, embedding, etc.


@dataclass
class CostBudget:
    """Cost budget for a user or organization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    
    # Scope
    user_id: str | None = None
    org_id: str | None = None
    
    # Budget limits
    daily_limit_usd: float = 10.0
    monthly_limit_usd: float = 100.0
    per_request_limit_usd: float = 1.0
    
    # Warning thresholds
    warning_threshold: float = 0.8  # 80% of limit
    
    # Usage
    daily_spend: float = 0.0
    monthly_spend: float = 0.0
    
    # Tracking
    daily_reset: datetime = field(default_factory=lambda: datetime.utcnow + timedelta(days=1))
    monthly_reset: datetime = field(default_factory=lambda: datetime.utcnow.replace(day=1) + timedelta(days=32))


class CostTracker:
    """
    Track and enforce LLM costs.
    
    Features:
    - Per-user and per-org budgets
    - Daily/monthly limits
    - Real-time cost tracking
    - Warning notifications
    """
    
    # Pricing per 1M tokens (example - should be configurable)
    PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "default": {"input": 1.0, "output": 2.0},
    }
    
    def __init__(self) -> None:
        self._entries: list[CostEntry] = []
        self._budgets: dict[str, CostBudget] = {}
        self._lock = asyncio.Lock()
        
        # Event callbacks
        self._on_warning: list[ callable[[str, CostBudget, float], None] ] = []
        self._on_limit_exceeded: list[ callable[[str, CostBudget], None] ] = []
    
    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost for token usage."""
        pricing = self.PRICING.get(model, self.PRICING["default"])
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    async def record(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        request_type: str = "chat",
    ) -> CostEntry:
        """Record a cost entry."""
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        entry = CostEntry(
            user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost,
            request_type=request_type,
        )
        
        async with self._lock:
            self._entries.append(entry)
            
            # Check budgets
            await self._check_budgets(user_id, cost)
        
        return entry
    
    async def _check_budgets(self, user_id: str, cost: float) -> None:
        """Check and enforce budgets."""
        budget = self._budgets.get(user_id)
        if not budget:
            return
        
        now = datetime.utcnow()
        
        # Reset if needed
        if now >= budget.daily_reset:
            budget.daily_spend = 0.0
            budget.daily_reset = now + timedelta(days=1)
        
        if now >= budget.monthly_reset:
            budget.monthly_spend = 0.0
            budget.monthly_reset = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        
        # Update spending
        budget.daily_spend += cost
        budget.monthly_spend += cost
        
        # Check limits
        if budget.monthly_spend >= budget.monthly_limit_usd:
            await self._trigger_limit_exceeded(budget)
        
        if budget.daily_spend >= budget.daily_limit_usd:
            await self._trigger_limit_exceeded(budget)
        
        # Check warnings
        for limit, spend, name in [
            (budget.daily_limit_usd, budget.daily_spend, "daily"),
            (budget.monthly_limit_usd, budget.monthly_spend, "monthly"),
        ]:
            if spend / limit >= budget.warning_threshold:
                await self._trigger_warning(user_id, budget, name)
    
    async def _trigger_warning(
        self,
        user_id: str,
        budget: CostBudget,
        limit_type: str,
    ) -> None:
        """Trigger budget warning."""
        for callback in self._on_warning:
            try:
                callback(user_id, budget, budget.daily_spend)
            except Exception as e:
                logger.error(f"Warning callback failed: {e}")
    
    async def _trigger_limit_exceeded(
        self,
        budget: CostBudget,
    ) -> None:
        """Trigger limit exceeded."""
        for callback in self._on_limit_exceeded:
            try:
                callback(budget.user_id or "", budget)
            except Exception as e:
                logger.error(f"Limit exceeded callback failed: {e}")
    
    async def check_limit(
        self,
        user_id: str,
        estimated_cost: float,
    ) -> bool:
        """
        Check if a request would exceed limits.
        
        Returns True if allowed, False if would exceed limit.
        """
        budget = self._budgets.get(user_id)
        if not budget:
            return True
        
        if budget.daily_spend + estimated_cost > budget.daily_limit_usd:
            return False
        
        if budget.monthly_spend + estimated_cost > budget.monthly_limit_usd:
            return False
        
        if estimated_cost > budget.per_request_limit_usd:
            return False
        
        return True
    
    def set_budget(self, budget: CostBudget) -> None:
        """Set a cost budget."""
        key = budget.user_id or budget.org_id or ""
        self._budgets[key] = budget
    
    async def get_spending(
        self,
        user_id: str,
        period: str = "daily",
    ) -> dict[str, Any]:
        """Get spending for a period."""
        now = datetime.utcnow()
        
        async with self._lock:
            if period == "daily":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "monthly":
                start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                start = now - timedelta(days=7)
            
            entries = [e for e in self._entries if e.timestamp >= start and e.user_id == user_id]
            
            total_cost = sum(e.cost_usd for e in entries)
            total_tokens = sum(e.total_tokens for e in entries)
            
            return {
                "period": period,
                "cost_usd": total_cost,
                "total_tokens": total_tokens,
                "request_count": len(entries),
            }
    
    def on_warning(
        self,
        callback: callable[[str, CostBudget, float], None],
    ) -> None:
        """Register warning callback."""
        self._on_warning.append(callback)
    
    def on_limit_exceeded(
        self,
        callback: callable[[str, CostBudget], None],
    ) -> None:
        """Register limit exceeded callback."""
        self._on_limit_exceeded.append(callback)


# ============================================================================
# Rate Limiting
# ============================================================================

@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    tokens_per_minute: int = 100000
    concurrent_requests: int = 5


class RateLimiter:
    """
    Rate limiting for API requests.
    
    Implements token bucket algorithm for smooth rate limiting.
    """
    
    def __init__(self) -> None:
        self._configs: dict[str, RateLimitConfig] = {}
        self._buckets: dict[str, dict[str, float]] = {}  # user -> bucket state
        self._timestamps: dict[str, list[datetime]] = {}  # For sliding window
        self._lock = asyncio.Lock()
    
    def set_config(self, user_id: str, config: RateLimitConfig) -> None:
        """Set rate limit config for a user."""
        self._configs[user_id] = config
    
    async def acquire(
        self,
        user_id: str,
        tokens: int = 1,
    ) -> bool:
        """
        Acquire a rate limit slot.
        
        Returns True if allowed, False if rate limited.
        """
        config = self._configs.get(user_id) or RateLimitConfig()
        
        async with self._lock:
            now = datetime.utcnow()
            
            # Initialize buckets if needed
            if user_id not in self._timestamps:
                self._timestamps[user_id] = []
            
            # Clean old timestamps (sliding window)
            self._timestamps[user_id] = [
                t for t in self._timestamps[user_id]
                if now - t < timedelta(hours=1)
            ]
            
            # Check concurrent requests
            active = len([t for t in self._timestamps[user_id] if now - t < timedelta(seconds=10)])
            if active >= config.concurrent_requests:
                return False
            
            # Check requests per minute
            last_minute = [t for t in self._timestamps[user_id] if now - t < timedelta(minutes=1)]
            if len(last_minute) >= config.requests_per_minute:
                return False
            
            # Check requests per hour
            if len(self._timestamps[user_id]) >= config.requests_per_hour:
                return False
            
            # Record request
            self._timestamps[user_id].append(now)
            
            return True
    
    async def wait_for_slot(
        self,
        user_id: str,
        tokens: int = 1,
        timeout: float = 30.0,
    ) -> bool:
        """Wait for a rate limit slot to become available."""
        start = datetime.utcnow()
        
        while True:
            if await self.acquire(user_id, tokens):
                return True
            
            if (datetime.utcnow() - start).total_seconds() >= timeout:
                return False
            
            await asyncio.sleep(0.5)
    
    def get_remaining(self, user_id: str) -> dict[str, int]:
        """Get remaining quota for a user."""
        config = self._configs.get(user_id) or RateLimitConfig()
        now = datetime.utcnow()
        
        timestamps = self._timestamps.get(user_id, [])
        
        last_minute = len([t for t in timestamps if now - t < timedelta(minutes=1)])
        last_hour = len([t for t in timestamps if now - t < timedelta(hours=1)])
        
        return {
            "requests_per_minute": config.requests_per_minute - last_minute,
            "requests_per_hour": config.requests_per_hour - last_hour,
        }


# ============================================================================
# Human-in-the-Loop (HITL)
# ============================================================================

class HITLRequestStatus(str, Enum):
    """Status of a HITL request."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    TIMEOUT = "timeout"


@dataclass
class HITLRequest:
    """A human-in-the-loop approval request."""
    id: str = field(default_factory=lambda: str(uuid4()))
    
    # Context
    agent_id: str = ""
    session_id: str = ""
    user_id: str = ""
    
    # Request details
    tool_name: str = ""
    tool_args: dict[str, Any] = field(default_factory=dict)
    reason: str = ""  # Why approval is needed
    
    # State
    status: HITLRequestStatus = HITLRequestStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    responded_at: datetime | None = None
    
    # Timeout
    timeout_seconds: float = 300.0
    
    # Response
    approver_id: str | None = None
    response: str | None = None


class HITLManager:
    """
    Human-in-the-loop approval system.
    
    Handles:
    - Approval requests for sensitive operations
    - Timeout handling
    - Audit logging
    - Notification to human reviewers
    """
    
    def __init__(
        self,
        default_timeout_seconds: float = 300.0,
        max_pending: int = 100,
    ) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self.max_pending = max_pending
        
        self._requests: dict[str, HITLRequest] = {}
        self._pending: list[str] = []  # Queue of pending request IDs
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._on_request: list[ callable[[HITLRequest], None] ] = []
        self._on_response: list[ callable[[HITLRequest], None] ] = []
    
    async def create_request(
        self,
        agent_id: str,
        session_id: str,
        user_id: str,
        tool_name: str,
        tool_args: dict[str, Any],
        reason: str,
        timeout_seconds: float | None = None,
    ) -> str:
        """Create a new approval request."""
        request = HITLRequest(
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id,
            tool_name=tool_name,
            tool_args=tool_args,
            reason=reason,
            timeout_seconds=timeout_seconds or self.default_timeout_seconds,
        )
        
        async with self._lock:
            # Check pending limit
            if len(self._pending) >= self.max_pending:
                raise RuntimeError("Too many pending HITL requests")
            
            self._requests[request.id] = request
            self._pending.append(request.id)
        
        # Notify listeners
        for callback in self._on_request:
            try:
                callback(request)
            except Exception as e:
                logger.error(f"HITL request callback failed: {e}")
        
        # Start timeout checker
        asyncio.create_task(self._check_timeout(request.id))
        
        return request.id
    
    async def approve(
        self,
        request_id: str,
        approver_id: str,
        response: str | None = None,
    ) -> bool:
        """Approve a request."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request or request.status != HITLRequestStatus.PENDING:
                return False
            
            request.status = HITLRequestStatus.APPROVED
            request.responded_at = datetime.utcnow()
            request.approver_id = approver_id
            request.response = response
            
            self._pending.remove(request_id)
        
        for callback in self._on_response:
            try:
                callback(request)
            except Exception as e:
                logger.error(f"HITL response callback failed: {e}")
        
        return True
    
    async def reject(
        self,
        request_id: str,
        approver_id: str,
        response: str | None = None,
    ) -> bool:
        """Reject a request."""
        async with self._lock:
            request = self._requests.get(request_id)
            if not request or request.status != HITLRequestStatus.PENDING:
                return False
            
            request.status = HITLRequestStatus.REJECTED
            request.responded_at = datetime.utcnow()
            request.approver_id = approver_id
            request.response = response
            
            self._pending.remove(request_id)
        
        for callback in self._on_response:
            try:
                callback(request)
            except Exception as e:
                logger.error(f"HITL response callback failed: {e}")
        
        return True
    
    async def get_request(self, request_id: str) -> HITLRequest | None:
        """Get a request by ID."""
        return self._requests.get(request_id)
    
    async def get_pending(self, user_id: str | None = None) -> list[HITLRequest]:
        """Get pending requests."""
        async with self._lock:
            requests = [
                self._requests[rid]
                for rid in self._pending
                if rid in self._requests
            ]
            
            if user_id:
                requests = [r for r in requests if r.user_id == user_id]
            
            return requests
    
    async def _check_timeout(self, request_id: str) -> None:
        """Check if a request has timed out."""
        request = self._requests.get(request_id)
        if not request:
            return
        
        await asyncio.sleep(request.timeout_seconds)
        
        async with self._lock:
            if request.status == HITLRequestStatus.PENDING:
                request.status = HITLRequestStatus.TIMEOUT
                request.responded_at = datetime.utcnow()
                
                if request_id in self._pending:
                    self._pending.remove(request_id)
        
        for callback in self._on_response:
            try:
                callback(request)
            except Exception as e:
                logger.error(f"HITL timeout callback failed: {e}")
    
    def on_request(self, callback: callable[[HITLRequest], None]) -> None:
        """Register request notification callback."""
        self._on_request.append(callback)
    
    def on_response(self, callback: callable[[HITLRequest], None]) -> None:
        """Register response notification callback."""
        self._on_response.append(callback)


# ============================================================================
# Audit Logging
# ============================================================================

class AuditLogger:
    """
    Audit logging for compliance and security.
    
    Logs:
    - All LLM requests with prompts/responses
    - Cost tracking
    - HITL decisions
    - Rate limit violations
    - Agent actions
    """
    
    def __init__(self, log_dir: str = "./logs/audit") -> None:
        from pathlib import Path
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._entries: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
    
    async def log(
        self,
        event_type: str,
        user_id: str,
        data: dict[str, Any],
        severity: str = "info",
    ) -> None:
        """Log an audit event."""
        entry = {
            "id": str(uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "severity": severity,
            "data": data,
        }
        
        async with self._lock:
            self._entries.append(entry)
            
            # Write to file periodically
            if len(self._entries) >= 100:
                await self._flush()
    
    async def _flush(self) -> None:
        """Flush entries to disk."""
        if not self._entries:
            return
        
        import json
        from datetime import datetime
        
        filename = self.log_dir / f"audit_{datetime.utcnow().strftime('%Y%m%d_%H')}.jsonl"
        
        with open(filename, "a") as f:
            for entry in self._entries:
                f.write(json.dumps(entry) + "\n")
        
        self._entries.clear()
    
    async def query(
        self,
        event_type: str | None = None,
        user_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Query audit logs."""
        # In production, this would query a database
        async with self._lock:
            results = list(self._entries)
        
        if event_type:
            results = [r for r in results if r["event_type"] == event_type]
        
        if user_id:
            results = [r for r in results if r["user_id"] == user_id]
        
        if start_time:
            results = [r for r in results if datetime.fromisoformat(r["timestamp"]) >= start_time]
        
        if end_time:
            results = [r for r in results if datetime.fromisoformat(r["timestamp"]) <= end_time]
        
        return results[-limit:]
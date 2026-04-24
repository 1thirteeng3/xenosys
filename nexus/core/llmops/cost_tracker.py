"""
XenoSys LLMOps - Cost Tracking Module
Per-agent, per-entity, per-user cost accounting.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# Cost Types
# ============================================================================

@dataclass
class CostRecord:
    """A cost record for a single operation."""
    id: UUID = field(default_factory=uuid4)
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    entity_id: Optional[str] = None
    user_id: str = ""
    model: str = ""
    provider: str = ""  # openai, anthropic, etc.
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = field(default_factory=Decimal)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Budget:
    """A budget limit for a user, entity, or global."""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    limit_usd: Decimal = field(default_factory=Decimal)
    period: str = "monthly"  # daily, weekly, monthly
    scope: str = "user"  # user, entity, global
    scope_id: Optional[str] = None
    alert_threshold: float = 0.8  # Alert at 80% of budget
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CostDashboard:
    """Cost dashboard data."""
    total_today: Decimal = field(default_factory=Decimal)
    total_week: Decimal = field(default_factory=Decimal)
    total_month: Decimal = field(default_factory=Decimal)
    forecast_month: Decimal = field(default_factory=Decimal)
    by_agent: Dict[str, Decimal] = field(default_factory=dict)
    by_entity: Dict[str, Decimal] = field(default_factory=dict)
    by_user: Dict[str, Decimal] = field(default_factory=dict)
    budget_status: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ============================================================================
# Pricing Configuration
# ============================================================================

class PricingConfig:
    """Pricing configuration per model."""
    
    # Default pricing (USD per million tokens)
    PRICING = {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.00, "output": 30.00},
        "gpt-4": {"input": 30.00, "output": 60.00},
        "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        "claude-3-opus": {"input": 15.00, "output": 75.00},
        "claude-3-sonnet": {"input": 3.00, "output": 15.00},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "default": {"input": 1.00, "output": 3.00},
    }
    
    @classmethod
    def get_pricing(cls, model: str) -> Dict[str, float]:
        """Get pricing for a model."""
        # Find matching pricing
        for model_name, pricing in cls.PRICING.items():
            if model.startswith(model_name):
                return pricing
        return cls.PRICING["default"]


# ============================================================================
# Cost Calculator
# ============================================================================

class CostCalculator:
    """Calculate LLM costs."""
    
    @staticmethod
    def calculate(
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> Decimal:
        """Calculate cost for a request."""
        pricing = PricingConfig.get_pricing(model)
        
        input_cost = Decimal(tokens_in) / 1_000_000 * Decimal(pricing["input"])
        output_cost = Decimal(tokens_out) / 1_000_000 * Decimal(pricing["output"])
        
        return input_cost + output_cost


# ============================================================================
# Cost Tracker
# ============================================================================

class CostTracker:
    """
    Track and manage costs.
    
    Provides:
    - Cost recording per operation
    - Budget enforcement
    - Cost dashboards
    - Spending alerts
    """
    
    def __init__(self):
        self._records: List[CostRecord] = []
        self._budgets: Dict[str, Budget] = {}
        self._lock = asyncio.Lock()
    
    # =========================================================================
    # Recording
    # =========================================================================
    
    async def record(
        self,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        entity_id: Optional[str] = None,
        user_id: str = "",
        model: str = "",
        provider: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CostRecord:
        """Record a cost."""
        # Calculate cost
        cost_usd = CostCalculator.calculate(model, tokens_in, tokens_out)
        
        record = CostRecord(
            session_id=session_id,
            agent_id=agent_id,
            entity_id=entity_id,
            user_id=user_id,
            model=model,
            provider=provider,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._records.append(record)
        
        # Check budgets
        await self._check_budgets(user_id, entity_id, cost_usd)
        
        logger.info(f"Recorded cost: ${cost_usd:.4f} ({model}, {tokens_in + tokens_out} tokens)")
        return record
    
    async def _check_budgets(
        self,
        user_id: str,
        entity_id: Optional[str],
        amount: Decimal,
    ) -> None:
        """Check and enforce budgets."""
        # Check user budget
        user_key = f"user:{user_id}"
        if user_key in self._budgets:
            budget = self._budgets[user_key]
            if budget.is_active:
                spent = await self._get_spending(budget)
                if spent + amount > budget.limit_usd:
                    logger.warning(f"User budget exceeded: {user_id}")
        
        # Check entity budget
        if entity_id:
            entity_key = f"entity:{entity_id}"
            if entity_key in self._budgets:
                budget = self._budgets[entity_key]
                if budget.is_active:
                    spent = await self._get_spending(budget)
                    if spent + amount > budget.limit_usd:
                        logger.warning(f"Entity budget exceeded: {entity_id}")
    
    async def _get_spending(self, budget: Budget) -> Decimal:
        """Get current spending for a budget."""
        now = datetime.utcnow()
        
        if budget.period == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif budget.period == "weekly":
            start = now - timedelta(days=now.weekday())
        else:  # monthly
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total = Decimal(0)
        for record in self._records:
            if record.timestamp >= start:
                # Check scope
                if budget.scope == "user" and record.user_id == budget.scope_id:
                    total += record.cost_usd
                elif budget.scope == "entity" and record.entity_id == budget.scope_id:
                    total += record.cost_usd
        
        return total
    
    # =========================================================================
    # Budget Management
    # =========================================================================
    
    async def set_budget(
        self,
        name: str,
        limit_usd: float,
        period: str = "monthly",
        scope: str = "user",
        scope_id: Optional[str] = None,
        alert_threshold: float = 0.8,
    ) -> Budget:
        """Set a budget."""
        budget = Budget(
            name=name,
            limit_usd=Decimal(str(limit_usd)),
            period=period,
            scope=scope,
            scope_id=scope_id,
            alert_threshold=alert_threshold,
        )
        
        key = f"{scope}:{scope_id or 'global'}"
        self._budgets[key] = budget
        
        return budget
    
    async def get_budget(self, scope: str, scope_id: str) -> Optional[Budget]:
        """Get a budget."""
        key = f"{scope}:{scope_id}"
        return self._budgets.get(key)
    
    # =========================================================================
    # Dashboards
    # =========================================================================
    
    async def get_dashboard(
        self,
        user_id: Optional[str] = None,
    ) -> CostDashboard:
        """Get cost dashboard."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        total_today = Decimal(0)
        total_week = Decimal(0)
        total_month = Decimal(0)
        by_agent: Dict[str, Decimal] = {}
        by_entity: Dict[str, Decimal] = {}
        by_user: Dict[str, Decimal] = {}
        
        for record in self._records:
            # Filter by user
            if user_id and record.user_id != user_id:
                continue
            
            # Time-based totals
            if record.timestamp >= today_start:
                total_today += record.cost_usd
            if record.timestamp >= week_start:
                total_week += record.cost_usd
            if record.timestamp >= month_start:
                total_month += record.cost_usd
            
            # By-agent
            if record.agent_id:
                by_agent[record.agent_id] = by_agent.get(record.agent_id, Decimal(0)) + record.cost_usd
            
            # By-entity
            if record.entity_id:
                by_entity[record.entity_id] = by_entity.get(record.entity_id, Decimal(0)) + record.cost_usd
            
            # By-user
            by_user[record.user_id] = by_user.get(record.user_id, Decimal(0)) + record.cost_usd
        
        # Forecast (linear projection)
        days_in_month = 30
        days_passed = now.day
        if days_passed > 0:
            forecast = (total_month / days_passed) * days_in_month
        else:
            forecast = total_month
        
        # Budget status
        budget_status: Dict[str, Dict[str, Any]] = {}
        for key, budget in self._budgets.items():
            if budget.scope == "user" and (not user_id or budget.scope_id == user_id):
                spent = await self._get_spending(budget)
                budget_status[key] = {
                    "limit": float(budget.limit_usd),
                    "spent": float(spent),
                    "remaining": float(budget.limit_usd - spent),
                    "percent": float(spent / budget.limit_usd) if budget.limit_usd > 0 else 0,
                    "alert": spent >= budget.limit_usd * Decimal(budget.alert_threshold),
                }
        
        return CostDashboard(
            total_today=total_today,
            total_week=total_week,
            total_month=total_month,
            forecast_month=forecast,
            by_agent={k: v for k, v in by_agent.items()},
            by_entity={k: v for k, v in by_entity.items()},
            by_user={k: v for k, v in by_user.items()},
            budget_status=budget_status,
        )


# Global cost tracker instance
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get or create global cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker
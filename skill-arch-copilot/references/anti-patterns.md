# Anti-Patterns to Avoid

Common mistakes in AI agent systems and multi-agent architectures, with explanations and alternatives.

## Architectural Anti-Patterns

### 1. God Object Agent

**Problem**: Single agent handling everything - routing, execution, memory, tools.

**Symptoms**:
- Agent class with 2000+ lines
- No clear separation of concerns
- Impossible to test individual features
- Changes cascade unpredictably

**Why It's Bad**:
- Violates single responsibility
- Creates bottlenecks
- Makes parallelization impossible
- Hinders reusability

**Solution**: Decompose into specialized agents:
```python
class OrchestratorAgent:
    def __init__(self):
        self.router = IntentRouter()
        self.executor = ExecutorAgent()
        self.memory = MemoryManager()
        self.reflector = ReflectorAgent()
    
    async def run(self, task):
        intent = await self.router.classify(task)
        agent = self.select_agent(intent)
        return await agent.delegate(task)
```

### 2. Monolithic Event Handler

**Problem**: Single event handler doing everything.

**Symptoms**:
- Event bus with massive switch statement
- One handler for all event types
- No clear event taxonomy

**Why It's Bad**:
- Impossible to maintain
- Can't scale отдельные handlers
- Testing becomes impractical

**Solution**: Modular handlers with typed subscriptions:
```python
class EventBus:
    def subscribe(self, event_types, handler):
        # Type-safe, composable handlers
        pass

# Usage
event_bus.subscribe([EventType.MESSAGE_RECEIVED], handle_message)
event_bus.subscribe([EventType.AGENT_COMPLETED], handle_completion)
```

### 3. Shared Mutable State

**Problem**: Multiple agents sharing state without synchronization.

**Symptoms**:
- Race conditions in memory access
- Non-deterministic behavior
- "Works on my machine" failures

**Why It's Bad**:
- Data corruption
- Impossible to debug
- Breaks horizontal scaling

**Solution**: Immutable data flow:
```python
# Instead of shared state
class AgentContext:
    def __init__(self, initial_state: dict):
        self._state = initial_state  # Immutable copy
        self._changes: list[StateChange] = []
    
    def update(self, change: StateChange):
        self._changes.append(change)
        # Changes propagate, don't mutate in place
```

### 4. Synchronous Everything

**Problem**: All operations blocking, no async/await.

**Symptoms**:
- UI freezes during LLM calls
- Can't handle concurrent requests
- Poor resource utilization

**Why It's Bad**:
- Blocks event loop
- Terrible throughput
- Wastes CPU cycles

**Solution**: Async-first design:
```python
# Bad
def process(message):
    result = llm.call(message)  # Blocks
    return result

# Good
async def process(message):
    result = await llm.acall(message)  # Non-blocking
    return result
```

### 5. Hard-coded Everything

**Problem**: No configuration, all values baked in.

**Symptoms**:
- Changing API keys requires code change
- Different deployments need different builds
- No way to tune behavior without redeploying

**Why It's Bad**:
- Inflexible
- Error-prone deployments
- Security risks (secrets in code)

**Solution**: Configuration-driven:
```python
class Agent:
    def __init__(self, config: AgentConfig):
        self.max_iterations = config.max_iterations
        self.timeout = config.timeout_seconds
        self.temperature = config.temperature
```

## Memory Anti-Patterns

### 6. Single-tier Memory

**Problem**: One memory layer for everything.

**Symptoms**:
- 100ms+ retrieval for simple queries
- Can't handle high-volume contexts
- Memory exhaustion errors

**Why It's Bad**:
- Performance doesn't scale
- No optimization for access patterns
- Can't balance speed vs. capacity

**Solution**: Tiered memory:
```python
class MemoryManager:
    def __init__(self):
        self.l1 = L1Memory(max_size=10000)    # Fast cache
        self.l2 = L2Memory()                   # Semantic
        self.l3 = L3Memory()                   # Persistent
```

### 7. No Eviction Policy

**Problem**: Memory grows unbounded.

**Symptoms**:
- Memory usage grows indefinitely
- OOM errors in production
- Retrieval degrades over time

**Why It's Bad**:
- Resource exhaustion
- Performance degradation
- System instability

**Solution**: LRU/TTL eviction:
```python
class L1Memory:
    def __init__(self, max_size):
        self.cache = OrderedDict()
        self.max_size = max_size
    
    async def write(self, entry):
        while len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)  # LRU eviction
```

### 8. Embedding Everything

**Problem**: Embedding all content regardless of need.

**Symptoms**:
- High storage costs
- Slow indexing
- Unnecessary computational overhead

**Why It's Bad**:
- Wastes resources
- Noisy similarity results
- Slow write operations

**Solution**: Selective embedding:
```python
async def write(self, entry):
    if entry.importance >= IMPORTANCE_THRESHOLD:
        # Only embed important entries
        entry.embedding = self.embedder.encode(entry.content)
```

## Agent Anti-Patterns

### 9. Infinite Loop Without Guard

**Problem**: No max iterations on ReAct loop.

**Symptoms**:
- Agent runs forever
- Exhausts API quotas
- Creates infinite costs

**Why It's Bad**:
- Resource exhaustion
- Financial risk
- Poor UX

**Solution**: Strict bounds:
```python
async def run(self, request):
    for i in range(request.max_iterations):
        thought = await self.think(request)
        if thought.is_terminal:
            return thought.result
```

### 10. No Error Recovery

**Problem**: Single failure point, no fallbacks.

**Symptoms**:
- One failed tool kills entire execution
- No retry logic
- Poor fault tolerance

**Why It's Bad**:
- Fragile system
- Poor reliability
- Bad user experience

**Solution**: Graceful degradation:
```python
async def execute_tool(self, tool_name, args):
    for attempt in range(MAX_RETRIES):
        try:
            return await tool.execute(args)
        except TransientError:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return await self.fallback(tool_name, args)
```

### 11. Tool Approval on Everything

**Problem**: HITL required for all tool calls.

**Symptoms**:
- Slow response times
- User fatigue
- Poor UX

**Why It's Bad**:
- Unnecessary friction
- Defeats automation purpose
- High operational burden

**Solution**: Risk-based approval:
```python
class Tool:
    def __init__(self):
        self.requires_approval = self.is_dangerous()
    
    def is_dangerous(self):
        # Only require approval for risky operations
        return self.category in ['destructive', 'external', 'financial']
```

## Integration Anti-Patterns

### 12. Tight Coupling to LLM Provider

**Problem**: Hard-coded OpenAI calls everywhere.

**Symptoms**:
- Can't switch models
- Testing requires API calls
- No fallback options

**Why It's Bad**:
- Vendor lock-in
- Fragile tests
- Limited flexibility

**Solution**: Abstract LLM interface:
```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, prompt: str) -> str: pass

class OpenAIProvider(LLMProvider): pass
class AnthropicProvider(LLMProvider): pass
```

### 13. No Rate Limiting

**Problem**: Unlimited API calls.

**Symptoms**:
- 429 Too Many Requests errors
- Rate limit blocks
- Unpredictable behavior

**Why It's Bad**:
- Service disruption
- Poor user experience
- Potential account restrictions

**Solution**: Token bucket rate limiter:
```python
class RateLimiter:
    def __init__(self, rpm=60):
        self.bucket = Semaphore(rpm)
    
    async def acquire(self):
        await self.bucket.acquire()
```

### 14. Missing Observability

**Problem**: No logging, tracing, or metrics.

**Symptoms**:
- "It broke" with no details
- Can't reproduce issues
- No performance visibility

**Why It's Bad**:
- Impossible to debug
- No optimization basis
- Poor reliability

**Solution**: Comprehensive telemetry:
```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("agent.run")
async def run(self, task):
    span = trace.get_current_span()
    span.set_attribute("agent.id", self.id)
    span.set_attribute("task.type", task.type)
```

## Cost Anti-Patterns

### 15. No Cost Controls

**Problem**: No budget limits on LLM usage.

**Symptoms**:
- Surprise bills
- No way to cap spending
- Financial risk

**Why It's Bad**:
- Business risk
- No predictability
- Potential for runaway costs

**Solution**: Budget enforcement:
```python
class CostTracker:
    async def check_limit(self, user_id, estimated):
        if self.get_spending(user_id) + estimated > self.limit:
            raise BudgetExceededError()
```

### 16. Storing Everything

**Problem**: No data lifecycle management.

**Symptoms**:
- Database grows forever
- Query performance degrades
- Storage costs spiral

**Why It's Bad**:
- Cost inefficiency
- Performance degradation
- Compliance risks (data retention)

**Solution**: TTL and archival:
```python
class MemoryEntry:
    ttl: timedelta = timedelta(days=30)  # Default TTL
    archive_after: timedelta = timedelta(days=90)  # Move to cold storage
```

## Code Quality Anti-Patterns

### 17. Premature Optimization

**Problem**: Complex caching before profiling.

**Symptoms**:
- Over-engineered code
- Complex cache invalidation logic
- Bugs in optimization code

**Why It's Bad**:
- Complexity without benefit
- Hard to maintain
- May not improve performance

**Solution**: Measure first:
```python
# Profile first, then optimize hot paths
import cProfile
cProfile.run('agent.run(task)', 'profile.prof')
```

### 18. Magic Numbers

**Problem**: Undocumented constants.

**Symptoms**:
- What does 3600 mean?
- No context for values
- Hard to tune

**Solution**: Named constants:
```python
MAX_ITERATIONS = 10
TIMEOUT_SECONDS = 300
IMPORTANCE_THRESHOLD = 0.7
```

### 19. Ignoring Type Safety

**Problem**: All types as `Any` or no type hints.

**Symptoms**:
- Runtime type errors
- No IDE support
- Hard to refactor

**Solution**: Strong typing:
```python
from typing import TypedDict

class AgentRequest(TypedDict):
    session_id: str
    user_id: str
    message: str
    max_iterations: int
```

## Security Anti-Patterns

### 20. Secrets in Code

**Problem**: API keys hardcoded.

**Solution**: Environment variables or secrets manager:
```python
import os
api_key = os.environ['OPENAI_API_KEY']
```

### 21. No Input Validation

**Problem**: Trusting user input.

**Solution**: Validate and sanitize:
```python
from pydantic import BaseModel, validator

class ToolArgs(BaseModel):
    query: str
    
    @validator('query')
    def validate_query(cls, v):
        if len(v) > MAX_QUERY_LENGTH:
            raise ValueError('Query too long')
        return v.strip()
```

### 22. SQL/NoSQL Injection

**Problem**: String concatenation for queries.

**Solution**: Parameterized queries:
```python
# Bad
query = f"SELECT * FROM memory WHERE id = '{user_id}'"

# Good
result = await session.execute(
    select(MemoryEntry).where(MemoryEntry.id == user_id)
)
```

## Testing Anti-Patterns

### 23. Testing Only Happy Path

**Problem**: Only test successful cases.

**Solution**: Comprehensive test coverage:
```python
async def test_agent_tool_failure():
    tool = MockTool(side_effect=ToolError("Failed"))
    with pytest.raises(RecoveryAction):
        await agent.execute_with_fallback(tool)

async def test_agent_timeout():
    slow_tool = MockTool(delay=600)  # > timeout
    result = await agent.execute(slow_tool)  # Should handle
    assert result.fallback_used
```

### 24. No Integration Tests

**Problem**: Only unit tests with mocks.

**Solution**: Test integrations:
```python
@pytest.mark.integration
async def test_full_agent_execution():
    # Real LLM, real memory, real tools
    agent = Agent(memory=RealMemory(), llm=RealLLM())
    result = await agent.run(Task(message="Test"))
    assert result.complete
```

## Summary Checklist

| Category | Anti-Pattern | Impact | Prevention |
|----------|-------------|--------|------------|
| Architecture | God Object | Maintainability | Decompose agents |
| Memory | Single tier | Performance | Implement L1/L2/L3 |
| Integration | Tight coupling | Flexibility | Abstract interfaces |
| Cost | No controls | Financial risk | Budget enforcement |
| Security | No validation | Vulnerability | Input sanitization |
| Testing | Happy path only | Reliability | Comprehensive tests |
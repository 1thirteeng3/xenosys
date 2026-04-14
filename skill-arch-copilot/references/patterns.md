# Design Pattern Catalog

Comprehensive reference for design patterns commonly found in AI systems and multi-agent architectures.

## Structural Patterns

### Facade Pattern

**Intent**: Provide a unified interface to a complex subsystem.

**Use Cases in AI Systems**:
- Gateway layer hiding channel complexity (Telegram, Discord, Slack)
- Tool registry providing single access point
- Memory manager abstracting tiered storage

**Implementation Pattern**:
```python
class MemoryManager:
    """Facade for L1/L2/L3 memory tiers."""
    
    def __init__(self):
        self.l1 = L1Memory()
        self.l2 = L2Memory()
        self.l3 = L3Memory()
    
    async def search(self, query):
        # Orchestrates search across tiers
        results = []
        for tier in [self.l1, self.l2, self.l3]:
            tier_results = await tier.search(query)
            results.extend(tier_results)
        return self._deduplicate_and_rank(results)
```

### Adapter Pattern

**Intent**: Convert interface of a class into another interface clients expect.

**Use Cases in AI Systems**:
- Channel adapters for different messaging platforms
- LLM provider abstraction (OpenAI → Anthropic → local)
- Tool execution adapters

**Implementation Pattern**:
```python
class ChannelAdapter(ABC):
    """Base adapter for messaging channels."""
    
    @abstractmethod
    async def connect(self): pass
    
    @abstractmethod
    async def send(self, target, content): pass

class TelegramAdapter(ChannelAdapter):
    async def send(self, target, content):
        # Telegram-specific implementation
        await self.telegram.send_message(chat_id=target, text=content)
```

### Proxy Pattern

**Intent**: Provide a surrogate or placeholder for another object.

**Use Cases in AI Systems**:
- Rate limiting proxies
- Caching proxies for LLM responses
- HITL approval proxies

## Creational Patterns

### Factory Pattern

**Intent**: Create objects without specifying exact class.

**Use Cases in AI Systems**:
- Agent factory for different agent types
- Tool factory for dynamic tool creation
- Memory tier factory

**Implementation Pattern**:
```python
class AgentFactory:
    @staticmethod
    def create(agent_type: str, **kwargs) -> Agent:
        agents = {
            "orchestrator": OrchestratorAgent,
            "executor": ExecutorAgent,
            "reflector": ReflectorAgent,
        }
        return agents[agent_type](**kwargs)
```

### Builder Pattern

**Intent**: Construct complex objects step by step.

**Use Cases in AI Systems**:
- Building agent configurations
- Constructing prompt templates
- Composing memory queries

## Behavioral Patterns

### Observer Pattern

**Intent**: Define one-to-many dependency between objects.

**Use Cases in AI Systems**:
- Event bus subscriptions
- Agent notifications
- Audit logging

**Implementation Pattern**:
```python
class EventBus:
    def subscribe(self, event_types, handler):
        subscription_id = uuid()
        self._handlers[subscription_id] = (event_types, handler)
        return subscription_id
    
    async def publish(self, event):
        for sub_id, (types, handler) in self._handlers.items():
            if event.type in types or "*" in types:
                await handler(event)
```

### State Pattern

**Intent**: Allow object to alter behavior when state changes.

**Use Cases in AI Systems**:
- Agent lifecycle states (IDLE → THINKING → ACTING → COMPLETED)
- Session states
- Workflow progression

**Implementation Pattern**:
```python
class AgentState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_TOOL = "waiting_tool"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"

class Agent:
    async def run(self, request):
        self.state = AgentState.THINKING
        # State-specific behavior
```

### Strategy Pattern

**Intent**: Define family of algorithms, encapsulate each.

**Use Cases in AI Systems**:
- Different reasoning strategies (ReAct, CoT, Plan-and-Solve)
- Memory eviction strategies (LRU, LFU, TTL)
- Routing strategies

### Chain of Responsibility

**Intent**: Pass request along chain of handlers.

**Use Cases in AI Systems**:
- Middleware processing
- Request/response pipelines
- Event propagation

## Architectural Patterns

### Event-Driven Architecture

**Characteristics**:
- Decoupled components via events
- Asynchronous processing
- Event sourcing for state changes

**Implementation**:
```python
# Event definitions
@dataclass
class Event:
    type: EventType
    timestamp: datetime
    data: dict

# Event bus for pub/sub
class EventBus:
    async def publish(self, event: Event):
        for handler in self._get_handlers(event.type):
            await handler(event)
```

### Layered Architecture

**Layers in AI Systems**:
1. **Gateway Layer**: Protocol handling, authentication
2. **Orchestration Layer**: Agent coordination
3. **Execution Layer**: Tool/prompt execution
4. **Memory Layer**: Data persistence
5. **Learning Layer**: Model training, adaptation

### Hexagonal Architecture

**Ports and Adapters**:
- **Driving Ports**: HTTP, WebSocket, CLI
- **Driven Ports**: LLM providers, databases, external APIs
- **Adapters**: Implement port interfaces

## Concurrency Patterns

### Producer-Consumer

**Use Cases**:
- Event queue processing
- Background job execution
- Batch processing

**Implementation**:
```python
class EventBus:
    async def start(self):
        self._processor = asyncio.create_task(self._process_events())
    
    async def _process_events(self):
        while True:
            event = await self._queue.get()
            await self._dispatch(event)
```

### Semaphore for Resource Pooling

**Use Cases**:
- Limiting concurrent LLM calls
- Connection pool management
- Rate limiting

## Data Patterns

### CQRS (Command Query Responsibility Segregation)

**Use Cases**:
- Separate read (retrieval) from write (logging) in memory
- Different views for different consumers

### Repository Pattern

**Use Cases**:
- Abstract memory tier access
- Tool storage and retrieval

## Anti-Patterns to Avoid

1. **God Object**: Single agent handling everything
2. **Spaghetti Code**: Unstructured event handling
3. **Callback Hell**: Nested async callbacks
4. **Shared Mutable State**: Race conditions in memory
5. **Premature Optimization**: Complex caching before profiling
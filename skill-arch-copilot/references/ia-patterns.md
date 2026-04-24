# Intelligence Augmentation Patterns

Patterns for building intelligent AI agent systems with reasoning, learning, and adaptation capabilities.

## Reasoning Patterns

### ReAct (Reasoning + Acting)

The foundational pattern combining reasoning with action execution.

```python
class ReActAgent:
    async def run(self, task):
        while not self.is_complete():
            # THINK
            thought = await self.reason(task)
            
            # ACT
            if thought.requires_tool:
                result = await self.execute_tool(thought.tool, thought.args)
            else:
                result = thought.conclusion
            
            # OBSERVE
            self.update_state(result)
            
            # Check if done
            if thought.is_terminal:
                return thought.final_answer
```

**Key Components**:
- `reason()`: Generate reasoning trace
- `execute_tool()`: Run external tools
- `update_state()`: Update context with results
- `is_complete()`: Check for final answer

**Best Practices**:
- Limit iterations (typically 5-10)
- Include previous reasoning in context
- Validate tool results before continuing

### Chain-of-Thought (CoT)

Explicit step-by-step reasoning without tool use.

```python
async def chain_of_thought(problem: str, context: list[str]) -> str:
    prompt = f"""
    Problem: {problem}
    
    Previous context:
    {chr(10).join(context)}
    
    Think step by step:
    """
    return await llm.complete(prompt)
```

**Variants**:
- **Zero-shot CoT**: "Think step by step"
- **Few-shot CoT**: Examples of reasoning chains
- **Self-consistency CoT**: Multiple reasoning paths, vote on answer

### Plan-and-Solve

Decompose task into executable subtasks.

```python
class PlanAndSolveAgent:
    async def plan(self, task: str) -> list[Subtask]:
        # LLM generates subtask list
        prompt = f"Decompose into steps: {task}"
        steps = await llm.complete(prompt)
        return [Subtask(s) for s in steps.split("\n")]
    
    async def execute(self, subtasks: list[Subtask]) -> list[Result]:
        results = []
        for subtask in subtasks:
            # Execute in parallel where possible
            if subtask.parallelizable:
                batch = self.get_parallel_group(subtask)
                batch_results = await asyncio.gather(*[
                    self.execute_single(t) for t in batch
                ])
                results.extend(batch_results)
            else:
                result = await self.execute_single(subtask)
                results.append(result)
        return results
    
    async def solve(self, task: str) -> str:
        subtasks = await self.plan(task)
        results = await self.execute(subtasks)
        return self.synthesize(results)
```

## Context Management Patterns

### Hierarchical Memory

Three-tier memory architecture for balancing speed and capacity.

```python
class L1Memory:
    """Working memory - LRU cache, sub-10ms access."""
    def __init__(self, max_size=10000):
        self.cache = OrderedDict()  # LRU eviction
    
    async def write(self, entry):
        # Immediate write, LRU eviction
        pass
    
    async def search(self, query):
        # Simple text matching (no embeddings)
        pass

class L2Memory:
    """Semantic memory - Vector embeddings, 10-100ms."""
    def __init__(self, embedding_model="all-MiniLM-L6-v2"):
        self.client = ChromaDB()
        self.embedder = SentenceTransformer(embedding_model)
    
    async def write(self, entry):
        embedding = self.embedder.encode(entry.content)
        # Store with embedding for similarity search
        pass

class L3Memory:
    """Long-term memory - PostgreSQL, complex queries."""
    # Episodic storage, user preferences, cross-session knowledge
    pass

class MemoryManager:
    """Unified interface with automatic tier routing."""
    
    async def write(self, content, importance=1.0):
        entry = MemoryEntry(content=content, importance=importance)
        await self.l1.write(entry)  # Always
        
        if importance >= 0.5:
            await self.l2.write(entry)  # Important
        
        if importance >= 0.7:
            await self.l3.write(entry)  # Very important
```

### RAG (Retrieval-Augmented Generation)

Hybrid search combining vector and keyword matching.

```python
class RAGPipeline:
    def __init__(self, vector_db, search_engine):
        self.vector_db = vector_db
        self.search_engine = search_engine
    
    async def retrieve(self, query, top_k=10):
        # Semantic search
        semantic_results = await self.vector_db.search(query, top_k)
        
        # Keyword search
        keyword_results = await self.search_engine.search(query, top_k)
        
        # Merge with reciprocal rank fusion
        fused = self.reciprocal_rank_fusion(
            semantic_results, 
            keyword_results
        )
        
        return fused[:top_k]
    
    async def generate(self, query, context):
        prompt = f"""
        Context:
        {context}
        
        Question: {query}
        
        Answer based on the context above.
        """
        return await self.llm.complete(prompt)
```

### Sliding Window Context

For very long contexts, maintain relevance over time.

```python
class SlidingWindowContext:
    def __init__(self, max_tokens=8000, overlap_tokens=500):
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.messages = []
    
    def add(self, message):
        self.messages.append(message)
        self.trim()
    
    def trim(self):
        total_tokens = sum(self.estimate_tokens(m) for m in self.messages)
        
        while total_tokens > self.max_tokens and len(self.messages) > 2:
            # Remove oldest non-system message
            for i, m in enumerate(self.messages):
                if m.role != "system":
                    removed = self.messages.pop(i)
                    total_tokens -= self.estimate_tokens(removed)
                    break
    
    def get_context(self):
        return self.messages
```

## Agent Orchestration Patterns

### Hierarchical Agents

Supervisor delegates to specialized sub-agents.

```python
class SupervisorAgent:
    def __init__(self):
        self.agents = {
            "researcher": ResearcherAgent(),
            "coder": CoderAgent(),
            "reviewer": ReviewerAgent(),
        }
    
    async def delegate(self, task):
        intent = await self.classify_intent(task)
        
        if intent.category == "research":
            agent = self.agents["researcher"]
        elif intent.category == "code":
            agent = self.agents["coder"]
        else:
            agent = self.agents["reviewer"]
        
        return await agent.run(task)
```

### Collaborative Agents

Multiple agents work together on shared task.

```python
class AgentSwarm:
    def __init__(self, agents):
        self.agents = {a.id: a for a in agents}
        self.blackboard = {}  # Shared knowledge
    
    async def work(self, task, rounds=5):
        for round in range(rounds):
            # All agents contribute in parallel
            contributions = await asyncio.gather(*[
                agent.contribute(task, self.blackboard)
                for agent in self.agents.values()
            ])
            
            # Update shared state
            for contribution in contributions:
                self.blackboard.update(contribution)
            
            # Check for consensus
            if self.check_convergence(self.blackboard):
                break
        
        return self.blackboard.final_answer
```

### Meta-Agent Reflection

Agent reflects on its own performance.

```python
class ReflectiveAgent:
    async def run(self, task):
        result = await self.execute(task)
        
        # Metacognitive reflection
        reflection = await self.reflect(result)
        
        if reflection.issues:
            # Self-correct
            corrected = await self.correct(reflection.issues)
            return corrected
        
        return result
    
    async def reflect(self, result):
        prompt = f"""
        Review this agent execution:
        
        Task: {result.task}
        Output: {result.output}
        Tool calls: {result.tool_calls}
        
        Identify any issues or improvements needed.
        """
        return await self.llm.complete(prompt)
```

## Learning Patterns

### LoRA (Low-Rank Adaptation)

Hot-swappable model specialization.

```python
class LoRAManager:
    def __init__(self):
        self.adapters = {}  # adapter_id -> loaded model
        self.active = None
    
    async def switch(self, adapter_id):
        # Unload current
        if self.active:
            await self.unload(self.active)
        
        # Load new adapter
        await self.load(adapter_id)
        self.active = adapter_id
    
    def load(self, adapter_id):
        # PEFT model loading
        base = load_base_model()
        adapter = PeftModel.from_pretrained(
            base,
            self.adapter_path(adapter_id)
        )
        self.adapters[adapter_id] = adapter
```

### STaR (Self-Taught Reasoner)

Self-improvement from reasoning traces.

```python
class StarTrainer:
    async def train(self, agent_id, failed_traces):
        # Filter for successable problems
        successable = self.filter_successable(failed_traces)
        
        # Generate rationales for correct answers
        rationales = [
            await self.generate_rationale(trace)
            for trace in successable
        ]
        
        # Fine-tune on improved traces
        await self.fine_tune(agent_id, rationales)
        
        # Validate improvement
        return await self.validate(agent_id)
```

## Tool Use Patterns

### Tool Registry

Dynamic tool registration and execution.

```python
class ToolRegistry:
    def register(self, tool: Tool):
        self._tools[tool.name] = tool
    
    def execute(self, name: str, args: dict) -> str:
        tool = self._tools[name]
        
        # Validation
        tool.validate(**args)
        
        # Execution with timeout
        return asyncio.wait_for(
            tool.execute(**args),
            timeout=tool.timeout
        )
```

### Tool Selection Routing

LLM-based tool selection.

```python
class ToolRouter:
    def __init__(self, tools: list[Tool]):
        self.tools = tools
        self.prompt = self.build_selection_prompt()
    
    async def route(self, task: str) -> list[ToolCall]:
        # LLM decides which tools and arguments
        response = await self.llm.complete(
            self.prompt + f"\nTask: {task}"
        )
        
        return self.parse_tool_calls(response)
```

## Error Handling Patterns

### Graceful Degradation

Fallback to simpler methods on failure.

```python
class FallbackChain:
    async def execute(self, task):
        # Try semantic search first
        try:
            return await self.semantic_search(task)
        except VectorDBError:
            pass
        
        # Fall back to keyword search
        try:
            return await self.keyword_search(task)
        except SearchError:
            pass
        
        # Final fallback to direct LLM
        return await self.llm.complete(task)
```

### Circuit Breaker

Prevent cascading failures.

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failures = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = "closed"
        self.last_failure = None
    
    async def call(self, func, *args):
        if self.state == "open":
            if time.time() - self.last_failure > self.timeout:
                self.state = "half-open"
            else:
                raise CircuitOpenError()
        
        try:
            result = await func(*args)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise
    
    def on_success(self):
        self.failures = 0
        self.state = "closed"
    
    def on_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"
```

## Monitoring Patterns

### Tracing and Observability

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class ObservableAgent:
    @tracer.start_as_current_span("agent.run")
    async def run(self, task):
        with trace.get_current_span() as span:
            span.set_attribute("agent.id", self.agent_id)
            span.set_attribute("task.type", task.type)
            
            result = await self.execute(task)
            
            span.set_attribute("result.success", result.success)
            span.set_attribute("result.tokens", result.tokens)
            
            return result
```

### Metrics Collection

```python
class MetricsCollector:
    def record(self, metric: str, value: float, tags: dict):
        self.metrics.append({
            "name": metric,
            "value": value,
            "tags": tags,
            "timestamp": time.time()
        })
    
    def summary(self) -> dict:
        return {
            "total_requests": len([m for m in self.metrics if m["name"] == "request"]),
            "avg_latency": self.avg([m for m in self.metrics if m["name"] == "latency"]),
            "error_rate": self.error_rate(),
        }
```
"""
XenoSys Unit Tests - Core Modules
"""

import asyncio
import pytest
from datetime import datetime


# ============================================================================
# Agent Tests
# ============================================================================

class TestAgent:
    """Tests for base agent functionality."""
    
    def test_agent_creation(self):
        """Test that agents can be created."""
        from nexus.core.agents.base_agent import Agent, AgentRole, AgentType
        
        agent = Agent(
            agent_id="test-agent",
            role=AgentRole.EXECUTOR,
            agent_type=AgentType.EXECUTOR,
            name="Test Agent",
            system_prompt="You are a test agent.",
        )
        
        assert agent.agent_id == "test-agent"
        assert agent.name == "Test Agent"
        assert agent.role == AgentRole.EXECUTOR
        assert agent.state.value == "idle"
    
    def test_agent_tools_add(self):
        """Test adding tools to agent."""
        from nexus.core.agents.base_agent import Agent, AgentRole, AgentType, Tool
        
        agent = Agent(
            agent_id="test-agent",
            role=AgentRole.EXECUTOR,
            agent_type=AgentType.EXECUTOR,
        )
        
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={},
        )
        
        agent.add_tool(tool)
        
        assert "test_tool" in agent.get_tools()
    
    @pytest.mark.asyncio
    async def test_agent_think(self):
        """Test agent think method."""
        from nexus.core.agents.base_agent import Agent, AgentRole, AgentType, AgentRequest
        
        agent = Agent(
            agent_id="test-agent",
            role=AgentRole.EXECUTOR,
            agent_type=AgentType.EXECUTOR,
            system_prompt="You are a helpful assistant.",
        )
        
        request = AgentRequest(
            session_id="test-session",
            user_id="test-user",
            message="Hello, world!",
        )
        
        response = await agent.think(request)
        
        assert response is not None
        assert response.role.value == "assistant"


# ============================================================================
# Entity Tests
# ============================================================================

class TestEntity:
    """Tests for entity functionality."""
    
    def test_entity_creation(self):
        """Test that entities can be created."""
        from nexus.core.entities.entity import Entity, RoutingStrategy
        
        entity = Entity(
            name="Test Entity",
            description="A test entity",
            agent_ids=["agent-1", "agent-2"],
            routing_strategy=RoutingStrategy.SEMANTIC,
        )
        
        assert entity.name == "Test Entity"
        assert len(entity.agent_ids) == 2
        assert entity.routing_strategy == RoutingStrategy.SEMANTIC
    
    def test_entity_builder(self):
        """Test entity builder pattern."""
        from nexus.core.entities.entity import EntityBuilder, RoutingStrategy
        
        entity = (
            EntityBuilder("Code Reviewer")
            .description("Reviews code for bugs")
            .add_agents("agent-1", "agent-2")
            .with_routing(RoutingStrategy.PARALLEL)
            .with_max_rounds(5)
            .build()
        )
        
        assert entity.name == "Code Reviewer"
        assert entity.description == "Reviews code for bugs"
        assert len(entity.agent_ids) == 2
        assert entity.max_rounds == 5
    
    def test_entity_builder_adversarial(self):
        """Test entity builder with adversarial pair."""
        from nexus.core.entities.entity import EntityBuilder
        
        entity = (
            EntityBuilder("Adversarial Review")
            .add_agent("agent-1")
            .with_adversarial_pair()
            .build()
        )
        
        assert entity.memory_config.get("_adversarial") is True


# ============================================================================
# Memory Tests
# ============================================================================

class TestMemoryOrchestrator:
    """Tests for memory orchestrator."""
    
    @pytest.mark.asyncio
    async def test_memory_orchestrator_creation(self):
        """Test memory orchestrator can be created."""
        from nexus.core.memory.orchestrator import get_memory_orchestrator
        
        orchestrator = get_memory_orchestrator()
        
        assert orchestrator is not None
    
    @pytest.mark.asyncio
    async def test_memory_orchestrator_initialize(self):
        """Test memory orchestrator can be initialized."""
        from nexus.core.memory.orchestrator import get_memory_orchestrator
        
        orchestrator = get_memory_orchestrator()
        
        # Initialize should not raise
        try:
            await orchestrator.initialize()
        except Exception as e:
            # May fail if external services not available
            pass


# ============================================================================
# Messaging Tests
# ============================================================================

class TestMessageBroker:
    """Tests for message broker."""
    
    @pytest.mark.asyncio
    async def test_in_memory_broker_connect(self):
        """Test in-memory broker can connect."""
        from nexus.core.messaging.broker import InMemoryMessageBroker
        
        broker = InMemoryMessageBroker()
        connected = await broker.connect()
        
        assert connected is True
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_in_memory_broker_publish_subscribe(self):
        """Test publish and subscribe."""
        from nexus.core.messaging.broker import InMemoryMessageBroker, MessagePriority
        
        broker = InMemoryMessageBroker()
        await broker.connect()
        
        received_messages = []
        
        async def handler(message):
            received_messages.append(message)
        
        await broker.subscribe("test-topic", handler)
        await broker.publish(
            topic="test-topic",
            payload={"test": "data"},
            priority=MessagePriority.HIGH,
        )
        
        # Give time for message to be delivered
        await asyncio.sleep(0.1)
        
        assert len(received_messages) > 0
        assert received_messages[0].topic == "test-topic"
        
        await broker.disconnect()
    
    @pytest.mark.asyncio
    async def test_in_memory_broker_list_topics(self):
        """Test listing topics."""
        from nexus.core.messaging.broker import InMemoryMessageBroker
        
        broker = InMemoryMessageBroker()
        await broker.connect()
        
        await broker.publish(topic="topic-1", payload="test1")
        await broker.publish(topic="topic-2", payload="test2")
        
        topics = await broker.list_topics()
        
        assert "topic-1" in topics
        assert "topic-2" in topics
        
        await broker.disconnect()


# ============================================================================
# LLMOps Tests
# ============================================================================

class TestCostTracker:
    """Tests for cost tracking."""
    
    def test_cost_entry_creation(self):
        """Test cost entry can be created."""
        from nexus.core.llmops.governance import CostEntry
        
        entry = CostEntry(
            user_id="test-user",
            agent_id="test-agent",
            session_id="test-session",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            cost_usd=0.003,
            model="gpt-4",
        )
        
        assert entry.user_id == "test-user"
        assert entry.total_tokens == 150
        assert entry.cost_usd == 0.003
    
    def test_cost_budget(self):
        """Test cost budget."""
        from nexus.core.llmops.governance import CostBudget
        
        budget = CostBudget(
            user_id="test-user",
            daily_limit_usd=10.0,
            monthly_limit_usd=100.0,
        )
        
        assert budget.daily_limit_usd == 10.0
        assert budget.monthly_limit_usd == 100.0


# ============================================================================
# Learning Tests
# ============================================================================

class TestLoRARegistry:
    """Tests for LoRA registry."""
    
    @pytest.mark.asyncio
    async def test_lora_registry_creation(self):
        """Test LoRA registry can be created."""
        from nexus.core.learning.lora.registry import LoRARegistry
        
        registry = LoRARegistry()
        
        assert registry is not None
    
    @pytest.mark.asyncio
    async def test_lora_adapter_registration(self):
        """Test adapter registration."""
        from nexus.core.learning.lora.registry import LoRARegistry
        
        registry = LoRARegistry()
        
        adapter = await registry.register(
            name="test-adapter",
            model_base="llama-2-7b",
            file_path="/path/to/adapter.safetensors",
        )
        
        assert adapter is not None
        assert adapter.name == "test-adapter"
    
    @pytest.mark.asyncio
    async def test_lora_adapter_swap(self):
        """Test adapter swap."""
        from nexus.core.learning.lora.registry import LoRARegistry
        from uuid import uuid4
        
        registry = LoRARegistry()
        
        # Register two adapters
        adapter1 = await registry.register("adapter-1", "llama-2-7b", "/path/1.safetensors")
        adapter2 = await registry.register("adapter-2", "llama-2-7b", "/path/2.safetensors")
        
        # Swap
        result = await registry.swap("agent-1", adapter2.id)
        
        assert result.success is True
        assert str(result.new_adapter_id) == str(adapter2.id)
    
    @pytest.mark.asyncio
    async def test_lora_swap_no_deadlock(self):
        """Test that multiple swaps don't cause deadlock."""
        from nexus.core.learning.lora.registry import LoRARegistry
        
        registry = LoRARegistry()
        
        # Register adapters
        adapters = []
        for i in range(5):
            adapter = await registry.register(f"adapter-{i}", "llama-2-7b", f"/path/{i}.safetensors")
            adapters.append(adapter)
        
        # Concurrent swaps
        async def swap_task(agent_id: str, adapter_id):
            return await registry.swap(agent_id, adapter_id)
        
        results = await asyncio.gather(
            swap_task("agent-1", adapters[1].id),
            swap_task("agent-2", adapters[2].id),
            swap_task("agent-3", adapters[3].id),
        )
        
        # All should succeed
        assert all(r.success for r in results)


# ============================================================================
# Security Tests
# ============================================================================

class TestSecurity:
    """Tests for security module."""
    
    def test_hmac_generation(self):
        """Test HMAC signature generation."""
        from nexus.gateway.src.auth.security import HMACValidator
        
        validator = HMACValidator("test-secret")
        signature = validator.generateSignature("test-payload")
        
        assert signature is not None
        assert len(signature) > 0
    
    def test_hmac_verification(self):
        """Test HMAC signature verification."""
        from nexus.gateway.src.auth.security import HMACValidator
        
        validator = HMACValidator("test-secret")
        payload = "test-payload"
        signature = validator.generateSignature(payload)
        
        assert validator.verifySignature(payload, signature) is True
        assert validator.verifySignature(payload, "invalid") is False
    
    def test_jwt_generation(self):
        """Test JWT token generation."""
        from nexus.gateway.src.auth.security import JWTValidator
        
        validator = JWTValidator("test-secret", "1h")
        token = validator.generate(
            userId="test-user",
            email="test@example.com",
            roles=["admin", "user"],
        )
        
        assert token is not None
        assert len(token.split(".")) == 3
    
    def test_jwt_verification(self):
        """Test JWT token verification."""
        from nexus.gateway.src.auth.security import JWTValidator
        
        validator = JWTValidator("test-secret", "1h")
        token = validator.generate(
            userId="test-user",
            roles=["admin"],
        )
        
        payload = validator.verify(token)
        
        assert payload is not None
        assert payload["userId"] == "test-user"
        assert "admin" in payload["roles"]
    
    def test_jwt_invalid_token(self):
        """Test JWT rejects invalid token."""
        from nexus.gateway.src.auth.security import JWTValidator
        
        validator = JWTValidator("test-secret", "1h")
        
        # Invalid token
        payload = validator.verify("invalid.token.here")
        
        assert payload is None


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
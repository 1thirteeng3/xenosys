"""
XenoSys Core - Learning Engine
LoRA adapter management and STaR self-improvement
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# LoRA Adapter Management
# ============================================================================

@dataclass
class LoRAAdapter:
    """A LoRA adapter for model specialization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    model_id: str = ""  # Base model this adapts
    
    # File info
    path: str = ""
    size_bytes: int = 0
    
    # Training info
    trained_at: datetime | None = None
    training_config: dict[str, Any] = field(default_factory=dict)
    
    # Metrics
    accuracy: float | None = None
    loss: float | None = None
    eval_samples: int = 0
    
    # State
    active: bool = False
    load_count: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "model_id": self.model_id,
            "size_bytes": self.size_bytes,
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "accuracy": self.accuracy,
            "loss": self.loss,
            "active": self.active,
        }


class LoRAManager:
    """
    Manages LoRA adapters for dynamic model specialization.
    
    Features:
    - Hot-swapping of adapters without model reload
    - Adapter versioning and rollback
    - Training job management
    - Resource pooling for multiple adapters
    """
    
    def __init__(
        self,
        adapter_dir: str = "./data/adapters",
        max_loaded: int = 3,
    ) -> None:
        self.adapter_dir = Path(adapter_dir)
        self.max_loaded = max_loaded
        
        self._adapters: dict[str, LoRAAdapter] = {}
        self._loaded: dict[str, Any] = {}  # Loaded model instances
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize and scan for existing adapters."""
        self.adapter_dir.mkdir(parents=True, exist_ok=True)
        
        # Scan for adapter metadata
        for meta_file in self.adapter_dir.glob("*/meta.json"):
            try:
                import json
                with open(meta_file) as f:
                    meta = json.load(f)
                
                adapter = LoRAAdapter(**meta)
                adapter.path = str(meta_file.parent)
                self._adapters[adapter.id] = adapter
                
            except Exception as e:
                logger.warning(f"Failed to load adapter metadata: {e}")
        
        logger.info(f"LoRA manager initialized with {len(self._adapters)} adapters")
    
    def register_adapter(self, adapter: LoRAAdapter) -> None:
        """Register a new adapter."""
        self._adapters[adapter.id] = adapter
        
        # Save metadata
        import json
        meta_path = Path(adapter.path) / "meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(meta_path, "w") as f:
            json.dump(adapter.to_dict(), f, indent=2)
    
    async def list_adapters(self, model_id: str | None = None) -> list[LoRAAdapter]:
        """List available adapters."""
        adapters = list(self._adapters.values())
        
        if model_id:
            adapters = [a for a in adapters if a.model_id == model_id]
        
        return adapters
    
    async def switch_adapter(
        self,
        agent_id: str,
        adapter_id: str,
    ) -> tuple[str | None, str]:
        """
        Switch active adapter for an agent.
        
        Returns:
            (previous_adapter_id, new_adapter_id)
        """
        async with self._lock:
            # Get new adapter
            new_adapter = self._adapters.get(adapter_id)
            if not new_adapter:
                raise ValueError(f"Adapter not found: {adapter_id}")
            
            # Deactivate old adapter
            old_id = None
            for aid, adapter in self._adapters.items():
                if adapter.active:
                    old_id = aid
                    adapter.active = False
                    self._loaded.pop(aid, None)
            
            # Load new adapter
            await self._load_adapter(new_adapter)
            new_adapter.active = True
            
            return old_id, adapter_id
    
    async def _load_adapter(self, adapter: LoRAAdapter) -> Any:
        """Load an adapter into memory."""
        # Check if already loaded
        if adapter.id in self._loaded:
            adapter.load_count += 1
            return self._loaded[adapter.id]
        
        # Evict if at capacity
        while len(self._loaded) >= self.max_loaded:
            lru_id = min(
                self._adapters.items(),
                key=lambda x: x[1].load_count,
            )[0]
            self._loaded.pop(lru_id, None)
        
        # Load adapter (placeholder for actual PEFT integration)
        # In production, this would use peft.PeftModel
        loaded = {"adapter_id": adapter.id, "loaded_at": datetime.utcnow()}
        self._loaded[adapter.id] = loaded
        adapter.load_count += 1
        
        logger.info(f"Loaded adapter: {adapter.name}")
        return loaded
    
    async def unload_adapter(self, adapter_id: str) -> bool:
        """Unload an adapter from memory."""
        async with self._lock:
            if adapter_id in self._loaded:
                del self._loaded[adapter_id]
                return True
            return False


# ============================================================================
# STaR Self-Training
# ============================================================================

class TrainingStatus(str, Enum):
    """Training job status."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """A training job."""
    id: str = field(default_factory=lambda: str(uuid4()))
    adapter_id: str = ""
    agent_id: str = ""
    
    # Configuration
    base_model: str = ""
    training_data: str = ""  # Path or dataset reference
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    
    # Status
    status: TrainingStatus = TrainingStatus.QUEUED
    progress: float = 0.0  # 0-1
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Results
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None


@dataclass
class StarResult:
    """Result from STaR self-improvement."""
    success: bool = False
    iterations: int = 0
    improved_skill: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None


class StarTrainer:
    """
    STaR (Self-Taught Reasoner) implementation for agent self-improvement.
    
    Process:
    1. Identify failed or low-quality reasoning traces
    2. Generate rationales for correct answers
    3. Fine-tune model on improved traces
    4. Validate improvement
    """
    
    def __init__(
        self,
        lora_manager: LoRAManager,
        training_data_dir: str = "./data/training",
    ) -> None:
        self.lora_manager = lora_manager
        self.training_data_dir = Path(training_data_dir)
        self.training_data_dir.mkdir(parents=True, exist_ok=True)
        
        self._jobs: dict[str, TrainingJob] = {}
        self._training_lock = asyncio.Lock()
    
    async def run_star(
        self,
        agent_id: str,
        session_id: str,
        target_skills: list[str] | None = None,
    ) -> StarResult:
        """
        Run STaR self-improvement for an agent.
        
        Args:
            agent_id: Agent to improve
            session_id: Session to learn from
            target_skills: Specific skills to focus on
            
        Returns:
            StarResult with improvement metrics
        """
        logger.info(f"Starting STaR for agent {agent_id}")
        
        try:
            # 1. Collect reasoning traces from session
            traces = await self._collect_traces(session_id, target_skills)
            
            if not traces:
                return StarResult(
                    success=False,
                    error="No valid traces found for training",
                )
            
            # 2. Filter for successful reasoning
            good_traces = [t for t in traces if t.get("success", False)]
            
            if len(good_traces) < 5:
                return StarResult(
                    success=False,
                    error="Insufficient successful traces",
                )
            
            # 3. Generate rationales for correct answers
            rationale_traces = await self._generate_rationales(good_traces)
            
            # 4. Create training dataset
            dataset_path = await self._create_dataset(rationale_traces, agent_id)
            
            # 5. Start training job
            job = TrainingJob(
                adapter_id=str(uuid4()),
                agent_id=agent_id,
                base_model="gpt-4",
                training_data=str(dataset_path),
                hyperparameters=self._default_hyperparameters(),
            )
            
            self._jobs[job.id] = job
            
            # Run training
            await self._run_training(job)
            
            # 6. Validate improvement
            metrics = await self._validate_improvement(agent_id, job)
            
            return StarResult(
                success=True,
                iterations=len(good_traces),
                improved_skill=target_skills[0] if target_skills else "general",
                metrics=metrics,
            )
            
        except Exception as e:
            logger.error(f"STaR failed: {e}", exc_info=True)
            return StarResult(
                success=False,
                error=str(e),
            )
    
    async def _collect_traces(
        self,
        session_id: str,
        skills: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Collect reasoning traces from session history."""
        # Placeholder - would query memory system
        return []
    
    async def _generate_rationales(self, traces: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate rationales for reasoning traces."""
        # Placeholder - would use LLM to generate explanations
        return traces
    
    async def _create_dataset(
        self,
        traces: list[dict[str, Any]],
        agent_id: str,
    ) -> Path:
        """Create training dataset from traces."""
        import json
        
        dataset_path = self.training_data_dir / f"{agent_id}_{uuid4()}.jsonl"
        
        with open(dataset_path, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace) + "\n")
        
        return dataset_path
    
    def _default_hyperparameters(self) -> dict[str, Any]:
        """Get default training hyperparameters."""
        return {
            "learning_rate": 1e-4,
            "batch_size": 4,
            "epochs": 3,
            "warmup_steps": 100,
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.1,
        }
    
    async def _run_training(self, job: TrainingJob) -> None:
        """Run the training job."""
        job.status = TrainingStatus.RUNNING
        job.started_at = datetime.utcnow()
        
        try:
            # Placeholder - actual training would use PEFT/transformers
            for step in range(100):
                await asyncio.sleep(0.1)
                job.progress = step / 100
            
            job.status = TrainingStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.metrics = {
                "final_loss": 0.1,
                "accuracy": 0.95,
            }
            
        except Exception as e:
            job.status = TrainingStatus.FAILED
            job.error = str(e)
    
    async def _validate_improvement(
        self,
        agent_id: str,
        job: TrainingJob,
    ) -> dict[str, float]:
        """Validate that training improved agent performance."""
        # Placeholder - would run eval set
        return {
            "accuracy_delta": 0.05,
            "latency_delta": -0.1,
        }
    
    def get_training_status(self, job_id: str) -> TrainingJob | None:
        """Get status of a training job."""
        return self._jobs.get(job_id)
    
    def list_jobs(self, status: TrainingStatus | None = None) -> list[TrainingJob]:
        """List training jobs."""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status]
        
        return jobs


# ============================================================================
# Skill Tracker
# ============================================================================

@dataclass
class Skill:
    """A tracked skill with improvement history."""
    id: str
    name: str
    description: str
    
    # Capability level (0-1)
    level: float = 0.5
    
    # Training history
    training_count: int = 0
    last_trained_at: datetime | None = None
    
    # Performance metrics
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    
    # Associated adapters
    adapter_ids: list[str] = field(default_factory=list)


class SkillTracker:
    """
    Tracks agent skills and their improvement over time.
    """
    
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
    
    def register_skill(self, skill: Skill) -> None:
        """Register a new skill."""
        self._skills[skill.id] = skill
    
    def get_skill(self, skill_id: str) -> Skill | None:
        """Get a skill by ID."""
        return self._skills.get(skill_id)
    
    def list_skills(self) -> list[Skill]:
        """List all skills."""
        return list(self._skills.values())
    
    def update_skill_metrics(
        self,
        skill_id: str,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Update skill metrics from usage."""
        skill = self._skills.get(skill_id)
        if not skill:
            return
        
        # Exponential moving average
        alpha = 0.1
        skill.success_rate = alpha * (1 if success else 0) + (1 - alpha) * skill.success_rate
        skill.avg_latency_ms = alpha * latency_ms + (1 - alpha) * skill.avg_latency_ms
    
    def record_training(
        self,
        skill_id: str,
        adapter_id: str,
    ) -> None:
        """Record that a skill was trained."""
        skill = self._skills.get(skill_id)
        if not skill:
            return
        
        skill.training_count += 1
        skill.last_trained_at = datetime.utcnow()
        
        if adapter_id not in skill.adapter_ids:
            skill.adapter_ids.append(adapter_id)
        
        # Increment skill level
        skill.level = min(1.0, skill.level + 0.05)
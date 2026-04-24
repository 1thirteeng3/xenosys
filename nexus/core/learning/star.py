"""
XenoSys Learning Engine - STaR Module
Self-Taught Reasoning for agent self-improvement.

STaR: https://arxiv.org/abs/2310.08560
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# STaR Types
# ============================================================================

@dataclass
class StarExample:
    """A STaR training example."""
    id: UUID = field(default_factory=uuid4)
    question: str = ""
    rationale: str = ""  # Reasoning trace
    answer: str = ""
    is_correct: bool = False
    agent_id: str = ""
    session_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StarCycleResult:
    """Result of a STaR cycle."""
    cycle_id: str
    examples_generated: int
    examples_correct: int
    accuracy_before: float
    accuracy_after: float
    improvement_score: float
    dataset_size: int


# ============================================================================
# STaR Engine
# ============================================================================

class StarEngine:
    """
    STaR (Self-Taught Reasoning) engine.
    
    STaR works by:
    1. Let the agent attempt to solve problems
    2. Generate rationales for correct solutions
    3. Fine-tune on these rationales
    4. Repeat to improve
    
    Provides:
    - Rationale generation
    - Dataset collection
    - Self-improvement cycles
    - Dreaming integration
    """
    
    def __init__(self):
        self._examples: List[StarExample] = []
        self._cycle_count = 0
        self._lock = asyncio.Lock()
    
    # =========================================================================
    # Example Collection
    # =========================================================================
    
    async def add_example(
        self,
        question: str,
        rationale: str,
        answer: str,
        is_correct: bool,
        agent_id: str,
        session_id: str,
    ) -> StarExample:
        """Add a STaR example from agent interaction."""
        example = StarExample(
            question=question,
            rationale=rationale,
            answer=answer,
            is_correct=is_correct,
            agent_id=agent_id,
            session_id=session_id,
        )
        
        async with self._lock:
            self._examples.append(example)
        
        logger.info(f"Added STaR example: {example.id} (correct={is_correct})")
        return example
    
    async def extract_from_session(
        self,
        session_id: str,
        agent_id: str,
        messages: List[Dict[str, Any]],
    ) -> List[StarExample]:
        """Extract STaR examples from a session."""
        examples = []
        
        # Extract question-answer pairs from messages
        for i, msg in enumerate(messages):
            if msg.get("role") != "assistant":
                continue
            
            # Find corresponding user message
            if i > 0 and messages[i-1].get("role") == "user":
                question = messages[i-1].get("content", "")
                answer = msg.get("content", "")
                
                # Check if final answer (simplified)
                is_correct = self._check_answer(answer)
                
                # Generate rationale (placeholder - would use actual reasoning)
                rationale = self._generate_rationale(question, answer)
                
                example = await self.add_example(
                    question=question,
                    rationale=rationale,
                    answer=answer,
                    is_correct=is_correct,
                    agent_id=agent_id,
                    session_id=session_id,
                )
                examples.append(example)
        
        return examples
    
    def _check_answer(self, answer: str) -> bool:
        """Check if answer is likely correct (placeholder)."""
        # In production, would verify against ground truth
        # For now, assume correct if answer is non-empty
        return len(answer.strip()) > 0
    
    def _generate_rationale(self, question: str, answer: str) -> str:
        """Generate a rationale for the answer (placeholder)."""
        # In production, would use actual reasoning trace
        return f"To answer '{question[:50]}...', I determined that {answer[:100]}..."
    
    # =========================================================================
    # STaR Cycle
    # =========================================================================
    
    async def run_cycle(
        self,
        agent_id: str,
        num_examples: int = 100,
    ) -> StarCycleResult:
        """Run a STaR improvement cycle."""
        self._cycle_count += 1
        cycle_id = f"star_{self._cycle_count}"
        
        # Get examples for this agent
        agent_examples = [e for e in self._examples if e.agent_id == agent_id]
        
        # Calculate accuracy before
        correct_before = sum(1 for e in agent_examples if e.is_correct)
        accuracy_before = correct_before / len(agent_examples) if agent_examples else 0.0
        
        # Select examples for training
        # Prioritize correct examples for learning
        correct_examples = [e for e in agent_examples if e.is_correct]
        incorrect_examples = [e for e in agent_examples if not e.is_correct]
        
        # Limit examples
        training_examples = (correct_examples[:num_examples] + 
                          incorrect_examples[:num_examples//4])[:num_examples]
        
        examples_generated = len(training_examples)
        examples_correct = sum(1 for e in training_examples if e.is_correct)
        
        # In production, would fine-tune LoRA here
        # For demo, just log
        logger.info(f"STaR cycle {cycle_id}: {examples_generated} examples, {examples_correct} correct")
        
        # Simulate improvement
        accuracy_after = min(accuracy_before + 0.05, 1.0)
        improvement_score = accuracy_after - accuracy_before
        
        return StarCycleResult(
            cycle_id=cycle_id,
            examples_generated=examples_generated,
            examples_correct=examples_correct,
            accuracy_before=accuracy_before,
            accuracy_after=accuracy_after,
            improvement_score=improvement_score,
            dataset_size=len(agent_examples),
        )
    
    # =========================================================================
    # Dataset Operations
    # =========================================================================
    
    async def get_dataset(
        self,
        agent_id: Optional[str] = None,
        correct_only: bool = False,
    ) -> List[StarExample]:
        """Get training dataset."""
        async with self._lock:
            examples = self._examples.copy()
        
        if agent_id:
            examples = [e for e in examples if e.agent_id == agent_id]
        if correct_only:
            examples = [e for e in examples if e.is_correct]
        
        return examples
    
    async def export_dataset(self, agent_id: str) -> List[Dict[str, Any]]:
        """Export dataset for training."""
        examples = await self.get_dataset(agent_id, correct_only=True)
        
        return [
            {
                "question": e.question,
                "rationale": e.rationale,
                "answer": e.answer,
            }
            for e in examples
        ]
    
    async def clear_old_examples(self, days: int = 30) -> int:
        """Clear examples older than specified days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        async with self._lock:
            before = len(self._examples)
            self._examples = [e for e in self._examples if e.created_at >= cutoff]
            after = len(self._examples)
        
        return before - after
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get STaR statistics."""
        async with self._lock:
            total = len(self._examples)
            correct = sum(1 for e in self._examples if e.is_correct)
            
            by_agent: Dict[str, int] = {}
            for e in self._examples:
                by_agent[e.agent_id] = by_agent.get(e.agent_id, 0) + 1
        
        return {
            "total_examples": total,
            "correct_examples": correct,
            "accuracy": correct / total if total > 0 else 0.0,
            "by_agent": by_agent,
            "cycles_run": self._cycle_count,
        }


# Global STaR engine instance
_star_engine: Optional[StarEngine] = None


def get_star_engine() -> StarEngine:
    """Get or create global STaR engine."""
    global _star_engine
    if _star_engine is None:
        _star_engine = StarEngine()
    return _star_engine
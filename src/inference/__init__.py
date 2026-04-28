"""
RLM Inference Engine - Módulo de Inferência Empírica

Este módulo fornece:
- LLMProvider: Interface abstrata para provedores LLM (Ollama, OpenAI, Anthropic)
- Planner: Construtor de DAG de tarefas
- RLMInferenceEngine: Motor de inferência com ciclo write→execute→analyze
- RLMConfig: Configuração validada

Uso:
    from src.inference import (
        LLMProviderType,
        LLMProviderFactory,
        RLMInferenceEngine,
        RLMInferenceEngineSync,
        RLMConfig
    )
"""

# Exports
from .rlm_inference import (
    # Exceptions
    RLMInferenceError,
    LLMProviderError,
    PlannerError,
    ExecutionError,
    InferenceCancelled,  # NOVO - cancelamento
    # Enums
    LLMProviderType,
    # Data Classes
    Task,
    TaskGraph,
    IterationResult,
    InferenceResult,
    RLMConfig,  # NOVO - configuração validada
    # Provider Interface
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    AnthropicProvider,
    LLMProviderFactory,
    # Parser
    PythonErrorParser,
    # Planner
    Planner,
    # Engine
    RLMInferenceEngine,
    RLMInferenceEngineSync,
    # Constants
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_ITERATION_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    DEFAULT_MODEL,
    DEFAULT_BASE_URL,
    # Security limits (NOVO)
    MAX_ERROR_OUTPUT_SIZE,
    MAX_CODE_SIZE,
    MAX_RETRY_DELAY,
    BASE_RETRY_DELAY,
)

__all__ = [
    # Exceptions
    "RLMInferenceError",
    "LLMProviderError",
    "PlannerError",
    "ExecutionError",
    "InferenceCancelled",
    # Enums
    "LLMProviderType",
    # Data Classes
    "Task",
    "TaskGraph",
    "IterationResult",
    "InferenceResult",
    "RLMConfig",
    # Provider Interface
    "LLMProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "LLMProviderFactory",
    # Parser
    "PythonErrorParser",
    # Planner
    "Planner",
    # Engine
    "RLMInferenceEngine",
    "RLMInferenceEngineSync",
    # Constants
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_ITERATION_TIMEOUT",
    "DEFAULT_REQUEST_TIMEOUT",
    "DEFAULT_MODEL",
    "DEFAULT_BASE_URL",
    # Security limits
    "MAX_ERROR_OUTPUT_SIZE",
    "MAX_CODE_SIZE",
    "MAX_RETRY_DELAY",
    "BASE_RETRY_DELAY",
]
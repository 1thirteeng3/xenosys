"""
Q4: Stateful Memory System - Módulo de Memória Persistente

Este módulo fornece:
- SessionManager: Gerenciador de estado entre sessões
- VariableRegistry: Rastreamento de variáveis
- Checkpointing com msgpack + lz4

CRÍTICO: Usa msgpack (não pickle) para segurança.

Uso:
    from src.memory import SessionManager, VariableRegistry
    
    sm = SessionManager()
    session_id = await sm.create_session()
    await sm.set_variable("data", [1,2,3])
"""

# Exports
from .session_manager import (
    SessionManager,
    SessionState,
    DEFAULT_CHECKPOINT_INTERVAL,
    DEFAULT_TOKEN_LIMIT,
    STATE_DIR,
)
from .variable_registry import (
    VariableRegistry,
    VariableMetadata,
)

__all__ = [
    "SessionManager",
    "SessionState",
    "VariableRegistry",
    "VariableMetadata",
    "DEFAULT_CHECKPOINT_INTERVAL",
    "DEFAULT_TOKEN_LIMIT",
    "STATE_DIR",
]
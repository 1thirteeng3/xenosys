"""
Core Module - Infraestrutura Compartilhada XenoSys

Este módulo fornece modelos de dados e utilitários compartilhados
por todos os componentes (Q1, Q2, etc.).

Submódulos:
- models: Modelos de dados globais
- logging: Utilitários de logging
- hooks: Lifecycle hooks centralizados
"""

import sys
import os

# Garante que o path inclui o diretório src para imports relativos
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core.models import (
    ExecutionResult,
    ContainerSession,
)

from core.logging import (
    JSONFormatter,
    setup_logger,
)

from core.hooks import (
    LifecycleHooks,
)

__all__ = [
    # Models
    "ExecutionResult",
    "ContainerSession",
    # Logging
    "JSONFormatter",
    "setup_logger",
    # Hooks
    "LifecycleHooks",
]
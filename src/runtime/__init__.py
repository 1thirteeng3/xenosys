"""
XenoSys Runtime Module

Fornece o ambiente de execução de código Python isolado e persistente
usando containers Docker com warm pool.

Componentes:
- ContainerManager: Gerenciador de ciclo de vida (Q1)
- DockerReplEngine: Camada de execução isolada com containment (Q2)
- ContainmentConfig: Configuração de isolamento (memory, CPU, PIDs, network, filesystem)
- LifecycleHooks: Sistema de callbacks para eventos de lifecycle

Nota: Usa módulos compartilhados do core (src.core) para evitar duplicações.
"""

# Imports do core compartilhado (fontes de verdade únicas)
from core.models import (
    ExecutionResult,
    ContainerSession,
)

from core.logging import (
    JSONFormatter,
    setup_logger,
)

# Q1 - Container Manager
from .container_manager import (
    ContainerManager,
    ContainerManagerSync,
    ContainerManagerError,
    ContainerNotAvailableError,
    RecoveryError,
)

from .container_manager import (
    ExecutionError as ContainerExecutionError,
    ExecutionResult as ContainerExecutionResult,
)

# Q2 - Docker REPL Engine
from .docker_repl_engine import (
    DockerReplEngine,
    DockerReplEngineSync,
    DockerReplEngineError,
    IsolationError,
    LifecycleError,
    ExecutionError,
    ExecutionTimeoutError,
    ContainmentConfig,
    LifecycleHooks,
    IsolationLevel,
)

# Q7 - Security Policing (NOVO)
from .security_policing import (
    SecurityPolicing,
    SecurityPolicingSync,
    SecurityConfig,
    SecurityConfigInvalidError,
    RootDaemonDetectedError,
    ContainerSecurityViolationError,
    BatteryManager,
    BatteryStatus,
    SecurityAudit,
    SecurityValidator,
    BatteryState,
    SecurityLevel,
)

__all__ = [
    # Core compartilhado
    "ExecutionResult",
    "ContainerSession",
    "JSONFormatter",
    "setup_logger",
    # Container Manager (Q1)
    "ContainerManager",
    "ContainerManagerSync",
    "ContainerManagerError",
    "ContainerNotAvailableError",
    "ContainerExecutionError",
    "ContainerExecutionResult",
    "RecoveryError",
    # Docker REPL Engine (Q2)
    "DockerReplEngine",
    "DockerReplEngineSync",
    "DockerReplEngineError",
    "IsolationError",
    "LifecycleError",
    "ExecutionError",
    "ExecutionTimeoutError",
    "ContainmentConfig",
    "LifecycleHooks",
    "IsolationLevel",
    # Security Policing (Q7)
    "SecurityPolicing",
    "SecurityPolicingSync",
    "SecurityConfig",
    "SecurityConfigInvalidError",
    "RootDaemonDetectedError",
    "ContainerSecurityViolationError",
    "BatteryManager",
    "BatteryStatus",
    "SecurityAudit",
    "SecurityValidator",
    "BatteryState",
    "SecurityLevel",
]
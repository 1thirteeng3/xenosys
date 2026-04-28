"""
Core Models - Modelos de Dados Compartilhados

Este módulo contains modelos de dados globais usados por todos os
componentes do XenoSys (Q1, Q2, etc.), eliminando duplicações
e conflitos de nomenclatura.

Modelos:
- ExecutionResult: Resultado de execução de código
- ContainerSession: Sessão de container
- ExecutionError: Erro de execução
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ExecutionResult:
    """
    Resultado da execução de código em um container.
    
    Attributes:
        container_id: ID do container que executou o código
        stdout: Output padrão do código executado
        stderr: Output de erro do código executado
        exit_code: Código de saída da execução
        duration: Tempo de execução em segundos
    """
    container_id: str
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "container_id": self.container_id,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration
        }


@dataclass
class ContainerSession:
    """
    Sessão de container representando uma instância de container.
    
    Attributes:
        container_id: ID único do container Docker
        name: Nome do container
        created_at: Timestamp de criação
        status: Status atual do container
        is_warm: Se o container é do warm pool
        config: Configuração de isolamento injetada (opcional)
        
        # Campos opcionais para Q1 (ContainerManager)
        health_last_check: Timestamp do último health check
        exec_container_id: ID do container de execução (exec create)
    """
    container_id: str
    name: str
    created_at: datetime
    status: str = "creating"
    is_warm: bool = False
    config: Any = None  # Permite injeção de ContainmentConfig sem dependência circular
    
    # Campos opcionais para Q1 (ContainerManager)
    health_last_check: Optional[datetime] = None
    exec_container_id: Optional[str] = None


__all__ = [
    "ExecutionResult",
    "ContainerSession",
]
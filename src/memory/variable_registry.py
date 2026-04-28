"""
Q4: Stateful Memory System - Variable Registry

Mantém registro de todas as variáveis criadas durante a sessão,
permitindo rastreamento, serialização e restauração.

CRÍTICO: Usa msgpack (não pickle) para segurança.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class VariableMetadata:
    """Metadados de uma variável registrada."""
    name: str
    type_name: str  # str(type(value))
    created_at: str  # ISO timestamp
    updated_at: str
    size_bytes: int  # Estimativa
    references: List[str] = field(default_factory=list)  # Outras variáveis usadas
    is_computed: bool = False  # Se depende de outras variáveis


class VariableRegistry:
    """
    Registry centralizado para todas as variáveis da sessão.
    
    Mantém track de:
    - Nome e tipo de cada variável
    - Timestamp de criação/atualização
    - Tamanho estimado
    - Dependências entre variáveis
    
    Permite:
    - Registro de novas variáveis
    - Atualização de existentes
    - Serialização para checkpoint
    - Restauração de checkpoint
    """
    
    def __init__(self, max_variables: int = 1000):
        self._variables: Dict[str, VariableMetadata] = {}
        self._values: Dict[str, Any] = {}
        self._max_variables = max_variables
        self._lock = asyncio.Lock()
        
        logger.info(f"VariableRegistry inicializado (max: {max_variables})")
    
    async def register(
        self,
        name: str,
        value: Any,
        references: Optional[List[str]] = None
    ) -> None:
        """Registra uma nova variável ou atualiza existente."""
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            
            # Calcular tamanho
            size = self._estimate_size(value)
            
            metadata = VariableMetadata(
                name=name,
                type_name=str(type(value)),
                created_at=now,
                updated_at=now,
                size_bytes=size,
                references=references or [],
                is_computed=bool(references)
            )
            
            self._variables[name] = metadata
            self._values[name] = value
            
            # Cleanup se excedeu limite
            if len(self._variables) > self._max_variables:
                await self._evict_oldest()
            
            logger.debug(f"Variável registrada: {name} ({metadata.type_name}, {size} bytes)")
    
    async def get(self, name: str) -> Optional[Any]:
        """Obtém valor de uma variável."""
        return self._values.get(name)
    
    async def get_metadata(self, name: str) -> Optional[VariableMetadata]:
        """Obtém metadados de uma variável."""
        return self._variables.get(name)
    
    async def list_variables(self) -> List[str]:
        """Lista todas as variáveis."""
        return list(self._variables.keys())
    
    async def get_all(self) -> Dict[str, Any]:
        """Retorna todas as variáveis (para serialização)."""
        return self._values.copy()
    
    async def get_metadata_all(self) -> Dict[str, VariableMetadata]:
        """Retorna todos os metadados."""
        return self._variables.copy()
    
    async def update(self, name: str, value: Any) -> None:
        """Atualiza uma variável existente."""
        if name not in self._values:
            await self.register(name, value)
            return
        
        async with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            size = self._estimate_size(value)
            
            metadata = self._variables[name]
            metadata.updated_at = now
            metadata.size_bytes = size
            
            self._values[name] = value
            
            logger.debug(f"Variável atualizada: {name}")
    
    async def delete(self, name: str) -> bool:
        """Remove uma variável."""
        async with self._lock:
            if name in self._variables:
                del self._variables[name]
                del self._values[name]
                logger.debug(f"Variável removida: {name}")
                return True
            return False
    
    async def clear(self) -> None:
        """Limpa todas as variáveis."""
        async with self._lock:
            self._variables.clear()
            self._values.clear()
            logger.info("Registry limpo")
    
    async def _evict_oldest(self) -> None:
        """Remove variáveis mais antigas para manter limite."""
        # Ordena por created_at
        sorted_vars = sorted(
            self._variables.items(),
            key=lambda x: x[1].created_at
        )
        
        # Remove 10% mais antigas
        to_remove = sorted_vars[:len(sorted_vars) // 10]
        for name, _ in to_remove:
            del self._variables[name]
            del self._values[name]
        
        logger.warning(f"Evicted {len(to_remove)} variáveis antigas")
    
    def _estimate_size(self, value: Any) -> int:
        """Estima tamanho em bytes."""
        import sys
        try:
            return sys.getsizeof(value)
        except:
            return len(str(value))
    
    async def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do registry."""
        total_size = sum(m.size_bytes for m in self._variables.values())
        return {
            "count": len(self._variables),
            "total_bytes": total_size,
            "max_variables": self._max_variables,
            "utilization": len(self._variables) / self._max_variables
        }
    
    # --- Serialização ---
    
    def to_dict(self) -> Dict[str, Any]:
        """Serializa para dicionário (para msgpack)."""
        return {
            "variables": {
                name: {
                    "metadata": {
                        "name": m.name,
                        "type_name": m.type_name,
                        "created_at": m.created_at,
                        "updated_at": m.updated_at,
                        "size_bytes": m.size_bytes,
                        "references": m.references,
                        "is_computed": m.is_computed
                    },
                    "value": self._values.get(name)
                }
                for name, m in self._variables.items()
            },
            "stats": {
                "max_variables": self._max_variables,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VariableRegistry":
        """Restaura de dicionário (de msgpack)."""
        registry = cls(max_variables=data["stats"]["max_variables"])
        
        for name, item in data["variables"].items():
            metadata = item["metadata"]
            value = item["value"]
            
            m = VariableMetadata(
                name=metadata["name"],
                type_name=metadata["type_name"],
                created_at=metadata["created_at"],
                updated_at=metadata["updated_at"],
                size_bytes=metadata["size_bytes"],
                references=metadata["references"],
                is_computed=metadata["is_computed"]
            )
            
            registry._variables[name] = m
            registry._values[name] = value
        
        logger.info(f"Restauradas {len(registry._variables)} variáveis")
        return registry
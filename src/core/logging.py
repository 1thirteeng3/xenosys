"""
Core Logging - Configurações de Logging Compartilhadas

Este módulo contains utilitários de logging compartilhados
por todos os componentes do XenoSys.

Componentes:
- JSONFormatter: Formatador JSON para logs
- setup_logger: Configurador de logger
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter para output estruturado."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
            
        return json.dumps(log_entry)


def setup_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Configura logger com formatação JSON.
    
    Args:
        name: Nome do logger
        level: Nível de logging (padrão: DEBUG)
        
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    
    return logger


__all__ = [
    "JSONFormatter",
    "setup_logger",
]
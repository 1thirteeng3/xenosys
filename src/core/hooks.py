"""
Sistema de Lifecycle Hooks (SSOT - Single Source of Truth)

Este módulo contém a implementação centralizada do sistema de hooks
para todas as fases do container. Usado por Q1 e Q2.

Fases suportadas:
- on_create: Quando container é criado
- on_start: Quando container é iniciado
- on_stop: Quando container é parado
- on_destroy: Quando container é destruído
- on_error: Quando ocorre erro
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from core.logging import setup_logger
from core.models import ContainerSession


logger = setup_logger("lifecycle_hooks")


class LifecycleHooks:
    """
    Sistema de lifecycle hooks para todas as fases do container.
    
    Implementa o Observer Pattern para permitir que múltiplos
    observadores se inscrevam em eventos de lifecycle.
    
    Uso:
        hooks = LifecycleHooks()
        
        # Adicionar hook
        hooks.on_create(lambda session: print(f"Criado: {session.name}"))
        
        # Executar hooks
        await hooks.trigger_create(session)
    """
    
    def __init__(self):
        """Inicializa o sistema de hooks."""
        self._hooks: Dict[str, List[Callable]] = {
            "on_create": [],
            "on_start": [],
            "on_stop": [],
            "on_destroy": [],
            "on_error": [],
        }
    
    def register(
        self,
        event: str,
        callback: Callable[[ContainerSession], Any]
    ):
        """
        Registra um callback para um evento.
        
        Args:
            event: Nome do evento
            callback: Função a ser chamada
        """
        if event not in self._hooks:
            raise ValueError(f"Evento desconhecido: {event}")
        
        self._hooks[event].append(callback)
    
    def on_create(
        self,
        callback: Callable[[ContainerSession], Any]
    ):
        """Registra hook para criação de container."""
        self.register("on_create", callback)
    
    def on_start(
        self,
        callback: Callable[[ContainerSession], Any]
    ):
        """Registra hook para início de container."""
        self.register("on_start", callback)
    
    def on_stop(
        self,
        callback: Callable[[ContainerSession], Any]
    ):
        """Registra hook para parada de container."""
        self.register("on_stop", callback)
    
    def on_destroy(
        self,
        callback: Callable[[ContainerSession], Any]
    ):
        """Registra hook para destruição de container."""
        self.register("on_destroy", callback)
    
    def on_error(
        self,
        callback: Callable[[ContainerSession, Exception], Any]
    ):
        """Registra hook para erros."""
        self.register("on_error", callback)
    
    async def trigger(
        self,
        event: str,
        session: ContainerSession,
        error: Optional[Exception] = None
    ):
        """
        Dispara todos os hooks registrados para um evento.
        
        Args:
            event: Nome do evento
            session: Sessão do container
            error: Exceção opcional (para eventos de erro)
        """
        if event not in self._hooks:
            logger.warning(f"Evento desconhecido: {event}")
            return
        
        for callback in self._hooks[event]:
            try:
                if event == "on_error" and error:
                    result = callback(session, error)
                else:
                    result = callback(session)
                
                # Suporta callbacks async
                if asyncio.iscoroutine(result):
                    await result
                    
            except Exception as e:
                logger.error(
                    f"Erro ao executar hook {event}: {str(e)}",
                    extra={"extra_data": {
                        "event": event,
                        "session": session.name,
                        "error": str(e)
                    }}
                )
    
    async def trigger_create(self, session: ContainerSession):
        """Dispara hooks de criação."""
        await self.trigger("on_create", session)
    
    async def trigger_start(self, session: ContainerSession):
        """Dispara hooks de início."""
        await self.trigger("on_start", session)
    
    async def trigger_stop(self, session: ContainerSession):
        """Dispara hooks de parada."""
        await self.trigger("on_stop", session)
    
    async def trigger_destroy(self, session: ContainerSession):
        """Dispara hooks de destruição."""
        await self.trigger("on_destroy", session)
    
    async def trigger_error(
        self,
        session: ContainerSession,
        error: Exception
    ):
        """Dispara hooks de erro."""
        await self.trigger("on_error", session, error)


__all__ = ["LifecycleHooks"]
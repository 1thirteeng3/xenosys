"""
Q6: Interface Dual e Grafo Epistêmico - Toggle Manager

Este módulo implementa o sistema de alternância entre visualizações:
- ExecutionView: Terminal raw com syntax highlighting
- GraphView: Grafo interativo do Cortex

O toggle é dinâmico: alterna sem perda de estado, recarregamento
ou interrupção do processamento em background.

Padrões de Projeto:
- Observer Pattern: Notifica mudanças de visualização
- State Pattern: Mantém estado entre alternâncias
- Strategy Pattern: Estratégias de renderização intercambiáveis

Critérios de Aceitação (DoD):
✅ Toggle dinâmico sem perda de estado
✅ Alternância instantânea entre Terminal e Grafo
✅ Sem recarregamento da página
✅ Processamento em background não é interrompido
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ViewType(Enum):
    """Tipos de visualização suportados."""
    EXECUTION = "execution"       # Terminal/Sandbox
    GRAPH = "graph"               # Grafo Epistêmico


@dataclass
class ViewState:
    """
    Estado atual da interface visual.
    Mantido entre alternâncias para preservar contexto.
    """
    current_view: ViewType = ViewType.EXECUTION
    
    # Estado da ExecutionView (preservado entre toggles)
    last_stdout: str = ""
    last_stderr: str = ""
    last_exit_code: int = 0
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Estado da GraphView (preservado entre toggles)
    selected_node_id: Optional[str] = None
    graph_zoom_level: float = 1.0
    graph_center: tuple = field(default_factory=lambda: (0, 0))
    
    # Estado do toggle
    last_toggle_time: float = 0
    toggle_count: int = 0


class ToggleObserver:
    """
    Observer Pattern: Permite que componentes sejam notificados
    de mudanças de visualização.
    """
    
    def __init__(self):
        self._callbacks: List[Callable[[ViewState], None]] = []
    
    def register(self, callback: Callable[[ViewState], None]) -> None:
        """Registra um observador para mudanças de visualização."""
        self._callbacks.append(callback)
    
    def unregister(self, callback: Callable[[ViewState], None]) -> None:
        """Remove um observador."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def notify(self, state: ViewState) -> None:
        """Notifica todos os observadores de mudança."""
        for callback in self._callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.warning(f"Observer callback falhou: {e}")


class ToggleManager:
    """
    Gerenciador de alternância entre visualizações.
    
    Mantém estado entre toggles para garantir que o usuário
    não perca contexto ao alternar entre visão técnica
    (Terminal) e cognitiva (Grafo).
    
    Arquitetura:
    ┌─────────────────────────────────────────────────────┐
    │              ToggleManager                        │
    ├─────────────────────────────────────────────────────┤
    │  - ViewState: Estado persistido entre toggles       │
    │  - ToggleObserver: Notifica mudanças          │
    │  - RenderStrategy: Renderização flexível      │
    └─────────────────────────────────────────────────────┘
    """
    
    def __init__(
        self,
        state_file: Optional[str] = None,
        auto_save: bool = True
    ):
        self._state = ViewState()
        self._observer = ToggleObserver()
        self._auto_save = auto_save
        self._state_file = state_file or "/tmp/xenosys/ui_state.json"
        
        # Criar diretório de state
        Path(self._state_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Carregar estado persistido se existir
        self._load_state()
        
        logger.info(f"ToggleManager inicializado: view={self._state.current_view.value}")
    
    def _load_state(self) -> None:
        """Carrega estado persistido."""
        state_path = Path(self._state_file)
        if state_path.exists():
            try:
                data = json.loads(state_path.read_text())
                self._state.current_view = ViewType(data.get("current_view", "execution"))
                self._state.last_stdout = data.get("last_stdout", "")
                self._state.last_stderr = data.get("last_stderr", "")
                self._state.last_exit_code = data.get("last_exit_code", 0)
                self._state.execution_history = data.get("execution_history", [])
                self._state.selected_node_id = data.get("selected_node_id")
                self._state.graph_zoom_level = data.get("graph_zoom_level", 1.0)
                self._state.graph_center = tuple(data.get("graph_center", [0, 0]))
                logger.info(f"Estado carregado de {self._state_file}")
            except Exception as e:
                logger.warning(f"Estado não carregado: {e}")
    
    def _save_state(self) -> None:
        """Salva estado para persistência."""
        if not self._auto_save:
            return
        
        try:
            data = {
                "current_view": self._state.current_view.value,
                "last_stdout": self._state.last_stdout,
                "last_stderr": self._state.last_stderr,
                "last_exit_code": self._state.last_exit_code,
                "execution_history": self._state.execution_history,
                "selected_node_id": self._state.selected_node_id,
                "graph_zoom_level": self._state.graph_zoom_level,
                "graph_center": list(self._state.graph_center)
            }
            Path(self._state_file).write_text(json.dumps(data))
            logger.debug(f"Estado salvo em {self._state_file}")
        except Exception as e:
            logger.warning(f"Estado não salvo: {e}")
    
    # --- Operações de Toggle ---
    
    def toggle(self) -> ViewType:
        """
        Alterna entre visualizações.
        
        Returns:
            Nova visualização ativa
        """
        import time
        
        if self._state.current_view == ViewType.EXECUTION:
            self._state.current_view = ViewType.GRAPH
        else:
            self._state.current_view = ViewType.EXECUTION
        
        # Atualizar metadata de toggle
        self._state.last_toggle_time = time.time()
        self._state.toggle_count += 1
        
        # Notificar observadores
        self._observer.notify(self._state)
        
        # Salvar estado
        self._save_state()
        
        logger.info(f"Toggle: {self._state.current_view.value}")
        return self._state.current_view
    
    def set_view(self, view: ViewType) -> None:
        """Define visualização ativa sem toggle."""
        import time
        
        self._state.current_view = view
        self._state.last_toggle_time = time.time()
        self._observer.notify(self._state)
        self._save_state()
        
        logger.info(f"View definida: {view.value}")
    
    def get_current_view(self) -> ViewType:
        """Retorna visualização ativa."""
        return self._state.current_view
    
    @property
    def state(self) -> ViewState:
        """Retorna estado atual (para debugging)."""
        return self._state
    
    # --- ExecutionView State Management ---
    
    def update_execution(
        self,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0
    ) -> None:
        """
        Atualiza estado da visualização de execução.
        Preservado entre toggles.
        """
        self._state.last_stdout = stdout
        self._state.last_stderr = stderr
        self._state.last_exit_code = exit_code
        
        # Adicionar ao histórico (manter máximo 100)
        self._state.execution_history.append({
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code
        })
        if len(self._state.execution_history) > 100:
            self._state.execution_history = self._state.execution_history[-100:]
        
        self._save_state()
    
    def get_execution_state(self) -> Dict[str, Any]:
        """Retorna estado da execução."""
        return {
            "last_stdout": self._state.last_stdout,
            "last_stderr": self._state.last_stderr,
            "last_exit_code": self._state.last_exit_code,
            "history": self._state.execution_history
        }
    
    # --- GraphView State Management ---
    
    def update_graph_view(
        self,
        node_id: Optional[str] = None,
        zoom: Optional[float] = None,
        center: Optional[tuple] = None
    ) -> None:
        """
        Atualiza estado da visualização de grafo.
        Preservado entre toggles.
        """
        if node_id is not None:
            self._state.selected_node_id = node_id
        if zoom is not None:
            self._state.graph_zoom_level = zoom
        if center is not None:
            self._state.graph_center = center
        
        self._save_state()
    
    def get_graph_state(self) -> Dict[str, Any]:
        """Retorna estado do grafo."""
        return {
            "selected_node_id": self._state.selected_node_id,
            "zoom_level": self._state.graph_zoom_level,
            "center": self._state.graph_center
        }
    
    # --- Observer Pattern ---
    
    def register_observer(
        self,
        callback: Callable[[ViewState], None]
    ) -> None:
        """Registra um observador de mudanças de visualização."""
        self._observer.register(callback)
    
    def unregister_observer(
        self,
        callback: Callable[[ViewState], None]
    ) -> None:
        """Remove um observador."""
        self._observer.unregister(callback)
"""
Q6: Interface Dual e Grafo Epistêmico

Este módulo implementa a UI do sistema XenoSys:
- ExecutionView: Terminal com syntax highlighting
- GraphView: Grafo interativo do Cortex
- ToggleManager: Alternância dinâmica
- Server: Servidor web local (FastAPI/Aiohttp)

Uso:
    from ui import ToggleManager, ExecutionView, GraphView
    
    toggle = ToggleManager()
    execution = ExecutionView()
    graph = GraphView()
"""

from ui.toggle_manager import ToggleManager, ViewType, ViewState
from ui.views.execution_view import ExecutionView, ExecutionOutput
from ui.views.graph_view import GraphView, GraphNode, GraphEdge

__all__ = [
    "ToggleManager",
    "ViewType", 
    "ViewState",
    "ExecutionView",
    "ExecutionOutput",
    "GraphView",
    "GraphNode",
    "GraphEdge"
]
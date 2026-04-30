"""
Q6: Teste de Interface Dual

Testa os componentes da Q6:
- ToggleManager
- ExecutionView
- GraphView

Usage:
    python -m ui.test_ui
"""

import asyncio
import json
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_toggle_manager():
    """Testa ToggleManager."""
    import tempfile
    from ui.toggle_manager import ToggleManager, ViewType
    
    logger.info("=== Testando ToggleManager ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = f"{tmpdir}/ui_state.json"
        toggle = ToggleManager(state_file=state_file)
        
        # Testar get_current_view
        assert toggle.get_current_view() == ViewType.EXECUTION
        logger.info("✓get_current_view retorna EXECUTION inicial")
        
        # Testar toggle
        new_view = toggle.toggle()
        assert new_view == ViewType.GRAPH
        logger.info("✓toggle alterna para GRAPH")
        
        # Testar toggle de volta
        new_view = toggle.toggle()
        assert new_view == ViewType.EXECUTION
        logger.info("✓toggle alterna de volta para EXECUTION")
        
        # Testar update_execution
        toggle.update_execution(
            stdout="Hello World",
            stderr="Error: Something went wrong",
            exit_code=1
        )
        state = toggle.get_execution_state()
        assert state["last_stdout"] == "Hello World"
        assert state["last_stderr"] == "Error: Something went wrong"
        assert state["last_exit_code"] == 1
        logger.info("✓update_execution atualiza estado")
        
        # Testar update_graph_view
        toggle.update_graph_view(node_id="test_node", zoom=1.5)
        state = toggle.get_graph_state()
        assert state["selected_node_id"] == "test_node"
        assert state["zoom_level"] == 1.5
        logger.info("✓update_graph_view atualiza estado")
        
        # Testar persistência
        toggle2 = ToggleManager(state_file=state_file)
        assert toggle2.get_current_view() == ViewType.EXECUTION
        logger.info("✓persistência funciona")
        
    logger.info("✓ToggleManager: todos os testes passaram\n")


def test_execution_view():
    """Testa ExecutionView."""
    from ui.views.execution_view import ExecutionView
    
    logger.info("=== Testando ExecutionView ===")
    
    view = ExecutionView(use_colors=True)
    
    # Testar render de output normal
    output = view.render(
        stdout="print('Hello World')\n42",
        stderr="",
        exit_code=0,
        duration_ms=150.5
    )
    assert output.stdout == "print('Hello World')\n42"
    assert output.exit_code == 0
    logger.info("✓render processa stdout")
    
    # Testar render de errors
    output = view.render(
        stdout="",
        stderr="NameError: name 'x' is not defined",
        exit_code=1,
        duration_ms=50.0
    )
    assert output.exit_code == 1
    assert any(line.line_type == "error" for line in output.lines)
    logger.info("✓render detecta errors")
    
    # Testar format_for_api
    api_data = view.format_for_api(output)
    assert api_data["has_errors"] == True
    assert api_data["exit_code"] == 1
    logger.info("✓format_for_api serializa corretamente")
    
    # Testar get_history
    history = view.get_history()
    assert len(history) == 2
    logger.info("✓get_history retorna histórico")
    
    logger.info("✓ExecutionView: todos os testes passaram\n")


def test_graph_view():
    """Testa GraphView."""
    from ui.views.graph_view import GraphView, GraphNode, GraphEdge, create_graph_node
    
    logger.info("=== Testando GraphView ===")
    
    view = GraphView(use_physics=True)
    
    # Testar add_node
    node = create_graph_node(
        node_id="test_1",
        content="Este é um documento de teste",
        metadata={"type": "document", "source": "user"}
    )
    view.add_node(node)
    logger.info("✓add_node adiciona nó")
    
    # Adicionar segundo nó PRIMEIRO (antes da aresta)
    node2 = GraphNode(
        id="test_2",
        label="Node 2",
        content="Conteúdo do nó 2",
        metadata={},
        created_at="2024-01-01"
    )
    view.add_node(node2)
    
    # Testar add_edge (depois dos nós)
    edge = GraphEdge(
        source_id="test_1",
        target_id="test_2",
        relation_type="SUPPORTS"
    )
    view.add_edge(edge)
    logger.info("✓add_edge adiciona aresta")
    
    details = view.get_node_details("test_2")
    assert details is not None
    assert details["content"] == "Conteúdo do nó 2"
    logger.info("✓get_node_details retorna details")
    
    # Testar get_stats
    stats = view.get_stats()
    assert stats["node_count"] == 2
    assert stats["edge_count"] == 1
    logger.info("✓get_stats retorna estatísticas")
    
    # Testar render (HTML)
    html = view.render()
    assert isinstance(html, str)
    logger.info("✓render gera HTML")
    
    logger.info("✓GraphView: todos os testes passaram\n")


def main():
    """Executa todos os testes."""
    logger.info("Iniciando testes da Q6...\n")
    
    try:
        test_toggle_manager()
        test_execution_view()
        test_graph_view()
        
        logger.info("=" * 50)
        logger.info("✓ TODOS OS TESTES PASSARAM")
        logger.info("=" * 50)
        return 0
        
    except Exception as e:
        logger.error(f"✗ TESTE FALHOU: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
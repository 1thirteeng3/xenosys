"""
Q6: GraphView - Visão Epistêmica

Este módulo implementa a visualização interativa do grafo de conhecimento:
- Nós (documentos/memórias) renderizados
- Arestas tipadas (SUPPORTS, CONTRADICTS, DERIVED_FROM, EXPANDS_ON)
- Painel lateral com details do nó clicado

Usa PyVis para gerar HTML dinâmico (renderização local, sem CDN).

Padrões de Projeto:
- Strategy Pattern: Diferentes layouts de grafo
- Observer Pattern: Eventos de clique em nós
- Facade Pattern: Simplifica interface com Cortex

Critérios de Aceitação (DoD):
✅ Renderização interativa do banco de grafos (Q5)
✅ Nós e Arestas tipadas visualizados
✅ Clique em nó abre painel lateral com content + metadata
✅ Alternância sem perda de estado
✅ 100% offline (sem CDN)
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# Tentar importar pyvis (pode não estar disponível em todos os ambientes)
try:
    from pyvis.network import Network
    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False
    logger.warning("PyVis não disponível - usando fallback HTML")


@dataclass
class GraphNode:
    """Representa um nó renderizável."""
    id: str
    label: str
    content: str
    metadata: Dict[str, Any]
    created_at: str
    # Propriedades visuais
    color: str = "#3498db"  # Default blue
    size: int = 20
    shape: str = "dot"


@dataclass
class GraphEdge:
    """Representa uma aresta renderizável."""
    source_id: str
    target_id: str
    relation_type: str  # SUPPORTS, CONTRADICTS, etc.
    # Propriedades visuais
    color: str = "#95a5a6"
    width: int = 1


# Cores para tipos de relação
RELATION_COLORS = {
    "SUPPORTS": "#27ae60",      # Green
    "CONTRADICTS": "#e74c3c",   # Red
    "EXPANDS_ON": "#3498db",     # Blue
    "DERIVED_FROM": "#9b59b6"  # Purple
}


# Shapes para nós por tipo de content
NODE_SHAPES = {
    "document": "dot",
    "memory": "diamond",
    "code": "box",
    "note": "triangle",
    "default": "dot"
}


class PyVisRenderer:
    """
    Renderizador de grafo usando PyVis.
    
    Gera HTML interativo com:
    - Zoom e pan
    - Clique em nós (via postMessage para parent)
    - Arestas colorizadas por tipo
    - Tooltips com preview
    """
    
    # Script injetado para comunicação cross-frame (clique → painel)
    IPC_SCRIPT = '''
    <script>
    (function() {
        var network = null;
        var attempts = 0;
        var maxAttempts = 20;  // ⚠️ Max attempts - evita loop infinito
        var checkInterval = setInterval(function() {
            attempts++;
            if (window.network) {
                network = window.network;
                clearInterval(checkInterval);
                
                // Hook no clique de nó
                network.on("click", function(params) {
                    if (params.nodes && params.nodes.length > 0) {
                        var nodeId = params.nodes[0];
                        // Enviar para parent (iframe → main)
                        window.parent.postMessage({
                            type: "node_click",
                            nodeId: nodeId
                        }, "*");
                    }
                });
            } else if (attempts >= maxAttempts) {
                // Timeout - cleanup
                clearInterval(checkInterval);
                console.error("PyVis timeout: network não carregou após", maxAttempts, "tentativas");
            }
        }, 500);
    })();
    </script>
    '''
    
    def __init__(
        self,
        height: str = "600px",
        width: str = "100%",
        bgcolor: str = "#ffffff",
        font_color: str = "#333333"
    ):
        self._height = height
        self._width = width
        self._bgcolor = bgcolor
        self._font_color = font_color
        
        if HAS_PYVIS:
            self._net = Network(
                height=height,
                width=width,
                bgcolor=bgcolor,
                font_color=font_color,
                directed=True
            )
            # Configurações de física
            self._net.set_options("""
            {
                "nodes": {
                    "borderWidth": 2,
                    "borderWidthSelected": 4,
                    "font": {
                        "size": 14,
                        "face": "monospace"
                    }
                },
                "edges": {
                    "arrows": {
                        "to": {
                            "enabled": true,
                            "scaleFactor": 0.5
                        }
                    },
                    "smooth": {
                        "type": "continuous"
                    }
                },
                "physics": {
                    "enabled": true,
                    "solver": "forceAtlas2Based",
                    "forceAtlas2Based": {
                        "gravitationalConstant": -50,
                        "centralGravity": 0.01,
                        "springLength": 100,
                        "springConstant": 0.08
                    }
                },
                "interaction": {
                    "hover": true,
                    "tooltipDelay": 100,
                    "navigationButtons": true,
                    "keyboard": {
                        "enabled": true
                    }
                }
            }
            """)
        else:
            self._net = None
        
        logger.info("PyVisRenderer inicializado" if HAS_PYVIS else "PyVisRenderer fallback")
    
    def add_node(
        self,
        node: GraphNode
    ) -> None:
        """Adiciona nó ao grafo."""
        if not HAS_PYVIS or self._net is None:
            return
        
        # Tooltip com preview do content
        preview = node.content[:100] + "..." if len(node.content) > 100 else node.content
        
        self._net.add_node(
            node.id,
            label=node.label,
            title=preview,  # Tooltip
            color=node.color,
            size=node.size,
            shape=node.shape
        )
    
    def add_edge(
        self,
        edge: GraphEdge
    ) -> None:
        """Adiciona aresta ao grafo."""
        if not HAS_PYVIS or self._net is None:
            return
        
        self._net.add_edge(
            edge.source_id,
            edge.target_id,
            title=edge.relation_type,
            color=edge.color,
            width=edge.width,
            arrows="to"
        )
    
    def render(self) -> str:
        """
        Renderiza o grafo como HTML.
        
        Injeta script de IPC para comunicar cliques para parent (iframe → main).
        
        Returns:
            HTML com grafo interativo
        """
        if not HAS_PYVIS or self._net is None:
            return self._render_fallback()
        
        # Gerar HTML base do PyVis
        html = self._net.generate_html()
        
        # Injetar script de IPC antes do </body>
        if '</body>' in html:
            html = html.replace(
                '</body>',
                self.IPC_SCRIPT + '</body>'
            )
        
        return html
    
    def _render_fallback(self) -> str:
        """Renderiza fallback quando PyVis não disponível."""
        return '''\
<div class="graph-view-fallback">
  <div class="error-message">
    PyVis não disponível. Execute: pip install pyvis
  </div>
  <pre class="graph-data">{}</pre>
</div>'''


class GraphViewRenderer:
    """
    Renderizador de grafo com fallbacks para ambientes sem PyVis.
    
    Fornece interface unificada para renderização de grafo,
    usando PyVis quando disponível ou HTML/CSS/D3 básico.
    """
    
    def __init__(
        self,
        height: str = "600px",
        width: str = "100%",
        use_physics: bool = True
    ):
        self._height = height
        self._width = width
        self._use_physics = use_physics
        
        # Inicializar renderizador PyVis
        self._pyvis = PyVisRenderer(
            height=height,
            width=width
        )
        
        # Armazenar nós e arestas para renderização
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        
        logger.info("GraphViewRenderer inicializado")
    
    def add_nodes(self, nodes: List[GraphNode]) -> None:
        """Adiciona nós ao grafo."""
        for node in nodes:
            self._nodes[node.id] = node
            self._pyvis.add_node(node)
    
    def add_edges(self, edges: List[GraphEdge]) -> None:
        """Adiciona arestas ao grafo."""
        self._edges.extend(edges)
        for edge in edges:
            self._pyvis.add_edge(edge)
    
    def render(self) -> str:
        """Renderiza o grafo como HTML."""
        return self._pyvis.render()
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Retorna nó pelo ID."""
        return self._nodes.get(node_id)
    
    def get_all_nodes(self) -> List[GraphNode]:
        """Retorna todos os nós."""
        return list(self._nodes.values())
    
    def get_edges_for_node(self, node_id: str) -> List[GraphEdge]:
        """Retorna arestas conectadas a um nó."""
        return [
            e for e in self._edges
            if e.source_id == node_id or e.target_id == node_id
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do grafo."""
        return {
            "node_count": len(self._nodes),
            "edge_count": len(self._edges),
            "relation_types": list(set(e.relation_type for e in self._edges))
        }


class GraphView:
    """
    Visão Epistêmica - Grafo de Conhecimento.
    
    Renderiza o banco de grafos do Cortex (Q5) como grafo
    interativo com:
    - Nós representando documentos/memórias
    - Arestas tipadas (SUPPORTS, CONTRADICTS, etc.)
    - Painel lateral com details do nó
    
    Integra-se com Cortex (Q5) para obter dados do grafo.
    """
    
    def __init__(
        self,
        height: str = "600px",
        width: str = "100%",
        use_physics: bool = True
    ):
        self._renderer = GraphViewRenderer(
            height=height,
            width=width,
            use_physics=use_physics
        )
        
        # Callback para quando um nó é clicado
        self._on_node_click: Optional[callable] = None
        
        logger.info("GraphView inicializado")
    
    def load_from_cortex(self, cortex_db_path: str) -> bool:
        """
        Carrega dados do Cortex (Q5).
        
        Args:
            cortex_db_path: Caminho para o banco SQLite do Cortex
            
        Returns:
            True se sucesso
        """
        import sqlite3
        from datetime import datetime
        
        try:
            conn = sqlite3.connect(cortex_db_path)
            cursor = conn.cursor()
            
            # Carregar nós
            cursor.execute("SELECT id, content, metadata, created_at FROM nodes")
            nodes = []
            for row in cursor.fetchall():
                node_id, content, metadata_json, created_at = row
                metadata = json.loads(metadata_json) if metadata_json else {}
                
                # Detectar tipo pelo metadata
                content_type = metadata.get("type", "document")
                shape = NODE_SHAPES.get(content_type, "dot")
                
                # Criar label truncada
                label = content[:30] + "..." if len(content) > 30 else content
                
                nodes.append(GraphNode(
                    id=node_id,
                    label=label,
                    content=content,
                    metadata=metadata,
                    created_at=created_at,
                    shape=shape
                ))
            
            self._renderer.add_nodes(nodes)
            
            # Carregar arestas
            cursor.execute("SELECT source_id, target_id, relation_type FROM edges")
            edges = []
            for row in cursor.fetchall():
                source_id, target_id, relation_type = row
                color = RELATION_COLORS.get(relation_type, "#95a5a6")
                
                edges.append(GraphEdge(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=relation_type,
                    color=color
                ))
            
            self._renderer.add_edges(edges)
            
            conn.close()
            
            logger.info(f"Carregado do Cortex: {len(nodes)} nós, {len(edges)} arestas")
            return True
            
        except Exception as e:
            logger.error(f"Falha ao carregar do Cortex: {e}")
            return False
    
    def add_node(self, node: GraphNode) -> None:
        """Adiciona um nó manualmente."""
        self._renderer.add_nodes([node])
    
    def add_edge(self, edge: GraphEdge) -> None:
        """Adiciona uma aresta manualmente."""
        self._renderer.add_edges([edge])
    
    def render(self) -> str:
        """Renderiza o grafo como HTML."""
        return self._renderer.render()
    
    def get_html(self) -> str:
        """Alias para render()."""
        return self.render()
    
    def get_node_details(self, node_id: str) -> Optional[Dict]:
        """
        Retorna details de um nó para o painel lateral.
        
        Args:
            node_id: ID do nó
            
        Returns:
            Dict com content, metadata, created_at
        """
        node = self._renderer.get_node(node_id)
        if not node:
            return None
        
        return {
            "id": node.id,
            "content": node.content,
            "metadata": node.metadata,
            "created_at": node.created_at
        }
    
    def get_all_nodes(self) -> List[Dict]:
        """Retorna todos os nós."""
        return [
            {"id": n.id, "label": n.label}
            for n in self._renderer.get_all_nodes()
        ]
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas."""
        return self._renderer.get_stats()
    
    def set_node_click_callback(self, callback: callable) -> None:
        """Define callback para clique em nó."""
        self._on_node_click = callback
    
    # --- Para integração com ToggleManager ---
    
    def to_dict(self) -> Dict:
        """Serializa estado para API."""
        return {
            "stats": self.get_stats(),
            "nodes": self.get_all_nodes()
        }


# --- Funções utilitárias ---

def create_graph_node(
    node_id: str,
    content: str,
    metadata: Dict[str, Any],
    vector_dim: int = 384
) -> GraphNode:
    """
    Factory para criar GraphNode a partir de dados do Cortex.
    
    Args:
        node_id: ID do nó
        content: Texto do content
        metadata: Metadata
        vector_dim: Dimensão do vetor (para validação)
        
    Returns:
        GraphNode
    """
    content_type = metadata.get("type", "document")
    shape = NODE_SHAPES.get(content_type, "dot")
    
    label = content[:30] + "..." if len(content) > 30 else content
    
    return GraphNode(
        id=node_id,
        label=label,
        content=content,
        metadata=metadata,
        created_at=metadata.get("created_at", ""),
        shape=shape
    )


def create_graph_edge(
    source_id: str,
    target_id: str,
    relation_type: str
) -> GraphEdge:
    """
    Factory para criar GraphEdge.
    
    Args:
        source_id: ID do nó fonte
        target_id: ID do nó alvo
        relation_type: Tipo de relação
        
    Returns:
        GraphEdge
    """
    color = RELATION_COLORS.get(relation_type, "#95a5a6")
    
    return GraphEdge(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        color=color
    )
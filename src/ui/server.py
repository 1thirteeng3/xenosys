"""
Q6: Servidor Web Local - FastAPI ONLY

Este módulo implementa o servidor web para servir a UI:
- FastAPI OBRIGATÓRIO (Fail-Fast se não instalado)
- Servir arquivos estáticos via StaticFiles
- Toggle via SPA (JavaScript) - não re-renderização server-side

ACESSO: Estritamente via localhost (127.0.0.1)
SEGURANÇA: Assets locais (sem CDN) - 100% offline
"""

import asyncio
import json
import logging
import os
import signal
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Constantes ---
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
MAX_EXECUTION_OUTPUT = 500_000  # 500KB max

# --- Concorrência: asyncio.Lock global ---
_state_lock = asyncio.Lock()


# --- FASTAPI MODELS (Validação) ---

class ExecutionData(BaseModel):
    """Validação de entrada - previne DoS via buffer overflow."""
    stdout: str = Field(default="", max_length=MAX_EXECUTION_OUTPUT)
    stderr: str = Field(default="", max_length=MAX_EXECUTION_OUTPUT)
    exit_code: int = Field(default=0, ge=-1, le=255)


class ThemeManager:
    """
    Gerenciador de temas (claro/escuro).
    Persiste preferência em arquivo local.
    """
    
    THEME_FILE = Path("/tmp/xenosys/theme.json")
    
    def __init__(self):
        self._theme = "light"
        self._load()
    
    def _load(self) -> None:
        """Carrega tema persistido."""
        if self.THEME_FILE.exists():
            try:
                data = json.loads(self.THEME_FILE.read_text())
                self._theme = data.get("theme", "light")
            except:
                pass
    
    def _save(self) -> None:
        """Salva tema com tratamento de exceções."""
        try:
            self.THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.THEME_FILE.write_text(json.dumps({"theme": self._theme}))
        except (OSError, PermissionError) as e:
            # ⚠️ Falha silenciosa - degradar graciosamente
            logger.warning(f"Theme save failed (using in-memory): {e}")
    
    def get_theme(self) -> str:
        """Retorna tema atual."""
        return self._theme
    
    def set_theme(self, theme: str) -> None:
        """Define tema."""
        if theme in ("light", "dark"):
            self._theme = theme
            self._save()
    
    def toggle(self) -> str:
        """Alterna tema."""
        self._theme = "dark" if self._theme == "light" else "light"
        self._save()
        return self._theme


# --- FastAPI Server (ÚNICO) ---


def create_app(
    toggle_manager,
    execution_view,
    graph_view,
    static_dir: Optional[str] = None
) -> FastAPI:
    """
    Factory APENAS para FastAPI - sem fallbacks.
    
    Args:
        toggle_manager: ToggleManager instance
        execution_view: ExecutionView instance
        graph_view: GraphView instance
        static_dir: Diretório de arquivos estáticos
        
    Returns:
        FastAPI app
    """
    
    # Determinar diretórios base
    base_dir = Path(__file__).parent
    static_path = base_dir / "static"
    template_path = base_dir / "templates"
    
    # Criar app FastAPI
    app = FastAPI(
        title="XenoSys UI",
        description="Interface Dual - Execution + Graph",
        version="1.0.6"
    )
    
    # Dependencies como estado global
    state = {
        "toggle_manager": toggle_manager,
        "execution_view": execution_view,
        "graph_view": graph_view,
        "theme": ThemeManager()
    }
    
    # --- ROTAS --- #
    
    @app.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        """UI principal - SPA com toggle via JavaScript."""
        return HTMLResponse(_generate_spa_html())
    
    @app.get("/api/state")
    async def get_state():
        """Estado atual do toggle."""
        tm = state["toggle_manager"]
        return JSONResponse({
            "current_view": tm.get_current_view().value,
            "theme": state["theme"].get_theme(),
            "toggle_count": tm.state.toggle_count,
            "execution": tm.get_execution_state(),
            "graph": tm.get_graph_state()
        })
    
    @app.post("/api/toggle")
    async def toggle():
        """
        Alterna visualização.
        NOTA: Toggle retorna estado apenas - UI atualiza via JavaScript (SPA).
        """
        new_view = state["toggle_manager"].toggle()
        return JSONResponse({
            "current_view": new_view.value,
            "toggle_count": state["toggle_manager"].state.toggle_count
        })
    
    @app.post("/api/set_view/{view_type}")
    async def set_view(view_type: str):
        """Define visualização específica."""
        from ui.toggle_manager import ViewType
        
        try:
            view = ViewType(view_type)
            state["toggle_manager"].set_view(view)
            return JSONResponse({"current_view": view.value})
        except ValueError:
            return JSONResponse(
                {"error": f"Invalid view: {view_type}"},
                status_code=400
            )
    
    # --- Execution API --- #
    
    @app.get("/api/execution")
    async def get_execution():
        """Dados de execução."""
        return JSONResponse(state["toggle_manager"].get_execution_state())
    
    @app.post("/api/execution")
    async def update_execution(data: ExecutionData):
        """Atualiza dados de execução (recebido do DockerReplEngine/Q2).
        
        Usa validação Pydantic para previnir DoS via buffer overflow.
        Usa lock para previnir race conditions.
        """
        async with _state_lock:  # ⚠️ Lock de concorrência
            state["toggle_manager"].update_execution(
                stdout=data.stdout,
                stderr=data.stderr,
                exit_code=data.exit_code
            )
        return JSONResponse({"success": True})
    
    @app.get("/api/execution/html")
    async def get_execution_html():
        """Retorna HTML renderizado da última execução."""
        exec_state = state["toggle_manager"].get_execution_state()
        exec_view = state["execution_view"]
        
        # Render se houver output
        if exec_state["last_stdout"] or exec_state["last_stderr"]:
            output = exec_view.render(
                stdout=exec_state["last_stdout"],
                stderr=exec_state["last_stderr"],
                exit_code=exec_state["last_exit_code"],
                duration_ms=0
            )
            html = exec_view.get_html(output)
        else:
            html = '<pre class="terminal-output">[Aguardando execução...]</pre>'
        
        return HTMLResponse(html)
    
    # --- Graph API --- #
    
    @app.get("/api/graph")
    async def get_graph():
        """Dados do grafo para visualização."""
        gv = state["graph_view"]
        return JSONResponse({
            "stats": gv.get_stats(),
            "nodes": gv.get_all_nodes()
        })
    
    @app.get("/api/graph/node/{node_id}")
    async def get_node(node_id: str):
        """Detalhes do nó para painel lateral."""
        details = state["graph_view"].get_node_details(node_id)
        if details:
            return JSONResponse(details)
        return JSONResponse({"error": "Not found"}, status_code=404)
    
    @app.get("/api/graph/html")
    async def get_graph_html():
        """HTML do grafo renderizado."""
        html = state["graph_view"].render()
        return HTMLResponse(html)
    
    @app.get("/api/graph/render")
    async def get_graph_render():
        """
        Iframe do grafo - permite isolamento de DOM.
        """
        return HTMLResponse(state["graph_view"].render())
    
    # --- Theme API --- #
    
    @app.get("/api/theme")
    async def get_theme():
        """Retorna tema atual."""
        return JSONResponse({"theme": state["theme"].get_theme()})
    
    @app.post("/api/theme")
    async def set_theme(data: Dict[str, Any]):
        """Define tema."""
        theme = data.get("theme", "light")
        state["theme"].set_theme(theme)
        return JSONResponse({"theme": theme})
    
    @app.post("/api/theme/toggle")
    async def toggle_theme():
        """Alterna tema."""
        theme = state["theme"].toggle()
        return JSONResponse({"theme": theme})
    
    # --- Montar arquivos estáticos --- #
    
    # Mount diretório static para assets (CSS, JS, fonts)
    if static_path.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(static_path)),
            name="static"
        )
        logger.info(f"Static files mounted: {static_path}")
    else:
        logger.warning(f"Static directory not found: {static_path}")
    
    return app


def _generate_spa_html() -> str:
    """
    Gera HTML da SPA.
    O toggle ocorre via JavaScript (SPA) - sem re-renderização server-side.
    """
    
    return '''\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>XenoSys - Interface Dual</title>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <div id="app" class="app-container">
        <header class="app-header">
            <h1 class="app-title">XenoSys</h1>
            <nav class="app-nav">
                <button id="btn-execution" class="nav-btn" data-view="execution">
                    Terminal
                </button>
                <button id="btn-graph" class="nav-btn" data-view="graph">
                    Grafo
                </button>
                <button id="btn-theme" class="nav-btn theme-toggle" title="Alternar tema">
                    ☀️
                </button>
            </nav>
        </header>
        
        <main class="app-main">
            <!-- Execution View -->
            <div id="view-execution" class="view active">
                <div class="view-header">
                    <h2>Execução</h2>
                    <span id="execution-status" class="status-indicator"></span>
                </div>
                <div class="terminal-container">
                    <pre id="terminal-output" class="terminal-output"></pre>
                </div>
            </div>
            
            <!-- Graph View -->
            <div id="view-graph" class="view">
                <div class="view-header">
                    <h2>Grafo Epistêmico</h2>
                    <span id="graph-stats" class="stats-indicator"></span>
                </div>
                <div id="graph-container" class="graph-container">
                    <iframe id="graph-iframe" src="/api/graph/render" frameborder="0"></iframe>
                </div>
            </div>
        </main>
        
        <!-- Node Panel (sidebar) -->
        <aside id="node-panel" class="node-panel">
            <button class="panel-close" id="btn-close-panel">&times;</button>
            <div class="panel-header">
                <h3>Detalhes do Nó</h3>
            </div>
            <div class="panel-content" id="panel-content">
                <!-- Conteúdo carregado dinamicamente -->
            </div>
        </aside>
    </div>
    
    <script src="/static/js/app.js"></script>
</body>
</html>'''


# --- CLI Entry Point ---


async def main():
    """CLI para iniciar servidor FastAPI."""
    import argparse
    import uvicorn
    from ui.toggle_manager import ToggleManager
    from ui.views.execution_view import ExecutionView
    from ui.views.graph_view import GraphView
    
    parser = argparse.ArgumentParser(description="XenoSys UI Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Porta")
    parser.add_argument("--cortex-db", default="/tmp/xenosys/cortex.db", help="Cortex DB")
    args = parser.parse_args()
    
    # Validação de host (segurança) - APENAS localhost
    if args.host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"Host inválido: {args.host}. Use 127.0.0.1")
    
    # Inicializar componentes com try/catch para erros claros
    try:
        toggle_manager = ToggleManager()
        execution_view = ExecutionView()
        graph_view = GraphView()
        logger.info("Componentes inicializados OK")
    except Exception as e:
        logger.error(f"Falha ao inicializar componentes: {e}", exc_info=True)
        sys.exit(1)
    
    # Carregar dados do Cortex (Q5) com erro claro
    cortex_db = Path(args.cortex_db)
    if cortex_db.exists():
        try:
            graph_view.load_from_cortex(str(cortex_db))
            logger.info(f"Carregado do Cortex: {cortex_db}")
        except Exception as e:
            logger.error(f"Falha ao carregar Cortex DB: {e} - continuando sem grafo")
    
    # Criar app FastAPI
    app = create_app(
        toggle_manager=toggle_manager,
        execution_view=execution_view,
        graph_view=graph_view
    )
    
    # Configurar signal handling para shutdown limpo
    loop = asyncio.get_event_loop()
    
    def signal_handler(sig, frame):
        logger.info(f"Recebido sinal {sig} - shutdown...")
        loop.stop()
    
    # Registrar handlers de sinal
    if sys.platform != 'win32':
        loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
    
    # Configurar uvicorn
    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    
    logger.info(f"Iniciando FastAPI em http://{args.host}:{args.port}")
    logger.info("Acesso restrito a localhost (127.0.0.1)")
    logger.info("Pressione Ctrl+C para encerrar")
    
    await server.serve()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
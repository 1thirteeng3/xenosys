# Q6: Interface Dual e Grafo Epistêmico

## Visão Geral

Este módulo implementa a interface de usuário do sistema XenoSys, rompendo com o paradigma linear de "chat" através de uma interface dual que alterna entre:

1. **ExecutionView** - Visão de Depuração: Terminal com stdout/stderr raw do código executado no container Docker
2. **GraphView** - Visão Epistêmica: Grafo interativo do Cortex representando o conhecimento

## Funcionalidades Implementadas

### ToggleManager
- Alternância instantânea entre Terminal e Grafo
- Preservação de estado entre alternâncias
- Persistência em arquivo JSON local
- Observer Pattern para notificação de mudanças

### ExecutionView
- Terminal com syntax highlighting
- Detecção automática de erros Python (SyntaxError, NameError, etc.)
- Cores ANSI para diferentes tipos de mensagem
- Histórico de execuções

### GraphView
- Renderização de grafo usando PyVis (quando disponível)
- Nós colorizados por tipo de conteúdo
- Arestas tipadas (SUPPORTS, CONTRADICTS, DERIVED_FROM, EXPANDS_ON)
- Painel lateral com detalhes do nó
- Fallback HTML para ambientes sem PyVis

### Servidor Web
- FastAPI como servidor primário
- Fallback para Aiohttp
- Acesso via localhost (127.0.0.1)
- Assets locais (100% offline)
- API REST para toggle, execution e graph
- Suporte a temas claro/escuro

## Arquitetura

```
src/ui/
├── __init__.py           # Exports públicos
├── toggle_manager.py    # Gerenciador de alternância
├── server.py           # Servidor web local
├── views/
│   ├── __init__.py
│   ├── execution_view.py  # Terminal view
│   └── graph_view.py     # Grafo view
└── test_ui.py          # Testes
```

## Uso

### API Python

```python
from ui import ToggleManager, ExecutionView, GraphView

# ToggleManager
toggle = ToggleManager()
toggle.toggle()  # Alterna visualização

# ExecutionView
exec_view = ExecutionView()
output = exec_view.render(stdout="...", stderr="...", exit_code=0, duration_ms=100)
html = exec_view.get_html(output)

# GraphView
graph = GraphView()
graph.load_from_cortex("/tmp/xenosys/cortex.db")  # Carrega do Q5
html = graph.render()
details = graph.get_node_details("node_id")
```

### Servidor Web

```bash
# Iniciar servidor
python -m ui.server --port 8080 --cortex-db /tmp/xenosys/cortex.db
```

Acessar em: http://127.0.0.1:8080

### API REST

| Endpoint | Método | Descrição |
|----------|--------|----------|
| `/api/state` | GET | Estado atual |
| `/api/toggle` | POST | Alternar visualização |
| `/api/execution` | GET/POST | Dados de execução |
| `/api/graph` | GET | Dados do grafo |
| `/api/graph/node/<id>` | GET | Detalhes do nó |
| `/api/theme` | GET/POST | Tema |

## Dependências

### Obrigatórias
- `numpy>=1.24.0`

### Opcionais
- `pyvis>=0.3.0` - Renderização de grafo
- `fastapi>=0.100.0` - Servidor web
- `aiohttp>=3.9.0` - Fallback servidor
- `uvicorn>=0.25.0` - ASGI server

## Testes

```bash
python -m ui.test_ui
```

## Critérios de Aceitação (DoD)

- [x] Visão de Depuração com stdout/stderr raw
- [x] Syntax highlighting para errores Python
- [x] Log de erros formatado
- [x] Renderização interativa do grafo (Q5)
- [x] Nós e Arestas tipadas visualizados
- [x] Clique em nó abre painel lateral
- [x] Toggle dinâmico sem perda de estado
- [x] Alternância instantânea (sem reload)
- [x] Tema claro/escuro com persistência
- [x] Servidor via localhost
- [x] Assets 100% offline (sem CDN)

## Integração com Q2 e Q5

### Q2 (DockerReplEngine)
A ExecutionView recebe a saída de execução:

```python
# Q2 executa código
result = await docker_repl.execute("print('hello')")

# ExecutionView renderiza
exec_view.update_execution(
    stdout=result.stdout,
    stderr=result.stderr,
    exit_code=result.exit_code
)
```

### Q5 (Cortex)
A GraphView carrega dados do grafo:

```python
# Q5 persiste nós
cortex.add_node(Node(...))

# GraphView carrega
graph = GraphView()
graph.load_from_cortex("/tmp/xenosys/cortex.db")
```

## Configuração

Variáveis de ambiente:
- `XENOSYS_UI_PORT`: Porta do servidor (padrão: 8080)
- `XENOSYS_UI_HOST`: Host (padrão: 127.0.0.1)
- `XENOSYS_STATE_FILE`: Arquivo de estado (padrão: /tmp/xenosys/ui_state.json)
- `XENOSYS_THEME_FILE`: Arquivo de tema (padrão: /tmp/xenosys/theme.json)
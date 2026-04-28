# Q4: Stateful Memory System - Memória Persistente

## A. Registro de Raciocínio Técnico (Chain of Thought)

### Trade-offs

1. **msgpack vs pickle**: msgpack é seguro (não executa código arbitrário), mas não suporta objetos arbitrários Python. Pickle é vetado por segurança.

2. **RAM vs Disk**: Manter state em /tmp (tmpfs) para performance, com checkpoint periódico.

3. **lz4 vs gzip**: lz4 mais rápido (10x) para compressão/descompressão em tempo real.

### Padrões de Projeto

1. **Session Pattern**: Uma sessão por contexto, isolada das outras.
2. **Registry Pattern**: VariableRegistry faz track de todas as variáveis.
3. **Memento Pattern**: Checkpoint serialization/deserialization.
4. **Template Method**: SessionManager com hooks para compressão customizável.

### Riscos e Mitigações

| Risco | Mitigação |
|-------|-----------|
|pickle vulnerabilities | msgpack only (use_bin_type) |
| memory leaks | max_variables limit + eviction |
| state corruption | atomic writes (rename) |
| race conditions | asyncio.Lock() |

---

## B. Funcionalidades Implementadas

### SessionManager
- `create_session(session_id?)`: Cria nova sessão
- `close_session(session_id?)`: Fecha com checkpoint final
- `set_variable(name, value, session_id?)`: Define variável
- `get_variable(name, session_id?, default)`: Obtém variável
- `list_variables(session_id?)`: Lista variáveis
- `set_context(key, value, session_id?)`: Define contexto
- `compress_context(session_id?)`: Comprime quando > 80% tokens
- `get_checkpoint_path(session_id)`: Caminho do arquivo

### VariableRegistry  
- `register(name, value, references?)`: Registra variável
- `get(name)`: Obtém valor
- `list_variables()`: Lista todas
- `get_stats()`: Estatísticas
- `to_dict()` / `from_dict(data)`: Serialização

### Checkpoint System
- Intervalo: 5 minutos (configurável)
- Formato: msgpack + lz4 compression
- Local: /tmp/xenosys/{session_id}.checkpoint
- Atomic: write to .tmp then rename

---

## C. Dependências

```
msgpack>=1.0.0  # Serialização segura
lz4>=4.0.0      # Compressão
```

---

## D. Testes

```bash
python3 tests/unit/test_memory.py
# ✓ 6 testes passaram
```

---

## E. Exemplo de Uso

```python
from src.memory import SessionManager

sm = SessionManager()

# Criar sessão
sid = await sm.create_session()

# Variáveis persistem entre chamadas
await sm.set_variable("data", [1, 2, 3], sid)
data = await sm.get_variable("data", sid)
print(data)  # [1, 2, 3]

# Checkpoint automático a cada 5 minutos
# Restore automático em nova sessão

await sm.shutdown()
```

---

## F. Snapshot de Estado

```
SNAPSHOT DE ESTADO:
Versão do Projeto: v1.0.5
Componentes Prontos:
  - check_docker.py (Q0)
  - container_manager.py (Q1)
  - docker_repl_engine.py (Q2)
  - rlm_inference.py (Q3)
  - session_manager.py (Q4) - NOVO
  - variable_registry.py (Q4) - NOVO

Dependências Instaladas:
  - msgpack>=1.0.0
  - lz4>=4.0.0

Pendências Técnicas:
  - Health check do SessionManager
  - Integração com Q3 (RLM)
```
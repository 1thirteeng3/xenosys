# Q5: Cortex - Banco de Grafos Híbrido e Ingestão Local

## Descrição

Este módulo implementa o sistema de gerenciamento epistêmico do XenoSys, construindo um banco de grafos local ancorado em SQLite. O Cortex fornece capacidades de busca híbrida combinando similaridade semântica e busca léxica, permitindo recuperação de conhecimento offline.

---

## A. Padrões de Projeto Aplicados

### 1. Repository Pattern
Abstração de persistência para o grafo de conhecimento via `GraphRepository`. Isola a lógica de acesso a dados SQLite.

### 2. Strategy Pattern
Múltiplos parsers (`TextParser`, `CSVParser`, `JSONParser`, `PDFParser`) implementam interface comum.

### 3. Factory Pattern
`ParserFactory` cria parser correto baseado na extensão do arquivo.

### 4. Producer-Consumer Pattern
`IngestionWorker` usa `asyncio.Queue` para processamento em background, permitindo que a deliberação do Orquestrador nunca seja bloqueada.

### 5. Observer Pattern
`AuditLogger` registra todas as operações de acesso a arquivos para rastreabilidade.

---

## B. Funcionalidades Implementadas

### B.1 Schema de Grafo Relacional

#### Tabela Nodes
| Coluna | Tipo | Descrição |
|-------|------|----------|
| id | TEXT | Primary key único |
| content | TEXT | Texto do documento |
| vector_blob | BLOB | Embedding 384D (binário) |
| metadata | TEXT | JSON de metadados |
| created_at | TEXT | ISO timestamp |

#### Tabela Edges
| Coluna | Tipo | Descrição |
|-------|------|----------|
| source_id | TEXT | Nó de origem |
| target_id | TEXT | Nó de destino |
| relation_type | TEXT | SUPPORTS/CONTRADICTS/EXPANDS_ON/DERIVED_FROM |

### B.2 Ingestão Otimizada

**FileReader suporta:**
- PDF (via PyPDF2)
- TXT, MD (texto puro)
- CSV (via pandas)
- JSON (parsing estruturado)

**Streaming:**
- Para arquivos > 100MB, usa generators/yield para evitar OOM
- Chunking configurável

### B.3 Motor de Busca Híbrida

**Fórmula de fusão (XENOSYS):**
```
S(q, d) = α * CosSim(q, d) + (1-α) * BM25(q, d)
```

Onde:
- `CosSim`: Similaridade de cosseno (numpy)
- `BM25`: Relevance via rank_bm25
- `α`: Peso configurável (default: 0.5)

### B.4 Processamento Assíncrono

- `EmbeddingEngine` executa em `ThreadPoolExecutor` (não bloqueia event loop)
- Vetorização despachada com `run_in_executor`
- BM25 índice construído em background

### B.5 Segurança

- Verificação de network policy antes de I/O
- Audit log de todo acesso a arquivos
- Blob binário para embeddings (não text-exposed)

---

## C. Dependências

```
PyPDF2>=3.0.0       # PDF parsing
pandas>=2.0.0        # CSV handling
sentence-transformers>=2.2.0  # Embeddings (CPU-only)
rank-bm25>=0.2.0    # BM25 algorithm
numpy>=1.24.0        # Similarity calc
```

**Proibido:**
- Qualquer biblioteca que faça network outbound em runtime
- Executar inferências na thread principal do Event Loop

---

## D. API Reference

###Criação de Instância

```python
from src.cortex import create_cortex

cortex = create_cortex("/tmp/cortex.db", alpha=0.5)
```

### Ciclo de Vida

```python
async def main():
    # Inicia Cortex
    await cortex.start()
    
    # Ingere documento
    node_id = await cortex.ingest_document("/path/to/doc.pdf")
    
    # Busca híbrida
    results = await cortex.search("query", top_k=5)
    
    # Adiciona relação
    cortex.add_edge(node_id_1, node_id_2, RelationType.SUPPORTS)
    
    # Para Cortex
    await cortex.stop()
```

### Métodos Principais

| Método | Descrição |
|--------|----------|
| `start()` | Inicia workers assíncronos |
| `stop()` | Para workers e fecha conexões |
| `ingest_document(file_path)` | Adiciona documento à fila |
| `search(query, top_k)` | Busca híbrida |
| `add_edge(source, target, type)` | Adiciona aresta |
| `get_node(id)` | Recupera nó |
| `get_neighbors(id)` | Recupera nós conectados |

---

## E. Testes

```bash
# Executa testes unitários
python3 -m pytest tests/unit/test_cortex.py -v

# Atau
python3 tests/unit/test_cortex.py
```

**Testes incluem:**
- ✓ GraphRepository (insert/get/search)
- ✓ Parsers (TXT, CSV, JSON)
- ✓ AuditLogger
- ✓ HybridSearch
- ✓ Ciclo de vida completo

---

## F. Considerações de Segurança

### Network Policy
- O módulo verifica política de rede antes de iniciar
- Em produção, garantir `--network none` no container Docker

### Modelo de Embedding
- `sentence-transformers` baixa modelo na primeira execução
- Para operação verdaderamente offline, pré-baixar modelo:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
# Modelo fica em cache local
```

### Auditoria
-Log em `/tmp/xenosys/audit.log`
- Formato: JSON lines (append-only)

---

## G. Limitações Conhecidas

1. **SQLite não é paralelo para escrita**: Usar WAL mode mitiga
2. **Blob limit**: SQLite BLOB limitado a ~1GB
3. **Embedding fixo**: 384 dimensões (all-MiniLM-L6-v2)

---

## H. Exemplo Completo

```python
import asyncio
from src.cortex import create_cortex, RelationType

async def example():
    # Cria instância
    cortex = create_cortex("/tmp/cortex.db")
    await cortex.start()
    
    # Ingere documentos
    doc1 = await cortex.ingest_document("/data/paper1.pdf")
    doc2 = await cortex.ingest_document("/data/paper2.pdf")
    
    # Adiciona relação
    cortex.add_edge(doc1, doc2, RelationType.SUPPORTS)
    
    # Busca
    results = await cortex.search("machine learning", top_k=3)
    
    print("Resultados:")
    for node, score in results:
        print(f"  {node.id}: {score:.3f}")
    
    await cortex.stop()

asyncio.run(example())
```

---

## I. Snapshot de Estado

```
SNAPSHOT DE ESTADO:
Versão do Projeto: v1.0.6
Componentes Prontos:
  - check_docker.py (Q0)
  - container_manager.py (Q1)
  - docker_repl_engine.py (Q2)
  - rlm_inference.py (Q3)
  - session_manager.py (Q4)
  - variable_registry.py (Q4)
  - cortex.py (Q5) - NOVO

Dependências Instaladas:
  - docker>=7.0.0
  - python-dotenv>=1.0.0
  - aiohttp>=3.9.0
  - msgpack>=1.0.0
  - lz4>=4.0.0
  - PyPDF2>=3.0.0
  - pandas>=2.0.0
  - sentence-transformers>=2.2.0
  - rank-bm25>=0.2.0
  - numpy>=1.24.0

Pendências Técnicas:
  - Integração Q5 com Q3 (RLM)
  - Health check do Cortex
  - Pre-loading de modelo embedding
```
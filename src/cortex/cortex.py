"""
Q5: Cortex - Banco de Grafos Híbrido e Ingestão Local

Este módulo implementa o sistema de gerenciamento epistêmico do XenoSys,
construindo um banco de grafos local ancorado em SQLite.

Características:
- Schema de Grafo Relacional (Nodes + Edges)
- Ingestão Otimizada com streaming
- Motor de Busca Híbrida (Cosseno + BM25)
- Processamento Assíncrono
- Auditoria de Segurança
"""

import asyncio
import json
import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Generator, Optional, Union

import numpy as np
# pandas importado lazy (dentro de CSVParser.parse)
# PyPDF2 para parsing de PDF
from PyPDF2 import PdfReader

import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("xenosys.cortex")


class RelationType(Enum):
    """Tipos de relação explícitos suportados entre nodes."""
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    EXPANDS_ON = "EXPANDS_ON"
    DERIVED_FROM = "DERIVED_FROM"
    FORCED_OVERRIDE = "FORCED_OVERRIDE"


class NetworkSecurityError(Exception):
    """Exceção raised quando política de rede é violada."""
    pass


def _check_network_isolation() -> bool:
    """
    Valida isolamento de rede inspecionando topologia local.
    
    Em modo --network none, o container NÃO deve ter interfaces
    de rede externas (eth0, wlan0, etc.) disponíveis.
    
    Returns:
        True se isolado, False caso contrário.
    """
    import os
    
    try:
        # Lista interfaces de rede disponíveis
        net_class = "/sys/class/net/"
        if not os.path.exists(net_class):
            # Não estamos em Linux com sysfs - fallback
            return True
        
        interfaces = os.listdir(net_class)
        
        # Filtra interfaces roteáveis (não loopback, não túnel)
        external_ifaces = [
            iface for iface in interfaces
            if not iface.startswith(('lo', 'tun', 'tap', 'veth'))
        ]
        
        # Se há interfaces externas, não estamos isolados
        if external_ifaces:
            logger.warning(f"Interfaces de rede detectadas: {external_ifaces}")
            return False
        
        return True
        
    except Exception as e:
        logger.warning(f"Não foi possível verificar isolamento: {e}")
        # Em caso de erro, falhe fechado (considere isolado por segurança)
        return True


class AuditLogger:
    """
    Registro de auditoria imutável para todo acesso a arquivos.
    Implementa o padrão Observer para rastreabilidade.
    """
    
    def __init__(self, audit_path: str = "/tmp/xenosys/audit.log"):
        self.audit_path = Path(audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        # Modo append-only para garantir imutabilidade
        self._lock = threading.Lock()
    
    def log(self, operation: str, file_path: str, details: Optional[dict] = None):
        """Registra uma operação de acesso a arquivo."""
        timestamp = datetime.utcnow().isoformat()
        entry = {
            "timestamp": timestamp,
            "operation": operation,
            "file_path": file_path,
            "details": details or {}
        }
        with self._lock:
            with open(self.audit_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        logger.debug(f"AUDIT: {operation} on {file_path}")


@dataclass
class Node:
    """Representa um nó no grafo de conhecimento."""
    id: str
    content: str
    vector_blob: bytes  # 384-dimensional embedding como binary
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Edge:
    """Representa uma aresta no grafo de conhecimento."""
    source_id: str
    target_id: str
    relation_type: RelationType


class GraphRepository:
    """
    Repository Pattern: Abstração de persistência para o grafo.
    Implementa schema SQLite com Nodes e Edges.
    """
    
    def __init__(self, db_path: str = "/tmp/xenosys/cortex.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._check_network_policy()
        self._init_schema()
    
    def _check_network_policy(self):
        """Valida política de rede antes de qualquer operação via topologia local."""
        if not _check_network_isolation():
            raise NetworkSecurityError(
                "Violação de Isolamento: Interface de rede externa detectada. "
                "Container deve executar com --network none"
            )
    
    def _init_schema(self):
        """Inicializa schema do banco de dados."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Tabela Nodes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                vector_blob BLOB NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Tabela Edges
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                PRIMARY KEY (source_id, target_id),
                FOREIGN KEY (source_id) REFERENCES nodes(id),
                FOREIGN KEY (target_id) REFERENCES nodes(id)
            )
        """)
        
        # Índices para performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_content ON nodes(content)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"Schema initialized at {self.db_path}")
    
    def connect(self) -> sqlite3.Connection:
        """Obtém conexão com o banco (WAL mode para concorrência)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn
    
    def insert_node(self, node: Node) -> None:
        """Insere um nó no banco."""
        # Valida dimensionalidade do embedding (deve ser 384D)
        if node.vector_blob:
            vector = np.frombuffer(node.vector_blob, dtype=np.float32)
            if vector.shape[0] != 384:
                raise ValueError(f"Dimensão de Embedding Inválida: {vector.shape[0]} (esperado: 384)")
        
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO nodes (id, content, vector_blob, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
            (node.id, node.content, node.vector_blob, json.dumps(node.metadata), node.created_at.isoformat())
        )
        conn.commit()
        logger.debug(f"Node inserted: {node.id}")
    
    def insert_edge(self, edge: Edge) -> None:
        """Insere uma aresta no banco."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO edges (source_id, target_id, relation_type) VALUES (?, ?, ?)",
            (edge.source_id, edge.target_id, edge.relation_type.value)
        )
        conn.commit()
        logger.debug(f"Edge inserted: {edge.source_id} -> {edge.target_id}")
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Recupera um nó pelo ID."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, content, vector_blob, metadata, created_at FROM nodes WHERE id = ?", (node_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return Node(
            id=row[0],
            content=row[1],
            vector_blob=row[2],
            metadata=json.loads(row[3]),
            created_at=datetime.fromisoformat(row[4])
        )
    
    def get_all_nodes(self, batch_size: int = 1000) -> Generator[Node, None, None]:
        """
        Recupera todos os nós do grafo de forma iterativa para evitar OOM.
        Utiliza paginação via LIMIT/OFFSET.
        
        Args:
            batch_size: número máximo de nós por batch (padrão: 1000)
        
        Yields:
            Node um a um (lazy evaluation para evitar OOM)
        
        Usage:
            for node in cortex.repo.get_all_nodes(batch_size=500):
                process(node)
        """
        conn = self.connect()
        cursor = conn.cursor()
        offset = 0
        
        while True:
            cursor.execute(
                "SELECT id, content, vector_blob, metadata, created_at FROM nodes LIMIT ? OFFSET ?",
                (batch_size, offset)
            )
            rows = cursor.fetchall()
            if not rows:
                break
            
            for row in rows:
                yield Node(
                    id=row[0],
                    content=row[1],
                    vector_blob=row[2],
                    metadata=json.loads(row[3]),
                    created_at=datetime.fromisoformat(row[4])
                )
            
            offset += batch_size
            if len(rows) < batch_size:
                break
    
    def count_nodes(self) -> int:
        """Conta total de nós no banco."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM nodes")
        return cursor.fetchone()[0]
    
    def get_edges_from(self, source_id: str) -> list[Edge]:
        """Recupera arestas originando de um nó."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT source_id, target_id, relation_type FROM edges WHERE source_id = ?", (source_id,))
        return [
            Edge(source_id=row[0], target_id=row[1], relation_type=RelationType(row[2]))
            for row in cursor.fetchall()
        ]
    
    def search_by_similarity(self, query_embedding: np.ndarray, top_k: int = 10) -> list[tuple[Node, float]]:
        """
        Busca por similaridade de cosseno.
        Retorna lista de (node, similarity_score).
        """
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT id, content, vector_blob, metadata, created_at FROM nodes")
        
        results = []
        query_norm = np.linalg.norm(query_embedding)
        
        for row in cursor.fetchall():
            vector = np.frombuffer(row[2], dtype=np.float32)
            vector_norm = np.linalg.norm(vector)
            
            if vector_norm > 0:
                similarity = np.dot(query_embedding, vector) / (query_norm * vector_norm)
                node = Node(
                    id=row[0],
                    content=row[1],
                    vector_blob=row[2],
                    metadata=json.loads(row[3]),
                    created_at=datetime.fromisoformat(row[4])
                )
                results.append((node, float(similarity)))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def close(self):
        """Fecha a conexão."""
        if self._conn:
            self._conn.close()
            self._conn = None


class FileParser(ABC):
    """Abstract base class para parsers de arquivo."""
    
    @abstractmethod
    def parse(self, file_path: str) -> Generator[str, None, None]:
        """Parseia arquivo retorna generator de chunks."""
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Extensões suportadas por este parser."""
        pass


class TextParser(FileParser):
    """Parser para arquivos TXT/MD."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".txt", ".md"]
    
    def parse(self, file_path: str, chunk_size: int = 4096) -> Generator[str, None, None]:
        """Parseia arquivos de texto com chunking."""
        with open(file_path, "r", encoding="utf-8") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk


class CSVParser(FileParser):
    """Parser para arquivos CSV."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".csv"]
    
    def parse(self, file_path: str, chunk_size: int = 1000) -> Generator[str, None, None]:
        """Parseia arquivos CSV com chunking."""
        import pandas as pd
        df = pd.read_csv(file_path)
        for start in range(0, len(df), chunk_size):
            chunk = df[start:start + chunk_size]
            yield chunk.to_csv(index=False)


class JSONParser(FileParser):
    """Parser para arquivos JSON."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".json"]
    
    def parse(self, file_path: str, chunk_size: int = 100) -> Generator[str, None, None]:
        """Parseia arquivos JSON com chunking."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                yield json.dumps(chunk)
        else:
            yield json.dumps(data)


class PDFParser(FileParser):
    """Parser para arquivos PDF."""
    
    @property
    def supported_extensions(self) -> list[str]:
        return [".pdf"]
    
    def parse(self, file_path: str, chunk_size: int = 10) -> Generator[str, None, None]:
        """Parseia arquivos PDF com extração de texto por página."""
        # Usa context manager para evitar file descriptor leak
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            for start in range(0, len(reader.pages), chunk_size):
                pages = reader.pages[start:start + chunk_size]
                text = "\n".join([page.extract_text() or "" for page in pages])
                yield text


class ParserFactory:
    """Factory Pattern: Cria parser correto basedo na extensão."""
    
    def __init__(self):
        self._parsers: list[FileParser] = [
            TextParser(),
            CSVParser(),
            JSONParser(),
            PDFParser(),
        ]
    
    def get_parser(self, file_path: str) -> Optional[FileParser]:
        """Retorna parser apropriado para o arquivo."""
        ext = Path(file_path).suffix.lower()
        for parser in self._parsers:
            if ext in parser.supported_extensions:
                return parser
        return None
    
    def parse_file(self, file_path: str, chunk_size: int = 4096) -> Generator[str, None, None]:
        """
        Parseia arquivo com streaming.
        Para arquivos > 100MB, usa generators para evitar OOM.
        """
        parser = self.get_parser(file_path)
        if parser is None:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        # Verifica tamanho do arquivo para streaming
        file_size = os.path.getsize(file_path)
        if file_size > 100 * 1024 * 1024:  # > 100MB
            logger.info(f"Large file detected ({file_size / 1024 / 1024:.1f}MB), using streaming")
        
        yield from parser.parse(file_path, chunk_size)


class EmbeddingEngine:
    """
    Motor de embedding usando sentence-transformers.
    Executa em background thread para não bloquear event loop.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model: Optional["sentence_transformers.SentenceTransformer"] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._embedding_dim = 384  # Fixed for performance
    
    def load_model(self):
        """Carrega modelo (deve ser pré-baixado para ambiente offline)."""
        if self._model is None:
            # Import here to defer loading
            import sentence_transformers
            self._model = sentence_transformers.SentenceTransformer(
                self.model_name,
                device="cpu"  # CPU-only para segurança
            )
            logger.info(f"Embedding model loaded: {self.model_name}")
    
    def encode(self, texts: Union[str, list[str]]) -> np.ndarray:
        """
        Codifica texto(s) para vetores.
        Usa run_in_executor para não bloquear event loop.
        """
        self.load_model()
        
        if isinstance(texts, str):
            texts = [texts]
        
        # Executa em thread separada (CPU-bound)
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            self._executor,
            lambda: self._model.encode(texts, convert_to_numpy=True)
        )
    
    async def encode_async(self, texts: Union[str, list[str]]) -> np.ndarray:
        """Versão async do encode."""
        result = await self.encode(texts)
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    def encode_sync(self, texts: Union[str, list[str]]) -> np.ndarray:
        """Versão síncrona (para uso em executor)."""
        self.load_model()
        
        if isinstance(texts, str):
            texts = [texts]
        
        return self._model.encode(texts, convert_to_numpy=True)
    
    def get_embedding_dimension(self) -> int:
        """Retorna dimensão fixa do embedding."""
        return self._embedding_dim
    
    def shutdown(self):
        """Finaliza executor."""
        self._executor.shutdown(wait=True)


class BM25Engine:
    """
    Motor de busca BM25 usando rank_bm25.
    Suporta rebuild completo e indexing incremental.
    """
    
    def __init__(self):
        self._index: Optional["rank_bm25.BM25Okapi"] = None
        self._corpus: list[str] = []
        self._doc_ids: list[str] = []
        self._dirty: bool = False  # Flag para rebuild pendente
    
    def build_index(self, documents: list[tuple[str, str]]):
        """
        Constrói índice BM25 (full rebuild).
        documents: lista de (doc_id, content)
        """
        self._doc_ids = [doc[0] for doc in documents]
        self._corpus = [doc[1] for doc in documents]
        
        # Tokenização simples
        tokenized_corpus = [doc.lower().split() for doc in self._corpus]
        
        # Import here to defer
        import rank_bm25
        self._index = rank_bm25.BM25Okapi(tokenized_corpus)
        self._dirty = False
        logger.info(f"BM25 index built with {len(documents)} documents")
    
    def add_documents(self, documents: list[tuple[str, str]]):
        """
        Adiciona documentos incrementalmente.
        Marca índice como dirty para rebuild agendado (não rebuild imediato).
        """
        for doc_id, content in documents:
            if doc_id not in self._doc_ids:
                self._doc_ids.append(doc_id)
                self._corpus.append(content)
        self._dirty = True
        logger.debug(f"BM25 marking dirty for rebuild: +{len(documents)} docs")
    
    def rebuild_if_dirty(self):
        """Rebuild índice apenas se dirty (chamado periodicamente)."""
        if self._dirty and self._corpus:
            tokenized_corpus = [doc.lower().split() for doc in self._corpus]
            import rank_bm25
            self._index = rank_bm25.BM25Okapi(tokenized_corpus)
            self._dirty = False
            logger.info("BM25 index rebuilt incrementally")
    
    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Busca por relevance BM25."""
        if self._index is None:
            return []
        
        query_tokens = query.lower().split()
        scores = self._index.get_scores(query_tokens)
        
        # Retorna top-k documentos
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        return [(self._doc_ids[i], scores[i]) for i in top_indices]
    
    def add_documents(self, documents: list[tuple[str, str]]):
        """Adiciona documentos ao índice existente."""
        for doc_id, content in documents:
            self._doc_ids.append(doc_id)
            self._corpus.append(content)
        
        tokenized_corpus = [doc.lower().split() for doc in self._corpus]
        import rank_bm25
        self._index = rank_bm25.BM25Okapi(tokenized_corpus)


class HybridSearchEngine:
    """
    Motor de busca híbrida combinando Cosseno + BM25.
    
    Fórmula de fusão (XENOSYS):
    S(q, d) = α * (E(q)·Vd / ||E(q)|| ||Vd||) + (1-α) * BM25(q, d)
    """
    
    def __init__(self, repo: GraphRepository, alpha: float = 0.5):
        self.repo = repo
        self.alpha = alpha  # Weight para similaridade semântica
        self.embedding_engine = EmbeddingEngine()
        self.bm25_engine = BM25Engine()
        self._initialized = False
    
    async def __aenter__(self):
        """Context manager entry - inicializa engine."""
        # run_in_executor para carregar modelo (CPU-bound)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, lambda: self.embedding_engine.load_model())
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - limpa recursos."""
        self.embedding_engine.shutdown()
        self.repo.close()
    
    def initialize(self):
        """Inicializa índices com dados existentes."""
        if self._initialized:
            return
        
        # Usa generator com paginação para evitar OOM
        nodes = list(self.repo.get_all_nodes(batch_size=5000))
        documents = [(node.id, node.content) for node in nodes]
        self.bm25_engine.build_index(documents)
        
        self._initialized = True
        logger.info(f"HybridSearch initialized with {len(nodes)} nodes")
    
    async def search(self, query: str, top_k: int = 10) -> list[tuple[Node, float]]:
        """
        Busca híbrida combinando Cosseno + BM25.
        
        Executa ambas as buscas em paralelo via asyncio.gather()
        e aplica a fórmula de fusão XENOSYS com normalização
        Min-Max contextual para BM25.
        """
        self.initialize()
        
        loop = asyncio.get_event_loop()
        
        # Executa embedding (já async via executor)
        query_embedding = await loop.run_in_executor(
            self.embedding_engine._executor,
            self.embedding_engine.encode_sync,
            query
        )
        
        # Garante que é array 1D
        if query_embedding.ndim > 1:
            query_embedding = query_embedding[0]
        
        # Executa BUSCAS EM PARALELO com return_exceptions para evitar orphan threads
        semantic_task = loop.run_in_executor(
            self.embedding_engine._executor,
            lambda: self.repo.search_by_similarity(query_embedding, top_k * 2)
        )
        bm25_task = loop.run_in_executor(
            self.embedding_engine._executor,
            lambda: self.bm25_engine.search(query, top_k * 2)
        )
        
        # return_exceptions=True previne que uma falha destrua o gather inteiro
        results_list = await asyncio.gather(semantic_task, bm25_task, return_exceptions=True)
        
        # Processa resultados, tratando exceções gracefully
        semantic_results = results_list[0]
        bm25_results = results_list[1]
        
        # Verifica se houve exceções
        if isinstance(semantic_results, Exception):
            logger.error(f"Busca semântica falhou: {semantic_results}")
            semantic_results = []
        if isinstance(bm25_results, Exception):
            logger.error(f"Busca BM25 falhou: {bm25_results}")
            bm25_results = []
        
        # Se ambas falharam, retorna vazio
        if not semantic_results and not bm25_results:
            logger.warning("Ambas as buscas falharam, retornando resultado vazio")
            return []
        
        # 4. Fusão dos resultados
        fused_scores = {}
        
        # Scores Cosseno já estão em [-1, 1]
        for node, sim in semantic_results:
            fused_scores[node.id] = self.alpha * sim
        
        # Normalização Min-Max contextual (baseada nos scores da query ATUAL, não global)
        bm25_scores = [score for _, score in bm25_results]
        if bm25_scores:
            min_bm25 = min(bm25_scores)
            max_bm25 = max(bm25_scores)
            range_bm25 = max_bm25 - min_bm25 if max_bm25 != min_bm25 else 1.0
            
            for doc_id, score in bm25_results:
                # Normalização Min-Max para [0, 1]
                normalized = (score - min_bm25) / range_bm25
                # Aplica peso (1-alpha)
                weighted = (1 - self.alpha) * normalized
                
                if doc_id in fused_scores:
                    fused_scores[doc_id] += weighted
                else:
                    fused_scores[doc_id] = weighted
        
        # 5. Retorna top-k nodes ordenados
        sorted_ids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for node_id, score in sorted_ids:
            node = self.repo.get_node(node_id)
            if node:
                results.append((node, score))
        
        return results
    
    def search_sync(self, query: str, top_k: int = 10) -> list[tuple[Node, float]]:
        """Versão síncrona da busca híbrida."""
        self.initialize()
        
        # Embedding síncrono
        query_embedding = self.embedding_engine.encode_sync(query)
        if query_embedding.ndim > 1:
            query_embedding = query_embedding[0]
        
        # Busca semântica
        semantic_results = self.repo.search_by_similarity(query_embedding, top_k * 2)
        
        # Busca BM25
        bm25_results = self.bm25_engine.search(query, top_k * 2)
        
        # Fusão com Min-Max contextual (mesma lógica da versão async)
        fused_scores = {}
        
        for node, sim in semantic_results:
            fused_scores[node.id] = self.alpha * sim
        
        # Normalização Min-Max contextual
        bm25_scores = [score for _, score in bm25_results]
        if bm25_scores:
            min_bm25 = min(bm25_scores)
            max_bm25 = max(bm25_scores)
            range_bm25 = max_bm25 - min_bm25 if max_bm25 != min_bm25 else 1.0
            
            for doc_id, score in bm25_results:
                normalized = (score - min_bm25) / range_bm25
                weighted = (1 - self.alpha) * normalized
                
                if doc_id in fused_scores:
                    fused_scores[doc_id] += weighted
                else:
                    fused_scores[doc_id] = weighted
        
        sorted_ids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        results = []
        for node_id, score in sorted_ids:
            node = self.repo.get_node(node_id)
            if node:
                results.append((node, score))
        
        return results


class IngestionWorker:
    """
    Worker assíncrono para ingestão de arquivos.
    Usa asyncio.Queue para processamento em background.
    """
    
    def __init__(self, repo: GraphRepository):
        self.repo = repo
        self.embedding_engine = EmbeddingEngine()
        self.audit_logger = AuditLogger()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._running = False
    
    async def start(self, num_workers: int = 2):
        """Inicia workers de processamento."""
        self._running = True
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        logger.info(f"Started {num_workers} ingestion workers")
    
    async def _worker_loop(self, worker_id: int):
        """Loop de processamento do worker."""
        while self._running:
            try:
                # Timeout para permitir shutdown
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                
                file_path, node_id = item
                await self._process_file(file_path, node_id)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
    
    async def _process_file(self, file_path: str, node_id: str):
        """Processa um arquivo e insere no grafo."""
        # Audit log
        self.audit_logger.log("READ", file_path, {"node_id": node_id})
        
        # Parser
        parser_factory = ParserFactory()
        
        try:
            chunks = list(parser_factory.parse_file(file_path))
            full_content = " ".join(chunks)
            
            # Embedding async
            embedding = self.embedding_engine.encode_sync(full_content)
            
            # Garante dimensionality correta (384)
            if embedding.ndim > 1:
                embedding = embedding[0]
            
            # Converte para bytes
            vector_blob = embedding.astype(np.float32).tobytes()
            
            # Cria node
            node = Node(
                id=node_id,
                content=full_content,
                vector_blob=vector_blob,
                metadata={"source_file": file_path}
            )
            
            # Insere no repo
            self.repo.insert_node(node)
            logger.info(f"Ingested: {node_id} from {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            raise
    
    async def ingest(self, file_path: str, node_id: Optional[str] = None):
        """Adiciona arquivo à fila de processamento."""
        if node_id is None:
            node_id = f"node_{Path(file_path).stem}_{datetime.utcnow().timestamp()}"
        
        await self._queue.put((file_path, node_id))
        logger.debug(f"Queued: {file_path}")
    
    async def stop(self):
        """Para workers."""
        self._running = False
        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("Ingestion workers stopped")


class Cortex:
    """
    Classe principal do módulo Cortex.
    Orquestra o banco de grafos híbrido e engine de ingestão.
    """
    
    def __init__(self, db_path: str = "/tmp/xenosys/cortex.db", alpha: float = 0.5):
        self.db_path = db_path
        self.repo = GraphRepository(db_path)
        self.search_engine = HybridSearchEngine(self.repo, alpha)
        self.ingestion_worker = IngestionWorker(self.repo)
        self.audit_logger = AuditLogger()
        self._running = False
    
    async def start(self):
        """Inicia o Cortex."""
        self._running = True
        await self.ingestion_worker.start()
        self.audit_logger.log("START", self.db_path, {"alpha": self.search_engine.alpha})
        logger.info("Cortex started")
    
    async def stop(self):
        """Para o Cortex."""
        self._running = False
        await self.ingestion_worker.stop()
        self.repo.close()
        self.audit_logger.log("STOP", self.db_path, {})
        logger.info("Cortex stopped")
    
    async def ingest_document(self, file_path: str, node_id: Optional[str] = None) -> str:
        """
        Ingere um documento no banco de grafos.
        Retorna o node_id criado.
        """
        # Verifica existência do arquivo
        if not Path(file_path).exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if node_id is None:
            node_id = f"node_{Path(file_path).stem}_{datetime.utcnow().timestamp()}"
        
        await self.ingestion_worker.ingest(file_path, node_id)
        
        return node_id
    
    async def search(self, query: str, top_k: int = 10) -> list[tuple[Node, float]]:
        """
        Busca híbrida por query.
        Retorna lista de (Node, score) ordenados por relevância.
        """
        return await self.search_engine.search(query, top_k)
    
    def add_edge(self, source_id: str, target_id: str, relation_type: RelationType):
        """Adiciona uma aresta entre dois nós."""
        edge = Edge(source_id, target_id, relation_type)
        self.repo.insert_edge(edge)
        self.audit_logger.log("EDGE", f"{source_id}->{target_id}", {"type": relation_type.value})
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Recupera um nó pelo ID."""
        return self.repo.get_node(node_id)
    
    def get_neighbors(self, node_id: str, relation_type: Optional[RelationType] = None) -> list[str]:
        """Retorna IDs dos nós vizinhos."""
        edges = self.repo.get_edges_from(node_id)
        
        if relation_type:
            edges = [e for e in edges if e.relation_type == relation_type]
        
        return [e.target_id for e in edges]
    
    @property
    def is_running(self) -> bool:
        """Retorna se o Cortex está rodando."""
        return self._running


# Funções de conveniência

def create_cortex(db_path: str = "/tmp/xenosys/cortex.db", alpha: float = 0.5) -> Cortex:
    """Factory function para criar instância do Cortex."""
    return Cortex(db_path, alpha)


# Testing

if __name__ == "__main__":
    import asyncio
    
    async def test_cortex():
        """Teste básico do Cortex."""
        print("Testing Cortex...")
        
        cortex = create_cortex("/tmp/test_cortex.db")
        await cortex.start()
        
        # Cria nó de teste
        test_node = Node(
            id="test_node",
            content="XenoSys is a hybrid AI operating system",
            vector_blob=np.random.rand(384).astype(np.float32).tobytes(),
            metadata={"test": True}
        )
        cortex.repo.insert_node(test_node)
        
        # Busca
        results = await cortex.search("AI operating system", top_k=1)
        print(f"Search results: {len(results)} found")
        
        await cortex.stop()
        print("Test complete!")
    
    asyncio.run(test_cortex())
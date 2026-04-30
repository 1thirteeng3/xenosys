"""
Q5: Cortex - Banco de Grafos Híbrido e Ingestão Local

Este módulo contém:
- GraphRepository: Persistence layer para grafos SQLite
- HybridSearchEngine: Busca híbrida (Cosseno + BM25)
- IngestionWorker: Processamento assíncrono de arquivos
- ParserFactory: Parsers para PDF, TXT, MD, CSV, JSON
- Cortex: Classe principal do módulo

用法 (Usage):
    from src.cortex import create_cortex
    
    cortex = create_cortex("/tmp/cortex.db")
    await cortex.start()
    
    # Ingestão de documento
    await cortex.ingest_document("/path/to/doc.pdf")
    
    # Busca
    results = await cortex.search("query", top_k=5)
    
    await cortex.stop()
"""

# Exports públicos
from .cortex import (
    # Classes principais
    Cortex,
    GraphRepository,
    HybridSearchEngine,
    EmbeddingEngine,
    BM25Engine,
    IngestionWorker,
    
    # Modelos de dados
    Node,
    Edge,
    RelationType,
    
    # Parsers
    ParserFactory,
    FileParser,
    TextParser,
    CSVParser,
    JSONParser,
    PDFParser,
    
    # Utilitários
    AuditLogger,
    NetworkSecurityError,
    
    # Factory
    create_cortex,
)

__all__ = [
    "Cortex",
    "GraphRepository", 
    "HybridSearchEngine",
    "EmbeddingEngine",
    "BM25Engine",
    "IngestionWorker",
    "Node",
    "Edge",
    "RelationType",
    "ParserFactory",
    "FileParser",
    "TextParser",
    "CSVParser",
    "JSONParser",
    "PDFParser",
    "AuditLogger",
    "NetworkSecurityError",
    "create_cortex",
]
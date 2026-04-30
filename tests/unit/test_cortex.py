"""
Testes unitários para Q5 - Cortex

Valida as funcionalidades do banco de grafos híbrido.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent))

# Import diretamente do módulo
from src.cortex.cortex import (
    GraphRepository,
    Node,
    Edge,
    RelationType,
    ParserFactory,
    TextParser,
    CSVParser,
    JSONParser,
    PDFParser,
    HybridSearchEngine,
    EmbeddingEngine,
    BM25Engine,
    AuditLogger,
    create_cortex,
)


class TestGraphRepository(unittest.TestCase):
    """Testa GraphRepository."""
    
    def setUp(self):
        """Cria banco temporário."""
        # Mock network isolation para testes
        with patch('src.cortex.cortex._check_network_isolation', return_value=True):
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            self.db_path = self.temp_db.name
            self.temp_db.close()
            self.repo = GraphRepository(self.db_path)
    
    def tearDown(self):
        """Limpa arquivos temporários."""
        self.repo.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        # Remove WAL files
        wal_path = self.db_path + "-wal"
        if os.path.exists(wal_path):
            os.unlink(wal_path)
    
    def test_insert_node(self):
        """Testa inserção de nó."""
        node = Node(
            id="test_node_1",
            content="Test content",
            vector_blob=np.random.rand(384).astype(np.float32).tobytes(),
            metadata={"key": "value"}
        )
        self.repo.insert_node(node)
        
        # Recupera nó
        retrieved = self.repo.get_node("test_node_1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, "test_node_1")
        self.assertEqual(retrieved.content, "Test content")
    
    def test_insert_edge(self):
        """Testa inserção de aresta."""
        # Insere dois nós
        node1 = Node("node1", "content1", np.random.rand(384).astype(np.float32).tobytes())
        node2 = Node("node2", "content2", np.random.rand(384).astype(np.float32).tobytes())
        self.repo.insert_node(node1)
        self.repo.insert_node(node2)
        
        # Insere aresta
        edge = Edge("node1", "node2", RelationType.SUPPORTS)
        self.repo.insert_edge(edge)
        
        # Recupera arestas
        edges = self.repo.get_edges_from("node1")
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].relation_type, RelationType.SUPPORTS)
    
    def test_search_by_similarity(self):
        """Testa busca por similaridade."""
        # Insere nós
        for i in range(5):
            node = Node(
                f"node_{i}",
                f"Content {i}",
                np.random.rand(384).astype(np.float32).tobytes()
            )
            self.repo.insert_node(node)
        
        # Busca
        query = np.random.rand(384).astype(np.float32)
        results = self.repo.search_by_similarity(query, top_k=3)
        
        self.assertLessEqual(len(results), 3)
        for node, score in results:
            self.assertIsInstance(node, Node)


class TestParsers(unittest.TestCase):
    """Testa os parsers de arquivo."""
    
    def setUp(self):
        """Cria arquivos temporários."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Limpa arquivos temporários."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_text_parser(self):
        """Testa parser de texto."""
        # Cria arquivo de texto
        text_file = os.path.join(self.temp_dir, "test.txt")
        with open(text_file, "w") as f:
            f.write("Hello world\nTest content")
        
        # Parseia
        parser = TextParser()
        chunks = list(parser.parse(text_file))
        
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0], "Hello world\nTest content")
    
    def test_csv_parser(self):
        """Testa parser CSV."""
        # Cria arquivo CSV
        csv_file = os.path.join(self.temp_dir, "test.csv")
        with open(csv_file, "w") as f:
            f.write("name,age\nAlice,30\nBob,25")
        
        # Parseia
        parser = CSVParser()
        chunks = list(parser.parse(csv_file))
        
        self.assertGreater(len(chunks), 0)
        self.assertIn("name", chunks[0])
    
    def test_json_parser(self):
        """Testa parser JSON."""
        # Cria arquivo JSON
        json_file = os.path.join(self.temp_dir, "test.json")
        with open(json_file, "w") as f:
            json.dump({"key": "value", "array": [1, 2, 3]}, f)
        
        # Parseia
        parser = JSONParser()
        chunks = list(parser.parse(json_file))
        
        self.assertGreater(len(chunks), 0)
        data = json.loads(chunks[0])
        self.assertEqual(data["key"], "value")
    
    def test_parser_factory_unsupported(self):
        """Testa parser factory com tipo não suportado."""
        factory = ParserFactory()
        parser = factory.get_parser("test.xyz")
        self.assertIsNone(parser)


class TestAuditLogger(unittest.TestCase):
    """Testa AuditLogger."""
    
    def setUp(self):
        """Cria logger temporário."""
        self.temp_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
        self.log_path = self.temp_file.name
        self.temp_file.close()
        self.logger = AuditLogger(self.log_path)
    
    def tearDown(self):
        """Limpa arquivos."""
        if os.path.exists(self.log_path):
            os.unlink(self.log_path)
    
    def test_log(self):
        """Testa logging."""
        self.logger.log("READ", "/tmp/test.txt", {"size": 1024})
        
        with open(self.log_path, "r") as f:
            line = f.readline()
            entry = json.loads(line)
            self.assertEqual(entry["operation"], "READ")
            self.assertEqual(entry["file_path"], "/tmp/test.txt")


class TestHybridSearch(unittest.TestCase):
    """Testa HybridSearchEngine."""
    
    def setUp(self):
        """Cria banco temporário."""
        # Mock network isolation para testes
        with patch('src.cortex.cortex._check_network_isolation', return_value=True):
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            self.db_path = self.temp_db.name
            self.temp_db.close()
            self.repo = GraphRepository(self.db_path)
        self.search = HybridSearchEngine(self.repo, alpha=0.5)
    
    def tearDown(self):
        """Limpa arquivos temporários."""
        self.repo.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        wal_path = self.db_path + "-wal"
        if os.path.exists(wal_path):
            os.unlink(wal_path)
    
    def test_initialization(self):
        """Testa inicialização."""
        # Insere nós
        for i in range(3):
            node = Node(
                f"node_{i}",
                f"Content about AI {i}",
                np.random.rand(384).astype(np.float32).tobytes()
            )
            self.repo.insert_node(node)
        
        self.search.initialize()
        
        self.assertTrue(self.search._initialized)


class TestCortexIntegration(unittest.TestCase):
    """Teste de integração do Cortex."""
    
    def setUp(self):
        """Cria Cortex temporário."""
        # Mock network isolation para testes
        with patch('src.cortex.cortex._check_network_isolation', return_value=True):
            self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            self.db_path = self.temp_db.name
            self.temp_db.close()
            self.cortex = create_cortex(self.db_path)
    
    def tearDown(self):
        """Limpa arquivos temporários."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        wal_path = self.db_path + "-wal"
        if os.path.exists(wal_path):
            os.unlink(wal_path)
    
    @unittest.skipIf(
        os.environ.get("SKIP_SLOW_TESTS"),
        "Skipping slow tests"
    )
    def test_cortex_lifecycle(self):
        """Testa ciclo de vida completo."""
        async def run():
            await self.cortex.start()
            self.assertTrue(self.cortex.is_running)
            
            await self.cortex.stop()
            self.assertFalse(self.cortex.is_running)
        
        asyncio.run(run())


def run_tests():
    """Executa tests."""
    # Cria test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Adiciona testes
    suite.addTests(loader.loadTestsFromTestCase(TestGraphRepository))
    suite.addTests(loader.loadTestsFromTestCase(TestParsers))
    suite.addTests(loader.loadTestsFromTestCase(TestAuditLogger))
    suite.addTests(loader.loadTestsFromTestCase(TestHybridSearch))
    suite.addTests(loader.loadTestsFromTestCase(TestCortexIntegration))
    
    # Executa
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
"""
Testes Unitários para RLMInferenceEngine

Estes testes verificam:
- PythonErrorParser
- TaskGraph
- LLM Providers (sem API real)
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from inference.rlm_inference import (
    Task,
    TaskGraph,
    PythonErrorParser,
    IterationResult,
    InferenceResult,
)


class TestPythonErrorParser:
    """Testes para PythonErrorParser."""
    
    def test_syntax_error(self):
        """Testa detecção de SyntaxError."""
        output = '  File "<stdin>", line 1\n    print(\n                       ^\nSyntaxError: EOF in multi-line statement'
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == True
        assert result["error_type"] == "SyntaxError"
        print("✓ SyntaxError detectado")
    
    def test_name_error(self):
        """Testa detecção de NameError."""
        output = 'NameError: name "x" is not defined'
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == True
        assert result["error_type"] == "NameError"
        assert "x" in result["error_message"]
        print("✓ NameError detectado")
    
    def test_type_error(self):
        """Testa detecção de TypeError."""
        output = 'TypeError: unsupported operand + for str and int'
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == True
        assert result["error_type"] == "TypeError"
        print("✓ TypeError detectado")
    
    def test_no_error(self):
        """Testa código sem erros."""
        output = 'Hello, World!\n42'
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == False
        assert result["error_type"] is None
        print("✓ Código sem erro OK")
    
    def test_import_error(self):
        """Testa detecção de ImportError."""
        output = "ModuleNotFoundError: No module named 'numpy'"
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == True
        assert result["error_type"] == "ModuleNotFoundError"
        print("✓ ImportError detectado")
    
    def test_index_error(self):
        """Testa detecção de IndexError."""
        output = "IndexError: list index out of range"
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == True
        assert result["error_type"] == "IndexError"
        print("✓ IndexError detectado")
    
    def test_key_error(self):
        """Testa detecção de KeyError."""
        output = "KeyError: 'missing_key'"
        result = PythonErrorParser.parse(output)
        assert result["has_error"] == True
        assert result["error_type"] == "KeyError"
        print("✓ KeyError detectado")


class TestTaskGraph:
    """Testes para TaskGraph."""
    
    def test_add_task(self):
        """Testa adicionar tarefa."""
        graph = TaskGraph()
        task = Task(
            task_id="task_1",
            description="Load data",
            dependencies=[]
        )
        graph.add_task(task)
        assert "task_1" in graph.tasks
        print("✓ Adicionar tarefa OK")
    
    def test_add_task_with_deps(self):
        """Testa adicionar tarefa com dependências."""
        graph = TaskGraph()
        
        task1 = Task(task_id="task_1", description="Load", dependencies=[])
        task2 = Task(
            task_id="task_2", 
            description="Process", 
            dependencies=["task_1"]
        )
        
        graph.add_task(task1)
        graph.add_task(task2)
        
        assert "task_1" in graph.tasks
        assert "task_2" in graph.tasks
        print("✓ Tarefa com dependências OK")
    
    def test_sorted_tasks(self):
        """Testa ordenação topológica."""
        graph = TaskGraph()
        
        task1 = Task(task_id="task_1", description="Load", dependencies=[])
        task2 = Task(
            task_id="task_2", 
            description="Process", 
            dependencies=["task_1"]
        )
        task3 = Task(
            task_id="task_3", 
            description="Output", 
            dependencies=["task_2"]
        )
        
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)
        
        sorted_tasks = graph.get_sorted_tasks()
        ids = [t.task_id for t in sorted_tasks]
        
        # task_1 deve vir primeiro
        assert ids[0] == "task_1"
        print("✓ Ordenação topológica OK")
    
    def test_ready_tasks(self):
        """Testa get_ready_tasks."""
        graph = TaskGraph()
        
        task1 = Task(task_id="task_1", description="Load", dependencies=[])
        task2 = Task(
            task_id="task_2", 
            description="Process", 
            dependencies=["task_1"]
        )
        
        graph.add_task(task1)
        graph.add_task(task2)
        
        ready = graph.get_ready_tasks(completed=set())
        assert len(ready) == 1
        assert ready[0].task_id == "task_1"
        print("✓ Tarefas ready OK")
    
    def test_is_complete(self):
        """Testa is_complete."""
        graph = TaskGraph()
        
        task = Task(task_id="task_1", description="Load", dependencies=[])
        graph.add_task(task)
        
        assert graph.is_complete() == False
        
        task.status = "completed"
        assert graph.is_complete() == True
        print("✓ is_complete OK")


class TestDataClasses:
    """Testes para data classes."""
    
    def test_iteration_result(self):
        """Testa IterationResult."""
        result = IterationResult(
            iteration=1,
            code="print(42)",
            is_success=True,
            should_retry=False
        )
        
        assert result.iteration == 1
        assert result.is_success == True
        
        # to_dict
        d = result.to_dict()
        assert d["iteration"] == 1
        assert d["is_success"] == True
        print("✓ IterationResult OK")
    
    def test_inference_result(self):
        """Testa InferenceResult."""
        result = InferenceResult(
            prompt="Calculate 2+2",
            success=True,
            final_output="4",
            total_duration=1.5
        )
        
        assert result.success == True
        assert result.total_duration == 1.5
        
        d = result.to_dict()
        assert d["success"] == True
        print("✓ InferenceResult OK")


def run_tests():
    """Executa todos os testes."""
    print("=== Testes RLMInferenceEngine ===\n")
    
    # TestPythonErrorParser
    print("1. PythonErrorParser:")
    tester = TestPythonErrorParser()
    tester.test_syntax_error()
    tester.test_name_error()
    tester.test_type_error()
    tester.test_no_error()
    tester.test_import_error()
    tester.test_index_error()
    tester.test_key_error()
    
    print("\n2. TaskGraph:")
    tester = TestTaskGraph()
    tester.test_add_task()
    tester.test_add_task_with_deps()
    tester.test_sorted_tasks()
    tester.test_ready_tasks()
    tester.test_is_complete()
    
    print("\n3. DataClasses:")
    tester = TestDataClasses()
    tester.test_iteration_result()
    tester.test_inference_result()
    
    print("\n=== Todos os testes passaram ===")


if __name__ == "__main__":
    run_tests()
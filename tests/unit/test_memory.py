"""
Testes Unitários - Q4: Stateful Memory System
"""

import asyncio
import os
import sys
import tempfile

# Adicionar src ao path
BASEDIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, BASEDIR)

from src.memory.session_manager import SessionManager
from src.memory.variable_registry import VariableRegistry


def test_variable_registry():
    """Teste 1: VariableRegistry básico"""
    print("=== Teste 1: VariableRegistry ===")
    
    reg = VariableRegistry()
    
    # Registrar variáveis
    asyncio.run(reg.register("nome", "Alice"))
    asyncio.run(reg.register("idade", 30))
    asyncio.run(reg.register("scores", [1, 2, 3]))
    
    # Listar
    vars = asyncio.run(reg.list_variables())
    print(f"✓ Variáveis: {vars}")
    assert len(vars) == 3
    
    # Get
    nome = asyncio.run(reg.get("nome"))
    assert nome == "Alice"
    print(f"✓ Get: {nome}")
    
    # Stats
    stats = asyncio.run(reg.get_stats())
    print(f"✓ Stats: {stats}")
    assert stats["count"] == 3
    
    # Serialização
    data = reg.to_dict()
    print(f"✓ Serialização: {len(data['variables'])} variáveis")
    
    print("✓ VariableRegistry OK")


def test_variable_registry_restore():
    """Teste 2: VariableRegistry restore"""
    print("\n=== Teste 2: VariableRegistry Restore ===")
    
    reg1 = VariableRegistry()
    asyncio.run(reg1.register("x", [1, 2, 3]))
    asyncio.run(reg1.register("y", {"a": 1}))
    
    # Serialize
    data = reg1.to_dict()
    
    # Restore
    reg2 = VariableRegistry.from_dict(data)
    
    vars = asyncio.run(reg2.list_variables())
    assert len(vars) == 2
    print(f"✓ Restauradas: {vars}")
    
    x = asyncio.run(reg2.get("x"))
    assert x == [1, 2, 3]
    print(f"✓ Valor restaurado: {x}")
    
    print("✓ Restore OK")


def test_session_manager_basic():
    """Teste 3: SessionManager básico"""
    print("\n=== Teste 3: SessionManager ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(state_dir=tmpdir)
        
        # Criar sessão
        sid = asyncio.run(sm.create_session())
        print(f"✓ Sessão criada: {sid}")
        
        # Variáveis
        asyncio.run(sm.set_variable("data", [1, 2, 3], sid))
        asyncio.run(sm.set_variable("name", "test", sid))
        
        vars = asyncio.run(sm.list_variables(sid))
        print(f"✓ Variáveis: {vars}")
        assert len(vars) == 2
        
        # Get
        data = asyncio.run(sm.get_variable("data", sid))
        print(f"✓ Get: {data}")
        assert data == [1, 2, 3]
        
        # Contexto
        asyncio.run(sm.set_context("mode", "test", sid))
        mode = asyncio.run(sm.get_context("mode", sid))
        assert mode == "test"
        print(f"✓ Contexto: {mode}")
        
        # Stats
        stats = asyncio.run(sm.get_stats(sid))
        print(f"✓ Stats: {stats}")
        
        # Close
        asyncio.run(sm.close_session(sid))
        print(f"✓ Sessão fechada")
        
        print("✓ SessionManager OK")


def test_checkpoint():
    """Teste 4: Checkpoint"""
    print("\n=== Teste 4: Checkpoint ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(
            state_dir=tmpdir,
            checkpoint_interval=1  # 1 segundo para teste
        )
        
        # Criar sessão com variáveis
        sid = asyncio.run(sm.create_session())
        asyncio.run(sm.set_variable("value", 42, sid))
        asyncio.run(sm.set_context("key", "data", sid))
        
        # Escrever checkpoint manualmente
        result = asyncio.run(sm._write_checkpoint(sid))
        assert result == True
        print(f"✓ Checkpoint escrito")
        
        # Deletar variáveis da memória (sync)
        sm._sessions[sid].variables.clear()
        
        # Restaurar
        result = asyncio.run(sm.restore_from_checkpoint(sid))
        assert result == True
        
        value = asyncio.run(sm.get_variable("value", sid))
        assert value == 42
        print(f"✓ Restaurado: value={value}")
        
        asyncio.run(sm.shutdown())
        
        print("✓ Checkpoint OK")


async def test_main_async():
    """Teste 5: Async Operations"""
    print("\n=== Teste 5: Async Operations ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(state_dir=tmpdir, checkpoint_interval=1)
        
        # Múltiplas sessões
        s1 = await sm.create_session("session-1")
        s2 = await sm.create_session("session-2")
        
        await sm.set_variable("var1", "val1", s1)
        await sm.set_variable("var2", "val2", s2)
        
        # Switch sessions
        await sm.set_active_session(s1)
        val1 = await sm.get_variable("var1")
        assert val1 == "val1"
        
        await sm.set_active_session(s2)
        val2 = await sm.get_variable("var2")
        assert val2 == "val2"
        
        print(f"✓ Múltiplas sessões OK")
        
        # List
        sessions = await sm.list_sessions()
        print(f"✓ Lista: {sessions}")
        
        await sm.shutdown()


def test_context_compression():
    """Teste 6: Context compression"""
    print("\n=== Teste 6: Context Compression ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        sm = SessionManager(
            state_dir=tmpdir,
            token_limit=100,  # Limite baixo para teste
            compress_threshold=0.5
        )
        
        sid = asyncio.run(sm.create_session())
        
        # Adicionar muito contexto
        asyncio.run(sm.set_context("large", "x" * 200, sid))
        
        # Comprimir
        result = asyncio.run(sm.compress_context(sid))
        print(f"✓ Compressão: {result}")
        
        # Verificar que foi marcado
        compressed = asyncio.run(sm.get_context("_compressed", sid))
        print(f"✓ Marcado como comprimido: {compressed}")
        
        asyncio.run(sm.shutdown())
        
        print("✓ Compression OK")


def main():
    print("=" * 60)
    print("TESTES - Q4: STATEFUL MEMORY SYSTEM")
    print("=" * 60)
    
    # Sync tests
    test_variable_registry()
    test_variable_registry_restore()
    test_session_manager_basic()
    test_checkpoint()
    test_context_compression()
    
    # Async tests
    asyncio.run(test_main_async())
    
    print("\n" + "=" * 60)
    print("TODOS OS TESTES PASSARAM")
    print("=" * 60)


if __name__ == "__main__":
    main()
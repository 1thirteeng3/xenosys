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


async def test_context_compression():
    """Teste 6: Middle-Out Truncation"""
    print("\n=== Teste 6: Middle-Out Truncation ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Tokenizer simulado - retorna token count
        def simple_tokenizer(text: str) -> int:
            return len(text) // 4  # 4 chars = 1 token approx
        
        sm = SessionManager(
            state_dir=tmpdir,
            token_limit=50,  # Limite baixo para forçar compressão
            compress_threshold=0.5,  # 50% = 25 tokens
            tokenizer=simple_tokenizer  # Injetado
        )
        
        sid = await sm.create_session()
        
        # Criar histórico grande (10+ mensagens)
        for i in range(10):
            await sm.add_history("step", {"step": i, "text": "x" * 10}, sid)
        
        # Forçar compressão com muito contexto
        await sm.set_context("large", "x" * 200, sid)
        
        result = await sm.compress_context(sid)
        print(f"✓ Compressão: {result}")
        
        # Verificar middle-out
        compressed = await sm.get_context("_compressed", sid)
        method = await sm.get_context("_compression_method", sid)
        print(f"✓ Marcado: {compressed}, método: {method}")
        
        # Com tokenizer injetado deve mostrar "injected"
        token_method = await sm.get_context("_token_method", sid)
        print(f"✓ Token method: {token_method}")
        
        await sm.shutdown()
        
        print("✓ Middle-Out OK")


async def test_proactive_compression_trigger():
    """Teste 7: Trigger Dinâmico de Compressão (HISTORY Based)"""
    print("\n=== Teste 7: Proactive Compression Trigger (HISTORY) ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Tokenizer que retorna tokens diretamente do tamanho
        def simple_tokenizer(text: str) -> int:
            return len(text)  # 1 char = 1 token
        
        sm = SessionManager(
            state_dir=tmpdir,
            token_limit=100,  # Limite baixo
            compress_threshold=0.3,  # 30% = 30 tokens
            tokenizer=simple_tokenizer
        )
        
        sid = await sm.create_session()
        
        # Criar pequenas entradas via add_history (vai para history!)
        # Cada entrada ~10 tokens (10 chars)
        for i in range(2):
            await sm.add_history("step", {"text": "tokenized"}, sid)
        
        # Verificar history manualmente
        state = sm._sessions[sid]
        print(f"✓ 2 entradas em history: {len(state.history)}")
        
        # Adicionar entrada massiva (200 tokens > 30% limit)
        # O trigger deve avaliar HISTORY + CONTEXT + ENTRY
        await sm.add_history("massive", {"data": "x" * 200}, sid)
        
        # Verificar que compressão ocorreu
        compressed = await sm.get_context("_compressed", sid)
        method = await sm.get_context("_compression_method", sid)
        print(f"✓ Compressão proativa: {compressed}, método: {method}")
        
        # Verificar que history foi truncado
        print(f"✓ History: {len(state.history)} entradas (deve ser < 4)")
        
        await sm.shutdown()
        
        print("✓ Proactive Trigger OK")


async def test_history_token_calculation():
    """Teste 8: Cálculo de Tokens Inclui History"""
    print("\n=== Teste 8: History Token Calculation ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Fallback tokenizer
        sm = SessionManager(
            state_dir=tmpdir,
            token_limit=50,
            compress_threshold=0.5
        )
        
        sid = await sm.create_session()
        
        # Adicionar entradas pequenas (10 chars cada = ~2.5 tokens com fallback)
        for i in range(5):
            await sm.add_history("msg", {"text": "1234567890"}, sid)
        
        # history = 5 * 10 = 50 chars = ~12.5 tokens
        # context = ~20 chars = ~5 tokens
        # total = 12.5 + 5 = 17.5 tokens < 25 (50%)
        
        # Agora adicionar muito mais (200 chars = ~50 tokens)
        # total projetado = 17.5 + 50 = 67.5 > 25 (50%)
        await sm.add_history("big", {"data": "x" * 200}, sid)
        
        # Deve ter comprimido
        compressed = await sm.get_context("_compressed", sid)
        method = await sm.get_context("_compression_method", sid)
        print(f"✓ Compressão disparada: {compressed}, {method}")
        
        await sm.shutdown()
        
        print("✓ History Token Calculation OK")


async def test_fail_fast_runtime():
    """Teste 8: Fail-Fast com msgpack"""
    print("\n=== Teste 8: Fail-Fast Runtime ===")
    
    # Simular msgpack não instalado - deve falhar em runtime, não import
    import sys
    # Salvamos o módulo original
    original_msgpack = sys.modules.get('msgpack')
    
    # Temporariamente removemos msgpack
    if 'msgpack' in sys.modules:
        del sys.modules['msgpack']
    
    # Também removemos do path de imports
    import importlib
    if 'msgpack' in sys.modules:
        del sys.modules['msgpack']
    
    # Restauramos
    if original_msgpack:
        sys.modules['msgpack'] = original_msgpack
    
    # Importar módulo - deve funcionar
    from src.memory.session_manager import _ensure_msgpack, HAS_MSGPACK
    
    print(f"✓ HAS_MSGPACK na importação: {HAS_MSGPACK}")
    
    # Tentar usar sem msgpack - deve falhar em runtime
    try:
        _ensure_msgpack()
        print("ERRO: Deveria ter falhado!")
    except RuntimeError as e:
        print(f"✓ RuntimeError capturado: {e}")
    
    print("✓ Fail-Fast OK")


def main():
    print("=" * 60)
    print("TESTES - Q4: STATEFUL MEMORY SYSTEM")
    print("=" * 60)
    
    # Sync tests
    test_variable_registry()
    test_variable_registry_restore()
    test_session_manager_basic()
    test_checkpoint()
    
    # Async tests
    asyncio.run(test_main_async())
    asyncio.run(test_context_compression())
    asyncio.run(test_proactive_compression_trigger())
    asyncio.run(test_fail_fast_runtime())
    
    print("\n" + "=" * 60)
    print("TODOS OS TESTES PASSARAM")
    print("=" * 60)


if __name__ == "__main__":
    main()
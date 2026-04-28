# Q1: Container Manager - Gerenciador de Ciclo de Vida

## Visão Geral

Este documento descreve a implementação do módulo ContainerManager para a plataforma XenoSys, responsável por criar, gerenciar e destruir containers Docker como sessões REPL persistentes.

## Funcionalidades Implementadas

### ✅ create_container()
- Cria containers Docker interativos modo `-it`
- Retorna container_id em < 800ms (usando warm pool)
-命名ação: `cog-` + uuid4 curto

### ✅ execute(code)
- Executa código Python no container
- Retorna stdout/stderr separados
- Suporta IPC streaming com stdin/stdout/stderr

### ✅ destroy()
- Remove container e todos os artefatos
- Limpa recursos automaticamente

### ✅ Warm Pool (N=3)
- Mantém 3 containers pré-inicializados
- Cold start rápido (< 800ms)

### ✅ Health Monitoring
- Verifica status a cada 30 segundos
- Executa em background async

### ✅ Recovery Automático
- Max 5 segundos para recovery
- Reconstitui container em caso de crash

### ✅ Restrições de Hardware
- RAM: 2GB (padrão)
- CPU: 2 cores (padrão)
- Rede: Desabilitada (segurança)

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    ContainerManager                          │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Container  │  │ Container  │  │ Container  │  (Warm Pool)│
│  │  Pool     │  │   Ready    │  │   Ready   │    N=3      │
│  └────────────┘  └────────────┘  └────────────┘            │
├─────────────────────────────────────────────────────────────┤
│  Health Monitor (30s interval)                               │
│  Recovery Controller (max 5s)                              │
└─────────────────────────────────────────────────────────────┘
```

## Padrões de Projeto Aplicados

1. **Object Pool**: Warm pool para inicialização rápida
2. **Factory**: Criação padronizada de containers
3. **Observer**: Health monitoring com callbacks
4. **Strategy**: Estratégias de recovery

## Dependências

```python
docker>=7.0.0
asyncio (stdlib)
```

## Uso

### API Assíncrona

```python
from src.runtime import ContainerManager

manager = ContainerManager(pool_size=3)

# Inicializa
await manager.initialize()

# Cria container (usa warm pool se disponível)
container_id = await manager.create_container()

# Executa código
result = await manager.execute(
    container_id,
    "print('Hello, World!')"
)
print(result.stdout)  # Hello, World!

# Destrói container
await manager.destroy(container_id)

# Encerramento
await manager.shutdown()
```

### API Síncrona

```python
from src.runtime import ContainerManagerSync

manager = ContainerManagerSync(pool_size=3)
manager.initialize()

container_id = manager.create_container()
result = manager.execute(container_id, "print('Hello!')")

manager.destroy(container_id)
manager.shutdown()
```

## Teste

```bash
python3 src/runtime/container_manager.py --test
```

## Tempo de Execução

- Criação com warm pool: < 1ms
- Criação cold: ~500ms
- Execução de código: ~60-100ms
- Destruição: ~50ms

## Limitações

- Imagem base deve estar disponível localmente (`python:3.12-slim`)
- Rede desabilitada por segurança
- Sem suporte a entrada stdin interativa (apenas exec)
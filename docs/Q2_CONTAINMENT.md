# Q2: Docker REPL Engine - Camada de Execução Isolada (Containment)

## A. Registro de Raciocínio Técnico (Chain of Thought)

### Trade-offs

Escolhi implementar uma **nova classe DockerReplEngine** ao invés de modificar o ContainerManager existente por:

1. **Separação de responsabilidades**: O ContainerManager gerencia o ciclo de vida (Q1), enquanto a nova classe foca no isolamento (Q2)
2. **Princípio Open/Closed**: Novas funcionalidades sem modificar código existente
3. **Testabilidade**: Classe isolada pode ser testada independentemente
4. **API Limpa**: Interface fluida com ContainmentConfig builder pattern

### Padrões de Projeto Aplicados

1. **Builder Pattern**: `ContainmentConfig.to_host_config_kwargs()` constrói HostConfig incrementalmente
2. **Observer Pattern**: `LifecycleHooks` notifica eventos em todas as fases do container
3. **Strategy Pattern**: `IsolationLevel` predefinem diferentes estratégias de isolamento
4. **Factory Pattern**: `DockerReplEngine` cria containers isolados com configuração validada

### Gestão de Riscos

| Risco | Mitigação |
|-------|-----------|
| Configuração inválida | Validação explícita em `validate()` antes da criação |
| Fork bomb (PIDs) | `pids_limit=64` hard limit + cgroups |
| Memory exhaustion | `mem_limit` + `mem_reservation` (mesmo valor) |
| Rede vazada | `--network none` explícito |
| tmpfs overflow | Size limit hardcoded (256MB max) |
| Rootfs writable | `read_only=True` no HostConfig |

---

## B. Implementação (Código Comentado)

### Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────────────┐
│                    DockerReplEngine                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐          │
│  │           ContainmentConfig                        │          │
│  │ .memory_limit: "512m"    # HARD 512MB-1GB    │          │
│  │  cpu_quota: 100000        # 1 vCPU           │          │
│  │  pids_limit: 64           # segurança        │          │
│  │  network_disabled: True   # --network none   │          │
│  │  tmpfs_enabled: True      # /tmp mount      │          │
│  │  tmpfs_size: "256m"       # max 256MB      │          │
│  │  readonly_rootfs: True      # rootfs RO      │          │
│  └─────────────────────────────────────────────────────────┘          │
│  ┌─────────────────────────────────────────────────────────┐          │
│  │           LifecycleHooks                         │          │
│  │  on_create → on_start → on_stop → on_destroy        │          │
│  └─────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Módulos Principais (docker_repl_engine.py)

| Módulo | Descrição |
|--------|----------|
| `ContainmentConfig` | Dataclass com todos os parâmetros de isolamento |
| `LifecycleHooks` | Sistema de callbacks para eventos |
| `DockerReplEngine` | Motor de execução isolado (async) |
| `DockerReplEngineSync` | Wrapper síncrono |

### Critérios de Aceitação Implementados

| Critério | Implementação |
|----------|--------------|
| memory limit HARD (512MB-1GB) | `mem_limit` + `mem_reservation` = same value |
| cpu quota = 1 vCPU | `cpu_period=100000`, `cpu_quota=100000` |
| pids limit = 64 | `pids_limit=64` |
| --network none | `network_mode="none"` |
| RootFS Read-Only | `read_only=True` |
| /tmp tmpfs (256MB) | `tmpfs="/tmp:size=256m,mode=1777"` |
| Workspace RO | Future enhancement |
| Lifecycle hooks | `on_create`, `on_start`, `on_stop`, `on_destroy`, `on_error` |

### Restrições Aplicadas

| Restrição | Implementação |
|-----------|-----------|
| Proibido --privileged | Não usado, validação explícita |
| Proibido --cap-add | Não usado, usa default |
| --init para PID 1 | `init=True` no HostConfig |
| Timeout 300s default | `DEFAULT_EXECUTE_TIMEOUT = 300` |

---

## C. Documentação da Quest

### Funcionalidades Implementadas

1. ✅ **ContainmentConfig** - Dataclass comBuilder Pattern
   - memory_limit (512MB-1GB HARD)
   - cpu_quota (1 vCPU)
   - pids_limit (64)
   - network_disabled (--network none)
   - tmpfs (256MB max)
   - readonly_rootfs
   - readonly_workspace

2. ✅ **LifecycleHooks** - Sistema de callbacks
   - on_create(session)
   - on_start(session)
   - on_stop(session)
   - on_destroy(session)
   - on_error(session, exception)

3. ✅ **DockerReplEngine** - Motor de execução
   - API async completa
   - Warm pool (N=3)
   - Execução de código Python
   - Métricas integradas

4. ✅ **DockerReplEngineSync** - Wrapper sync
   - Para uso em contextos não-async

### Dependências

```bash
pip install -r requirements.txt
```

- `docker>=7.0.0` - Docker SDK for Python

### Instruções de Teste

```bash
# 1. Teste rápido (verifica configuração)
python3 src/runtime/docker_repl_engine.py --test

# 2. Teste integrado (requer Docker)
python3 -c "
import asyncio
from src.runtime import DockerReplEngine, ContainmentConfig

async def test():
    # Configuração Q2
    config = ContainmentConfig()
    print(f'Config: memory={config.memory_limit}, cpu={config.cpu_quota}, pids={config.pids_limit}')
    
    # Engine
    engine = DockerReplEngine(config=config, pool_size=1)
    await engine.initialize()
    
    # Criar container
    session = await engine.create_container()
    print(f'Container: {session.name}')
    
    # Executar código
    result = await engine.execute(session, 'print(2+2)')
    print(f'Output: {result.stdout}')
    
    # Destruir
    await engine.destroy(session)
    await engine.shutdown()

asyncio.run(test())
"
```

---

## D. Snapshot de Estado

```
SNAPSHOT DE ESTADO:
Versão do Projeto: v1.0.2
Componentes Prontos:
  - check_docker.py (Q0)
  - container_manager.py (Q1)
  - docker_repl_engine.py (Q2) - NOVO
  - docs/Q0_SETUP.md
  - docs/Q1_CONTAINER_MANAGER.md
  - docs/Q2_CONTAINMENT.md - NOVO

Dependências Instaladas:
  - docker>=7.0.0
  - requests>=2.26.0
  - urllib3>=1.26.0

Pendências Técnicas:
  - Workspace mounted RO (implementação futura)
  - Recovery code testado com crash real
  - Integration tests
```

---

## Limitações Conhecidas

1. **Workspace mounted RO**: A implementação atual prepara o framework, mas requer path de workspace para mount
2. **Exit code detection**: Baseado em heurística "Error:" no output, pode não cobrir todos os casos
3. **IPC streaming**: Suporta básico stdin/stdout, streaming bidirecional futuro

---

## Referências

- [Docker HostConfig API](https://docker-py.readthedocs.io/en/stable/host-config.html)
- [cgroups v2](https://www.kernel.org/doc/Documentation/admin-guide/cgroup-v2.rst)
- [Security Best Practices](docs/SECURITY.md)
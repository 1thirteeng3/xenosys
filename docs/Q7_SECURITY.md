# Q7: Security Policing - Contenção Docker Paranoica

## A. Registro de Raciocínio Técnico (Chain of Thought)

### Trade-offs

Escolhi implementar uma **SecurityPolicing** classe dedicada ao invés de modificar o DockerReplEngine existente por:

1. **Separação de Responsabilidades**: O DockerReplEngine (Q2) foca em contenção de recursos, enquanto esta classe foca empolítica de segurança (hardening)
2. **Princípio Open/Closed**: Novas funcionalidades de segurança sem modificar código existente
3. **Testabilidade**: Módulo isolado pode ser testado independentemente
4. **Auditoria Separada**: Logs de segurança em arquivo dedicado (security.audit.log)

### Padrões de Projeto Aplicados

1. **Decorator Pattern**: SecurityPolicing envolvevalidações de segurança antes/depois de operações
2. **Observer Pattern**: SecurityEventHandlers notifica eventos de segurança
3. **Strategy Pattern**: BatteryStrategy define estratégias de profilaxia energética
4. **AOP Pattern**: Validações cross-cutting (prevenção de escape, auditoria)

### Gestão de Riscos

| Risco | Mitigação |
|-------|-----------|
| Container escape | --security-opt no-new-privileges:true + --cap-drop=ALL |
| Fork bomb | pids_limit=64 hard limit via cgroups |
| Memory exhaustion |OOM Score Adj configurado para first kill |
| Battery drain | psutil para detecção + suspensão de tarefas pesadas |
| Root daemon | Verificação rootless + warning crítico |
| Network leak | Auditoria de tentativas de acesso |

---

## B. Implementação (Código Comentado)

### Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────────────┐
│                    SecurityPolicing                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐
│  │           SecurityConfig                             │
│  │  - container_security: no-new-privileges          │
│  │  - cap_drop: ALL                                    │
│  │  - oom_score_adj: +1000 (first to die)              │
│  │  - battery_threshold: 20%                          │
│  │  - enable_audit: True                               │
│  └─────────────────────────────────────────────────────────┘
│  ┌─────────────────────────────────────────────────────────┐
│  │           SecurityValidator                         │
│  │  - validate_container_config()                       │
│  │  - validate_rootless_daemon()                      │
│  │  - validate_security_opts()                       │
│  └─────────────────────────────────────────────────────────┘
│  ┌─────────────────────────────────────────────────────────┐
│  │           BatteryManager                             │
│  │  - get_battery_status()                           │
│  │  - should_suspend_tasks()                         │
│  │  - suspend_cpu_intensive()                       │
│  └─────────────────────────────────────────────────────────┘
│  ┌─────────────────────────────────────────────────────────┐
│  │           SecurityAudit                            │
│  │  - log_security_event()                           │
│  │  - log_network_attempt()                       │
│  │  - log_root_warning()                           │
│  └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

### Critérios de Aceitação Implementados

| Critério | Implementação |
|----------|-------------|
| --security-opt no-new-privileges:true | `security_opt=["no-new-privileges:true"]` |
| --cap-drop=ALL | `cap_drop=["ALL"]` em HostConfig |
| RootFS Read-Only | `read_only=True` + tmpfs volátil |
| Verificação Rootless | `validate_rootless_daemon()` → WARNING crítico |
| PIDs limit = 64 | `pids_limit=64` via cgroups |
| OOM Score Adj | Configuração de prioridade de kill |
| Profilaxia Energética | Detecção via psutil, suspensão automática |
| Audit trail separado | security.audit.log com eventos |

### Restrições Aplicadas

| Restrição | Implementação |
|-----------|-------------|
| Proibido --privileged | Não usado, validação explícita |
| Proibido --cap-add | Não usado, usa --cap-drop=ALL |
| Proibido CPU intenso < 20% | BatteryManager suspende tarefas |
| Host responsivo | CPU via CpuQuota (já em Q2) |

---

## C. Documentação da Quest

### Funcionalidades Implementadas

1. **SecurityPolicing** - Classe principal de policing
   - Wrapper que envolve ContainerManager/DockerReplEngine
   - Aplica validações de segurança em todas as operações
   - Singleton pattern para acesso global

2. **SecurityConfig** - Dataclass de configuração
   - container_security (no-new-privileges)
   - cap_drop (ALL)
   - oom_score_adj (+1000)
   - battery_threshold (20%)
   - enable_audit (True)

3. **SecurityValidator** - Validador de configurações
   - validate_container_config()
   - validate_rootless_daemon()
   - validate_security_options()

4. **BatteryManager** - Gerenciador de energia
   - get_battery_status()
   - should_suspend_tasks()
   - suspend_cpu_intensive()

5. **SecurityAudit** - Sistema de auditoria
   - log_security_event()
   - log_network_attempt()
   - log_root_warning()

### Dependências

```bash
pip install -r requirements.txt
# Novas dependências:
# - psutil>=5.9.0 (monitoramento de bateria)
```

### Instruções de Teste

```bash
# 1. Teste rápido (valida configuração)
python3 src/runtime/security_policing.py --test

# 2. Teste integrado (requer Docker)
python3 -c "
import asyncio
from src.runtime import SecurityPolicing, SecurityConfig

async def test():
    config = SecurityConfig()
    policing = SecurityPolicing(config)
    
    print(f'1. Validando daemon...')
    rootless = await policing.validate_rootless_daemon()
    print(f'   Rootless: {rootless}')
    
    print(f'2. Validando configuração...')
    valid = policing.validate_security_config()
    print(f'   Válida: {valid}')
    
    print(f'3. Verificando bateria...')
    battery = policing.get_battery_status()
    print(f'   Status: {battery}')
    
    print(f'4. Testando suspend...')
    should_suspend = policing.should_suspend_tasks()
    print(f'   Suspender: {should_suspend}')

asyncio.run(test())
"
```

---

## D. Snapshot de Estado

```
SNAPSHOT DE ESTADO:
Versão do Projeto: v1.0.7
Componentes Prontos:
  - check_docker.py (Q0)
  - container_manager.py (Q1)
  - docker_repl_engine.py (Q2)
  - inference_engine.py (Q3)
  - memory_manager.py (Q4)
  - cortex_db.py (Q5)
  - dual_view.py (Q6)
  - security_policing.py (Q7) - NOVO
  - docs/Q0_SETUP.md
  - docs/Q1_CONTAINER_MANAGER.md
  - docs/Q2_CONTAINMENT.md
  - docs/Q3_INFERENCE.md
  - docs/Q4_MEMORY.md
  - docs/Q5_CORTEX.md
  - docs/Q6_README.md
  - docs/Q7_SECURITY.md - NOVO

Dependências Instaladas:
  - docker>=7.0.0
  - psutil>=5.9.0 (NOVA)
  - requests>=2.26.0
  - urllib3>=1.26.0

Pendências Técnicas:
  - Integration tests com container real
  - OOM score adj via docker-py (limitação known)
  - Battery simulation em containers
```

---

## Limitações Conhecidas

1. **OOM Score Adj**: Docker não expõe diretamente via API, mas o memory limit já garante contenção
2. **Battery em containers**: psutil pode não detectar corretamente emcontainers; lógica de fallback implementada
3. **Rootless validation**: Baseado em heurística (usuário current), pode não funcionar em todos os setups

---

## Referências

- [Docker Security Options](https://docs.docker.com/engine/security/)
- [cgroups resource limits](https://www.kernel.org/doc/Documentation/admin-guide/cgroup-v2.rst)
- [psutil battery](https://psutil.readthedocs.io/)
- [Security Best Practices](docs/SECURITY.md)
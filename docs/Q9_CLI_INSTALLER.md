# Q9: CLI & Offline Installer - O Appliance XenoSys

## A. Registro de Raciocínio Técnico (Chain of Thought)

### Trade-offs

**Por que argparse ao invés de click/typer?**

Escolhi usar **argparse** (biblioteca padrão) ao invés de click ou typer por:

1. **Zero Dependências**: argparse é parte da biblioteca padrão Python, não requer pip install
2. **Air-Gapped Real**: Sem necessidade de baixar libraries em runtime
3. **Simplicidade**: Interface direta e previsível
4. **Manutenção**: Sem dependência externa que pode quebrar

**Alternativa Rejeitada (typer/click)**:
- Requerem pip install dinâmico em runtime
- Aumentam a surface de ataque
- Violam o critério "Zero outbound"

### Padrões de Projeto Aplicados

1. **Factory Pattern**: `generate_env_file()` cria configurações com chaves rotacionadas
2. **Strategy Pattern**: `validate_prerequisites()` com múltiplas estratégias de validação
3. **State Machine**: Start → Running → Stopped com transições previsíveis
4. **Observer Pattern**: Audit logger notifica eventos de segurança
5. **Fail-Fast**: Qualquer falha em pré-requisitos bloqueia a instalação

### Gestão de Riscos

| Risco | Mitigação |
|-------|-----------|
| Docker não instalado | Fail-Fast na CLI com mensagem clara |
| Modo root detectado | Alerta crítico no audit log |
| Servidor não inicia | Timeout com cleanup de PID |
| Recursos zumbis | SIGTERM → SIGKILL em graceful shutdown |
| Rede vazando | CLI não faz nenhum request outbound |
| Arquivos sensíveis expostos | .env não versionado + proteção de permissões |

---

## B. Implementação (Código Comentado)

### Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────────────┐
│                   XenoSys CLI                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐
│  │            xenosys_cli.py (argparse)                  │
│  │  - start: Inicia Orquestrador + FastAPI + Docker       │
│  │  - stop: SIGTERM + cleanup tmpfs                    │
│  │  - status: Verifica Q5 + conectividade + container   │
│  │  - logs: Agrega físico + audit trail                │
│  └─────────────────────────────────────────────────────────┘
│  ┌─────────────────────────────────────────────────────────┐
│  │            Makefile (idempotente)                    │
│  │  - install: Valida + cria venv + dirs               │
│  │  - validate: check_docker.py                       │
│  │  - clean: Remove artefatos                          │
│  │  - test: pytest                                   │
│  └─────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────┘
```

### Critérios de Aceitação Implementados

| Critério | Implementação |
|----------|-------------|
| Air-Gapped Real | Zero requests em runtime - argparse padrão |
| CLI Unificada | `xenosys start/stop/status/logs` via argparse |
| Idempotência | Makefile valida sem erros |
| Injeção de Ambiente | `generate_env_file()` com chaves rotacionadas |
| Validação Prerequisites | `validate_prerequisites()` com Fail-Fast |
| Agregação de Logs | `cmd_logs()` concatena arquivos |
| Fail-Fast CLI | Qualquer falha bloqueia operação |

### Comandos CLI

```bash
# Iniciar o Orquestrador
python3 xenosys_cli.py start

# Encerrar graciosamente
python3 xenosys_cli.py stop

# Verificar saúde
python3 xenosys_cli.py status

# Ver logs
python3 xenosys_cli.py logs

# Via Makefile
make install    #安装
make validate   #验证
make status     #状态
make test      #测试
make clean     #清理
```

### Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│              START COMMAND                                │
├─────────────────────────────────────────────────────────────┤
│  1. VALIDATE                                               │
│     ├── Docker instalado?                                 │
│     ├── Docker daemon rodando?                           │
│     ├── Modo rootless verificado?                         │
│     └── Se algo falhar → FAIL FAST                         │
│                                                          │
│  2. ENVIRONMENT                                           │
│     ├── .env existe?                                      │
│     └── Se não → gerar com chaves rotacionadas             │
│                                                          │
│  3. START                                                 │
│     ├── Inicar uvicorn + FastAPI                         │
│     ├── Escrever PID file                                │
│     └── Retornar status                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## C. Documentação da Quest (README Local)

### Funcionalidades Implementadas

✅ **CLI Unificada (argparse)**:
- `xenosys start`: Inicia Orquestrador, FastAPI e aloca Docker
- `xenosys stop`: Encerra graciosamente com SIGTERM
- `xenosys status`: Verifica saúde Q5, conectividade, containers
- `xenosys logs`: Agrega logs físicos e Audit Trail

✅ **Makefile Idempotente**:
- `make install`: Instala tudo
- `make validate`: Valida pré-requisitos
- `make clean`: Remove artefatos
- `make test`: Executa testes

✅ **Injeção de Ambiente**:
- Gera .env automaticamente
- Chaves de encriptação rotacionadas
- Paths configurados

✅ **Validação Fail-Fast**:
- Docker instalado?
- Daemon executando?
- Modo rootless?
- Qualquer falha bloqueia

✅ **Agregação de Logs**:
- /tmp/xenosys/xenosys.log
- /tmp/xenosys/security.audit.log
- /tmp/xenosys/server.log

### Dependências

**Novas bibliotecas**:
- Nenhuma! Usamos argparse (biblioteca padrão Python)

**Existentes (requirements.txt)**:
- docker>=7.0.0
- python-dotenv>=1.0.0
- fastapi>=0.100.0
- uvicorn[standard]>=0.25.0

### Restrições Implementadas

| Restrição | Status |
|-----------|--------|
| Stack argparse/click | ✅ argparse (padrão) |
| Proibido pip install dinâmico em runtime | ✅ Makefile cria venv antes |
| Fail-Fast em hardware/sistema | ✅ validate_prerequisites() |
| .env não versionado | ✅ Gerado em tempo de execução |

---

## D. Snapshot de Estado

**SNAPSHOT DE ESTADO:**
====================
Versão do Projeto: v1.0.9 (Q9 - CLI & Offline Installer)
Componentes Prontos: [Q0, Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q9]
Dependências Instaladas: 
  - docker>=7.0.0 (reutilizada)
  - python-dotenv>=1.0.0 (reutilizada)
  - fastapi>=0.100.0 (reutilizada)
  - uvicorn[standard]>=0.25.0 (reutilizada)
Pendências Técnicas: [Nenhuma - todas as Quests implementadas]
---

## Instruções de Teste

### Teste Manual

1. **Validação de Pré-requisitos**:
```bash
cd /workspace/project/xenosys
python3 check_docker.py
```

2. **Iniciar Sistema**:
```bash
python3 xenosys_cli.py start
# Saída: XenoSys iniciado (PID=xxxxx)
```

3. **Verificar Status**:
```bash
python3 xenosys_cli.py status
# Saída: Docker: OK, Daemon: executando, Cortex: existe, Server: executando
```

4. **Ver Logs**:
```bash
python3 xenosys_cli.py logs
# Saída: Agrega todos os logs
```

5. **Parar Sistema**:
```bash
python3 xenosys_cli.py stop
# Saída: XenoSys encerrado
```

### Via Makefile

```bash
make install    # Instala e valida
make status    # Quick status
make test      # Unit tests
make clean    # Limpa artefatos
```

### Auditor

O auditor pode validar:

1. **check_docker.py** executa sem erros
2. **xenosys start** inicia FastAPI
3. **xenosys status** retorna system healthy
4. **xenosys stop** encerra graciosamente
5. **xenosys logs** agrega logs

Nota: Todo o sistema é **offline-first** - sem requests externos em nenhuma operação.
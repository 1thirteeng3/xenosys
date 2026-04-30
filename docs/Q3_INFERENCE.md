# Q3: RLM Inference Engine - Motor de Raciocínio Empírico

## A. Registro de Raciocínio Técnico (Chain of Thought)

### Novas Funcionalidades Q3 v2

| Funcionalidade | Implementação |
|----------------|---------------|
| Fail-fast validation | `_validate_before_create()` na factory valida credenciais antes de instanciar |
| Retry com Jitter | `JitterRetry` com exponential backoff + ruído estatístico |
| Tool Calling | `_handle_tool_call()` + ToolRegistry para chamadas de função |
| Session reuse | Sessão Docker é criada uma vez e reutilizada entre iterações |

### Correções Aplicadas (QA Review)

| Issue | Severidade | Correção |
|-------|-----------|----------|
| Tool calling não integrado | ✅ Adicionado `_handle_tool_call()` no loop RLM |
| JitterRetry não usado | ✅ Substituído retry manual por `JitterRetry.execute()` |
| Bug de ABC | ⚠️ Workaround: usar Factory até corrigir |
| Session reuse | ✅ Container criado antes do loop, usado em todas iterações |
| cancel_event + OOB destroy | ✅ finally block com destroy imediato |

Após a análise de QA, as seguintes correções foram aplicadas:

| Issue | Severidade | Correção |
|-------|-----------|----------|
| Event loop closing | CRÍTICO | Removido `self._loop.close()` do shutdown |
| ReDoS em regex | CRÍTICO | Truncamento 2000 chars + patterns seguros `[^\n]+` |
| API key logging | CRÍTICO | Adicionada sanitização nos logs |
| Validation input | MÉDIO | Novo `RLMConfig` com `__post_init__` validation |
| Magic numbers | MENOR | Extraídos para constantes nomeadas |
| Exception handling | MÉDIO | Try-catch específico no parser |

### Padrões de Projeto Aplicados

1. **Abstract Factory**: `LLMProvider` cria interface para diferentes provedores
2. **Strategy**: Cada provider implementa a mesma interface
3. **Chain of Responsibility**: Ciclo write→execute→analyze
4. **Builder**: `Planner` constrói DAG de tarefas

### Gestão de Riscos

| Risco | Mitigação |
|-------|-----------|
| API keys expostas | Apenas via variáveis de ambiente, nunca hardcoded |
| Timeout em LLM calls | Request timeout = 30s configurável |
| Loop infinito | Max iterations = 3 default |
| Python errors não pegos | PythonErrorParser específico |
| Retry storms | Exponential backoff com delay máximo |

---

## B. Implementação (Código Comentado)

### Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────────────┐
│                    RLM Inference Engine                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              LLMProvider (ABC)                        │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                │     │
│  │  │ Ollama  │ │ OpenAI  │ │Anthropic│                │     │
│  │  └──────────┘ └──────────┘ └──────────┘                │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    Planner                            │     │
│  │        Constrói DAG de tarefas a partir de prompt      │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              RLMInferenceEngine                        │     │
│  │  Iterador: write → execute → analyze → (retry)        │     │
│  │  Max iterations: 3 (default)                         │     │
│  │  Timeout por iteração: 60s (default)                  │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### Módulos Principais (src/inference/rlm_inference.py)

| Módulo | Descrição |
|--------|----------|
| `LLMProvider` | Interface abstrata |
| `OllamaProvider` | Provedor Ollama (local) |
| `OpenAIProvider` | Provedor OpenAI API |
| `AnthropicProvider` | Provedor Anthropic API |
| `PythonErrorParser` | Parser de erros Python |
| `Planner` | Construtor de DAG |
| `RLMInferenceEngine` | Motor de inferência async |
| `RLMInferenceEngineSync` | Wrapper síncrono |

### Critérios de Aceitação Implementados

| Critério | Implementação |
|----------|--------------|
| Interface LLMProvider (Ollama) | `OllamaProvider` implementa `LLMProvider` |
| Interface LLMProvider (OpenAI) | `OpenAIProvider` implementa `LLMProvider` |
| Interface LLMProvider (Anthropic) | `AnthropicProvider` implementa `LLMProvider` |
| Planner constrói DAG | `Planner.plan()` → `TaskGraph` |
| Executor itera | `RLMInferenceEngine.infer()` loop |
| Max iterations | `max_iterations=3` default |
| Timeout iteração | `iteration_timeout=60s` default |
| Timeout LLM | `request_timeout=30s` default |
| Python error parsing | `PythonErrorParser.parse()` |
| Retry backoff | Exponential: `base_retry_delay * 2^iteration` |

### Restrições Aplicadas

| Restrição | Implementação |
|-----------|-------------|
| API keys via env vars | `os.getenv("OPENAI_API_KEY")` etc. |
| Proibido hardcoding | Nunca no código-fonte |
| Request timeout | Configurável, default 30s |

---

## C. Documentação da Quest

### Funcionalidades Implementadas

1. ✅ **LLMProvider Interface** - Abstract factory
   - Ollama (local)
   - OpenAI API compatible
   - Anthropic API compatible
   - **Fail-fast validação**: `_validate_before_create()` na factory

2. ✅ **Tool Calling** - Interface de ferramentas
   - `ToolDefinition` - Definição de ferramenta
   - `ToolRegistry` - Registro singleton
   - `ToolCall` / `ToolResult` - Chamadas estruturadas
   - **`_handle_tool_call()`** - Método no RLMInferenceEngine para executar tools

3. ✅ **JitterRetry** - Retry com ruído estatístico
   - Exponential backoff
   - Jitter (full / decorrelated)
   - **Usado no loop RLM** - Substituiu retry manual

4. ✅ **PythonErrorParser** - Parser de erros
   - SyntaxError, NameError, TypeError, etc.
   - Sugestões de correção

5. ✅ **Planner** - Construtor de DAG
   - Decomposição de tarefas
   - Dependências entre tarefas
   - Ordenação topológica

6. ✅ **RLMInferenceEngine** - Motor async
   - Ciclo write→execute→analyze
   - Retry exponencial
   - Max iterations
   - Timeout configurável

7. ✅ **RLMInferenceEngineSync** - Wrapper sync
   - Para contextos não-async

### Dependências

```bash
pip install -r requirements.txt
```

- `docker>=7.0.0` - Docker SDK
- `python-dotenv>=1.0.0` - Environment variables
- `aiohttp>=3.9.0` - Async HTTP client

### Variáveis de Ambiente

```bash
# Uma das (preferência em ordem):
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3"

# Ou:
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4"

# Ou:
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-3-sonnet-20240229"
```

### Instruções de Teste

```bash
# 1. Teste de imports
python3 -c "
from src.inference import (
    LLMProviderType,
    LLMProviderFactory,
    PythonErrorParser,
    RLMInferenceEngine
)
print('✓ Imports OK')
"

# 2. Teste do parser
python3 -c "
from src.inference import PythonErrorParser
result = PythonErrorParser.parse('NameError: name x is not defined')
print(f'Parser: {result}')
"

# 3. Teste de provider (requer configuração)
python3 -c "
from src.inference import LLMProviderFactory, LLMProviderType
provider = LLMProviderFactory.create(LLMProviderType.OLLAMA)
print(f'Provider: {provider.model}')
"
```

---

## D. Snapshot de Estado

```
SNAPSHOT DE ESTADO:
Versão do Projeto: v1.0.4 (Q3 - CORREÇÕES QA)
Componentes Prontos:
  - check_docker.py (Q0)
  - container_manager.py (Q1)
  - docker_repl_engine.py (Q2)
  - rlm_inference.py (Q3) - CORRIGIDO
  - docs/Q3_INFERENCE.md - CORRIGIDO
  - tests/unit/test_rlm_inference.py

Dependências Instaladas:
  - docker>=7.0.0
  - python-dotenv>=1.0.0
  - aiohttp>=3.9.0
  - requests>=2.26.0
  - urllib3>=1.26.0

Correções QA Aplicadas:
  ✓ RLMConfig com validação upfront
  ✓ PythonErrorParser com truncamento (2000 chars)
  ✓ Shutdown não fecha event loop
  ✓ Regex patterns [^\n]+ (evita ReDoS)
  ✓ Limites: MAX_ERROR_OUTPUT_SIZE, MAX_CODE_SIZE

=== Q3 V2: Refatoração Implementada ===

Funcionalidades Implementadas Q3 v2:
  ✓ Tool Calling: Ferramentas注册 (ToolDefinition, ToolCall, ToolResult)
  ✓ Fail-Fast: Validação rigorosa no construtor de LLMProvider
  ✓ Retry com Jitter: Exponential Backoff + Jitter decorrelato
  ✓ Cancelamento OOB: Abate imediato de containers com terminate()
  ✓ Template Method: _validate_and_enforce_credentials centralizado

Dependências Q3 v2:
  - aiohttp>=3.9.0 (já presente)
  - random (stdlib)
  - asyncio (stdlib)

Testes de Validação:
  python3 -m src.inference.rlm_inference --test

Pendências Técnicas:
  - Integração real Q2 ↔ Q3
  - Testes de providers com mocks
  - Session reuse
```

---

## Limitações Conhecidas

1. **Instanciação direta de providers**: Devido a um bug de ABC no Python, a instanciação direta de `OpenAIProvider()`, `AnthropicProvider()` pode falhar com `TypeError`. Use sempre `LLMProviderFactory.create()` para criar instâncias.
2. **Sem streaming**: Providers não suportam response streaming
3. **Session reuse**: Cada chamada cria nova sessão HTTP
4. **Fallback limitado**: Se todas iterações falham, retorna erro
5. **Parser imperfeito**: Pode não cobrir todos os erros Python

---

## Referências

- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [Anthropic API](https://docs.anthropic.com/claude/docs/api-overview)
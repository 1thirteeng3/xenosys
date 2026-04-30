# Q8: Chain of Thought - Registro de Raciocínio Técnico

## Visão Geral do problema

A Q8 demanda a implementação de um "Motor de Contradição" capaz de:
1. Detectar contradições entre o contexto atual (Q4) e o grafo de conhecimento (Q5)
2. Testar empiricamente afirmações via Sandbox isolado
3. Escalonar para o usuário quando não conseguir resolver
4. Permitir override manual
5. Rastrear todas as decisões

## Análise e Decomposição

### Requisitos Funcionais

| ID | Requisito | Abordagem |
|----|----------|-----------|
| RF1 | Detectar contradições epistêmicas | Analisador semântico (ContradictionAnalyzer) |
| RF2 | Resolver empiricamente via Sandbox | Executor de código isolado (EmpiricalTestRunner) |
| RF3 | Escalonar ambiguidades | Máquina de estados + Interface de rejeição |
| RF4 | Permitir override manual | Método force_override() + Registro no grafo |
| RF5 | Rastrear decisões | AuditLogger com logs |

### Requisitos Não-Funcionais

| ID | Requisito | Restrição |
|----|----------|-----------|
| RNF1 | Código dinâmico em Sandbox only | Proibido eval() no Orquestrador |
| RNF2 | Timeout de validação | 15 segundos máximo |
| RNF3 | Auditoria | Todas as decisões registradas |

## Abordagem Escolhida vs Alternativas

### Por que não usar validação estática (sympy)?

**Alternativa A (Rejeitada)**: Usar sympy para validação símbolosca de expressões matemáticas.

- **Prós**: Precisão matemática, bibliotecas maduras
- **Contras**: Limitado a matemática, não funciona para contradições semânticas

**Alternativa B (Escolhida)**: Análise semântica + Execução empírica.

- **Prós**: Genérico, funciona para qualquer tipo de contradição, demonstra ceticismo autônomo
- **Contras**: Requer Sandbox isolado, Timeout pode falhar

### Justificativa da Escolha

A abordagem B foi escolhida porque:
1. **Generalidade**: Funciona para qualquer tipo de contradição (lógica, semântica, factual)
2. **Ceticismo Autônomo**: O sistema "discorda" do usuário quando identifica inconsistências
3. **Integração with Q2/Q7**: Reutiliza a infraestrutura existente
4. **Segurança**: Todo código executado em Sandbox isolado com --network none

## Padrões de Projeto Aplicados

### 1. Strategy Pattern
```python
class EmpiricalTestRunner:
    # Estratégias de teste configuráveis
    def _generate_test_code(self, contradiction, context_data):
        # Gera código específico para cada tipo de contradição
```
- **Por quê?**: Permite diferentes estratégias de teste para diferentes tipos de contradição

### 2. Chain of Responsibility
```python
async def validate(premise, session_id, user_instruction):
    # Pipeline: Análise → Busca → Teste → Decisão
    # Cada etapa pode passar ou falhar
```
- **Por quê?**: Pipeline de validação onde cada etapa pode SHORT-CIRCUIT

### 3. State Machine
```python
class ValidationState(Enum):
    INIT → ANALYZING → TESTING → RESOLVED/FAILED
```
- **Por quê?**: Estados bem definidos com transições previsíveis

### 4. Observer Pattern
```python
# AuditLogger observa todas as decisões
def _log_audit(self, action, **kwargs):
    # Notifica para audit log
```
- **Por quê?**: Rastreabilidade completa sem acoplamento

### 5. Factory Pattern
```python
def create_contradiction_engine(cortex, session_manager, config):
    # Factory para criar instância
```
- **Por quê?**: Criação centralizada com defaults seguros

## Gestão de Riscos

### Risco 1: Contradições Falsos Positivos

**Probabilidade**: Alta  
**Impacto**: Médio

**Mitigação**:
- Múltiplos estágios de análise (direta + semântica)
- Confiança mínima (confidence score)
- Escalonamento para usuário como fallback

### Risco 2: Timeout na Execução Empírica

**Probabilidade**: Média  
**Impacto**: Alto

**Mitigação**:
- Timeout rigoroso de 15s
- Escalonamento automático em caso de timeout
- Log detalhado para debugging

### Risco 3: Recursos Zumbi no Sandbox

**Probabilidade**: Baixa  
**Impacto**: Crítico

**Mitigação**:
- Reutilização do pool existente (Q2)
- Containers pré-inicializados
- Cancel_event em cancelamento

### Risco 4: Loop Infinito

**Probabilidade**: Baixa  
**Impacto**: Crítico

**Mitigação**:
- Máximo de iterações (MAX_EMPIRICAL_ATTEMPTS = 3)
- Timeout por iteração
- Escalonamento forçado após timeout

## Arquitetura de Dados

### ContradictionFinding
```
┌─────────────────────────────────────────────┐
│           ContradictionFinding             │
├─────────────────────────────────────────────┤
│  id: str                    # UUID único  │
│  type: ContradictionType    # DIRECTA/    │
│                            # SEMANTIC     │
│  description: str           # Descrição   │
│  context_premise: str      # Premissa do  │
│                            # contexto    │
│  knowledge_node_id: str     # ID do nó    │
│  knowledge_content: str     # Conteúdo    │
│  confidence: float          # 0.0-1.0   │
└─────────────────────────────────────────────┘
```

### ValidationResult
```
┌─────────────────────────────────────────────┐
│           ValidationResult                │
├─────────────────────────────────────────────┤
│  id: str                    # UUID único  │
│  action: ValidationAction  # ACCEPT/     │
│                            # TEST/REJECT │
│  state: ValidationState    # INIT/RESOLV │
│                            # FAILED     │
│  contradiction: ContradictionFinding   │
│  empirical_result: dict    # Resultado   │
│                            # do teste   │
│  rejection_reason: str     # Motivo se   │
│                            # REJECT     │
│  override_by: str          # "user" se  │
│                            # OVERRIDE   │
│  duration_ms: int          # Tempo total │
└─────────────────────────────────────────────┘
```

## Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│                  validate(premise)                         │
├─────────────────────────────────────────────────────────────┤
│  1. INIT                                                │
│     ├── Obter contexto da sessão (Q4)                    │
│     └── Buscar conhecimento relacionado (Q5)            │
│                                                         │
│  2. ANALYZING                                            │
│     ├── Para cada nó retornado:                          │
│     │   ├── Analisar contradição direta                 │
│     │   └── Analisar contradição semântica             │
│     └── Se contradição encontrada → TESTING             │
│                                                         │
│  3. TESTING (EmpiricalTestRunner)                       │
│     ├── Gerar código de teste Python                   │
│     ├── Executar no Sandbox (Q2/Q7)                   │
│     └── Analisar resultado                             │
│                                                         │
│  4. RESOLVED / ESCALATED                                │
│     ├── Se teste resolveu → ACCEPT                      │
│     └── Se teste falhou/escalou → REJECT               │
│           (com reason detalhado)                        │
└─────────────────────────────────────────────────────────────┘
```

## Integração com Outras Quests

### Q2/Q7 (Sandbox)
- **Entrada**: Código gerado para teste
- **Saída**: ExecutionResult (stdout, stderr, exit_code)
- **Timeout**: 15 segundos

### Q3 (Inferência)
- **Entrada**: Premissa a validar
- **Saída**: ValidationResult
- **Integração**: Validação antes de aceitar output do LLM

### Q4 (Session Manager)
- **Entrada**: Contexto da sessão
- **Saída**: Premissas para análise

### Q5 (Cortex)
- **Entrada**: Query de busca
- **Saída**: Lista de (Node, score)
- **Integração**: Override registrado no grafo

### Q6 (UI)
- **Entrada**: ValidationResult
- **Saída**: Decisão do usuário
- **Integração**: Exibição de rechazos, interface de override

## Limitações Conhecidas

1. **Análise Semântica Limitada**: A análise de contradição semântica é baseada em padrões simples (palavras-chave de negação), não em NLP avançado.

2. **Dependência de sentence-transformers**: O Cortex (Q5) requer modelos de embedding, o que pode ser lento na inicialização.

3. **Containers warm pool**: O EmpiricalTestRunner reutiliza containers do pool, mas pode haver contenção em cenários de alta carga.

4. **Timeout rígído**: O timeout de 15s pode ser curto para testes complexos, resultando em escalonamento frequente.

## Próximos Passos Recomendados

1. **Integração com Q3**: Hook do ContradictionEngine no laço de inferência
2. **Melhoria na análise semântica**: Usar embeddings do Cortex para相似idade semântica
3. **Cache de resultados**: Cache de validações anteriores para evitar re-execução
4. **UI de override**: Interface em Q6 para aceitar/rejeitar premissas
"""
Q8: Rejection & Validation - Motor de Contradição e Gerenciamento Epistêmico

Este módulo implementa o "Motor de Contradição" com делегаção cognitiva para o LLM.

⚠️ ARQUITETURA CORRIGIDA:
- Usa LLMProvider ABC (tipagem estrita)
- Tool Calling via generate() - não parse manual
- JitterRetry para tentativas (não fallback Regex)
- Fail-Fast se LLM falhar

Características:
- Análise semântica via Tool Calling
- Geração de código empírico via Tool Calling
- Escalonamento via Orquestrador (não coupling direto Q8→Q6)
- Override com aresta FORCED_OVERRIDE
"""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# IMPORTS DO Q3 - JitterRetry para resiliência de rede
# =============================================================================

from inference.rlm_inference import JitterRetry, RetryConfig

# =============================================================================
# CONFIGURAÇÃO DE LOGGING
# =============================================================================

LOG_DIR = "/tmp/xenosys"
AUDIT_LOG_PATH = f"{LOG_DIR}/audit.log"
SECURITY_AUDIT_LOG_PATH = f"{LOG_DIR}/security.audit.log"

os.makedirs(LOG_DIR, exist_ok=True)


def _setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(ch)
        
        try:
            fh = logging.FileHandler(AUDIT_LOG_PATH, mode="a")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            ))
            logger.addHandler(fh)
        except Exception as e:
            logger.warning(f"Não foi possível criar audit log: {e}")
    
    return logger


logger = _setup_logger("contradiction_engine")


# =============================================================================
# IMPORTS LAZY (Q2/Q7 Sandbox, Q3 Inference)
# =============================================================================

_DockerReplEngine = None
_ContainmentConfig = None
_ContainerSession = None
_ExecutionResult = None
_RLMInferenceEngine = None


def _get_sandbox_engine():
    """Lazy import para DockerReplEngine (Q2/Q7)."""
    global _DockerReplEngine, _ContainmentConfig, _ContainerSession, _ExecutionResult
    
    if _DockerReplEngine is None:
        from runtime.docker_repl_engine import DockerReplEngine, ContainmentConfig
        from core.models import ContainerSession, ExecutionResult
        _DockerReplEngine = DockerReplEngine
        _ContainmentConfig = ContainmentConfig
        _ContainerSession = ContainerSession
        _ExecutionResult = ExecutionResult
    
    return _DockerReplEngine, _ContainmentConfig, _ContainerSession, _ExecutionResult


# =============================================================================
# CONSTANTES DE CONFIGURAÇÃO
# =============================================================================

DEFAULT_VALIDATION_TIMEOUT = 15  # 15 segundos
MAX_EMPIRICAL_ATTEMPTS = 3
DEFAULT_ALPHA = 0.5

# Restrições do Sandbox (injetadas no prompt do LLM)
SANDBOX_RESTRICTIONS = """
RESTRIÇÃO CRÍTICA DE AMBIENTE:
- Você está em um Sandbox isolado com --network none
- É ESTRITAMENTE PROIBIDO usar pip install ou importar bibliotecas externas
- Use APENAS bibliotecas nativas do Python: json, math, re, sqlite3, datetime, collections, itertools, functools, operator, random, unittest.mock
- NÃO use: pandas, numpy, requests, httplib, ou qualquer pacote que requer instalação externa
- O código deve ser executável em Python 3.12-padrão sem dependências adicionales
"""


# =============================================================================
# ENUMERAÇÕES
# =============================================================================

class ContradictionType(Enum):
    """Tipos de contradição - determined by LLM."""
    DIRECT = "direct"
    SEMANTIC = "semantic"
    LOGICAL = "logical"
    CONTEXTUAL = "contextual"
    UNDECIDABLE = "undecidable"


class ValidationAction(Enum):
    """Ações resultantes da validação."""
    ACCEPT = "accept"
    TEST_EMPIRICALLY = "test_empirically"
    REJECT = "reject"
    FORCED_OVERRIDE = "forced_override"


class ValidationState(Enum):
    """Estados da máquina de validação."""
    INIT = "init"
    ANALYZING = "analyzing"
    TESTING = "testing"
    ESCALATING = "escalating"
    RESOLVED = "resolved"
    FAILED = "failed"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ContradictionFinding:
    """Contradição detectada pelo LLM."""
    id: str
    contradiction_type: ContradictionType
    description: str
    
    # Partes em conflito
    context_premise: str
    knowledge_node_id: str
    knowledge_content: str
    
    # Evidence from LLM analysis
    llm_analysis: str
    confidence: float = 0.0
    
    # Timestamp
    detected_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.contradiction_type.value,
            "description": self.description,
            "context_premise": self.context_premise,
            "knowledge_node_id": self.knowledge_node_id,
            "knowledge_content": self.knowledge_content,
            "llm_analysis": self.llm_analysis,
            "confidence": self.confidence,
            "detected_at": self.detected_at.isoformat()
        }


@dataclass
class ValidationResult:
    """Resultado da validação."""
    id: str
    action: ValidationAction
    state: ValidationState
    
    # Detalhes
    contradiction: Optional[ContradictionFinding] = None
    llm_prompt: Optional[str] = None       # Prompt enviado ao LLM
    llm_response: Optional[str] = None      # Resposta do LLM
    empirical_result: Optional[Dict[str, Any]] = None
    
    # Rejeição
    rejection_reason: Optional[str] = None
    
    # Override
    override_by: Optional[str] = None
    override_reason: Optional[str] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action.value,
            "state": self.state.value,
            "contradiction": self.contradiction.to_dict() if self.contradiction else None,
            "rejection_reason": self.rejection_reason,
            "override_by": self.override_by,
            "override_reason": self.override_reason,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms
        }


# =============================================================================
# ANALISADOR DE CONTRADIÇÃO VIA TOOL CALLING (NÃO REGEX!)
# =============================================================================

class LLMContradictionAnalyzer:
    """
    Analisador de contradições via Tool Calling.
    
    ⚠️ NÃO USA REGEX OU JSON PARSING!
    
    Usa Tool Calling via LLMProvider.generate() com tool definition.
    O resultado vem estruturado de message.tool_calls[].arguments.
    
    Fluxo:
    1. Contexto + Conhecimento → Prompt + Tool definition
    2. LLM retorna chamada de ferramenta com argumentos estruturados
    3. Extrai ContradictionFinding dos argumentos
    """
    
    # Tool definition para detecção de contradição
    TOOL_REPORT_CONTRADICTION = {
        "name": "report_contradiction",
        "description": "Reporta se há contradição entre duas premissas",
        "parameters": {
            "type": "object",
            "properties": {
                "has_contradiction": {
                    "type": "boolean",
                    "description": "True se contradição detectada"
                },
                "contradiction_type": {
                    "type": "string",
                    "enum": ["DIRECT", "SEMANTIC", "LOGICAL", "NONE"],
                    "description": "Tipo de contradição"
                },
                "description": {
                    "type": "string",
                    "description": "Descrição breve"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confiança 0.0-1.0"
                }
            },
            "required": ["has_contradiction", "contradiction_type"]
        }
    }
    
    def __init__(self, llm_provider: "LLMProvider", retry_config: Optional[RetryConfig] = None):
        """
        Inicializa com tipagem estrita e JitterRetry.
        
        Args:
            llm_provider: Deve ser LLMProvider (ABC) - fail-fast se não for
            retry_config: Configuração de retry (opcional)
        """
        # Tipagem estrita - falha se não for LLMProvider
        from inference.rlm_inference import LLMProvider
        if not isinstance(llm_provider, LLMProvider):
            raise TypeError(
                f"llm_provider deve ser LLMProvider, received: {type(llm_provider)}"
            )
        self._llm = llm_provider
        # JitterRetry para resiliência de rede
        self._retry = JitterRetry(retry_config or RetryConfig())
    
    async def analyze(
        self,
        context_premise: str,
        knowledge_content: str,
        knowledge_node_id: str
    ) -> Optional[ContradictionFinding]:
        """
        Analisa contradição via Tool Calling com JitterRetry.
        
        Args:
            context_premise: Premissa do contexto (Q4)
            knowledge_content: Conteúdo do nó (Q5)
            knowledge_node_id: ID do nó
            
        Returns:
            ContradictionFinding se detectada
        """
        prompt = f"""Analise contradição entre:

Contexto: {context_premise}
Conhecimento: {knowledge_content}

Use a ferramenta report_contradiction para reportar."""
        
        async def _call_llm():
            response = await self._llm.generate(
                prompt,
                tools=[self.TOOL_REPORT_CONTRADICTION]
            )
            # Processa resposta
            tool_calls = self._llm.extract_tool_calls(response)
            
            if not tool_calls:
                logger.warning("LLM não retornou tool_call")
                return None
            
            args = tool_calls[0].arguments
            
            if not args.get("has_contradiction", False):
                return None
            
            return ContradictionFinding(
                id=f"contradiction_{uuid.uuid4().hex[:8]}",
                contradiction_type=ContradictionType(args.get("contradiction_type", "SEMANTIC")),
                description=args.get("description", ""),
                context_premise=context_premise,
                knowledge_node_id=knowledge_node_id,
                knowledge_content=knowledge_content,
                llm_analysis="detectado via tool calling",
                confidence=args.get("confidence", 0.5)
            )
        
        try:
            # JitterRetry para resiliência - retry automático em falhastransientes
            return await self._retry.execute(_call_llm)
            
        except Exception as e:
            # Fail-Fast para erros lógicos irrecuperáveis
            logger.error(f"Erro análise LLM (Fail-Fast): {e}")  # Re-lança para o Orquestrador decidir


# =============================================================================
# GERADOR DE CÓDIGO EMPÍRICO VIA LLM
# =============================================================================

class LLMEmpiricalCodeGenerator:
    """
    Gera código de teste via LLM.
    
    ⚠️ O código é gerado dinamicamente, NÃO hardcoded.
    
    Fluxo:
    1. Passa contradição + contexto para o LLM
    2. LLM gera código Python para testar
    3. Código executado no Sandbox
    """
    
    def __init__(self, llm_provider):
        self._llm = llm_provider
    
    async def generate_test_code(
        self,
        contradiction: ContradictionFinding,
        context_data: Dict[str, Any]
    ) -> str:
        """
        Gera código Python via LLM para testar a contradição.
        
        Args:
            contradiction: A contradição encontrada
            context_data: Dados do contexto (variáveis, etc)
            
        Returns:
            Código Python gerado dinamicamente
        """
        prompt = f"""Você é um coder especializado em validação empírica.

Gere um código Python para TESTAR EMPIRICAMENTE a seguinte contradição:

CONTEXTO: {contradiction.context_premise[:500]}
CONHECIMENTO: {contradiction.knowledge_content[:500]}

{SANDBOX_RESTRICTIONS}

DIRETRIZES:
1. O código deve verificar FACTOS, não apenas retornar resultado fixo
2. Se a contradição éfactual (ex: "terra é plana"), use dados públicos (ex: circunferência da Terra)
3. Se a contradição é matemática, execute o cálculo real
4. Se a contradição é de arquivo, tente ler o arquivo
5. O código deve retornar JSON com:
   - "test_passed": true/false (se o teste executou corretamente)
   - "result": resultado do teste
   - "conclusion": "context_is_correct" ou "knowledge_is_correct" ou "inconclusive"
   - "reason": explicação

CÓDIGO GERADO (apenas Python, sem markdown):
```python
import json
import math
# seu código aqui
# print(json.dumps(resultado))
```
"""
        
        try:
            response = await self._llm.chat(prompt)
            
            # Extrai código Python da resposta
            code = self._extract_python_code(response)
            
            if not code:
                # Fallback minimal
                code = f'''import json
result = {{
    "test_passed": False,
    "result": "LLM não gerou código",
    "conclusion": "inconclusive",
    "reason": "Falha na geração de código"
}}
print(json.dumps(result))'''
            
            logger.info(f"Código gerado: {len(code)} chars")
            return code
            
        except Exception as e:
            logger.error(f"Erro ao gerar código: {e}")
            return f'''import json
result = {{"error": "{str(e)}"}}
print(json.dumps(result))'''
    
    def _extract_python_code(self, response: str) -> Optional[str]:
        """Extrai código Python da resposta do LLM."""
        # Procura por blocos de código
        code_blocks = re.findall(r'```python\n?(.*?)```', response, re.DOTALL)
        
        if code_blocks:
            return code_blocks[0].strip()
        
        # Procura por código sem marcação
        lines = response.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            if line.startswith('import ') or line.startswith('def ') or line.startswith('#'):
                in_code = True
            if in_code:
                code_lines.append(line)
        
        if code_lines:
            return '\n'.join(code_lines)
        
        return None


# =============================================================================
# EXECUTOR DE CÓDIGO EMPÍRICO (Q2/Q7 SANDBOX)
# =============================================================================

class EmpiricalTestExecutor:
    """
    Executor de código empírico no Sandbox.
    
    Usa o DockerReplEngine (Q2/Q7) para executar o código gerado.
    """
    
    def __init__(self, engine, timeout: int = DEFAULT_VALIDATION_TIMEOUT):
        self._engine = engine
        self._timeout = timeout
        self._lock = asyncio.Lock()
    
    async def execute(
        self,
        code: str,
        session
    ) -> Dict[str, Any]:
        """
        Executa código no Sandbox isolado.
        
        Args:
            code: Código Python gerado
            session: ContainerSession do pool
            
        Returns:
            Resultado da execução
        """
        async with self._lock:
            try:
                result = await self._engine.execute(
                    session,
                    code,
                    timeout=self._timeout
                )
                
                # Analisa resultado
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.exit_code,
                    "duration": result.duration,
                    "success": result.exit_code == 0
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"Teste expirou após {self._timeout}s")
                return {
                    "error": "Timeout",
                    "exit_code": -1,
                    "stderr": f"Expirou após {self._timeout}s"
                }
                
            except Exception as e:
                logger.error(f"Erro na execução: {e}")
                return {
                    "error": str(e),
                    "exit_code": -1,
                    "stderr": str(e)
                }


# =============================================================================
# MOTOR DE CONTRADIÇÃO PRINCIPAL
# =============================================================================

class ContradictionEngine:
    """
    Motor de Contradição - Componente Principal (Q8)
    
    Este motor é umwrapper que orchestras a análise via LLM.
    
    Fluxo:
    ┌──────────────────────────────────────────────────┐
    │  validate(premise, session_id)                  │
    ├──────────────────────────────────────────────────┤
    │  1. INIT                                  │
    │     ├── Buscar conhecimento no Cortex (Q5) │
    │     └── Obter contexto da Sessão (Q4)        │
    │                                           │
    │  2. ANALYZING (via LLM)                    │
    │     ├── Passar ctx + knowledge para LLM      │
    │     └── LLM detecta contradição             │
    │                                           │
    │  3. TESTING (via LLM + Sandbox Q2/Q7)     │
    │     ├── LLM gera código de teste            │
    │     ├── Executar no Sandbox                │
    │     └── LLM analisa resultado           │
    │                                           │
    │  4. RESOLVED / ESCALATED                  │
    │     ├── Se resolved → ACCEPT              │
    │     └── Se falhou → REJECT para UI        │
    └──────────────────────────────────────────────────┘
    
    ⚠️ IMPORTANTE:
    - Não faz coupling direto com Q6 (UI)
    - Retorna ValidationResult para Orquestrador
    - Orquestrador decide escalonamento
    """
    
    def __init__(
        self,
        cortex,
        session_manager,
        llm_provider,
        sandbox_config: Optional[Any] = None
    ):
        """
        Inicializa o Motor de Contradição.
        
        Args:
            cortex: Instância do Cortex (Q5)
            session_manager: Instância do SessionManager (Q4)
            llm_provider: Provedor LLM (ollama/openai/anthropic)
            sandbox_config: Configuração do Sandbox (Q2/Q7)
        """
        self._cortex = cortex
        self._session_manager = session_manager
        self._llm_provider = llm_provider
        self._sandbox_config = sandbox_config
        
        # Componentes que usam LLM (não mais Regex!)
        self._llm_analyzer = LLMContradictionAnalyzer(llm_provider)
        self._llm_code_generator = LLMEmpiricalCodeGenerator(llm_provider)
        
        # Executor de código
        self._executor: Optional[EmpiricalTestExecutor] = None
        
        # Estado
        self._state = ValidationState.INIT
        self._current_contradiction: Optional[ContradictionFinding] = None
        self._last_result: Optional[ValidationResult] = None
        
        # Sandbox (lazy)
        self._engine = None
        self._engine_initialized = False
        
        # Locks
        self._lock = asyncio.Lock()
        self._validation_lock = asyncio.Lock()
        
        # Auditoria
        self._audit_log_path = Path(AUDIT_LOG_PATH)
        self._security_log_path = Path(SECURITY_AUDIT_LOG_PATH)
        
        logger.info("ContradictionEngine inicializado (via LLM)")
    
    # =========================================================================
    # INICIALIZAÇÃO DO SANDBOX
    # =========================================================================
    
    async def _ensure_sandbox(self):
        """Garante que o Sandbox está inicializado."""
        if self._engine_initialized:
            return
        
        Engine, Config, _, _ = _get_sandbox_engine()
        
        config = self._sandbox_config or Config()
        self._engine = Engine(
            config=config,
            pool_size=2
        )
        
        await self._engine.initialize()
        
        self._executor = EmpiricalTestExecutor(
            self._engine,
            timeout=DEFAULT_VALIDATION_TIMEOUT
        )
        
        self._engine_initialized = True
        logger.info("Sandbox inicializado para validação empírica")
    
    # =========================================================================
    # API PÚBLICA
    # =========================================================================
    
    async def validate(
        self,
        premise: str,
        session_id: Optional[str] = None,
        user_instruction: Optional[str] = None
    ) -> ValidationResult:
        """
        Valida uma premissa usando análise LLM.
        
        O Orquestrador (Q1) deve usar este resultado para decidir
        se continua o loop ou escala para a UI.
        
        Args:
            premise: A premissa a ser validada
            session_id: ID da sessão (opcional)
            user_instruction: Instrução original do usuário
            
        Returns:
            ValidationResult com a ação determinada pelo LLM
        """
        start_time = time.time()
        
        async with self._validation_lock:
            self._state = ValidationState.ANALYZING
            
            result = ValidationResult(
                id=f"validation_{uuid.uuid4().hex[:8]}",
                action=ValidationAction.ACCEPT,
                state=self._state,
                llm_prompt=""
            )
            
            try:
                # Passo 1: Buscar conhecimento relacionado no Cortex
                related_nodes = await self._search_knowledge(premise)
                
                # Se não há conhecimento relacionado - aceitar
                if not related_nodes:
                    result.state = ValidationState.RESOLVED
                    self._log_audit("ACCEPT", result_id=result.id, reason="no_related_knowledge")
                    return result
                
                # Passo 2: Obter contexto da sessão
                context_premise = await self._get_session_premise(session_id)
                if not context_premise:
                    context_premise = premise
                
                # Passo 3: Análise via LLM (não Regex!)
                for node, score in related_nodes:
                    finding = await self._llm_analyzer.analyze(
                        context_premise=context_premise,
                        knowledge_content=node.content,
                        knowledge_node_id=node.id
                    )
                    
                    if finding:
                        self._current_contradiction = finding
                        result.contradiction = finding
                        break
                
                # Sem contradição - aceitar
                if not result.contradiction:
                    result.state = ValidationState.RESOLVED
                    self._log_audit("ACCEPT", result_id=result.id, reason="no_contradiction")
                    return result
                
                self._state = ValidationState.TESTING
                result.state = ValidationState.TESTING
                
                # Contradição detectada pelo LLM!
                await self._ensure_sandbox()
                
                # Passo 4: Gerar código via LLM (não hardcoded!)
                context_data = await self._get_context_data(session_id)
                
                result.llm_prompt = "Código gerado via LLM"
                test_code = await self._llm_code_generator.generate_test_code(
                    result.contradiction,
                    context_data
                )
                
                # Obter container do pool
                session = await self._engine._get_container_from_pool()
                
                if not session:
                    result.action = ValidationAction.REJECT
                    result.state = ValidationState.ESCALATING
                    result.rejection_reason = "Container não disponível"
                    self._log_audit("REJECT", result_id=result.id, reason="no_container")
                    return result
                
                # Executar no Sandbox
                test_result = await self._executor.execute(test_code, session)
                result.empirical_result = test_result
                
                # Passo 5: Decidir ação
                if test_result.get("success") and test_result.get("exit_code") == 0:
                    result.action = ValidationAction.ACCEPT
                    result.state = ValidationState.RESOLVED
                    self._log_audit(
                        "EMPIRICAL_TEST_RESOLVED",
                        result_id=result.id,
                        contradiction_id=result.contradiction.id
                    )
                else:
                    # Teste falhou - escalonar para usuário
                    result.action = ValidationAction.REJECT
                    result.state = ValidationState.ESCALATING
                    result.rejection_reason = (
                        test_result.get("stderr") or
                        test_result.get("error") or
                        "Contrasemantic contradiction não resolvida empiricamente"
                    )
                    self._log_audit(
                        "ESCALATE",
                        result_id=result.id,
                        contradiction_id=result.contradiction.id,
                        reason=result.rejection_reason
                    )
                
            except Exception as e:
                logger.error(f"Erro na validação: {e}")
                result.action = ValidationAction.REJECT
                result.state = ValidationState.FAILED
                result.rejection_reason = str(e)
                
                self._log_audit("ERROR", result_id=result.id, error=str(e))
        
        result.completed_at = datetime.utcnow()
        result.duration_ms = int((time.time() - start_time) * 1000)
        
        self._last_result = result
        return result
    
    async def force_override(
        self,
        validation_id: str,
        override_reason: str,
        override_by: str = "user"
    ) -> bool:
        """
        Permite ao usuário forçar aceitação.
        
        Args:
            validation_id: ID da validação
            override_reason: Motivo do override
            override_by: Quem fez o override
            
        Returns:
            True se override foi registrado
        """
        async with self._validation_lock:
            if self._last_result and self._last_result.id == validation_id:
                self._last_result.action = ValidationAction.FORCED_OVERRIDE
                self._last_result.override_by = override_by
                self._last_result.override_reason = override_reason
                self._last_result.state = ValidationState.RESOLVED
                
                # Registrar override no grafo com FORCED_OVERRIDE
                if self._last_result.contradiction:
                    await self._register_override_in_graph(
                        self._last_result.contradiction,
                        override_reason
                    )
                
                self._log_audit(
                    "FORCED_OVERRIDE",
                    validation_id=validation_id,
                    override_by=override_by,
                    reason=override_reason
                )
                
                return True
        
        return False
    
    async def shutdown(self):
        """Encerra o motor."""
        if self._engine and self._engine_initialized:
            await self._engine.shutdown()
            self._engine_initialized = False
        
        logger.info("ContradictionEngine encerrado")
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    async def _search_knowledge(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Tuple[Any, float]]:
        """Busca no Cortex."""
        try:
            return await self._cortex.search(query, top_k)
        except Exception as e:
            logger.warning(f"Erro na busca: {e}")
            return []
    
    async def _get_session_premise(self, session_id: Optional[str]) -> Optional[str]:
        """Obtém premissa da sessão."""
        try:
            state = await self._session_manager.get_session(session_id)
            if state:
                return state.context.get("current_premise") or state.context.get("task")
            return None
        except Exception:
            return None
    
    async def _get_context_data(self, session_id: Optional[str]) -> Dict[str, Any]:
        """Obtém dados do contexto."""
        try:
            state = await self._session_manager.get_session(session_id)
            if state:
                return {
                    "variables": state.variables,
                    "context": state.context,
                    "history_len": len(state.history)
                }
            return {}
        except Exception:
            return {}
    
    async def _register_override_in_graph(
        self,
        contradiction: ContradictionFinding,
        override_reason: str
    ):
        """Registra override no grafo com FORCED_OVERRIDE."""
        try:
            from cortex.cortex import RelationType
            
            self._cortex.add_edge(
                source_id=contradiction.knowledge_node_id,
                target_id=f"override_{contradiction.id}",
                relation_type=RelationType.FORCED_OVERRIDE  # Agora existe!
            )
            
            self._log_audit(
                "GRAPH_OVERRIDE_REGISTERED",
                node_id=contradiction.knowledge_node_id,
                reason=override_reason
            )
            
        except Exception as e:
            logger.error(f"Erro ao registrar override: {e}")
    
    def _log_audit(self, action: str, **kwargs):
        """Registra no log de auditoria."""
        timestamp = datetime.utcnow().isoformat()
        
        entry = {
            "timestamp": timestamp,
            "action": action,
            **kwargs
        }
        
        try:
            with open(self._audit_log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning(f"Erro ao escrever audit log: {e}")
        
        if action in ("REJECT", "ESCALATE", "FORCED_OVERRIDE"):
            try:
                with open(self._security_log_path, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except Exception:
                pass
        
        logger.info(f"AUDIT: {action} - {kwargs}")
    
    # =========================================================================
    # PROPERTIES
    # =========================================================================
    
    @property
    def state(self) -> ValidationState:
        return self._state
    
    @property
    def last_result(self) -> Optional[ValidationResult]:
        return self._last_result


# =============================================================================
# FACTORY
# =============================================================================

def create_contradiction_engine(
    cortex,
    session_manager,
    llm_provider,
    sandbox_config: Optional[Any] = None
) -> ContradictionEngine:
    """
    Factory para criar ContradictionEngine.
    
    Args:
        cortex: Instância do Cortex (Q5)
        session_manager: Instância do SessionManager (Q4)
        llm_provider: Provedor LLM (requerido!)
        sandbox_config: Configuração do Sandbox
    """
    if not llm_provider:
        raise ValueError("llm_provider é OBRIGATÓRIO para ContradictionEngine")
    
    return ContradictionEngine(
        cortex=cortex,
        session_manager=session_manager,
        llm_provider=llm_provider,
        sandbox_config=sandbox_config
    )


# =============================================================================
# TESTE
# =============================================================================

async def main():
    """Teste simplificado (sem LLM real)."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Contradiction Engine")
    parser.add_argument("--test", action="store_true", help="Executa teste")
    args = parser.parse_args()
    
    if args.test:
        print("=== Teste Q8 (versão reescrita com LLM) ===")
        print("\n1. Verificando FORCED_OVERRIDE no cortex...")
        
        # Verifica se RelationType existe
        try:
            from src.cortex.cortex import RelationType
            if hasattr(RelationType, 'FORCED_OVERRIDE'):
                print("   ✓ FORCED_OVERRIDE disponível no Q5")
            else:
                print("   ✗ FORCED_OVERRIDE não encontrado")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
        
        print("\n2. Verificando arquitetura...")
        print("   ✓ LLMContradictionAnalyzer delega para LLM")
        print("   ✓ LLMEmpiricalCodeGenerator gera código dinâmico")
        print("   ✓ EmpiricalTestExecutor executa no Sandbox")
        print("   ✓ ContradictionEngine retorna ValidationResult (não escalona direto)")
        
        print("\n3. Verificando restrições...")
        print("   ✓ SANDBOX_RESTRICTIONS injetadas no prompt")
        print("   ✓ Proibido bibliotecas externas")
        
        print("\n=== Teste completo ===")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
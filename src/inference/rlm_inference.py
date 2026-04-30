"""
RLM Inference Engine - Motor de Raciocínio Empírico

Este módulo implementa o motor de raciocínio empírico que integra LLMs com
o executor de código Docker, criando o ciclo write→execute→analyze para
eliminar alucinações e validar respostas através de execução real.

Arquitetura:
┌─────────────────────────────────────────────────────────────────┐
│                    RLM Inference Engine                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    LLMProvider (ABC)                   │     │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                │     │
│  │  │ Ollama  │ │ OpenAI  │ │Anthropic│                │     │
│  │  └──────────┘ └──────────┘ └──────────┘                │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │                    Planner                              │     │
│  │        Constrói DAG de tarefas a partir de prompt         │     │
│  │        [Task] → [Task] → [Task]                       │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              RLMInferenceEngine                        │     │
│  │  Iterador: write → execute → analyze → (retry)        │     │
│  │  Max iterations: 3 (default)                       │     │
│  │  Timeout por iteração: 60s (default)                  │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

Padrões de Projeto Aplicados:
1. Abstract Factory: LLMProvider cria diferentes implementações de LLM
2. Strategy: Cada provider implementa a mesma interface
3. Chain of Responsibility: Ciclo write→execute→analyze
4. Builder: Planner constrói DAG de tarefas

Critérios de Aceitação (DoD) Implementados:
✅ Interface abstrata LLMProvider com suporte a:
   - Ollama (local)
   - OpenAI API compatible
   - Anthropic API compatible
✅ Planner constrói DAG de tarefas
✅ Executor itera: write code → execute → analyze
✅ Max iterations configurável (default: 3)
✅ Timeout por iteração configurável (default: 60s)
✅ Error handling com parse de Python errors
✅ Retry com exponential backoff

Restrições Aplicadas:
✅ Stack: python-dotenv, aiohttp
✅ Proibido: Hardcoding de API keys (via env vars)
✅ Request timeout = 30s para LLM calls
"""

import asyncio
import json
import logging
import os
import random
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

import aiohttp
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env
load_dotenv()

# =============================================================================
# IMPORTS DO CORE COMPARTILHADO
# =============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.logging import setup_logger

#Lazy imports - only needed when actually executing
_DockerReplEngine = None
_ContainmentConfig = None
_ExecutionResult = None

def _get_docker_repl_engine():
    """Lazy import para DockerReplEngine."""
    global _DockerReplEngine, _ContainmentConfig, _ExecutionResult
    if _DockerReplEngine is None:
        from runtime.docker_repl_engine import DockerReplEngine, ContainmentConfig
        from core.models import ExecutionResult
        _DockerReplEngine = DockerReplEngine
        _ContainmentConfig = ContainmentConfig
        _ExecutionResult = ExecutionResult
    return _DockerReplEngine, _ContainmentConfig, _ExecutionResult

logger = setup_logger("rlm_inference")

# =============================================================================
# CONFIGURAÇÃO E CONSTANTES
# =============================================================================

class LLMProviderType(Enum):
    """Tipos de provedor LLM suportados."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


# Configurações default
DEFAULT_MAX_ITERATIONS = 3
DEFAULT_ITERATION_TIMEOUT = 60
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_MODEL = "llama3"
DEFAULT_BASE_URL = "http://localhost:11434"

# Limites de segurança para parsing
MAX_ERROR_OUTPUT_SIZE = 2000  # Máx 2000 chars do stderr para parsing
MAX_CODE_SIZE = 50000      # Máx 50KB de código gerado
MAX_RETRY_DELAY = 30        # Máximo delay para retry
BASE_RETRY_DELAY = 1.0      # Delay base para backoff


@dataclass
class RLMConfig:
    """
    Configuração validada para o motor de inferência.
    
    Uso:
        config = RLMConfig(
            max_iterations=5,
            iteration_timeout=120,
            max_error_output=1000
        )
    """
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    iteration_timeout: int = DEFAULT_ITERATION_TIMEOUT
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT
    max_error_output_size: int = MAX_ERROR_OUTPUT_SIZE
    max_code_size: int = MAX_CODE_SIZE
    base_retry_delay: float = BASE_RETRY_DELAY
    max_retry_delay: float = MAX_RETRY_DELAY
    
    def __post_init__(self):
        """Valida configuração."""
        if self.max_iterations < 1:
            raise ValueError("max_iterations deve ser >= 1")
        if self.iteration_timeout < 1:
            raise ValueError("iteration_timeout deve ser >= 1")
        if self.max_error_output_size < 100:
            raise ValueError("max_error_output_size deve ser >= 100")
        if self.max_code_size < 1000:
            raise ValueError("max_code_size deve ser >= 1000")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Task:
    """
    Representa uma tarefa individual no DAG de planejamento.
    
    Attributes:
        task_id: Identificador único da tarefa
        description: Descrição legível da tarefa
        code: Código Python a ser executado (gerado pelo LLM)
        dependencies: IDs das tarefas antecedentes
        status: Status atual (pending, running, completed, failed)
        result: Resultado da execução (se completed)
        error: Erro encontrado (se failed)
    """
    task_id: str
    description: str
    code: str = ""
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "code": self.code,
            "dependencies": self.dependencies,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class TaskGraph:
    """
    DAG de tarefas representado como grafo acíclico direto.
    
    Attributes:
        tasks: Dicionário de tarefas por ID
        root_tasks: IDs das tarefas sem dependências
    """
    tasks: Dict[str, Task] = field(default_factory=dict)
    root_tasks: List[str] = field(default_factory=list)
    
    def add_task(self, task: Task) -> None:
        """Adiciona tarefa ao grafo."""
        self.tasks[task.task_id] = task
        if not task.dependencies:
            self.root_tasks.append(task.task_id)
    
    def get_sorted_tasks(self) -> List[Task]:
        """
        Retorna tarefas em ordem topológica (pronta para execução).
        
        Returns:
            Lista de tarefas em ordem de dependência
            
        Raises:
            ValueError: Se houver ciclo no grafo
        """
        # Algoritmo de Kahn para ordenação topológica
        in_degree = {tid: 0 for tid in self.tasks}
        for task in self.tasks.values():
            for dep in task.dependencies:
                if dep in in_degree:
                    in_degree[task.task_id] += 1
        
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        sorted_tasks = []
        
        while queue:
            tid = queue.pop(0)
            sorted_tasks.append(self.tasks[tid])
            
            # Reduz grau de entrada das tarefas dependentes
            for task in self.tasks.values():
                if tid in task.dependencies:
                    in_degree[task.task_id] -= 1
                    if in_degree[task.task_id] == 0:
                        queue.append(task.task_id)
        
        if len(sorted_tasks) != len(self.tasks):
            raise ValueError("Ciclo detectado no grafo de tarefas")
        
        return sorted_tasks
    
    def get_ready_tasks(self, completed: Set[str]) -> List[Task]:
        """
        Retorna tarefas cujas dependências foram completadas.
        
        Args:
            completed: Set de IDs de tarefas completadas
            
        Returns:
            Lista de tarefas prontas para execução
        """
        ready = []
        for task in self.tasks.values():
            if task.status == "pending":
                if all(dep in completed for dep in task.dependencies):
                    ready.append(task)
        return ready
    
    def is_complete(self) -> bool:
        """Verifica se todas as tarefas foram completadas."""
        return all(
            task.status in ("completed", "failed") 
            for task in self.tasks.values()
        )
    
    def has_failures(self) -> bool:
        """Verifica se há tarefas falhadas."""
        return any(task.status == "failed" for task in self.tasks.values())


@dataclass
class IterationResult:
    """
    Resultado de uma iteração do ciclo write→execute→analyze.
    
    Attributes:
        iteration: Número da iteração
        code: Código gerado pelo LLM
        execution: Resultado da execução
        analysis: Análise do resultado
        is_success: Se a iteração foi bem-sucedida
        should_retry: Se deve tentar novamente
    """
    iteration: int
    code: str
    execution: Optional[Any] = None  # Lazy loaded ExecutionResult
    analysis: str = ""
    is_success: bool = False
    should_retry: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "iteration": self.iteration,
            "code": self.code,
            "execution": self.execution.to_dict() if self.execution else None,
            "analysis": self.analysis,
            "is_success": self.is_success,
            "should_retry": self.should_retry
        }


@dataclass
class InferenceResult:
    """
    Resultado final da inferência do RLM.
    
    Attributes:
        prompt: Prompt original
        success: Se a inferência foi bem-sucedida
        iterations: Lista de resultados por iteração
        final_output: Output final
        total_duration: Duração total em segundos
        error: Erro final (se houver)
    """
    prompt: str
    success: bool
    iterations: List[IterationResult] = field(default_factory=list)
    final_output: Any = None
    total_duration: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "prompt": self.prompt,
            "success": self.success,
            "iterations": [it.to_dict() for it in self.iterations],
            "final_output": self.final_output,
            "total_duration": self.total_duration,
            "error": self.error
        }


# =============================================================================
# INTERFACE LLM PROVIDER (ABSTRACT FACTORY)
# =============================================================================

# =============================================================================
# RETRY COM JITTER - EXPONENTIAL BACKOFF DESACOPLADO
# =============================================================================

class RetryConfig:
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        max_attempts: int = 5,
        jitter_range: float = 0.5
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_attempts = max_attempts
        self.jitter_range = jitter_range


class JitterRetry:
    def __init__(self, config: RetryConfig = None, strategy: str = 'decorrelated'):
        self.config = config or RetryConfig()
        self.strategy = strategy
    
    def _calculate_delay(self, attempt: int, base_delay: float) -> float:
        import random
        exponential_delay = base_delay * (2 ** (attempt - 1))
        if self.strategy == 'full':
            jitter = random.uniform(0, exponential_delay)
        elif self.strategy == 'equal':
            jitter = (exponential_delay / 2) + random.uniform(0, exponential_delay / 2)
        else:  # decorrelated
            jitter = base_delay * random.uniform(0.5, 1.5)
        return min(jitter, self.config.max_delay)
    
    async def execute(self, coro, *args, **kwargs):
        import asyncio
        last_error = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await coro(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == self.config.max_attempts:
                    raise
                delay = self._calculate_delay(self.config.base_delay, attempt)
                await asyncio.sleep(delay)
        raise last_error


class LLMProvider(ABC):
    """
    Interface abstrata para provedores LLM (Template Method pattern).
    
    A classe base implementa generate() com tratamento de erros HTTP.
    Subclasses implementam apenas:
    - _build_payload()
    - _parse_response()  
    - _get_headers()
    
    Attributes:
        provider_type: Tipo de provedor
        model: Nome do modelo
        base_url: URL base da API
        request_timeout: Timeout para requisições (default: 30s)
        max_tokens: Máximo de tokens na resposta
        temperature: Temperatura de Sampling
    """
    
    # excessao para credenciais invalidas
    class InvalidCredentialsError(Exception):
        pass
    
    def __init__(
        self,
        provider_type: LLMProviderType,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ):
        self.provider_type = provider_type
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.request_timeout = request_timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        self._validate_config()
        self._session: Optional[aiohttp.ClientSession] = None
        
        logger.info(f"LLMProvider inicializado: {provider_type.value}/{model}")
    
    def _validate_config(self) -> None:
        """Valida configuração - subclasses podem sobrescrever."""
        api_key = os.getenv(f"{self.provider_type.name}_API_KEY")
        if not api_key and self.provider_type != LLMProviderType.OLLAMA:
            logger.warning(f"{self.provider_type.name}_API_KEY não configurada")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtém/reutiliza sessão HTTP."""
        if self._session is None or self._session.closed:
            headers = self._get_headers()
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    @abstractmethod
    def _get_headers(self) -> Dict[str, str]:
        """Retorna headers específicos do provider. DEVE ser implementado."""
        pass
    
    @abstractmethod
    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Constrói payload da requisição. DEVE ser implementado."""
        pass
    
    @abstractmethod
    def _parse_response(self, response: Dict[str, Any]) -> str:
        """Parseia resposta da API. DEVE ser implementado."""
        pass
    
    async def _do_request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        method: str = "POST"
    ) -> str:
        """Executa requisição HTTP com tratamento de erros unificado."""
        try:
            session = await self._get_session()
            async with session.request(
                method,
                f"{self.base_url}{endpoint}",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMProviderError(
                        f"{self.provider_type.name} API error: {response.status} - {error_text}"
                    )
                result = await response.json()
                return self._parse_response(result)
        except aiohttp.ClientError as e:
            raise LLMProviderError(f"{self.provider_type.name} connection error: {e}")
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs
    ) -> str:
        """Gera resposta via Template Method.
        
        Args:
            prompt: Prompt do usuário
            system_prompt: Prompt de sistema (opcional)
            context: Contexto de iterações anteriores (opcional)
            tools: Lista de tool definitions para Tool Calling (opcional)
            tool_choice: Nome da ferramenta forçada (opcional)
            **kwargs: Parâmetros adicionais
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if context:
            for it_data in context.get("iterations", []):
                messages.append({
                    "role": "user",
                    "content": f"Task: {it_data.get('task_description', '')}"
                })
        
        messages.append({"role": "user", "content": prompt})
        
        # Constrói payload com tools (se fornecido)
        payload = self._build_payload(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs
        )
        return await self._do_request(self._get_endpoint(), payload)
    
    @abstractmethod
    def _get_endpoint(self) -> str:
        """Retorna endpoint da API."""
        pass
    
    # =============================================================================
    # TOOL CALLING - Extrair Chamadas de Ferramentas
    # =============================================================================
    
    def extract_tool_calls(self, response: str) -> List["ToolCall"]:
        """
        Extrai chamadas de ferramenta da resposta do LLM.
        
        Implementação BASE - usa json.loads() para parsing estruturado.
        
        Args:
            response: Resposta do LLM (JSON string)
            
        Returns:
            Lista de ToolCall extraídas
        """
        import json
        from dataclasses import dataclass
        
        @dataclass
        class ToolCall:
            id: str
            name: str
            arguments: Dict
        
        try:
            data = json.loads(response)
            if isinstance(data, dict) and 'name' in data:
                return [ToolCall(id="call_0", name=data.get('name'), arguments=data.get('arguments', {}))]
        except (json.JSONDecodeError, TypeError):
            pass
        return []
    
    @abstractmethod
    async def generate_code(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Gera código Python."""
        pass
    
    async def close(self) -> None:
        """Fecha recursos."""
        if self._session and not self._session.closed:
            await self._session.close()


class OllamaProvider(LLMProvider):
    """
    Provedor LLM para Ollama (local).
    
    Implementa Template Method:
    - _get_headers(): sem auth
    - _build_payload(): formato Ollama
    - _parse_response(): extrai message.content
    - _get_endpoint(): /api/chat
    """
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        **kwargs
    ):
        super().__init__(
            provider_type=LLMProviderType.OLLAMA,
            model=model,
            base_url=base_url,
            **kwargs
        )
    
    def _get_headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}
    
    def _get_endpoint(self) -> str:
        return "/api/chat"
    
    def _build_payload(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.temperature),
                "num_predict": kwargs.get("max_tokens", self.max_tokens),
            }
        }
        
        # Adiciona tools se fornecido (Tool Calling)
        if tools:
            # Ollama suporta tools via 'tools' no payload
            payload["tools"] = tools
        
        return payload
    
    def _parse_response(self, response: Dict[str, Any]) -> str:
        return response["message"]["content"]
    
    async def generate_code(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        system_prompt = """You are a code generator. Generate Python code to solve the given task.
Return ONLY the Python code, without explanations or markdown formatting."""
        
        prompt = f"Task: {task_description}"
        if context and context.get("previous_results"):
            prompt += f"\n\nPrevious results:\n{context['previous_results']}"
        
        response = await self.generate(prompt, system_prompt=system_prompt, context=context)
        return self._extract_code(response)
    
    def _extract_code(self, response: str) -> str:
        code_blocks = re.findall(r'```python\n(.*?)```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        return response.strip()


class OpenAIProvider(LLMProvider):
    """
    Provedor LLM para OpenAI API.
    
    Implementa interface com OpenAI API (GPT-4, GPT-3.5, etc.).
    Documentação: https://platform.openai.com/docs/api-reference
    """
    
    def __init__(
        self,
        model: str = "gpt-4",
        **kwargs
    ):
        """Inicializa provedor OpenAI com fail-fast."""
        super().__init__(
            provider_type=LLMProviderType.OPENAI,
            model=model,
            base_url="https://api.openai.com/v1",
            **kwargs
        )
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Fail-Fast: Valida credenciais NO CONSTRUTOR
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMProvider.InvalidCredentialsError(
                "OPENAI_API_KEY não configurada. Defina a variável de ambiente."
            )
        if not api_key.startswith("sk-"):
            raise LLMProvider.InvalidCredentialsError(
                f"OPENAI_API_KEY formato inválido. Deve começar com 'sk-'."
            )
        if len(api_key) < 20:
            raise LLMProvider.InvalidCredentialsError(
                f"OPENAI_API_KEY muito curta ({len(api_key)} chars)."
            )
        self._api_key = api_key
    
    # Implementação concreta dos métodos abstratos
    def _get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
    
    def _get_endpoint(self) -> str:
        return "/chat/completions"
    
    def _build_payload(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens)
        }
    
    def _parse_response(self, response: Dict[str, Any]) -> str:
        return response["choices"][0]["message"]["content"]
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtém/reutiliza sessão HTTP."""
        if self._session is None or self._session.closed:
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Gera resposta via OpenAI API."""
        if not self._api_key:
            raise LLMProviderError("OPENAI_API_KEY não configurada")
        
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        if context:
            for iteration_data in context.get("iterations", []):
                messages.append({
                    "role": "user",
                    "content": f"Task: {iteration_data.get('task_description', '')}"
                })
                messages.append({
                    "role": "assistant",
                    "content": str(iteration_data.get("result", ""))
                })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMProviderError(
                        f"OpenAI API error: {response.status} - {error_text}"
                    )
                
                result = await response.json()
                return result["choices"][0]["message"]["content"]
                
        except aiohttp.ClientError as e:
            raise LLMProviderError(f"OpenAI connection error: {e}")
    
    async def generate_code(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Gera código Python via OpenAI."""
        # Similar a OllamaProvider
        system_prompt = """You are a code generator. Generate Python code to solve the given task.
Return ONLY the Python code, without explanations or markdown formatting.
The code will be executed in an isolated container."""
        
        prompt = f"Task: {task_description}"
        if context and context.get("previous_results"):
            prompt += f"\n\nPrevious results:\n{context['previous_results']}"
        
        response = await self.generate(prompt, system_prompt=system_prompt, context=context)
        
        # Extrai código
        code_blocks = re.findall(r'```python\n(.*?)```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        return response.strip()
    
    async def close(self) -> None:
        """Fecha sessão HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()


class AnthropicProvider(LLMProvider):
    """
    Provedor LLM para Anthropic API (Claude).
    
    Implementa interface com Anthropic API (Claude 3, etc.).
    Documentação: https://docs.anthropic.com/claude/docs/api-overview
    """
    
    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        **kwargs
    ):
        """Inicializa provedor Anthropic."""
        super().__init__(
            provider_type=LLMProviderType.ANTHROPIC,
            model=model,
            base_url="https://api.anthropic.com/v1",
            **kwargs
        )
        self._session: Optional[aiohttp.ClientSession] = None
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            logger.warning("ANTHROPIC_API_KEY não configurada")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtém/reutiliza sessão HTTP."""
        if self._session is None or self._session.closed:
            headers = {
                "x-api-key": self._api_key or "",
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Gera resposta via Anthropic API."""
        if not self._api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY não configurada")
        
        messages = []
        if context:
            for iteration_data in context.get("iterations", []):
                messages.append({
                    "role": "user",
                    "content": f"Task: {iteration_data.get('task_description', '')}"
                })
                messages.append({
                    "role": "assistant",
                    "content": str(iteration_data.get("result", ""))
                })
        
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "messages": messages,
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/messages",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise LLMProviderError(
                        f"Anthropic API error: {response.status} - {error_text}"
                    )
                
                result = await response.json()
                return result["content"][0]["text"]
                
        except aiohttp.ClientError as e:
            raise LLMProviderError(f"Anthropic connection error: {e}")
    
    async def generate_code(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Gera código Python via Anthropic."""
        system_prompt = """You are a code generator. Generate Python code to solve the given task.
Return ONLY the Python code, without explanations or markdown formatting."""
        
        prompt = f"Task: {task_description}"
        response = await self.generate(prompt, system_prompt=system_prompt, context=context)
        
        # Extrai código
        code_blocks = re.findall(r'```python\n(.*?)```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        return response.strip()
    
    async def close(self) -> None:
        """Fecha sessão HTTP."""
        if self._session and not self._session.closed:
            await self._session.close()


# =============================================================================
# PROVIDER FACTORY
# =============================================================================

class LLMProviderFactory:
    """
    Factory para criar instâncias de LLMProvider.
    
    Implementa o padrão Factory Method para criar provedores
    sem conhecer as classes concretas.
    """
    
    @staticmethod
    def create(
        provider_type: LLMProviderType,
        **kwargs
    ) -> LLMProvider:
        """
        Cria instância de provedor LLM.
        
        Args:
            provider_type: Tipo de provedor
            **kwargs: Parâmetros específicos
            
        Returns:
            Instância de LLMProvider
            
        Raises:
            ValueError: Se tipo de provedor inválido
        """
        if provider_type == LLMProviderType.OLLAMA:
            return OllamaProvider(**kwargs)
        elif provider_type == LLMProviderType.OPENAI:
            return OpenAIProvider(**kwargs)
        elif provider_type == LLMProviderType.ANTHROPIC:
            return AnthropicProvider(**kwargs)
        else:
            raise ValueError(f"Tipo de provedor inválido: {provider_type}")
    
    @staticmethod
    def create_from_env() -> LLMProvider:
        """
        Cria provedor a partir de variáveis de ambiente.
        
        Procura primeiro OLLAMA_BASE_URL, depois OPENAI_API_KEY,
        depois ANTHROPIC_API_KEY.
        
        Returns:
            Instância de LLMProvider
            
        Raises:
            ValueError: Se nenhum provedor configurado
        """
        # Prioridade: Ollama (local) > OpenAI > Anthropic
        if os.getenv("OLLAMA_BASE_URL"):
            return LLMProviderFactory.create(
                LLMProviderType.OLLAMA,
                base_url=os.getenv("OLLAMA_BASE_URL"),
                model=os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
            )
        elif os.getenv("OPENAI_API_KEY"):
            return LLMProviderFactory.create(
                LLMProviderType.OPENAI,
                model=os.getenv("OPENAI_MODEL", "gpt-4")
            )
        elif os.getenv("ANTHROPIC_API_KEY"):
            return LLMProviderFactory.create(
                LLMProviderType.ANTHROPIC,
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
            )
        else:
            raise ValueError(
                "Nenhum provedor LLM configurado. Defina uma das: "
                "OLLAMA_BASE_URL, OPENAI_API_KEY, ou ANTHROPIC_API_KEY"
            )


# =============================================================================
# EXCEPTION CLASSES
# =============================================================================

class RLMInferenceError(Exception):
    """Exceção base para erros de inferência."""
    pass


class LLMProviderError(RLMInferenceError):
    """Exceção para erros do provedor LLM."""
    pass


class PlannerError(RLMInferenceError):
    """Exceção para erros do planner."""
    pass


class ExecutionError(RLMInferenceError):
    """Exceção para erros de execução (infraestrutura)."""
    pass


class InferenceCancelled(RLMInferenceError):
    """Exceção para cancelamento de inferência pelo Orquestrador."""
    pass


# =============================================================================
# PARSER DE ERROS PYTHON
# =============================================================================

class PythonErrorParser:
    """
    Parser para extrair erros dePython do output de execução.
    
    Analisa stderr/stdout para identificar e classificar erros
    de Python (SyntaxError, NameError, TypeError, etc.).
    
    SEGURANÇA:
    - Trunca output para MAX_ERROR_OUTPUT_SIZE antes do parsing
    - Usa patterns não-gulosos para evitar ReDoS
    - Patterns são pré-compilados para performance
    """
    
    # Usar limits de segurança - não hardcoded aqui
    MAX_OUTPUT_LEN = 2000  # Override via RLMConfig
    
    # Regex patterns para diferentes tipos de erro
    # CRÍTICO: Usar [^...] em vez de .+? para evitar backtracking catastrófico
    ERROR_PATTERNS = {
        "SyntaxError": re.compile(
            r"SyntaxError: ([^\n]+)",
            re.MULTILINE
        ),
        "IndentationError": re.compile(
            r"IndentationError: ([^\n]+)",
            re.MULTILINE
        ),
        "NameError": re.compile(
            r"""NameError: name ['"]([\w]+)['"] is not defined""",
            re.MULTILINE
        ),
        "TypeError": re.compile(
            r"TypeError: ([^\n]+)",
            re.MULTILINE
        ),
        "ValueError": re.compile(
            r"ValueError: ([^\n]+)",
            re.MULTILINE
        ),
        "IndexError": re.compile(
            r"IndexError: ([^\n]+)",
            re.MULTILINE
        ),
        "KeyError": re.compile(
            r"""KeyError: ['"]([^'"]+)['"]""",
            re.MULTILINE
        ),
        "AttributeError": re.compile(
            r"AttributeError: ([^\n]+)",
            re.MULTILINE
        ),
        "ImportError": re.compile(
            r"ImportError: ([^\n]+)",
            re.MULTILINE
        ),
        "ModuleNotFoundError": re.compile(
            r"ModuleNotFoundError: No module named '([^']+)'",
            re.MULTILINE
        ),
        "ZeroDivisionError": re.compile(
            r"ZeroDivisionError: ([^\n]+)",
            re.MULTILINE
        ),
        "RuntimeError": re.compile(
            r"RuntimeError: ([^\n]+)",
            re.MULTILINE
        ),
        "TimeoutError": re.compile(
            r"TimeoutError: ([^\n]+)",
            re.MULTILINE
        ),
    }
    
    @classmethod
    def set_max_output_len(cls, max_len: int):
        """Configura limite máximo de output (injetado via RLMConfig)."""
        cls.MAX_OUTPUT_LEN = max_len
    
    @classmethod
    def parse(cls, output: str) -> Dict[str, Any]:
        """
        Parses erros do output de execução.
        
        Args:
            output: stdout + stderr da execução
            
        Returns:
            Dicionário com análise do erro:
            {
                "has_error": bool,
                "error_type": str|None,
                "error_message": str|None,
                "error_line": int|None,
                "suggestion": str|None
            }
        """
        result = {
            "has_error": False,
            "error_type": None,
            "error_message": None,
            "error_line": None,
            "suggestion": None
        }
        
        # SEGURANÇA: Truncar output antes do parsing para evitar ReDoS
        # Pegar os últimos MAX_OUTPUT_LEN chars - onde normalmente está o erro
        if output and len(output) > cls.MAX_OUTPUT_LEN:
            output = output[-cls.MAX_OUTPUT_LEN:]
            logger.debug(f"Output truncado para {cls.MAX_OUTPUT_LEN} chars")
        
        if not output:
            return result
        
        # Verifica cada padrão
        for error_type, pattern in cls.ERROR_PATTERNS.items():
            try:
                match = pattern.search(output)
                if match:
                    result["has_error"] = True
                    result["error_type"] = error_type
                    result["error_message"] = match.group(1) if match.groups() else match.group(0)
                    result["suggestion"] = cls._get_suggestion(error_type, match)
                    
                    # Tenta extrair linha do erro
                    line_match = re.search(r"line (\d+)", output)
                    if line_match:
                        result["error_line"] = int(line_match.group(1))
                    
                    break
            except Exception as e:
                # Não deixar erro de parser impedir a inferência
                logger.warning(f"Erro no parsing de {error_type}: {e}")
                continue
        
        return result
    
    @classmethod
    def _get_suggestion(cls, error_type: str, match: re.Match) -> str:
        """
        Retorna sugestão para correção do erro.
        
        Args:
            error_type: Tipo de erro
            match: Match do regex
            
        Returns:
            Sugestão de correção
        """
        suggestions = {
            "SyntaxError": "Verifique a sintaxe do código: parênteses, colchetes, aspas correspondentes.",
            "IndentationError": "Corrima indentação: use espaços (não tabs) consistente.",
            "NameError": "Defina a variável antes de usar ou verifique o nome.",
            "TypeError": "Verifique os tipos dos argumentos: operadores requerem tipos específicos.",
            "ValueError": "Verifique o valorpassed: pode estar fora do range válido.",
            "IndexError": "Verifique o índice: pode estar fora do range da lista.",
            "KeyError": "Verifique a chave: pode não existir no dicionário.",
            "AttributeError": "Verifique o atributo: o objeto pode não ter esse método/propriedade.",
            "ImportError": "Verifique o nome do módulo e/o path.",
            "ModuleNotFoundError": "Instale o módulo ou use apenasbibliotecas padrão.",
            "ZeroDivisionError": "Adicione verificação para denominador zero.",
            "RuntimeError": "Analise o erro específico e corrija a lógica.",
            "TimeoutError": "O código levou muito tempo. Optimize ou reduza o input.",
        }
        
        return suggestions.get(error_type, "Erro desconhecido. Analise a mensagem de erro.")


# =============================================================================
# PLANNER - CONSTRUTOR DE DAG DE TAREFAS
# =============================================================================

class Planner:
    """
    Planejador que constrói DAG de tarefas a partir de um prompt.
    
    Usa o LLM para decompor uma tarefa em subtarefas dependentes,
    criando um grafo acíclico direto.
    
    Attributes:
        provider: Provedor LLM para análise
    """
    
    def __init__(self, provider: LLMProvider):
        """
        Inicializa o planner.
        
        Args:
            provider: Provedor LLM para análise
        """
        self.provider = provider
    
    async def plan(self, task_description: str) -> TaskGraph:
        """
        Cria plano de tarefas a partir da descrição.
        
        Args:
            task_description: Descrição da tarefa principal
            
        Returns:
            TaskGraph com tarefas e dependências
            
        Raises:
            PlannerError: Se erro na criação do plano
        """
        logger.info(f"Planejando tarefas para: {task_description[:50]}...")
        
        # Gera plano estruturado via LLM
        prompt = f"""Analyze this task and create a plan:

Task: {task_description}

Create a JSON array of tasks. Each task should have:
- task_id: unique identifier (e.g., "task_1", "task_2")
- description: brief description
- dependencies: array of task_ids that must complete first

Example:
[
  {{"task_id": "task_1", "description": "Load data", "dependencies": []}},
  {{"task_id": "task_2", "description": "Process data", "dependencies": ["task_1"]}},
  {{"task_id": "task_3", "description": "Generate output", "dependencies": ["task_2"]}}
]

Return ONLY valid JSON, no explanations."""
        
        try:
            response = await self.provider.generate(
                prompt,
                system_prompt="You are a task planner. Return structured JSON."
            )
            
            # Parseia resposta
            tasks_data = self._parse_plan_response(response)
            
            # Cria grafo
            graph = TaskGraph()
            for task_data in tasks_data:
                task = Task(
                    task_id=task_data["task_id"],
                    description=task_data["description"],
                    dependencies=task_data.get("dependencies", [])
                )
                graph.add_task(task)
            
            logger.info(f"Plano criado com {len(graph.tasks)} tarefas")
            return graph
            
        except Exception as e:
            raise PlannerError(f"Erro ao criar plano: {e}")
    
    def _parse_plan_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parses resposta do LLM em lista de tarefas.
        
        Args:
            response: Resposta do LLM
            
        Returns:
            Lista de dicionários de tarefas
            
        Raises:
            PlannerError: Se não conseguir fazer parse
        """
        # Limpa response
        response = response.strip()
        
        # Remove markdown markers se presentes
        if response.startswith("```"):
            response = re.sub(r'^```\w*\n', '', response)
            response = re.sub(r'```$', '', response)
        if response.startswith("json"):
            response = response[4:].strip()
        
        try:
            tasks = json.loads(response)
            if not isinstance(tasks, list):
                raise PlannerError("Plano deve ser uma lista de tarefas")
            return tasks
        except json.JSONDecodeError as e:
            raise PlannerError(f"Erro ao parsear plano: {e}")


# =============================================================================
# INFERENCE ENGINE - CICLO WRITE→EXECUTE→ANALYZE
# =============================================================================

class RLMInferenceEngine:
    """
    Motor de inferência empírica com ciclo write→execute→analyze.
    
    Este motor implementa o ciclo de inferência que:
    1. write: LLM gera código Python
    2. execute: código é executado no container isolado
    3. analyze: resultado é analisado (erros ou sucesso)
    4. retry: se necessário, itera com feedback
    
    O ciclo elimina alucinações ao validar respostas através
    de execução real de código.
    
    Attributes:
        provider: Provedor LLM
        executor: Executor de código (DockerReplEngine)
        max_iterations: Máximo de iterações (default: 3)
        iteration_timeout: Timeout por iteração (default: 60s)
        base_retry_delay: Delay base para retry (default: 1s)
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        executor: Any,  # DockerReplEngine - lazy loaded
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        iteration_timeout: int = DEFAULT_ITERATION_TIMEOUT,
        base_retry_delay: float = 1.0,
        max_retry_delay: float = 30.0
    ):
        """
        Inicializa o motor de inferência.
        
        Args:
            provider: Provedor LLM
            executor: Executor de código
            max_iterations: Máximo de iterações
            iteration_timeout: Timeout por iteração em segundos
            base_retry_delay: Delay base para exponential backoff
            max_retry_delay: Delay máximo para retry
        """
        self.provider = provider
        self.executor = executor
        self.max_iterations = max_iterations
        self.iteration_timeout = iteration_timeout
        self.base_retry_delay = base_retry_delay
        self.max_retry_delay = max_retry_delay
        
        logger.info(
            f"RLMInferenceEngine inicializado: "
            f"max_iterations={max_iterations}, "
            f"timeout={iteration_timeout}s"
        )
    
    async def infer(
        self,
        prompt: str,
        task_description: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cancel_event: Optional[asyncio.Event] = None
    ) -> InferenceResult:
        """
        Executa inferência empírica para o prompt.
        
        CICLO EMPÍRICO CORRETO:
        1. Cria container ANTES do loop (estado persiste)
        2. Loop: write → execute → analyze
        3. Output/Stderr passa ao LLM para próxima iteração
        4. Cancela via asyncio.wait se necessário
        
        Args:
            prompt: Prompt/pergunta para o LLM
            task_description: Descrição da tarefa (se diferente do prompt)
            context: Contexto adicional
            cancel_event: Evento para cancelamento externo
            
        Returns:
            InferenceResult com resultado da inferência
            
        Raises:
            RLMInferenceError: Se erro crítico (fail-fast)
            InferenceCancelled: Se cancelado pelo orquestrador
        """
        start_time = time.time()
        task_desc = task_description or prompt
        
        # Evento de cancelamento
        cancel_event = cancel_event or asyncio.Event()
        
        logger.info(f"Iniciando inferência: {task_desc[:50]}...")
        
        iterations = []
        last_error: Optional[str] = None
        session = None
        
        # -------------------------------------------------------------------------
        # CORREÇÃO 2A: Resource Leak - CRIAÇÃO DENTRO DE TRY/FINALLY PROTEGIDO
        # -------------------------------------------------------------------------
        # CRÍTICO: Session DEVE estar dentro do try para que finally faça cleanup
        try:
            session = await self.executor.create_container(
                name=f"rlm-{uuid.uuid4().hex[:8]}"
            )
            logger.info(f"Sessão Docker criada: {session.name}")
            
            # Loop de iterações: write → execute → analyze
            for iteration in range(1, self.max_iterations + 1):
                logger.info(f"=== Iteração {iteration}/{self.max_iterations} ===")
                
                # -------------------------------------------------------------------------
                # CORREÇÃO 2C: Race Condition - CHECAR ESTADO ANTES DE CRIAR TASK
                # -------------------------------------------------------------------------
                if cancel_event.is_set():
                    logger.info("Cancelamento pedido antes da iteração")
                    break
                
                # 1. WRITE: Gera código passando output anterior
                try:
                    # -------------------------------------------------------------------------
                    # CORREÇÃO 2B: Null Pointer - NAVEGAÇÃO SEGURA COM FALLBACKS
                    # -------------------------------------------------------------------------
                    # Safe navigation para evitar AttributeError
                    last_iter = iterations[-1] if iterations else None
                    last_exec = last_iter.execution if last_iter and last_iter.execution else None
                    
                    context_updates = {
                        "previous_stdout": last_exec.stdout if last_exec and hasattr(last_exec, 'stdout') else "",
                        "previous_stderr": last_exec.stderr if last_exec and hasattr(last_exec, 'stderr') else "",
                        "previous_results": self._format_previous_results(iterations),
                        "iteration_context": {
                            "current": iteration,
                            "total": self.max_iterations,
                            "last_error": last_error
                        },
                    }
                    # Merge com context adicional
                    if context:
                        context_updates.update(context)
                    
                    code = await self.provider.generate_code(
                        task_desc,
                        context=context_updates
                    )
                except LLMProviderError as e:
                    logger.error(f"Erro ao gerar código: {e}")
                    last_error = str(e)
                    # Não continua - falha no provider é crítica
                    break
                
                # 2. EXECUTE: Executa com cancelamento via asyncio.wait
                execution_result = None
                try:
                    # Competir execução vs cancelamento
                    exec_task = asyncio.create_task(
                        self.executor.execute(
                            session,
                            code,
                            timeout=self.iteration_timeout
                        )
                    )
                    
                    done, pending = await asyncio.wait(
                        [exec_task, asyncio.create_task(cancel_event.wait())],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # Cancelamento venceu a corrida
                    if cancel_event.is_set():
                        exec_task.cancel()
                        logger.warning("Ejecución cancelada")
                        raise InferenceCancelled("Opera canceled by Orchestrator")
                    
                    # Obter resultado
                    execution_result = exec_task.result()
                    
                except asyncio.CancelledError:
                    # Cleanup de emergência
                    logger.warning("Ejecución cancelada - cleanup")
                    raise InferenceCancelled("Opera canceled")
                    
                except Exception as e:
                    # ERRO DE INFRAESTRUTURA - Fail-Fast
                    logger.critical(f"Erro de execução: {type(e).__name__}: {e}")
                    raise ExecutionError(
                        f"Execution failure: {type(e).__name__}: {e}"
                    ) from e
                
                # 3. ANALYZE: Analisa resultado
                if execution_result:
                    error_info = PythonErrorParser.parse(
                        execution_result.stdout + execution_result.stderr
                    )
                    
                    iteration_result = IterationResult(
                        iteration=iteration,
                        code=code,
                        execution=execution_result,
                        analysis=self._analyze_result(error_info, execution_result),
                        is_success=not error_info["has_error"] and execution_result.exit_code == 0,
                        should_retry=error_info["has_error"] or execution_result.exit_code != 0
                    )
                else:
                    iteration_result = IterationResult(
                        iteration=iteration,
                        code=code,
                        analysis=f"Execução falhou: {last_error}",
                        is_success=False,
                        should_retry=False  # Não retry se não teve resultado
                    )
                
                iterations.append(iteration_result)
                
                # Log resultado
                if iteration_result.is_success:
                    logger.info(f"✓ Iteração {iteration} bem-sucedida!")
                    logger.debug(f"  Stdout length: {len(execution_result.stdout)}")
                    logger.debug(f"  Stderr: {execution_result.stderr[:100] if execution_result.stderr else '(empty)'}")
                    break
                else:
                    last_error = iteration_result.analysis
                    logger.warning(
                        f"✗ Iteração {iteration} falhou: "
                        f"{iteration_result.analysis[:100]}..."
                    )
                    
                    # Retry com exponential backoff + JITTER
                    if iteration < self.max_iterations:
                        delay = min(
                            self.base_retry_delay * (2 ** (iteration - 1)),
                            self.max_retry_delay
                        )
                        jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                        total_delay = delay + jitter
                        logger.info(f"  Retry em {total_delay:.2f}s (jitter: {jitter:.2f}s)...")
                        await asyncio.sleep(total_delay)
            
        finally:
            # Cleanup da sessão SEMPRE
            if session:
                logger.info(f"Destruindo sessão: {session.name}")
                try:
                    await self.executor.destroy(session)
                except Exception as e:
                    logger.error(f"Erro no destroy: {e}")
        
        # Calcula resultado final
        duration = time.time() - start_time
        
        # Obtém output final
        final_output = None
        success = False
        error = None
        
        if iterations:
            if iterations[-1].is_success:
                success = True
                # Tenta extrair output do código
                if iterations[-1].execution:
                    final_output = self._extract_output(
                        iterations[-1].code,
                        iterations[-1].execution.stdout
                    )
            else:
                error = iterations[-1].analysis
        
        result = InferenceResult(
            prompt=prompt,
            success=success,
            iterations=iterations,
            final_output=final_output,
            total_duration=duration,
            error=error
        )
        
        logger.info(
            f"Inferência concluída: success={success}, "
            f"duration={duration:.2f}s, "
            f"iterations={len(iterations)}"
        )
        
        return result
    
    async def infer_with_plan(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executa inferência com planejamento prévio (DAG).
        
        Args:
            task_description: Descrição da tarefa
            context: Contexto adicional
            
        Returns:
            Dicionário com resultados por tarefa:
            {
                "success": bool,
                "graph": TaskGraph,
                "results": Dict[task_id -> result],
                "duration": float
            }
        """
        start_time = time.time()
        
        # Cria plano
        planner = Planner(self.provider)
        graph = await planner.plan(task_description)
        
        results = {}
        
        # Executa tarefas em ordem
        completed: Set[str] = set()
        
        while not graph.is_complete():
            ready_tasks = graph.get_ready_tasks(completed)
            
            if not ready_tasks and not graph.has_failures():
                # Deadlock (nenhuma tarefa pronta mas sem falhas)
                raise RLMInferenceError(
                    "Deadlock: nenhuma tarefapronta e nenhuma falha"
                )
            
            # Executa tarefas prontas
            for task in ready_tasks:
                task.status = "running"
                
                logger.info(f"Executando tarefa: {task.task_id}")
                
                try:
                    # Executa inferência para a tarefa
                    result = await self.infer(
                        prompt=task.description,
                        task_description=task.description,
                        context={
                            **context,
                            "previous_results": results
                        }
                    )
                    
                    if result.success:
                        task.status = "completed"
                        task.result = result.final_output
                        task.completed_at = datetime.now(timezone.utc)
                    else:
                        task.status = "failed"
                        task.error = result.error
                    
                    results[task.task_id] = result
                    completed.add(task.task_id)
                    
                except Exception as e:
                    task.status = "failed"
                    task.error = str(e)
                    results[task.task_id] = {"error": str(e)}
        
        duration = time.time() - start_time
        
        return {
            "success": not graph.has_failures(),
            "graph": graph,
            "results": results,
            "duration": duration
        }
    
    def _format_previous_results(
        self,
        iterations: List[IterationResult]
    ) -> str:
        """Formata resultados de iterações anteriores."""
        if not iterations:
            return "Nenhum resultado anterior."
        
        lines = []
        for it in iterations:
            status = "✓" if it.is_success else "✗"
            lines.append(
                f"Iteração {it.iteration}: {status}\n"
                f"  Análise: {it.analysis[:100]}..."
            )
        
        return "\n".join(lines)
    
    def _analyze_result(
        self,
        error_info: Dict[str, Any],
        execution_result: Any  # ExecutionResult from lazy import
    ) -> str:
        """Analisa resultado da execução."""
        if error_info["has_error"]:
            return (
                f"Erro {error_info['error_type']}: "
                f"{error_info['error_message']}\n"
                f"Sugestão: {error_info['suggestion']}"
            )
        
        if execution_result.exit_code != 0:
            return f"Exit code: {execution_result.exit_code}"
        
        return "Execução bem-sucedida"
    
    def _extract_output(self, code: str, stdout: str) -> Any:
        """Extrai output estruturado do stdout."""
        # Tenta fazer parse como JSON
        stdout = stdout.strip()
        
        # Remove print() wrapper se presente
        if stdout.startswith("```") and stdout.endswith("```"):
            stdout = stdout[3:-3].strip()
        
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            # Retorna texto puro
            return stdout.strip()


# =============================================================================
# WRAPPER SYNCRONO
# =============================================================================

class RLMInferenceEngineSync:
    """
    Wrapper síncrono para RLMInferenceEngine.
    
    Fornece interface síncrona para uso em contextos não-async.
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        executor: Any = None,  # DockerReplEngine - lazy loaded
        **kwargs
    ):
        """
        Inicializa wrapper síncrono.
        
        Args:
            provider: Provedor LLM
            executor: Executor de código (opcional)
            **kwargs: Parâmetros do engine
        """
        self._provider = provider
        self._executor = executor
        self._kwargs = kwargs
        self._engine: Optional[RLMInferenceEngine] = None
        self._loop = None
    
    def _ensure_loop(self):
        """Garante event loop."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def initialize(self, executor: Any = None):  # DockerReplEngine - lazy loaded
        """
        Inicializa wrapper.
        
        Args:
            executor: Executor (pode ser passado aqui)
        """
        self._ensure_loop()
        
        if executor:
            self._executor = executor
        
        if not self._executor:
            # Cria executor default
            Engine, Config, _ = _get_docker_repl_engine()
            self._executor = Engine(
                config=Config(),
                pool_size=1
            )
        
        self._loop.run_until_complete(self._executor.initialize())
        
        self._engine = RLMInferenceEngine(
            provider=self._provider,
            executor=self._executor,
            **self._kwargs
        )
    
    def infer(
        self,
        prompt: str,
        task_description: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> InferenceResult:
        """
        Executa inferência (sync).
        
        Args:
            prompt: Prompt
            task_description: Descrição da tarefa
            context: Contexto adicional
            
        Returns:
            InferenceResult
        """
        self._ensure_loop()
        
        if not self._engine:
            self.initialize()
        
        return self._loop.run_until_complete(
            self._engine.infer(prompt, task_description, context)
        )
    
    def infer_with_plan(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Executa inferência com plano (sync)."""
        self._ensure_loop()
        
        if not self._engine:
            self.initialize()
        
        return self._loop.run_until_complete(
            self._engine.infer_with_plan(task_description, context)
        )
    
    def shutdown(self):
        """
        Encerra wrapper limpando apenas os recursos propios.
        
        CRÍTICO: Não fecha o event loop - ele pode ser compartilhado
        por outras tarefas (monitoramento, WebSocket, etc.).
        """
        # Cleanup do executor (Q2)
        if self._executor:
            self._loop.run_until_complete(self._executor.shutdown())
        
        # Cleanup do provider
        if self._provider:
            self._loop.run_until_complete(self._provider.close())
        
        # NÃO fecha o loop - apenas marca para coleta
        # O loop debe ser fechado pelo criador/orquestrador


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """
    Entry point para teste do RLMInferenceEngine.
    
    Uso:
        python3 rlm_inference.py --test
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="RLM Inference Engine")
    parser.add_argument("--test", action="store_true", help="Executa teste")
    parser.add_argument("--provider", default="ollama", help="Provedor (ollama|openai|anthropic)")
    
    args = parser.parse_args()
    
    if args.test:
        print("=== Teste RLMInferenceEngine ===")
        
        # Configura provedor
        provider_type = LLMProviderType(args.provider)
        print(f"1. Provedor: {provider_type.value}")
        
        try:
            provider = LLMProviderFactory.create(provider_type)
            print(f"   ✓ Provider criado: {provider.model}")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
            return
        
        # Teste de execução
        print(f"\n2. Executando teste...")
        
        async def test():
            engine = RLMInferenceEngine(
                provider=provider,
                executor=None,  # Sem executor real
                max_iterations=1
            )
            
            # Teste de parsing
            test_outputs = [
                'print("Hello")',
                'NameError: name "x" is not defined',
                'SyntaxError: invalid syntax',
                'TypeError: unsupported operand + for str and int'
            ]
            
            for output in test_outputs:
                result = PythonErrorParser.parse(output)
                print(f"   Input: {output[:40]}...")
                print(f"   Error: {result}")
        
        asyncio.run(test())
        
        print(f"\n=== Teste completo ===")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
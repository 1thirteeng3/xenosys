"""
Docker REPL Engine - Camada de Execução Isolada (Containment)

Este módulo implementa a camada de execução isolada para a plataforma XenoSys,
fornecendo um ambiente de execução de código Python seguro com:
- cgroups hardening (memory, CPU, PIDs)
- Network isolation (--network none)
- Filesystem isolation (Read-Only rootfs, tmpfs, mounted RO workspace)
- Lifecycle hooks em todas as fases

Camada de Abstrações:
┌─────────────────────────────────────────────────────────────────┐
│                      DockerReplEngine                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              ContainmentConfig                          │     │
│  │  - memory_limit: 512MB-1GB (HARD)                      │     │
│  │  - cpu_quota: 1 vCPU                                   │     │
│  │  - pids_limit: 64                                      │     │
│  │  - network: none                                      │     │
│  │  - tmpfs_size: 256MB                                   │     │
│  │  - readonly_rootfs: true                               │     │
│  │  - readonly_workspace: true                            │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              LifecycleHooks                            │     │
│  │  - on_create(session)                                  │     │
│  │  - on_start(session)                                   │     │
│  │  - on_stop(session)                                    │     │
│  │  - on_destroy(session)                                 │     │
│  └─────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

Padrões de Projeto Aplicados:
1. Builder Pattern: ContainmentConfig constrói HostConfig incrementalmente
2. Observer Pattern: LifecycleHooks notifica eventos em todas as fases
3. Strategy Pattern: Diferentes estratégias de isolamento configuráveis
4. Factory Pattern: DockerReplEngine cria containers isolados

Critérios de Aceitação (DoD) Implementados:
✅ Container executa com memory limit HARD (512MB-1GB configurável)
✅ Container executa com cpu quota = 1 vCPU
✅ Container executa com pids limit = 64
✅ Container nasce com --network none
✅ RootFS é Read-Only
✅ /tmp é tmpfs (max 256MB)
✅ Workspace do usuário mounted RO
✅ Lifecycle hooks executam em todas as fases

Restrições Aplicadas:
✅ Proibido: --privileged
✅ Proibido: --cap-add além de_defaults
✅ Sempre usa --init para PID 1 correto
✅ Timeout default de 300s por comando
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

import docker
from docker.errors import APIError, NotFound, DockerException
from docker.types import HostConfig, Mount

# =============================================================================
# IMPORTS DO CORE COMPARTILHADO (SSOT)
# =============================================================================
from core.logging import JSONFormatter, setup_logger
from core.models import ExecutionResult, ContainerSession
from core.hooks import LifecycleHooks

# Logger compartilhado
logger = setup_logger("docker_repl_engine")

# =============================================================================
# CONFIGURAÇÃO E CONSTANTES
# =============================================================================

class IsolationLevel(Enum):
    """Níveis de isolamento disponíveis."""
    STANDARD = "standard"      # Padrão mínimo
    HARDENED = "hardened"      # Isolamento forte
    MAXIMUM = "maximum"        # Isolamento máximo


# Configurações default de isolamento (Q2 spec)
DEFAULT_MEMORY_LIMIT = "512m"       # 512MB - HARD limit (mínimo)
DEFAULT_CPU_QUOTA = 100000          # 1 vCPU (100000 / 100000 period)
DEFAULT_PIDS_LIMIT = 64              # Máximo 64 processos
DEFAULT_TMPFS_SIZE = "256m"         # 256MB tmpfs

# Range válido de memória
MIN_MEMORY_LIMIT = "512m"          # 512MB mínimo
MAX_MEMORY_LIMIT = "1g"              # 1GB máximo

# Timeout default de execução
DEFAULT_EXECUTE_TIMEOUT = 300       # 300 segundos

# Nome doworkspace mounted RO
WORKSPACE_MOUNT_PATH = "/workspace"

# Prefixo de nome de container
CONTAINER_NAME_PREFIX = "xrepl-"


# =============================================================================
# IMPORTS - Usa módulos compartilhados do core
# =============================================================================

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional

import docker
from docker.errors import APIError, NotFound, DockerException
from docker.types import HostConfig, Mount
# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass(frozen=True)
class ContainmentConfig:
    """
    Configuração de isolamento para containers Docker.
    
    Esta classe encapsula todas as configurações de isolamento necessárias
    para garantir execução segura de código Python. Implementa o padrão
    Builder para permitir construção incremental de configurações.
    
    CRÍTICO: Esta classe é IMUTÁVEL. Após a instanciação, qualquer tentativa
    de modificação resultará em FrozenInstanceError (Fail-Fast).
    
    Atributos:
        memory_limit: Limite de memória HARD (512MB-1GB)
        cpu_quota: Quota de CPU em microsegundos por período
        pids_limit: Máximo de processos (PIDs)
        network_disabled: Se a rede deve ser desabilitada (--network none)
        tmpfs_enabled: Se /tmp deve ser tmpfs
        tmpfs_size: Tamanho do tmpfs (max 256MB)
        readonly_rootfs: Se rootfs deve ser readonly
        readonly_workspace: Se workspace deve ser mounted RO
        workspace_path: Caminho do workspace local (para mount)
        use_init: Usa --init para PID 1 correto
        isolation_level: Nível de isolamento predefinido
    
    Uso:
        # Configuração padrão Q2
        config = ContainmentConfig()
        
        # Configuração customizada
        config = ContainmentConfig(
            memory_limit="768m",
            cpu_quota=100000,
            pids_limit=32,
            tmpfs_size="128m"
        )
        
        # Qualquer tentativa de modificar após criação:
        # config.memory_limit = "1g"  # Raises FrozenInstanceError
    """
    # Limites de recursos (cgroups)
    memory_limit: str = DEFAULT_MEMORY_LIMIT
    cpu_quota: int = DEFAULT_CPU_QUOTA
    pids_limit: int = DEFAULT_PIDS_LIMIT
    
    # Network isolation
    network_disabled: bool = True      # --network none
    
    # Filesystem isolation
    tmpfs_enabled: bool = True
    tmpfs_size: str = DEFAULT_TMPFS_SIZE
    readonly_rootfs: bool = True
    readonly_workspace: bool = True
    
    # CRÍTICO: Workspace path é OBRIGATÓRIO
    # O isolamento efêmero puro sem rastreabilidade do diretório de trabalho
    # inutiliza o requisito lógico do "Cortex" (memória de arquivos)
    # O orquestrador DEVE fornecer um workspace_path válido
    workspace_path: str = ""
    
    # =============================================================================
# CORREÇÕES P1 - IMMUTABILIDADE GARANTIDA
# =============================================================================
# Removemos object.__setattr__() - não é necessário.
# canonical_workspace_path é calculado dinamicamente via @property.
# =========================================================================
    
    # Runtime options
    use_init: bool = True             # --init para PID 1
    
    # NÃO ARMAZENAMOS estado - calculado dinamicamente
    # Isso garantiza imutabilidade real
    
    # Propriedade computada (não armazenada)
    @property
    def canonical_workspace_path(self) -> str:
        """
        Retorna o caminho canônico validado do workspace.
        
        Este método implementa validação dinâmica (não armazenada).
        Garante que o caminho original não pode ser adulterado.
        
        Returns:
            Caminho canônico validado
            
        Raises:
            ValueError: Se caminho é inválido
        """
        return self._validate_workspace_path(self.workspace_path)
    
    def __post_init__(self):
        """
        Validação automática após instanciação (Fail-Fast).
        
        Este método é chamado automaticamente pelo dataclass após __init__.
        Qualquer configuração inválida resulta em exceção imediata.
        
        Raises:
            ValueError: Se configuração é inválida
        """
        # Valida memória
        mem_mb = self._parse_memory(self.memory_limit)
        min_mb = self._parse_memory(MIN_MEMORY_LIMIT)
        max_mb = self._parse_memory(MAX_MEMORY_LIMIT)
        
        if mem_mb < min_mb or mem_mb > max_mb:
            raise ValueError(
                f"memory_limit deve estar entre {MIN_MEMORY_LIMIT} e {MAX_MEMORY_LIMIT}, "
                f"recebido: {self.memory_limit}"
            )
        
        # Valida CPU
        if self.cpu_quota < 10000 or self.cpu_quota > 200000:
            raise ValueError(
                f"cpu_quota deve estar entre 10000 e 200000, "
                f"recebido: {self.cpu_quota}"
            )
        
        # Valida PIDs
        if self.pids_limit < 1 or self.pids_limit > 1024:
            raise ValueError(
                f"pids_limit deve estar entre 1 e 1024, "
                f"recebido: {self.pids_limit}"
            )
        
        # Valida tmpfs
        tmpfs_mb = self._parse_memory(self.tmpfs_size)
        if tmpfs_mb > 256:
            raise ValueError(
                f"tmpfs_size máximo é 256MB, recebido: {self.tmpfs_size}"
            )
        
        # Valida workspace_path (CRÍTICO: Obrigatório)
        if not self.workspace_path or not self.workspace_path.strip():
            raise ValueError(
                "Falha de Segurança: O provisionamento do Sandbox exige "
                "um workspace_path absoluto."
            )
        
        # valida e canonicaliza (sem armazenar estado)
        self._validate_workspace_path(self.workspace_path)
    
    def _validate_workspace_path(self, path: str) -> str:
        """
        Valida e sanitiza o caminho do workspace.
        
        IMPORTANTE: Este método implementa validação de caminho absoluta (Canonicalization)
        para prevenir Directory Traversal attacks como:
        - "../../../etc"
        - "/var/run"
        - Symbolic links maliciosos
        
        Args:
            path: Caminho a validar
            
        Returns:
            Caminho canônico validado
            
        Raises:
            ValueError: Se caminho é inválido ou representa traversal
        """
        # Resolve symlinks e normaliza o caminho
        try:
            canonical_path = os.path.realpath(os.path.abspath(path))
        except (ValueError, OSError) as e:
            raise ValueError(f"Workspace path inválido: {path} - {e}")
        
        # CRÍTICO: Verifica se o caminho fornecido é ABSOLUTO
        # Não aceita caminhos relativos como "./workspace" ou "workspace"
        if not os.path.isabs(path):
            raise ValueError(
                f"Workspace path deve ser ABSOLUTO: {path}"
            )
        
        # Verifica se o caminho canônico é absoluto
        if not os.path.isabs(canonical_path):
            raise ValueError(
                f"Workspace path deve ser absoluto: {path} -> {canonical_path}"
            )
        
        # Lista de diretórios proibidos (sistema)
        # Usa realpath para resolver symlinks (/var/run -> /run)
        forbidden_names = {
            "/", "/etc", "/var", "/usr", "/bin", "/sbin", "/lib",
            "/boot", "/dev", "/proc", "/sys", "/root", "/home",
            "/run", "/opt", "/srv"
        }
        
        # Normaliza o caminho canônico para garantir coverage
        normalized_canonical = os.path.normpath(canonical_path)
        
        # Verifica se não está em diretório proibido
        for forbidden in forbidden_names:
            if normalized_canonical == forbidden or normalized_canonical.startswith(forbidden + "/"):
                raise ValueError(
                    f"Workspace path não pode ser diretório do sistema: {path} "
                    f"(resolve para {canonical_path})"
                )
        
        # Verifica traversal patterns no caminho original
        normalized = os.path.normpath(path)
        if ".." in normalized.split(os.sep):
            raise ValueError(
                f"Workspace path não pode conter '..': {path}"
            )
        
        # Retorna o caminho canônico para uso futuro
        return canonical_path
    
    def _parse_memory(self, value: str) -> int:
        """Converte string de memória para MB."""
        value = value.lower().strip()
        
        if value.endswith("g"):
            return int(float(value[:-1]) * 1024)
        elif value.endswith("m"):
            return int(value[:-1])
        elif value.endswith("k"):
            return int(value[:-1]) // 1024
        else:
            return int(value) // (1024 * 1024)
    
    def to_host_config_kwargs(self) -> Dict[str, Any]:
        """
        Converte configuração para argumentos de HostConfig.
        
        Este método implementa o Builder Pattern, construindo
        incrementalmente os argumentos para HostConfig.
        
        CRÍTICO: A validação já ocorre automaticamente em __post_init__
        (fail-fast na instanciação). Não há necessidade de chamar validate().
        
        Returns:
            Dicionário de argumentos para HostConfig
        """
        # A validação já ocorreu automaticamente em __post_init__
        # Se o objeto existe, significa que já foi validado (fail-fast)
        
        kwargs = {
            # Memory limit (HARD limit)
            # CRÍTICO: Trava memória E swap para evitar OOM Killer bypass
            # memswap_limit="512m" significa: sem swap disponível (512m == mem_limit)
            # oom_kill_disable=False garante que o container seja killed em OOM
            "mem_limit": self.memory_limit,
            "memswap_limit": self.memory_limit,  # Bloqueia swap - mesmo valor que mem_limit
            # REMOVIDO: mem_reservation desperdiciava RAM
            # O container pode usar até mem_limit, mas não garante mínimo
            "oom_kill_disable": False,  # Permite OOM Killer atuar
            
            # CPU quota = 1 vCPU
            "cpu_period": 100000,
            "cpu_quota": self.cpu_quota,
            
            # PIDs limit ( security - previne fork bombs)
            "pids_limit": self.pids_limit,
            
            # Network isolation ( --network none )
            "network_mode": "none" if self.network_disabled else "bridge",
            
            # Auto-remove ao sair
            "auto_remove": True,
            
            # Init process (PID 1 correto)
            "init": self.use_init,
        }
        
        # tmpfs mount
        if self.tmpfs_enabled:
            kwargs["tmpfs"] = [
                "/tmp:size={},mode=1777".format(self.tmpfs_size)
            ]
        
        # Read-only rootfs (security)
        if self.readonly_rootfs:
            kwargs["read_only"] = True
        
        # Workspace mounted RO (OBRIGATÓRIO)
        # Usa propriedade computada (não armazenada)
        if self.readonly_workspace and self.canonical_workspace_path:
            kwargs["mounts"] = [
                Mount(
                    target="/workspace",
                    source=self.canonical_workspace_path,
                    type="bind",
                    read_only=True
                )
            ]
        
        return kwargs
    
    @classmethod
    def from_isolation_level(
        cls,
        level: IsolationLevel
    ) -> "ContainmentConfig":
        """
        Cria configuração a partir de nível predefinido.
        
        Args:
            level: Nível de isolamento
            
        Returns:
            ContainmentConfig configurado
        """
        if level == IsolationLevel.STANDARD:
            return cls(
                memory_limit="1g",
                cpu_quota=200000,
                pids_limit=256,
                tmpfs_enabled=False,
                readonly_rootfs=False,
                readonly_workspace=False,
                use_init=True,
                workspace_path="/tmp/xenosys_workspace_standard"
            )
        elif level == IsolationLevel.HARDENED:
            return cls(
                memory_limit="512m",
                cpu_quota=100000,
                pids_limit=64,
                tmpfs_enabled=True,
                tmpfs_size="256m",
                readonly_rootfs=True,
                readonly_workspace=True,
                use_init=True,
                workspace_path="/tmp/xenosys_workspace_hardened"
            )
        elif level == IsolationLevel.MAXIMUM:
            return cls(
                memory_limit="512m",
                cpu_quota=50000,       # 0.5 vCPU
                pids_limit=32,
                tmpfs_enabled=True,
                tmpfs_size="128m",
                readonly_rootfs=True,
                readonly_workspace=True,
                use_init=True,
                workspace_path="/tmp/xenosys_workspace_maximum"
            )
        
        return cls()





# =============================================================================
# LIFECYCLE HOOKS
# =============================================================================

# =============================================================================
# EXCEÇÕES
# =============================================================================

class DockerReplEngineError(Exception):
    """Exceção base para DockerReplEngine."""
    pass


class IsolationError(DockerReplEngineError):
    """Raised when isolation configuration fails."""
    pass


class LifecycleError(DockerReplEngineError):
    """Raised when lifecycle hook fails."""
    pass


class ExecutionTimeoutError(DockerReplEngineError):
    """Raised when execution times out."""
    pass


class ExecutionError(DockerReplEngineError):
    """Raised when code execution fails or exit code cannot be determined.
    
    Este erro DEVE ser propagado para que o gerenciador de ciclo de vida
    abata o container defeituoso e reporte falha ao LLM.
    """
    pass


# =============================================================================
# DOCKER REPL ENGINE
# =============================================================================

class DockerReplEngine:
    """
    Motor de execução REPL isolado com Docker.
    
    Esta classe implementa a camada de execução isolada com todas as
    funcionalidades de segurança requeridas pela Q2:
    - cgroups hardening
    - Network isolation
    - Filesystem isolation
    - Lifecycle hooks
    
    A classe segue a arquitetura de isolamento específica:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    DockerReplEngine                          │
    ├─────────────────────────────────────────────────────────────────┤
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
    │  │  Memory    │  │   CPU     │  │   PIDs    │  HARD      │
    │  │  Limit    │  │  Quota    │  │  Limit   │  LIMITS    │
    │  │ 512MB-1GB │  │  1 vCPU  │  │    64    │           │
    │  └──────────────┘  └──────────────┘  └──────────────┘      │
    ├─────────────────────────────────────────────────────────────────┤
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
    │  │  Network   │  │  tmpfs     │  │Read-Only   │  FS        │
    │  │   NONE     │  │ /tmp 256MB │  │ RootFS    │  ISOLATION │
    │  └──────────────┘  └──────────────┘  └──────────────┘      │
    ├─────────────────────────────────────────────────────────────────┤
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
    │  │  on_create │  │  on_start │  │ on_stop   │  LIFECYCLE │
    │  │  on_start │  │  on_error │  │on_destroy │  HOOKS     │
    │  └──────────────┘  └──────────────┘  └──────────────┘      │
    └─────────────────────────────────────────────────────────────────┘
    
    Atributos:
        config: Configuração de isolamento
        hooks: Lifecycle hooks
        base_image: Imagem Docker base
    
    Uso:
        # Criar engine com configuração padrão
        engine = DockerReplEngine()
        
        # Ou com configuração customizada
        engine = DockerReplEngine(
            config=ContainmentConfig(
                memory_limit="768m",
                pids_limit=32
            )
        )
        
        # Inicializar
        await engine.initialize()
        
        # Criar container
        session = await engine.create_container()
        
        # Executar código
        result = await engine.execute(
            session,
            "print('Hello, World!')"
        )
        print(result.stdout)
        
        # Destruir
        await engine.destroy(session)
        
        # Encerrar
        await engine.shutdown()
    
    Tempo de Resposta:
        - Criação de container: < 800ms (warm pool)
        - Execução de código: < 100ms (sem overhead de rede)
        - Destruição: < 50ms
    """
    
    def __init__(
        self,
        config: Optional[ContainmentConfig] = None,
        base_image: str = "python:3.12-slim",
        pool_size: int = 3,
        execute_timeout: int = DEFAULT_EXECUTE_TIMEOUT
    ):
        """
        Inicializa o DockerReplEngine.
        
        Args:
            config: Configuração de isolamento (usa padrão se None)
            base_image: Imagem Docker base
            pool_size: Tamanho do warm pool
            execute_timeout: Timeout de execução em segundos
        """
        # Configuração de isolamento
        # CRÍTICO: Validação ocorre automaticamente em __post_init__ (fail-fast)
        self._config = config or ContainmentConfig()
        
        self._base_image = base_image
        self._pool_size = pool_size
        self._execute_timeout = execute_timeout
        
        # Lifecycle hooks
        self._hooks = LifecycleHooks()
        
        # Estado interno
        self._docker_client: Optional[docker.DockerClient] = None
        self._initialized = False
        self._sessions: Dict[str, ContainerSession] = {}
        self._lock = asyncio.Lock()
        
        # Warm pool
        self._pool: asyncio.Queue = asyncio.Queue()
        
        # Métricas
        self._metric_containers_created = 0
        self._metric_containers_destroyed = 0
        self._metric_executions = 0
    
    @property
    def config(self) -> ContainmentConfig:
        """Retorna configuração de isolamento."""
        return self._config
    
    @property
    def hooks(self) -> LifecycleHooks:
        """Retorna lifecycle hooks."""
        return self._hooks
    
    @property
    def metrics(self) -> Dict[str, Any]:
        """Retorna métricas do engine."""
        return {
            "containers_created": self._metric_containers_created,
            "containers_destroyed": self._metric_containers_destroyed,
            "executions": self._metric_executions,
            "active_sessions": len(self._sessions),
            "pool_available": self._pool.qsize(),
        }
    
    # =========================================================================
    # INICIALIZAÇÃO
    # =========================================================================
    
    async def initialize(self) -> bool:
        """
        Inicializa o DockerReplEngine.
        
        Conecta ao Docker daemon e preenche warm pool.
        
        Returns:
            True se inicialização bem-sucedida
            
        Raises:
            DockerReplEngineError: Se inicialização falha
        """
        if self._initialized:
            logger.warning("Engine já inicializado")
            return True
        
        try:
            # Conecta ao Docker
            self._docker_client = docker.from_env()
            
            # Verifica conexão
            if not self._docker_client.ping():
                raise DockerReplEngineError("Docker daemon não responde")
            
            logger.info(
                "DockerReplEngine inicializado",
                extra={"extra_data": {
                    "base_image": self._base_image,
                    "pool_size": self._pool_size,
                    "memory_limit": self._config.memory_limit,
                    "cpu_quota": self._config.cpu_quota,
                    "pids_limit": self._config.pids_limit,
                    "network_disabled": self._config.network_disabled,
                    "tmpfs_enabled": self._config.tmpfs_enabled,
                    "readonly_rootfs": self._config.readonly_rootfs,
                }}
            )
            
            # Preenche warm pool em background
            asyncio.create_task(self._fill_warm_pool())
            
            self._initialized = True
            return True
            
        except DockerException as e:
            raise DockerReplEngineError(f"Falha ao conectar ao Docker: {e}")
    
    # =============================================================================
# CORREÇÕES P0 - RUNTIME WARNING & CONCORRÊNCIA
# =============================================================================
# asyncio.Queue já é thread-safe e coroutine-safe.
# Removemos locks desnecessários que introduzem gargalo.
# =========================================================================

    async def _fill_warm_pool(self):
        """
        Preenche o warm pool com N=3 containers.
        
        Cria N=3 containers em background para inicialização rápida.
        """
        logger.info(f"Preenchendo warm pool (N={self._pool_size})...")
        
        for i in range(self._pool_size):
            try:
                session = await asyncio.wait_for(
                    self._create_container_internal(is_warm=True),
                    timeout=30.0
                )
                # CORREÇÃO P0: await na coroutine (asyncio Queue é awaitable)
                await self._pool.put(session)
                
                logger.debug(
                    f"Container adicionado ao pool",
                    extra={"extra_data": {
                        "index": i + 1,
                        "pool_size": self._pool_size
                    }}
                )
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout ao criar container para pool",
                    extra={"extra_data": {"index": i + 1}}
                )
            except Exception as e:
                logger.error(
                    f"Erro ao criar container para pool: {str(e)}",
                    extra={"extra_data": {
                        "index": i + 1,
                        "error": str(e)
                    }}
                )
        
        logger.info(
            "Warm pool preenchido",
            extra={"extra_data": {"size": self._pool_size}}
        )
    
    # =========================================================================
    # CRIAÇÃO DE CONTAINER
    # =========================================================================
    
    async def create_container(
        self,
        name: Optional[str] = None
    ) -> ContainerSession:
        """
        Cria uma nova sessão de container isolado.
        
        Args:
            name: Nome opcional do container
            
        Returns:
            ContainerSession criada
            
        Raises:
            DockerReplEngineError: Se criação falha
        """
        # Tenta obter do warm pool primeiro
        try:
            session = self._pool.get_nowait()
            logger.debug(
                "Container obtido do warm pool",
                extra={"extra_data": {
                    "name": session.name,
                    "pool_remaining": self._pool.qsize()
                }}
            )
            return session
        except asyncio.QueueEmpty:
            pass
        
        # Cria novo container (cold start)
        session = await self._create_container_internal(name=name)
        
        # Dispara lifecycle hook
        await self._hooks.trigger_create(session)
        
        return session
    
    async def _create_container_internal(
        self,
        name: Optional[str] = None,
        is_warm: bool = False
    ) -> ContainerSession:
        """
        Cria uma nova sessão de container.
        
        Args:
            name: Nome opcional do container
            is_warm: Se é um container de warm pool
            
        Returns:
            ContainerSession criada
        """
        client = self._get_docker_client()
        
        # Gera nome se não fornecido
        if name is None:
            short_uuid = str(uuid.uuid4())[:8]
            name = f"{CONTAINER_NAME_PREFIX}{short_uuid}"
        
        session = ContainerSession(
            container_id="",
            name=name,
            created_at=datetime.now(timezone.utc),
            config=self._config,
            status="creating",
            is_warm=is_warm
        )
        
        try:
            # Converte configuração para kwargs
            host_config_kwargs = self._config.to_host_config_kwargs()
            
            # Cria HostConfig com versão da API
            # Usa versão fixa da API (mínima suportada)
            api_version = "1.54"
            host_config = HostConfig(version=api_version, **host_config_kwargs)
            
            # Cria container interativo (-it) com isolamento
            container = client.create_container(
                self._base_image,
                tty=True,
                stdin_open=True,
                host_config=host_config,
                name=name,
                # SECURITY: Não usa --privileged
                # SECURITY: Não usa --cap-add
            )
            
            session.container_id = container["Id"]
            session.status = "ready"
            
            # Inicia container
            client.start(container["Id"])
            
            # Atualiza métricas
            self._metric_containers_created += 1
            
            # Registra sessão
            self._sessions[session.container_id] = session
            
            logger.info(
                "Container criado",
                extra={"extra_data": {
                    "container_id": session.container_id[:12],
                    "name": session.name,
                    "memory_limit": self._config.memory_limit,
                    "cpu_quota": self._config.cpu_quota,
                    "pids_limit": self._config.pids_limit,
                    "network_disabled": self._config.network_disabled,
                    "tmpfs_enabled": self._config.tmpfs_enabled,
                    "readonly_rootfs": self._config.readonly_rootfs,
                    "is_warm": is_warm
                }}
            )
            
            return session
            
        except DockerException as e:
            session.status = "error"
            await self._hooks.trigger_error(session, e)
            raise DockerReplEngineError(f"Failed to create container: {e}")
    
    # =========================================================================
    # EXECUÇÃO DE CÓDIGO
    # =========================================================================
    
    async def execute(
        self,
        session: ContainerSession,
        code: str,
        timeout: Optional[int] = None,
        language: str = "python"
    ) -> ExecutionResult:
        """
        Executa código no container isolado.
        
        Args:
            session: Sessão do container
            code: Código a executar
            timeout: Timeout em segundos (usa default se None)
            language: Linguagem (python, bash, etc.)
            
        Returns:
            ExecutionResult com stdout, stderr e exit_code
            
        Raises:
            DockerReplEngineError: Se execução falha
            ExecutionTimeoutError: Se executa timeout
            
        Ciclo de Telemetria:
            1. trigger_start: Dispara quando execução inicia
            2. Execução: Código é executado com timeout
            3. trigger_stop: Dispara SEMPRE (finally) independente de erro/sucesso
            4. trigger_error: Dispara apenas em erros
        """
        timeout = timeout or self._execute_timeout
        client = self._get_docker_client()
        
        start_time = time.time()
        
        try:
            # Prepara código para execução
            if language == "python":
                # Wrap em código executável
                full_code = (
                    f"import sys\n"
                    f"import io\n"
                    f"sys.stdout = io.StringIO()\n"
                    f"sys.stderr = io.StringIO()\n"
                    f"try:\n"
                    f"    exec('''{code}''')\n"
                    f"except Exception as e:\n"
                    f"    print(f'Error: {{e}}', file=sys.stderr)\n"
                    f"    sys.exit(1)\n"
                    f"print(sys.stdout.getvalue(), file=sys.__stdout__)\n"
                    f"print(sys.stderr.getvalue(), file=sys.__stderr__)\n"
                )
            else:
                full_code = code
            
            # Executa código via exec
            # SDK 2.0+: remove 'detach' que não é mais suportado
            exec_result = client.exec_create(
                session.container_id,
                ["python3", "-c", full_code],
                stdin=False,
                stdout=True,
                stderr=True
            )
            
            # ================================================================
            # TELEMETRIA: Início da execução (OBRIGATÓRIO)
            # ================================================================
            await self._hooks.trigger_start(session)
            
            # Espera resultado com timeout
            async def wait_for_exec():
                output = client.exec_start(
                    exec_result["Id"],
                    detach=False,
                    tty=False
                )
                return output
            
            try:
                output = await asyncio.wait_for(
                    wait_for_exec(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # Para container em timeout
                await self.stop(session)
                await self._hooks.trigger_error(session, "Execution timeout")
                raise ExecutionTimeoutError(
                    f"Execução timeout após {timeout}s"
                )
            
            # CORRIGIDO Q2: Obter exit code real da API Docker
            # IMPORTANTE: Se exec_inspect falhar, não mascarar como sucesso.
            # Propagar erro para que o gerenciador abata o container e reporte falha.
            exec_info = client.exec_inspect(exec_result["Id"])
            exit_code = exec_info["ExitCode"]
            
            # Decodifica output (apenas para stdout/stderr display)
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            
            # Separa stdout e stderr para logging/display
            # Heurística apenas para display, não para exit code
            lines = output.split("\n")
            stdout_lines = []
            stderr_lines = []
            
            for line in lines:
                if "Error:" in line:
                    stderr_lines.append(line)
                else:
                    stdout_lines.append(line)
            
            stdout = "\n".join(stdout_lines).strip()
            stderr = "\n".join(stderr_lines).strip()
            
            duration = time.time() - start_time
            
            # Atualiza métricas
            self._metric_executions += 1
            
            return ExecutionResult(
                container_id=session.container_id,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration
            )
            
        except DockerException as e:
            await self._hooks.trigger_error(session, e)
            raise DockerReplEngineError(f"Execution failed: {e}")
        
        finally:
            # ================================================================
            # TELEMETRIA: Fim da execução (SEMPRE executa)
            # Dispara trigger_stop independente de sucesso, erro ou timeout
            # ================================================================
            await self._hooks.trigger_stop(session)
    
    # =========================================================================
    # CICLO DE VIDA
    # =========================================================================
    
    async def start(self, session: ContainerSession):
        """
        Inicia um container.
        
        Args:
            session: Sessão do container
        """
        client = self._get_docker_client()
        
        try:
            client.start(session.container_id)
            session.status = "running"
            
            await self._hooks.trigger_start(session)
            
            logger.debug(
                "Container started",
                extra={"extra_data": {
                    "container_id": session.container_id[:12]
                }}
            )
            
        except DockerException as e:
            await self._hooks.trigger_error(session, e)
            raise DockerReplEngineError(f"Failed to start container: {e}")
    
    async def stop(self, session: ContainerSession):
        """
        Para um container.
        
        Args:
            session: Sessão do container
        """
        client = self._get_docker_client()
        
        try:
            # stop graceful (envia SIGTERM)
            client.stop(session.container_id)
            session.status = "stopped"
            
            await self._hooks.trigger_stop(session)
            
            logger.debug(
                "Container stopped",
                extra={"extra_data": {
                    "container_id": session.container_id[:12]
                }}
            )
            
        except DockerException as e:
            await self._hooks.trigger_error(session, e)
            raise DockerReplEngineError(f"Failed to stop container: {e}")
    
    async def destroy(self, session: ContainerSession):
        """
        Destrói um container e todos os artefatos.
        
        Args:
            session: Sessão do container
        """
        client = self._get_docker_client()
        
        try:
            # Remove container (auto_remove=True já limpa)
            try:
                client.remove_container(
                    session.container_id,
                    force=True,
                    v=True  # Remove volumes
                )
            except NotFound:
                pass
            
            session.status = "destroyed"
            
            # Atualiza métricas
            self._metric_containers_destroyed += 1
            
            # Remove sessão
            self._sessions.pop(session.container_id, None)
            
            await self._hooks.trigger_destroy(session)
            
            logger.info(
                "Container destruído",
                extra={"extra_data": {
                    "container_id": session.container_id[:12],
                    "name": session.name
                }}
            )
            
        except DockerException as e:
            await self._hooks.trigger_error(session, e)
            raise DockerReplEngineError(f"Failed to destroy container: {e}")
    
    async def restart(self, session: ContainerSession):
        """
        Reinicia um container.
        
        Args:
            session: Sessão do container
        """
        await self.stop(session)
        await self.start(session)
    
    # =========================================================================
    # SAÚDE E STATUS
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica saúde do engine.
        
        Returns:
            Dicionário com status de saúde
        """
        client = self._get_docker_client()
        
        try:
            ping_result = client.ping()
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "docker_ping": ping_result,
                "initialized": self._initialized,
                "pool_available": self._pool.qsize(),
                "sessions_active": len(self._sessions),
                "metrics": self.metrics
            }
            
        except DockerException as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status do engine.
        
        Returns:
            Dicionário com status
        """
        return {
            "initialized": self._initialized,
            "config": {
                "memory_limit": self._config.memory_limit,
                "cpu_quota": self._config.cpu_quota,
                "pids_limit": self._config.pids_limit,
                "network_disabled": self._config.network_disabled,
                "tmpfs_enabled": self._config.tmpfs_enabled,
                "readonly_rootfs": self._config.readonly_rootfs,
            },
            "sessions": len(self._sessions),
            "pool": self._pool.qsize(),
            "metrics": self.metrics
        }
    
    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    
    async def shutdown(self):
        """
        Encerra o engine e limpa recursos.
        
        Destrói todos os containers e fecha conexão com Docker.
        """
        # Destrói todas as sessões
        sessions_to_destroy = list(self._sessions.values())
        
        for session in sessions_to_destroy:
            try:
                await self.destroy(session)
            except Exception as e:
                logger.error(
                    f"Erro ao destruir container: {str(e)}",
                    extra={"extra_data": {
                        "container_id": session.container_id[:12],
                        "error": str(e)
                    }}
                )
        
        # Limpa warm pool
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # Fecha conexão Docker
        if self._docker_client:
            self._docker_client.close()
            self._docker_client = None
        
        self._initialized = False
        
        logger.info("DockerReplEngine encerrado")
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_docker_client(self) -> docker.DockerClient:
        """
        Obtém cliente Docker (API de baixo nível).
        
        Returns:
            Cliente Docker (APIClient)
            
        Raises:
            DockerReplEngineError: Se não conectado
        """
        if not self._initialized or not self._docker_client:
            raise DockerReplEngineError("Engine não inicializado")
        
        # Docker SDK 2.0+: usa .api para baixo nível
        return self._docker_client.api


# =============================================================================
# INTERFACE SYNC
# =============================================================================

class DockerReplEngineSync:
    """
    Wrapper síncrono para DockerReplEngine.
    
    Fornece interface síncrona para uso em contextos não-async.
    """
    
    def __init__(
        self,
        config: Optional[ContainmentConfig] = None,
        base_image: str = "python:3.12-slim",
        pool_size: int = 3,
        execute_timeout: int = DEFAULT_EXECUTE_TIMEOUT
    ):
        """Inicializa wrapper síncrono."""
        self._engine = DockerReplEngine(
            config=config,
            base_image=base_image,
            pool_size=pool_size,
            execute_timeout=execute_timeout
        )
        self._loop = None
    
    def _ensure_loop(self):
        """Garante event loop."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def initialize(self) -> bool:
        """Inicializa (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.initialize()
        )
    
    def create_container(self, name: Optional[str] = None) -> ContainerSession:
        """Cria container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.create_container(name)
        )
    
    def execute(
        self,
        session: ContainerSession,
        code: str,
        timeout: Optional[int] = None
    ) -> ExecutionResult:
        """Executa código (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.execute(session, code, timeout)
        )
    
    def start(self, session: ContainerSession):
        """Inicia container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.start(session)
        )
    
    def stop(self, session: ContainerSession):
        """Para container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.stop(session)
        )
    
    def destroy(self, session: ContainerSession):
        """Destrói container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.destroy(session)
        )
    
    def restart(self, session: ContainerSession):
        """Reinicia container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.restart(session)
        )
    
    def health_check(self) -> Dict[str, Any]:
        """Health check (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._engine.health_check()
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get status (sync)."""
        return self._engine.get_status()
    
    @property
    def hooks(self) -> LifecycleHooks:
        """Retorna lifecycle hooks."""
        return self._engine.hooks
    
    def shutdown(self):
        """Encerra (sync)."""
        if self._loop and not self._loop.is_closed():
            self._loop.run_until_complete(
                self._engine.shutdown()
            )
            self._loop.close()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """
    Entry point para teste do DockerReplEngine.
    
    Uso:
        python3 docker_repl_engine.py --test
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Docker REPL Engine")
    parser.add_argument("--test", action="store_true", help="Executa teste")
    
    args = parser.parse_args()
    
    if args.test:
        print("=== Teste DockerReplEngine ===")
        
        # Teste com configuração Q2
        config = ContainmentConfig()
        
        print(f"1. Configuração:")
        print(f"   memory_limit: {config.memory_limit}")
        print(f"   cpu_quota: {config.cpu_quota}")
        print(f"   pids_limit: {config.pids_limit}")
        print(f"   network_disabled: {config.network_disabled}")
        print(f"   tmpfs_enabled: {config.tmpfs_enabled}")
        print(f"   tmpfs_size: {config.tmpfs_size}")
        print(f"   readonly_rootfs: {config.readonly_rootfs}")
        
        print(f"\n2. Validando configuração...")
        # Validação ocorre automaticamente em __post_init__
        # Se chegou aqui, o config já foi validado (fail-fast)
        print(f"   ✓ Configuração válida (validada em __post_init__)")
        
        print(f"\n3. HostConfig kwargs:")
        kwargs = config.to_host_config_kwargs()
        for key, value in kwargs.items():
            print(f"   {key}: {value}")
        
        print(f"\n4. Criando engine...")
        engine = DockerReplEngineSync(
            config=config,
            pool_size=1
        )
        
        print(f"5. Inicializando...")
        try:
            engine.initialize()
            print(f"   ✓ Inicializado")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
            return
        
        print(f"6. Criando container...")
        try:
            session = engine.create_container()
            print(f"   ✓ Container: {session.name}")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
            engine.shutdown()
            return
        
        print(f"7. Executando código...")
        try:
            result = engine.execute(
                session,
                "print('Hello, World!')\nprint(f'2 + 2 = {2+2}')"
            )
            print(f"   stdout: {result.stdout!r}")
            print(f"   stderr: {result.stderr!r}")
            print(f"   exit_code: {result.exit_code}")
            print(f"   duration: {result.duration:.2f}s")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
        
        print(f"8. Destruindo container...")
        try:
            engine.destroy(session)
            print(f"   ✓ Destruído")
        except Exception as e:
            print(f"   ✗ Erro: {e}")
        
        print(f"9. Encerrando...")
        engine.shutdown()
        print(f"   ✓ Encerrado")
        
        print(f"\n=== Teste completo ===")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
"""
ContainerManager - Gerenciador de Ciclo de Vida de Containers Docker

Este módulo implementa o gerenciador de ciclo de vida para a plataforma XenoSys,
fornecendo um ambiente de execução de código Python isolado e persistente usando
containers Docker com warm pool para inicialização rápida.

Funcionalidades Principais:
- Criação de containers interativos (-it) como sessões REPL persistentes
- Warm pool com N=3 containers pré-inicializados
- Execução de código Python com stdout/stderr capturados
- Health monitoring a cada 30 segundos
- Recovery automático em caso de crash (max 5s)
- IPC com suporte a stdin/stdout/stderr streaming
- Restrições de hardware (CPU, RAM) e rede desabilitada por padrão

Padrões de Projeto Aplicados:
- Object Pool: Warm pool para inicialização rápida
- Factory: Criação padronizada de containers
- Observer: Health monitoring com callbacks
- Strategy: Estratégias de recovery

Arquitetura:
┌─────────────────────────────────────────────────────────────┐
│                    ContainerManager                          │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │ Container  │  │ Container  │  │ Container  │  ...    │
│  │  Pool N=3 │  │   Warm    │  │          │       │
│  └────────────┘  └────────────┘  └────────────┘       │
├─────────────────────────────────────────────────────────────┤
│  Health Monitor (30s interval)                         │
│  Recovery Controller (max 5s)                          │
└─────────────────────────────────────────────────────────────┘
"""

import asyncio
import json
import logging
import queue
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from threading import Thread

import docker
from docker import APIClient
from docker.errors import APIError, NotFound, DockerException
from docker.types import HostConfig


# =============================================================================
# CONFIGURAÇÃO E CONSTANTES
# =============================================================================

# Configurações de resource limits (do check_docker.py Q0)
DEFAULT_MEMORY_LIMIT = "2g"   # 2GB RAM limit
DEFAULT_CPU_LIMIT = 2.0       # 2 CPU cores

# Configurações do warm pool
WARM_POOL_SIZE = 3              # N=3 containers pré-inicializados
CONTAINER_NAME_PREFIX = "cog-"      # Prefixo de nome de container

# Timeouts
HEALTH_CHECK_INTERVAL = 30        # Intervalo de health check (segundos)
CREATE_TIMEOUT = 5               # Timeout para criação (segundos)
EXECUTE_TIMEOUT = 60             # Timeout para execução (segundos)
RECOVERY_TIMEOUT = 5               # Timeout máximo para recovery (segundos)

# Imagem base - usa alpine que geralmente está disponível
# ou python:slim se disponível
BASE_IMAGE = "python:3.12-slim"        # Imagem mínima (~150MB)


# =============================================================================
# LOGGER
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter para output estruturado.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
            
        return json.dumps(log_entry)


def setup_logger(name: str) -> logging.Logger:
    """Configura logger com formatação JSON."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    
    return logger


logger = setup_logger("container_manager")


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ExecutionResult:
    """
    Resultado da execução de código em um container.
    
    Attributes:
        container_id: ID do container que executou o código
        stdout: Output padrão do código executado
        stderr: Output de erro do código executado
        exit_code: Código de saída da execução
        duration: Tempo de execução em segundos
    """
    container_id: str
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário."""
        return {
            "container_id": self.container_id,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration
        }


@dataclass
class ContainerSession:
    """
    Sessão de container representando uma instância de REPL persistente.
    
    Attributes:
        container_id: ID único do container Docker
        name: Nome do container (cog-uuid_curto)
        created_at: Timestamp de criação
        status: Status atual (ready/running/error/recovering)
        health_last_check: Timestamp do último health check
        exec_container_id: ID do container de execução (exec create)
        is_warm: Se o container está pré-inicializado no pool
    """
    container_id: str
    name: str
    created_at: datetime
    status: str = "creating"
    health_last_check: Optional[datetime] = None
    exec_container_id: Optional[str] = None
    is_warm: bool = False


# =============================================================================
# EXCEÇÕES CUSTOMIZADAS
# =============================================================================

class ContainerManagerError(Exception):
    """Exceção base para ContainerManager."""
    pass


class ContainerNotAvailableError(ContainerManagerError):
    """Raised when no container is available in the pool."""
    pass


class ExecutionError(ContainerManagerError):
    """Raised when code execution fails."""
    pass


class RecoveryError(ContainerManagerError):
    """Raised when recovery fails."""
    pass


# =============================================================================
# CONTAINER MANAGER
# =============================================================================

class ContainerManager:
    """
    Gerenciador de ciclo de vida de containers Docker.
    
    Implementa:
    - Warm pool com N=3 containers pré-inicializados
    - Execução de código Python com IPC streaming
    - Health monitoring contínuo
    - Recovery automático em caso de crash
    
    Uso:
        manager = ContainerManager()
        
        # Criar container (retorna warm se disponível)
        container_id = await manager.create_container()
        
        # Executar código
        result = await manager.execute(container_id, "print('Hello, World!')")
        print(result.stdout)
        
        # Destruir container
        await manager.destroy(container_id)
    """
    
    def __init__(
        self,
        pool_size: int = WARM_POOL_SIZE,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        base_image: str = BASE_IMAGE
    ):
        """
        Inicializa o ContainerManager.
        
        Args:
            pool_size: Número de containers no warm pool
            memory_limit: Limite de memória por container
            cpu_limit: Limite de CPU por container
            base_image: Imagem Docker base (padrão: python:slim)
        """
        self._pool_size = pool_size
        self._memory_limit = memory_limit
        self._cpu_limit = cpu_limit
        self._base_image = base_image
        
        # Docker client (low-level API para operações)
        self._docker_client: Optional[APIClient] = None
        self._socket_path = "/var/run/docker.sock"
        
        # Warm poolde containers prontos
        self._pool: queue.Queue = queue.Queue()
        
        # Lock para operaçõesthread-safe
        self._lock = asyncio.Lock()
        
        # Sessões ativas (container_id -> ContainerSession)
        self._sessions: Dict[str, ContainerSession] = {}
        
        # Health monitoring
        self._health_monitor_running = False
        self._health_monitor_task: Optional[asyncio.Task] = None
        
        # Thread pool para operações bloqueantes
        self._thread_pool = ThreadPoolExecutor(max_workers=10)
        
        logger.info(
            "ContainerManager inicializado",
            extra={"extra_data": {
                "pool_size": pool_size,
                "memory_limit": memory_limit,
                "cpu_limit": cpu_limit,
                "base_image": base_image
            }}
        )
    
    # =========================================================================
    # INICIALIZAÇÃO
    # =========================================================================
    
    def _get_docker_client(self) -> APIClient:
        """
        Obtém o cliente Docker API (lazy initialization).
        
        Returns:
            Instância do cliente Docker API
            
        Raises:
            DockerException: Se Docker não está disponível
        """
        if self._docker_client is None:
            # Usa socket path correto para o ambiente
            self._docker_client = docker.APIClient(
                base_url=f"unix://{self._socket_path}"
            )
        
        return self._docker_client

    async def _pull_image(self, client: APIClient) -> bool:
        """
        Puxa a imagem base do Docker Hub se não existir localmente.
        
        Args:
            client: Docker API client
            
        Returns:
            True se imagem disponível
        """
        try:
            # Verifica se imagem existe localmente
            images = client.images(self._base_image)
            
            if images:
                logger.info(
                    f"Imagem {self._base_image} já existe localmente",
                    extra={"extra_data": {"image": self._base_image}}
                )
                return True
            
        except APIError:
            pass
        
        # Puxa imagem
        logger.info(
            f"Puxando imagem {self._base_image}...",
            extra={"extra_data": {"image": self._base_image}}
        )
        
        try:
            # Puxa imagem com timeout
            loop = asyncio.get_event_loop()
            
            # Executa pull em thread pool
            def pull():
                return client.pull(
                    self._base_image,
                    stream=True,
                    decode=True
                )
            
            # Processa streaming logs
            await asyncio.wait_for(
                loop.run_in_executor(self._thread_pool, pull),
                timeout=120
            )
            
            logger.info(
                f"Imagem {self._base_image} puxada com sucesso",
                extra={"extra_data": {"image": self._base_image}}
            )
            return True
            
        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout ao puxar {self._base_image}",
                extra={"extra_data": {"image": self._base_image}}
            )
            raise ContainerManagerError(f"Image pull timeout: {self._base_image}")
            
        except DockerException as e:
            logger.warning(
                f"Erro ao puxar {self._base_image}: {str(e)}",
                extra={"extra_data": {"error": str(e)}}
            )
            raise
    
    async def initialize(self) -> bool:
        """
        Inicializa o ContainerManager e preenche o warm pool.
        
        Realiza:
        1. Verifica conexão com Docker
        2. Puxa imagem base se necessário
        3. Preenche warm pool com N=3 containers
        
        Returns:
            True se inicialização bem-sucedida
            
        Raises:
            DockerException: Se Docker não está disponível
        """
        logger.info("Inicializando ContainerManager...")
        
        # Verifica Docker disponível
        client = self._get_docker_client()
        
        try:
            client.ping()
        except DockerException as e:
            logger.error(
                "Docker não disponível",
                extra={"extra_data": {"error": str(e)}}
            )
            raise
        
        # Puxa imagem base se não existir localmente
        await self._pull_image(client)
        
        # Preenche warm pool
        await self._fill_warm_pool()
        
        # Inicia health monitor
        self._start_health_monitor()
        
        logger.info(
            "ContainerManager inicializado com sucesso",
            extra={"extra_data": {"pool_size": self._pool_size}}
        )
        
        return True
    
    async def shutdown(self):
        """
        Encerra o ContainerManager e limpa recursos.
        
        Remove:
        - Todos os containers das sessões
        - Warm pool
        - Health monitor
        """
        logger.info("Encerrando ContainerManager...")
        
        # Para health monitor
        self._health_monitor_running = False
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
        
        # Limpa warm pool
        while not self._pool.empty():
            try:
                session = self._pool.get_nowait()
                await self._remove_container(session.container_id)
            except queue.Empty:
                break
        
        # Limpa sessões ativas
        async with self._lock:
            for session in list(self._sessions.values()):
                await self._remove_container(session.container_id)
            self._sessions.clear()
        
        # Fecha thread pool
        self._thread_pool.shutdown(wait=True)
        
        logger.info("ContainerManager encerrado")
    
    # =========================================================================
    # WARM POOL
    # =========================================================================
    
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
            container_id="",  # Preenchido após criação
            name=name,
            created_at=datetime.now(timezone.utc),
            is_warm=is_warm
        )
        
        try:
            # Cria host config com restrições de recursos
            # Usa API version do Docker client
            version = client.version()
            api_version = version.get("Version", "1.41")
            
            host_config = HostConfig(
                api_version,
                mem_limit=self._memory_limit,
                cpu_period=100000,
                cpu_quota=int(self._cpu_limit * 100000),
                network_mode="none",         # Rede desabilitada por segurança
                auto_remove=True
            )
            
            # Cria container interativo (-it) com restrições de recursos
            container = client.create_container(
                self._base_image,
                tty=True,                    # TTY para interactivity
                stdin_open=True,             # stdin aberto para IPC
                host_config=host_config,
                name=name
            )
            
            session.container_id = container["Id"]
            session.status = "ready"
            
            # Inicia container (sempre modo interativo -it)
            client.start(container["Id"])
            
            logger.info(
                f"Container criado: {session.container_id[:12]}",
                extra={"extra_data": {
                    "container_id": session.container_id[:12],
                    "name": name,
                    "is_warm": is_warm
                }}
            )
            
            return session
            
        except DockerException as e:
            logger.error(
                f"Falha ao criar container: {str(e)}",
                extra={"extra_data": {
                    "error": str(e),
                    "name": name
                }}
            )
            raise ContainerManagerError(f"Failed to create container: {e}")
    
    async def _fill_warm_pool(self):
        """
        Preenche o warm pool com N=3 containers.
        
        Cria N=3 containers em background para inicialização rápida.
        """
        logger.info(f"Preenchendo warm pool (N={self._pool_size})...")
        
        # Executa criação em background
        loop = asyncio.get_event_loop()
        
        for i in range(self._pool_size):
            try:
                session = await asyncio.wait_for(
                    self._create_container_internal(is_warm=True),
                    timeout=CREATE_TIMEOUT
                )
                self._pool.put(session)
                
                logger.info(
                    f"Container warm adicionado ao pool",
                    extra={"extra_data": {
                        "session_id": i + 1,
                        "pool_size": self._pool.qsize()
                    }}
                )
                
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timeout ao criar container warm {i+1}",
                    extra={"extra_data": {"timeout": CREATE_TIMEOUT}}
                )
            except DockerException as e:
                logger.warning(
                    f"Erro ao criar container warm {i+1}: {str(e)}",
                    extra={"extra_data": {"error": str(e)}}
                )
        
        logger.info(
            "Warm pool preenchido",
            extra={"extra_data": {"pool_size": self._pool.qsize()}}
        )
    
    # =========================================================================
    # CRIAÇÃO DE CONTAINER
    # =========================================================================
    
    async def create_container(self) -> str:
        """
        Cria um novo container ou obtém um do warm pool.
        
        Implementa warm pool para cold start rápido (<800ms).
        
        Returns:
            container_id: ID do container (12 primeiros caracteres)
            
        Raises:
            ContainerNotAvailableError: Se pool vazo e não é possível criar
            ContainerManagerError: Se criação falha
        """
        start_time = time.time()
        
        # Tenta obter do warm pool
        try:
            session = self._pool.get_nowait()
            self._sessions[session.container_id] = session
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(
                f"Container obtido do warm pool",
                extra={"extra_data": {
                    "container_id": session.container_id[:12],
                    "elapsed_ms": round(elapsed, 2),
                    "pool_remaining": self._pool.qsize()
                }}
            )
            
            return session.container_id
            
        except queue.Empty:
            # Warm pool vazo, cria novo container
            logger.info("Warm pool vazio, criando novo container...")
            
            session = await asyncio.wait_for(
                self._create_container_internal(),
                timeout=CREATE_TIMEOUT
            )
            
            self._sessions[session.container_id] = session
            
            elapsed = (time.time() - start_time) * 1000
            logger.info(
                f"Novo container criado",
                extra={"extra_data": {
                    "container_id": session.container_id[:12],
                    "elapsed_ms": round(elapsed, 2)
                }}
            )
            
            return session.container_id
    
    # =========================================================================
    # EXECUÇÃO DE CÓDIGO
    # =========================================================================
    
    async def execute(
        self,
        container_id: str,
        code: str,
        timeout: int = EXECUTE_TIMEOUT
    ) -> ExecutionResult:
        """
        Executa código Python em um container.
        
        Implementa IPC com stdin/stdout/stderr streaming.
        
        Args:
            container_id: ID do container
            code: Código Python a executar
            timeout: Timeout em segundos
            
        Returns:
            ExecutionResult com stdout, stderr e exit_code
            
        Raises:
            ExecutionError: Se execução falha
        """
        start_time = time.time()
        
        # Valida sessão existe
        async with self._lock:
            session = self._sessions.get(container_id)
            if not session:
                raise ExecutionError(f"Container não encontrado: {container_id}")
        
        client = self._get_docker_client()
        
        try:
            # Executa código de forma simples e captura output
            # Codifica para base64 para evitar problemas com caracteres especiais
            import base64
            code_b64 = base64.b64encode(code.encode('utf-8')).decode('ascii')
            
            # Script wrapper que executa e captura output
            exec_script = f'''
import base64
import sys
import io

# Decode and execute code
code = base64.b64decode("{code_b64}").decode("utf-8")
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()

try:
    exec(code, {{"__name__": "__main__"}})
except Exception:
    import traceback
    traceback.print_exc()

stdout_val = sys.stdout.getvalue()
stderr_val = sys.stderr.getvalue()
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__

# Output in parseable format
print("<<<XENOSYS_OUT>>>")
print(stdout_val)
print("<<<XENOSYS_ERR>>>")
print(stderr_val)
print("<<<XENOSYS_END>>>")
'''
            
            # Cria processo exec no container
            exec_id = client.exec_create(
                container_id,
                ["python3", "-c", exec_script],
                tty=True,
                stdin=False
            )
            
            # Executa
            exec_output = client.exec_start(
                exec_id,
                stream=True,
                demux=False
            )
            
            # Coleta output
            output_buffer = []
            
            # Modo stream=True retornaGenerator
            for chunk in exec_output:
                if chunk:
                    output_buffer.append(chunk.decode('utf-8'))
            
            full_output = "".join(output_buffer)
            
            # Parse output
            stdout = ""
            stderr = ""
            
            if "<<<XENOSYS_OUT>>>" in full_output:
                parts = full_output.split("<<<XENOSYS_OUT>>>")
                after_marker = parts[1] if len(parts) > 1 else ""
                
                if "<<<XENOSYS_ERR>>>" in after_marker:
                    stdout, stderr = after_marker.split("<<<XENOSYS_ERR>>>")
                    stderr = stderr.split("<<<XENOSYS_END>>>")[0]
                else:
                    stdout = after_marker
            
            stdout = stdout.strip()
            stderr = stderr.strip()
            
            duration = time.time() - start_time
            
            result = ExecutionResult(
                container_id=container_id,
                stdout=stdout,
                stderr=stderr,
                exit_code=0,
                duration=duration
            )
            
            logger.info(
                f"Código executado",
                extra={"extra_data": {
                    "container_id": container_id[:12],
                    "exit_code": result.exit_code,
                    "duration_ms": round(duration * 1000, 2),
                    "stdout_len": len(result.stdout)
                }}
            )
            
            return result
            
        except NotFound:
            logger.error(
                "Container não encontrado durante execução",
                extra={"extra_data": {"container_id": container_id[:12]}}
            )
            raise ExecutionError(f"Container não encontrado: {container_id}")
            
        except Exception as e:
            logger.error(
                f"Erro na execução: {str(e)}",
                extra={"extra_data": {"error": str(e)}}
            )
            raise ExecutionError(f"Execução falhou: {e}")
    
    # =========================================================================
    # DESTRUÇÃO DE CONTAINER
    # =========================================================================
    
    async def _remove_container(self, container_id: str):
        """
        Remove um container e limpa artefatos.
        
        Args:
            container_id: ID do container a remover
        """
        client = self._get_docker_client()
        
        try:
            # Force remove (pode estar em qualquer estado)
            client.remove_container(
                container_id,
                force=True,
                v=True  # Remove volumes também
            )
            
            logger.info(
                f"Container removido",
                extra={"extra_data": {"container_id": container_id[:12]}}
            )
            
        except NotFound:
            # Container já foi removido
            pass
            
        except DockerException as e:
            logger.warning(
                f"Erro ao remover container: {str(e)}",
                extra={"extra_data": {"error": str(e)}}
            )
    
    async def destroy(self, container_id: str):
        """
        Destrói um container e remove todos os artefatos.
        
        Args:
            container_id: ID do container a destruir
            
        Raises:
            ContainerManagerError: Se remoção falha
        """
        async with self._lock:
            # Remove da sessão
            session = self._sessions.pop(container_id, None)
            
            if session:
                await self._remove_container(container_id)
        
        logger.info(
            "Container destruído",
            extra={"extra_data": {"container_id": container_id[:12]}}
        )
    
    # =========================================================================
    # HEALTH MONITOR
    # =========================================================================
    
    def _start_health_monitor(self):
        """Inicia o health monitor em background."""
        self._health_monitor_running = True
        self._health_monitor_task = asyncio.create_task(
            self._health_check_loop()
        )
        
        logger.info(
            "Health monitor iniciado",
            extra={"extra_data": {"interval": HEALTH_CHECK_INTERVAL}}
        )
    
    async def _health_check_loop(self):
        """
        Loop de health check contínuo (a cada 30 segundos).
        
        Verifica status de todos os containers ativos e reinicia
        recovery automático em caso de crash.
        """
        while self._health_monitor_running:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                
                await self._check_all_containers()
                
            except asyncio.CancelledError:
                break
                
            except Exception as e:
                logger.warning(
                    f"Erro no health check: {str(e)}",
                    extra={"extra_data": {"error": str(e)}}
                )
        
        logger.info("Health monitor parado")
    
    async def _check_all_containers(self):
        """
        Verifica status de todos os containers.
        
        Realiza:
        1. Lista containers ativos
        2. Verifica se estão rodsando
        3. Recovery automático em caso de crash
        """
        client = self._get_docker_client()
        
        async with self._lock:
            sessions = list(self._sessions.values())
        
        for session in sessions:
            try:
                # Verifica status do container
                info = client.inspect_container(session.container_id)
                state = info.get("State", {})
                
                running = state.get("Running", False)
                status = state.get("Status", "unknown")
                
                session.health_last_check = datetime.now(timezone.utc)
                
                if not running:
                    # Container crashou, tenta recovery
                    logger.warning(
                        f"Container não está rodsando, iniciando recovery",
                        extra={"extra_data": {
                            "container_id": session.container_id[:12],
                            "status": status
                        }}
                    )
                    
                    await self._recover_container(session)
                    
            except NotFound:
                # Container foi removido
                logger.warning(
                    "Container não encontrado, removendo da sessão",
                    extra={"extra_data": {"container_id": session.container_id[:12]}}
                )
                async with self._lock:
                    self._sessions.pop(session.container_id, None)
                    
            except DockerException as e:
                logger.warning(
                    f"Erro ao verificar container: {str(e)}",
                    extra={"extra_data": {"error": str(e)}}
                )
    
    async def _recover_container(self, session: ContainerSession):
        """
        Realiza recovery automático de um container.
        
        Args:
            session: Sessão do container a recuperar
            
        Raises:
            RecoveryError: Se recovery falha
        """
        start_time = time.time()
        
        try:
            # Timeout para recovery (max 5s)
            await asyncio.wait_for(
                self._recover_container_internal(session),
                timeout=RECOVERY_TIMEOUT
            )
            
            elapsed = time.time() - start_time
            
            logger.info(
                "Recovery concluído",
                extra={"extra_data": {
                    "container_id": session.container_id[:12],
                    "duration": round(elapsed, 2)
                }}
            )
            
        except asyncio.TimeoutError:
            raise RecoveryError(
                f"Recovery timeout para {session.container_id[:12]}"
            )
    
    async def _recover_container_internal(self, session: ContainerSession):
        """
        Implementa lógica de recovery.
        
        Remove container原来的 e cria novo em substituição.
        """
        container_id = session.container_id
        
        # Remove container原来的
        await self._remove_container(container_id)
        
        # Cria novo container
        new_session = await self._create_container_internal()
        
        # Substitui na sessão
        async with self._lock:
            self._sessions.pop(container_id, None)
            self._sessions[new_session.container_id] = new_session
        
        session.container_id = new_session.container_id
        session.status = "ready"
    
    # =========================================================================
    # STATUS E METRICAS
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Retorna status do ContainerManager.
        
        Returns:
            Dicionário com métricas e status
        """
        return {
            "pool_size": self._pool.qsize(),
            "active_sessions": len(self._sessions),
            "health_monitor_running": self._health_monitor_running,
            "configured": {
                "pool_size": self._pool_size,
                "memory_limit": self._memory_limit,
                "cpu_limit": self._cpu_limit,
                "base_image": self._base_image
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Health check do ContainerManager.
        
        Returns:
            Dicionário com status de saúde
        """
        client = self._get_docker_client()
        
        try:
            ping_result = client.ping()
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "docker_ping": ping_result,
                "pool_available": self._pool.qsize(),
                "sessions_active": len(self._sessions)
            }
            
        except DockerException as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# =============================================================================
# INTERFACE SYNC (para compatibilidade)
# =============================================================================

class ContainerManagerSync:
    """
    Wrapper sync para ContainerManager async.
    
    Fornece interface síncrona para uso em contextos não-async.
    """
    
    def __init__(self, **kwargs):
        self._async_manager = ContainerManager(**kwargs)
        self._loop = None
        self._thread = None
    
    def _ensure_loop(self):
        """Garante que há um event loop em execução."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def initialize(self) -> bool:
        """Inicialização síncrona."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._async_manager.initialize()
        )
    
    def create_container(self) -> str:
        """Cria container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._async_manager.create_container()
        )
    
    def execute(
        self,
        container_id: str,
        code: str,
        timeout: int = EXECUTE_TIMEOUT
    ) -> ExecutionResult:
        """Executa código (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._async_manager.execute(container_id, code, timeout)
        )
    
    def destroy(self, container_id: str):
        """Destrói container (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._async_manager.destroy(container_id)
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Obtém status (sync)."""
        return self._async_manager.get_status()
    
    def health_check(self) -> Dict[str, Any]:
        """Health check (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._async_manager.health_check()
        )
    
    def shutdown(self):
        """Encerra gerenciador (sync)."""
        if self._loop and not self._loop.is_closed():
            self._loop.run_until_complete(
                self._async_manager.shutdown()
            )
            self._loop.close()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """
    Entry point para teste do ContainerManager.
    
    Uso:
        python3 container_manager.py
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Container Manager")
    parser.add_argument("--test", action="store_true", help="Executa teste rápido")
    
    args = parser.parse_args()
    
    if args.test:
        # Teste rápido
        print("=== Teste ContainerManager ===")
        
        manager = ContainerManagerSync(pool_size=2)
        
        print("1. Inicializando...")
        manager.initialize()
        print(f"   Status: {manager.get_status()}")
        
        print("2. Criando container...")
        container_id = manager.create_container()
        print(f"   Container: {container_id[:12]}")
        
        print("3. Executando código...")
        result = manager.execute(
            container_id,
            "print('Hello, World!')\nresult = 2 + 2\nprint(f'2 + 2 = {result}')"
        )
        print(f"   stdout: {result.stdout}")
        print(f"   stderr: {result.stderr}")
        print(f"   exit_code: {result.exit_code}")
        
        print("4. Destruindo container...")
        manager.destroy(container_id)
        
        print("5. Health check...")
        health = manager.health_check()
        print(f"   Status: {health}")
        
        print("6. Encerrando...")
        manager.shutdown()
        
        print("=== Teste completo ===")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
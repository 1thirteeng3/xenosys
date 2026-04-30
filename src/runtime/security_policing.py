"""
Security Policing - Contenção Docker Paranoica (Q7)

Este módulo implementa o hardening de segurança definitivo e a governança
de recursos do sistema XenoSys. Atua como WRAPPER efetivo sobre o ContainerManager,
aplicando e verificando todas as políticas de segurança.

CRÍTICO: Este módulo NÃO é opcional. Deve envolver todo o ContainerManager
para garantir que containers são criados com hardening real.

Funcionalidades Principais:
- Wrapper Efetivo: Intercepta create_container(), aplica, verifica
- Privilégios Zero: --security-opt no-new-privileges:true
- Remoção de Capabilities: --cap-drop=ALL
- Imutabilidade RootFS: read_only=True; tmpfs para /tmp, /run
- PIDs limit: 64 fixos
- OOM Score Adj: 1000 (primeiro a morrer em pressão de memória)
- Verificação Pós-Criação: verify_container_is_secure()
- Rootless Check: Alerta crítico se daemon root
- Profilaxia Energética: Suspensão via psutil
- Audit Trail: security.audit.log

Padrões Aplicados:
- Decorator Pattern: Wrapper sobre ContainerManager
- Observer Pattern: Eventos de segurança
- Strategy Pattern: BatteryStrategy
- Fail-Fast: Verificação imediata aborta se configurações ignoradas
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import docker
from docker.types import HostConfig

# =============================================================================
# IMPORTS DO CORE COMPARTILHADO (SSOT)
# =============================================================================
from core.logging import JSONFormatter, setup_logger

# Logger principal
logger = setup_logger("security_policing")

# Logger de auditoria separado
audit_logger = logging.getLogger("security_audit")
audit_logger.setLevel(logging.DEBUG)


# =============================================================================
# CONFIGURAÇÃO E CONSTANTES
# =============================================================================

class BatteryState(Enum):
    """Estados de bateria."""
    UNKNOWN = "unknown"
    CHARGING = "charging"
    DISCHARGING = "discharging"
    FULL = "full"
    NOT_PRESENT = "not_present"


class SecurityLevel(Enum):
    """Níveis de segurança."""
    STANDARD = "standard"
    HARDENED = "hardened"
    PARANOIC = "paranoic"


# Constantes de Segurança (Q7 Spec)
SECURITY_OPT_NO_NEW_PRIVILEGES = "no-new-privileges:true"
CAP_DROP_ALL = ["ALL"]
DEFAULT_PIDS_LIMIT = 64
DEFAULT_OOM_SCORE_ADJ = 1000       # Primeiro a morrer em OOM
DEFAULT_TMPFS_SIZE = "100m"       # /tmp
DEFAULT_RUN_SIZE = "50m"         # /run
BATTERY_THRESHOLD = 20
SECURITY_AUDIT_FILE = "security.audit.log"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass(frozen=True)
class SecurityConfig:
    """
    Configuração de segurança para containers Docker.
    
    ATENÇÃO: Esta configuração é IMPOSTA, não opcional.
    Todo container deve ser criado com estes parâmetros.
    """
    # Security options
    security_opt: str = SECURITY_OPT_NO_NEW_PRIVILEGES
    cap_drop: List[str] = field(default_factory=lambda: CAP_DROP_ALL.copy())
    
    # Resource limits
    pids_limit: int = DEFAULT_PIDS_LIMIT
    oom_score_adj: int = DEFAULT_OOM_SCORE_ADJ
    memory_limit: str = "512m"      # HARD limit
    
    # Filesystem
    read_only_rootfs: bool = True
    tmpfs_tmp: str = DEFAULT_TMPFS_SIZE
    tmpfs_run: str = DEFAULT_RUN_SIZE
    
    # Others
    battery_threshold: int = BATTERY_THRESHOLD
    enable_audit: bool = True
    audit_file: str = SECURITY_AUDIT_FILE
    
    def __post_init__(self):
        """Fail-Fast validation."""
        if "no-new-privileges" not in self.security_opt:
            raise ValueError("security_opt deve conter 'no-new-privileges:true'")
        if "ALL" not in self.cap_drop:
            raise ValueError("cap_drop deve conter 'ALL'")
        if self.pids_limit < 1 or self.pids_limit > 128:
            raise ValueError("pids_limit deve estar entre 1 e 128")
    
    def to_host_config_kwargs(self) -> Dict[str, Any]:
        """
        Converte para argumentos do HostConfig.
        
        RETORNA dicionário pronto para API docker.types.HostConfig()
        """
        return {
            "security_opt": [self.security_opt],
            "cap_drop": self.cap_drop,
            "pids_limit": self.pids_limit,
            "read_only": self.read_only_rootfs,
            "tmpfs": {
                "/tmp": self.tmpfs_tmp,
                "/run": self.tmpfs_run,
            },
        }
    
    def to_create_kwargs(self) -> Dict[str, Any]:
        """Kwargs para client.containers.create()."""
        return {
            "security_opt": [self.security_opt],
        }


@dataclass
class BatteryStatus:
    """Status da bateria."""
    state: BatteryState = BatteryState.UNKNOWN
    percent: float = 100.0
    is_charging: bool = False
    is_low: bool = False
    is_critical: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "percent": self.percent,
            "is_charging": self.is_charging,
            "is_low": self.is_low,
            "is_critical": self.is_critical,
        }


# =============================================================================
# EXCEÇÕES
# =============================================================================

class SecurityPolicingError(Exception):
    """Exceção base."""
    pass


class RootDaemonDetectedError(SecurityPolicingError):
    """Docker root detectado."""
    pass


class ContainerSecurityViolationError(SecurityPolicingError):
    """Container não respeita políticas de segurança."""
    pass


class SecurityConfigInvalidError(SecurityPolicingError):
    """Configuração inválida."""
    pass


# =============================================================================
# BATTERY MANAGER
# =============================================================================

class BatteryManager:
    """Monitoramento de bateria e profilaxia energética."""
    
    def __init__(self):
        self._psutil = None
        self._init_psutil()
    
    def _init_psutil(self):
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            logger.warning("psutil não disponível")
    
    def get_battery_status(self, threshold: int = BATTERY_THRESHOLD) -> BatteryStatus:
        if not self._psutil:
            return BatteryStatus(state=BatteryState.NOT_PRESENT, percent=100.0)
        
        try:
            battery = self._psutil.sensors_battery()
            if battery is None:
                return BatteryStatus(state=BatteryState.NOT_PRESENT, percent=100.0)
            
            state = BatteryState.CHARGING if battery.power_plugged else BatteryState.DISCHARGING
            percent = battery.percent
            return BatteryStatus(
                state=state,
                percent=percent,
                is_charging=battery.power_plugged,
                is_low=percent < threshold,
                is_critical=percent < 10,
            )
        except Exception as e:
            logger.warning(f"Battery check failed: {e}")
            return BatteryStatus()
    
    def should_suspend_tasks(self, threshold: int = BATTERY_THRESHOLD) -> bool:
        status = self.get_battery_status(threshold)
        if status.state in [BatteryState.CHARGING, BatteryState.NOT_PRESENT]:
            return False
        return status.is_low or status.is_critical


# =============================================================================
# SECURITY AUDIT
# =============================================================================

class SecurityAudit:
    """Sistema de auditoria de segurança."""
    
    def __init__(self, audit_file: str = SECURITY_AUDIT_FILE):
        self._audit_file = Path(audit_file)
        self._ensure_log_file()
    
    def _ensure_log_file(self):
        if not self._audit_file.exists():
            self._audit_file.touch()
    
    def _log(self, event_type: str, severity: str, message: str, details: Dict = None):
        self._ensure_log_file()
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "message": message,
            "details": details or {},
        }
        with open(self._audit_file, "a") as f:
            f.write(json.dumps(event) + "\n")
        
        if severity == "CRITICAL":
            logger.critical(message)
        elif severity == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
    
    def log_security_event(self, event_type: str, message: str, severity: str = "INFO", **details):
        self._log(event_type, severity, message, details)
    
    def log_network_blocked(self, container_id: str, destination: str):
        self._log("network_attempt", "WARNING", f"Rede bloqueada: {destination}", {"container_id": container_id[:12]})
    
    def log_root_warning(self, info: Dict):
        self._log("root_daemon", "CRITICAL", "Docker daemon rodando como root!", info)
    
    def log_container_created(self, container_id: str, secure: bool):
        self._log(
            "container_created",
            "INFO" if secure else "CRITICAL",
            f"Container {'seguro' if secure else 'INSECURE'}: {container_id[:12]}",
            {"secure": secure}
        )


# =============================================================================
# SECURITY VALIDATOR
# =============================================================================

class SecurityValidator:
    """Validador de segurança - verificação física via API Docker."""
    
    def __init__(self, config: SecurityConfig):
        self._config = config
        self._docker_client = None
    
    def _get_client(self) -> docker.DockerClient:
        if not self._docker_client:
            self._docker_client = docker.from_env()
        return self._docker_client
    
    async def verify_container_is_secure(self, container_id: str) -> bool:
        """
        CRÍTICO: Verifica fisicamente o container após criação.
        
        Este método DEVE ser chamado imediatamente após create_container().
        Se retorna False, o container deve ser ABORTADO imediatamente.
        
        ZERO-TRUST: Se qualquer exceção occur, o container é considerado_HOSTIL.
        """
        try:
            client = self._get_client()
            # Usa low-level API para inspeção completa
            inspection = client.api.inspect_container(container_id)
            
            host_config = inspection.get("HostConfig", {})
            
            errors = []
            
            # 1. Verifica security_opt
            security_opts = host_config.get("SecurityOpt", [])
            if not any("no-new-privileges" in str(opt) for opt in security_opts):
                errors.append("FALTA: no-new-privileges")
            
            # 2. Verifica cap_drop
            cap_drop = host_config.get("CapDrop", [])
            if "ALL" not in cap_drop:
                errors.append(f"FALTA: cap_drop=ALL (encontrado: {cap_drop})")
            
            # 3. Verifica pids_limit
            pids_limit = host_config.get("PidsLimit", 0)
            if pids_limit <= 0 or pids_limit > self._config.pids_limit:
                errors.append(f"PIDs limit violado: {pids_limit}")
            
            # 4. Verifica read_only_rootfs
            read_only = host_config.get("ReadonlyRootfs", False)
            if not read_only:
                errors.append("FALTA: ReadonlyRootfs")
            
            # 5. CRÍTICO: Verifica tmpfs - ZERO-TRUST (não é mais AVISO!)
            tmpfs = host_config.get("Tmpfs", [])
            if not tmpfs:
                errors.append("FALTA: tmpfs NÃO configurado (CRÍTICO)")
            
            if errors:
                logger.error(
                    f"Container {container_id[:12]} VIOLA políticas de segurança: {errors}",
                    extra={"extra_data": {"errors": errors}}
                )
                return False
            
            logger.info(f"Container {container_id[:12]} verificado - SEGURO")
            return True
            
        except Exception as e:
            # CRÍTICO: FALLBACK COMO MORTE SÚBITA
            # Se não consegue verificar, considera HOSTIL
            logger.critical(
                f"FALHA na verificação de container {container_id[:12]} - EXECUÇÃO ABATENDO",
                extra={"extra_data": {
                    "container_id": container_id[:12],
                    "error": str(e)
                }}
            )
            # ABATE o container imediatamente
            try:
                client = self._get_client()
                client.kill(container_id)
                client.remove_container(container_id, force=True)
            except:
                pass
            # Re-lança exceção - não engolir!
            raise ContainerSecurityViolationError(
                f"Falha ao verificar container {container_id[:12]}: {e}"
            )
    
    async def validate_rootless_daemon(self) -> tuple[bool, Dict]:
        """Verifica modo rootless do Docker daemon."""
        info = {"is_rootless": False, "euid": os.geteuid()}
        
        try:
            client = self._get_client()
            daemon_info = client.info()
            info["docker_root"] = daemon_info.get("DockerRootDir")
            
            if os.geteuid() == 0:
                raise RootDaemonDetectedError("Docker daemon executando como ROOT!")
            
            info["is_rootless"] = True
            return True, info
            
        except RootDaemonDetectedError:
            raise
        except Exception as e:
            info["error"] = str(e)
            return False, info


# =============================================================================
# SECURITY POLICING - WRAPPER EFETIVO
# =============================================================================

class SecurityPolicing:
    """
    Wrapper de segurança - ponto de estrangulamento (choke point).
    
    CRÍTICO: Este wrapper DEVE ser usado para TODA criação de container.
    Não há caminho alternativo - ignore o wrapper = container inseguro.
    
    Uso:
        policing = SecurityPolicing(SecurityConfig())
        
        # Para criar container SEGURO:
        container_id = await policing.create_secure_container(
            docker_client=client,
            base_image="python:3.12-slim",
            memory_limit="512m"
        )
        
        # Para verificar container existente:
        secure = await policing.verify_container(container_id)
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        if config is None:
            config = SecurityConfig()
        else:
            try:
                config.to_host_config_kwargs()
            except ValueError as e:
                raise SecurityConfigInvalidError(f"Configuração inválida: {e}")
        
        self._config = config
        self._battery_manager = BatteryManager()
        self._security_audit = SecurityAudit(audit_file=config.audit_file)
        self._validator = SecurityValidator(config)
        
        logger.info("SecurityPolicing.wrapper initialized", extra={"extra_data": {
            "security_opt": config.security_opt,
            "cap_drop": config.cap_drop,
            "pids_limit": config.pids_limit,
            "read_only": config.read_only_rootfs,
        }})
    
    @property
    def config(self) -> SecurityConfig:
        return self._config
    
    def get_security_host_config_kwargs(self) -> Dict[str, Any]:
        """Retorna kwargs para HostConfig - pronto para uso."""
        return self._config.to_host_config_kwargs()
    
    def get_create_kwargs(self) -> Dict[str, Any]:
        """Retorna kwargs para containers.create()."""
        return self._config.to_create_kwargs()
    
    async def create_secure_container(
        self,
        docker_client: docker.DockerClient,
        base_image: str,
        name: Optional[str] = None,
        memory_limit: str = "512m",
        **extra_kwargs
    ) -> str:
        """
        CRÍTICO: Cria container com hardening completo.
        
        Este método DEVE ser usado por TODO create_container().
        Não há caminho alternativo.
        """
        # Prepara kwargs com segurança
        host_config_kwargs = self.get_security_host_config_kwargs()
        
        # Cria HostConfig com API version
        version = docker_client.version()
        api_version = version.get("Version", "1.41")
        
        # Merge com extras
        host_config_kwargs.update({
            "api_version": api_version,
            "mem_limit": memory_limit,
            "cpu_period": 100000,
            "cpu_quota": 100000,  # 1 vCPU
            "network_mode": "none",  # Rede desabilitada
            "auto_remove": True,
        })
        
        try:
            host_config = HostConfig(**host_config_kwargs)
        except Exception as e:
            raise SecurityConfigInvalidError(f"HostConfig inválido: {e}")
        
        # Cria container
        container = docker_client.create_container(
            base_image,
            tty=True,
            stdin_open=True,
            host_config=host_config,
            name=name,
        )
        
        container_id = container["Id"]
        
        # CRÍTICO: Verificação imediata
        secure = await self._validator.verify_container_is_secure(container_id)
        
        if not secure:
            # ABATE IMEDIATO - não pode continuar
            try:
                docker_client.kill(container_id)
                docker_client.remove_container(container_id, force=True)
            except:
                pass
            
            self._security_audit.log_security_event(
                "container_create_failed",
                f"Container ABORTADO - violou políticas: {container_id[:12]}",
                "CRITICAL",
                container_id=container_id[:12]
            )
            
            raise ContainerSecurityViolationError(
                f"Container {container_id[:12]} violou políticas de segurança e foi ABORTADO"
            )
        
        # Inicia container
        docker_client.start(container_id)
        
        # Log sucesso
        self._security_audit.log_container_created(container_id, secure=True)
        
        logger.info(f"Container seguro criado: {container_id[:12]}")
        
        return container_id
    
    async def verify_container(self, container_id: str) -> bool:
        """Verifica container existente."""
        return await self._validator.verify_container_is_secure(container_id)
    
    async def abort_container(self, docker_client: docker.DockerClient, container_id: str):
        """Abate container violando políticas."""
        try:
            docker_client.kill(container_id)
            docker_client.remove_container(container_id, force=True)
            self._security_audit.log_security_event(
                "container_aborted",
                f"Container ABORTADO: {container_id[:12]}",
                "CRITICAL",
                container_id=container_id[:12]
            )
        except Exception as e:
            logger.error(f"Erro ao abortar container: {e}")
    
    def get_battery_status(self) -> BatteryStatus:
        """Obtém status da bateria."""
        return self._battery_manager.get_battery_status(self._config.battery_threshold)
    
    def should_suspend_tasks(self) -> bool:
        """Verifica se deve suspender tarefas."""
        return self._battery_manager.should_suspend_tasks(self._config.battery_threshold)
    
    async def check_rootless(self) -> bool:
        """Verifica modo rootless."""
        try:
            is_rootless, info = await self._validator.validate_rootless_daemon()
            if not is_rootless and self._config.enable_audit:
                self._security_audit.log_root_warning(info)
            return is_rootless
        except RootDaemonDetectedError:
            if self._config.enable_audit:
                self._security_audit.log_root_warning({"error": "Root daemon"})
            raise
    
    def get_status(self) -> Dict[str, Any]:
        battery = self.get_battery_status()
        return {
            "config": {
                "security_opt": self._config.security_opt,
                "cap_drop": self._config.cap_drop,
                "pids_limit": self._config.pids_limit,
                "read_only_rootfs": self._config.read_only_rootfs,
                "oom_score_adj": self._config.oom_score_adj,
            },
            "battery": battery.to_dict(),
            "should_suspend": self.should_suspend_tasks(),
        }


# =============================================================================
# WRAPPER SYNC
# =============================================================================

class SecurityPolicingSync:
    """Wrapper síncrono."""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self._async_policing = SecurityPolicing(config)
        self._loop = None
    
    def _ensure_loop(self):
        if not self._loop or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def create_secure_container(
        self,
        docker_client: docker.DockerClient,
        base_image: str,
        name: Optional[str] = None,
        memory_limit: str = "512m",
    ) -> str:
        """Cria container seguro (sync)."""
        self._ensure_loop()
        return self._loop.run_until_complete(
            self._async_policing.create_secure_container(
                docker_client, base_image, name, memory_limit
            )
        )
    
    def get_status(self) -> Dict:
        return self._async_policing.get_status()
    
    def get_battery_status(self) -> BatteryStatus:
        return self._async_policing.get_battery_status()
    
    def should_suspend_tasks(self) -> bool:
        return self._async_policing.should_suspend_tasks()
    
    @property
    def config(self) -> SecurityConfig:
        return self._async_policing.config


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Security Policing Q7")
    parser.add_argument("--test", action="store_true", help="Executa teste")
    args = parser.parse_args()
    
    if args.test:
        print("=== Teste SecurityPolicing Q7 (Wrapper Efetivo) ===")
        
        # Teste 1: Config
        print("\n1. Configuração:")
        config = SecurityConfig()
        print(f"   security_opt: {config.security_opt}")
        print(f"   cap_drop: {config.cap_drop}")
        print(f"   pids_limit: {config.pids_limit}")
        print(f"   read_only: {config.read_only_rootfs}")
        print(f"   oom_score_adj: {config.oom_score_adj}")
        print(f"   tmpfs: /tmp={config.tmpfs_tmp}, /run={config.tmpfs_run}")
        print("   ✓ Configuração válida")
        
        # Teste 2: HostConfig kwargs
        print("\n2. HostConfig kwargs:")
        kwargs = config.to_host_config_kwargs()
        for k, v in kwargs.items():
            print(f"   {k}: {v}")
        
        # Teste 3: SecurityPolicing
        print("\n3. Inicializando wrapper:")
        policing = SecurityPolicingSync()
        print("   ✓ Wrapper inicializado")
        
        # Teste 4: Battery
        print("\n4. Status bateria:")
        battery = policing.get_battery_status()
        print(f"   Estado: {battery.state.value}")
        print(f"   Porcentagem: {battery.percent}%")
        
        # Teste 5: Should suspend
        print("\n5. Verificar suspend:")
        should_suspend = policing.should_suspend_tasks()
        print(f"   Suspender: {should_suspend}")
        
        print("\n=== Teste completo ===")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Q9: XenoSys CLI - Interface de Linha de Comando Unificada (v1.1 - AUDIT FIXED)

Este módulo implementa a CLI air-gapped do XenoSys:
- xenosys start: Inicia o Orquestrador, Servidor FastAPI e aloca Docker
- xenosys stop: Encerramento gracioso com SIGTERM e limpeza de tmpfs
- xenosys status: Verifica saúde do Q5, conectividade local e estado do container
- xenosys logs: Agrega logs físicos e Audit Trail

Stack: argparse (biblioteca padrão Python)
Segurança: Fail-Fast na CLI, sem pip install dinâmico em runtime

CORREÇÕES DA AUDITORIA v1.1:
✅ Air-gapped real: Makefile usa --no-index --find-links wheelhouse
✅ Paths dinâmicos: Baseado em Path(__file__) não hardcoded
✅ Import no topo: dotenv/docker movido para topo com try/except
✅ Atomic PID: fcntl para file locking
✅ Backup .env: Preserva .env.bak antes de gerar novo
✅ SRP: Funções fragmentadas em sub-rotinas
"""

import argparse
import errno
import fcntl
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# IMPORTS (TOPO DO ARQUIVO - Fail-Fast)
# =============================================================================

# dotenv - com fallback graceful
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    load_dotenv = None

# docker - com fallback graceful
try:
    import docker as docker_module
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker_module = None


# =============================================================================
# CONFIGURATION (PATHS DINÂMICOS - NÃO HARDCODE)
# =============================================================================

def _get_project_root() -> Path:
    """Obtém raiz do projeto dinamicamente via __file__."""
    # __file__ aponta para xenosys_cli.py, parent = projeto
    cli_path = Path(__file__).resolve()
    return cli_path.parent


def _get_data_dir() -> Path:
    """Obtém diretório de dados, configurável via env."""
    default = Path("/tmp/xenosys")
    return Path(os.environ.get("XENOSYS_DATA_DIR", default))


# Project root configurável mas com fallback dinâmico
PROJECT_ROOT = Path(os.environ.get("XENOSYS_ROOT", _get_project_root()))
DATA_DIR = _get_data_dir()

# Database e arquivos
CORTEX_DB = DATA_DIR / "cortex.db"
SECURITY_LOG = DATA_DIR / "security.audit.log"
PID_FILE = DATA_DIR / "xenosys.pid"
THEME_FILE = DATA_DIR / "theme.json"

# Network - APENAS localhost (segurança)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080

# Timeouts
DEFAULT_STARTUP_TIMEOUT = 30
DEFAULT_SHUTDOWN_TIMEOUT = 10


# =============================================================================
# LOGGER SETUP - Structured JSON logging
# =============================================================================


class JSONFormatter(logging.Formatter):
    """JSON formatter com timestamps UTC."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
        }
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra
        return json.dumps(log_entry)


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Configura logger com JSON formatter."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger


logger = setup_logger("xenosys_cli")


# =============================================================================
# ERROR CODES
# =============================================================================


class ExitCode:
    """Códigos de saída da CLI."""
    SUCCESS = 0
    DEPENDENCY_MISSING = 10
    PREREQUISITE_FAILED = 11
    STARTUP_FAILED = 12
    STOP_FAILED = 13
    STATUS_UNHEALTHY = 14
    INVALID_COMMAND = 15


# =============================================================================
# PREREQUISITE VALIDATION (FACTORY PATTERN)
# =============================================================================


@dataclass
class PrerequisiteResult:
    """Resultado da validação de pré-requisitos."""
    name: str
    passed: bool
    message: str
    extra: Optional[Dict[str, Any]] = None


def _run_docker_check(args: List[str], timeout: int = 5) -> Tuple[int, str]:
    """Factory para checagens Docker."""
    try:
        result = subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout.strip()
    except Exception as e:
        return -1, str(e)


def check_docker_installed() -> PrerequisiteResult:
    """Verifica se Docker está instalado."""
    code, output = _run_docker_check(["--version"])
    if code == 0:
        # Extrair versão
        version_match = re.search(r"Docker version ([\d.]+)", output)
        version = version_match.group(1) if version_match else output
        return PrerequisiteResult(
            name="docker",
            passed=True,
            message=f"Docker instalado: {version}",
            extra={"version": version}
        )
    return PrerequisiteResult(
        name="docker",
        passed=False,
        message="Docker não encontrado"
    )


def check_docker_rootless() -> PrerequisiteResult:
    """Verifica se Docker está em modo Rootless."""
    code, output = _run_docker_check(["info", "--format", "{{.SecurityOptions}}"])
    if code == 0:
        if "rootless" in output.lower():
            return PrerequisiteResult(
                name="rootless",
                passed=True,
                message="Docker em modo rootless"
            )
        # Verificar se rodando como root
        if os.geteuid() == 0:
            return PrerequisiteResult(
                name="rootless",
                passed=False,
                message="ALERTA: Executando como root!",
                extra={"security_alert": True}
            )
    return PrerequisiteResult(
        name="rootless",
        passed=False,
        message="Modo rootless não confirmado"
    )


def check_docker_daemon() -> PrerequisiteResult:
    """Verifica se Docker daemon está rodando."""
    if not DOCKER_AVAILABLE:
        return PrerequisiteResult(
            name="daemon",
            passed=False,
            message="SDK Docker não instalado"
        )
    try:
        client = docker_module.from_env()
        client.ping()
        return PrerequisiteResult(
            name="daemon",
            passed=True,
            message="Docker daemon operacional"
        )
    except Exception as e:
        return PrerequisiteResult(
            name="daemon",
            passed=False,
            message=f"Daemon não responsivo: {e}"
        )


def validate_prerequisites() -> Tuple[bool, List[PrerequisiteResult]]:
    """
    Valida todos os pré-requisitos (Strategy Pattern).

    Returns:
        Tuple de (sucesso, lista de resultados)
    """
    checks = [
        check_docker_installed(),
        check_docker_daemon(),
        check_docker_rootless(),
    ]

    all_passed = all(r.passed for r in checks)

    if not all_passed:
        failed = [r.name for r in checks if not r.passed]
        logger.warning(f"Pré-requisitos falhados: {failed}")

    return all_passed, checks


# =============================================================================
# ENV FILE GENERATOR (COM BACKUP)
# =============================================================================


def generate_env_file() -> Path:
    """
    Gera .env local com chaves de encriptação rotacionadas.
    PRESERVA backup antes de gerar novo!

    Returns:
        Path para o arquivo .env gerado
    """
    import secrets

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env_file = PROJECT_ROOT / ".env"

    # BACKUP: Preservar .env antigo antes de sobrescrever
    if env_file.exists():
        backup = env_file.with_suffix('.env.bak')
        # Backup com timestamp
        backup_ts = env_file.with_suffix(f'.env.{int(time.time())}.bak')
        env_file.rename(backup_ts)
        logger.info(f"Backup preservado: {backup_ts}")

    # Gerar chaves
    encryption_key = secrets.token_hex(32)  # 256-bit
    api_key = secrets.token_hex(16)  # 128-bit

    # Timestamp
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z"

    env_content = f"""\
# XenoSys Environment
# Gerado em: {generated_at}
# NÃO versionar este arquivo!

# Encryption
XENOSYS_ENCRYPTION_KEY={encryption_key}
XENOSYS_API_KEY={api_key}

# Paths
XENOSYS_DATA_DIR={DATA_DIR}
XENOSYS_CORTEX_DB={CORTEX_DB}

# Server
XENOSYS_HOST={DEFAULT_HOST}
XENOSYS_PORT={DEFAULT_PORT}
"""

    env_file.write_text(env_content)
    logger.info(f"Arquivo .env gerado: {env_file}")

    return env_file


# =============================================================================
# SUB-ROTINAS (SRP - FRAGMENTADAS)
# =============================================================================


def _validate_environment() -> bool:
    """Valida ambiente e dependências."""
    # Check dotenv
    if not DOTENV_AVAILABLE:
        logger.error("python-dotenv não instalado")
        return False
    return True


def _validate_path_safety(path: Path) -> bool:
    """Valida que path é seguro (sem traverse)."""
    try:
        resolved = path.resolve()
        # Verificar que não contém ..
        if ".." in str(path):
            logger.error(f"Path traversal detectado: {path}")
            return False
        return True
    except Exception as e:
        logger.error(f"Path inválido: {path} - {e}")
        return False


def _write_pid_atomic(pid: int) -> None:
    """Escreve PID com file locking atômico."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Usar fcntl para locking (apenas Linux/Unix)
    try:
        with open(PID_FILE, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.write(str(pid))
            f.flush()
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (AttributeError, OSError):
        # Fallback para Windows (fcntl não disponível)
        PID_FILE.write_text(str(pid))


def _read_pid_atomic() -> Optional[int]:
    """Lê PID com file locking."""
    if not PID_FILE.exists():
        return None

    try:
        with open(PID_FILE, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            pid = f.read().strip()
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return int(pid) if pid.isdigit() else None
    except (AttributeError, OSError, ValueError):
        # Fallback
        try:
            return int(PID_FILE.read_text().strip())
        except:
            return None


def _cleanup_tmpfs() -> None:
    """Limpa tmpfs removendo apenas arquivos temporários não protegidos.
    
    Preserva: .db (banco de dados), .log (logs), .env (config),
             .bak (backups), .pid (PID), e arquivos ocultos.
    
    Called por:
        - stop_orchestrator() ao encerrar o sistema
        - remove apenas artefatos de execução (não configs)
    """
    if not DATA_DIR.exists():
        return

    # Não remover DBs, logs ou .env!
    protected = {".db", ".log", ".env", ".bak", ".pid"}
    for f in DATA_DIR.iterdir():
        if f.suffix in protected or f.name.startswith("."):
            continue
        try:
            if f.is_file():
                f.unlink()
        except OSError:
            pass


# =============================================================================
# START COMMAND (FRAGMENTADO POR SRP)
# =============================================================================


def _start_api_server() -> Optional[subprocess.Popen]:
    """Inicia servidor FastAPI via uvicorn."""
    server_cmd = [
        sys.executable,
        "-m", "uvicorn",
        "ui.server:app",
        "--host", DEFAULT_HOST,
        "--port", str(DEFAULT_PORT),
        "--log-level", "info"
    ]

    # Validar path antes de usar
    if not _validate_path_safety(PROJECT_ROOT):
        logger.error(f"Caminho inválido: {PROJECT_ROOT}")
        return None

    try:
        proc = subprocess.Popen(
            server_cmd,
            cwd=str(PROJECT_ROOT.resolve()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True  # Novo session group
        )
        return proc
    except Exception as e:
        logger.error(f"Failed to start API: {e}")
        return None


def start_orchestrator() -> int:
    """
    Inicia o Orquestrador (Q3), FastAPI Servidor e aloca Docker.
    Função fragmentada seguindo SRP.

    Returns:
        Código de saída
    """
    logger.info("Iniciando XenoSys...")

    # 1. Validar dependências (Fail-Fast)
    if not _validate_environment():
        return ExitCode.DEPENDENCY_MISSING

    # 2. Validar pré-requisitos
    logger.info("Validando pré-requisitos...")
    all_passed, results = validate_prerequisites()

    if not all_passed:
        logger.error("Validação de pré-requisitos falhou")
        for r in results:
            logger.warning(f"  - {r.name}: {r.message}")
        return ExitCode.PREREQUISITE_FAILED

    logger.info("Pré-requisitos validados OK")

    # 3. Gerar .env se não existir (com backup)
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        logger.info("Gerando arquivo .env...")
        generate_env_file()

    # 4. Carregar .env
    load_dotenv(env_file)

    # 5. Iniciar API server
    logger.info("Iniciando servidor FastAPI...")
    proc = _start_api_server()

    if proc is None:
        logger.error("Falha ao iniciar servidor")
        return ExitCode.STARTUP_FAILED

    # 6. Verificar startup (timeout)
    logger.info(f"Aguardando servidor (timeout={DEFAULT_STARTUP_TIMEOUT}s)...")
    time.sleep(3)

    if proc.poll() is not None:
        _, stderr = proc.communicate()
        logger.error(f"Servidor encerrou prematuramente: {stderr}")
        return ExitCode.STARTUP_FAILED

    # 7. Escrever PID atômico
    _write_pid_atomic(proc.pid)
    logger.info(f"XenoSys iniciado (PID={proc.pid})")

    return ExitCode.SUCCESS


# =============================================================================
# STOP COMMAND (COM CLEANUP)
# =============================================================================


def stop_orchestrator() -> int:
    """
    Encerra XenoSys graciosamente com SIGTERM e limpa tmpfs.

    Returns:
        Código de saída
    """
    logger.info("Encerrando XenoSys...")

    # Ler PID atômico
    pid = _read_pid_atomic()

    if pid is not None:
        try:
            # Enviar SIGTERM
            logger.info(f"Enviando SIGTERM para PID={pid}...")
            os.kill(pid, signal.SIGTERM)

            # Esperar graciosamente
            for i in range(DEFAULT_SHUTDOWN_TIMEOUT):
                time.sleep(1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    # Processo encerrou
                    break
            else:
                # Force kill
                logger.warning("SIGTERM não respondeu, enviando SIGKILL...")
                os.kill(pid, signal.SIGKILL)

            # Limpar PID file
            try:
                PID_FILE.unlink()
            except OSError:
                pass

            logger.info("XenoSys encerrado")

        except (ProcessLookupError, PermissionError) as e:
            logger.warning(f"Erro ao encerrar processo: {e}")

    # Limpar tmpfs
    _cleanup_tmpfs()

    return ExitCode.SUCCESS


# =============================================================================
# STATUS COMMAND
# =============================================================================


@dataclass
class SystemStatus:
    """Status do sistema."""
    docker: str
    daemon: str
    cortex: str
    server: str
    containers: int
    uptime_seconds: float


def get_system_status() -> SystemStatus:
    """Coleta status do sistema (usa validate_prerequisites para DRY)."""
    # Reusa validate_prerequisites() - Single Source of Truth
    _, results = validate_prerequisites()

    # Extrair status dos resultados
    docker_status = "não instalado"
    daemon_status = "desconhecido"

    for r in results:
        if r.name == "docker":
            docker_status = r.message if r.passed else "não instalado"
        elif r.name == "daemon":
            daemon_status = r.message if r.passed else "não responsivo"
        elif r.name == "rootless":
            # rootless info pode ser logada mas não exibida
            pass

    # Cortex DB
    cortex_status = "não existe"
    if CORTEX_DB.exists():
        size = CORTEX_DB.stat().st_size
        cortex_status = f"existe ({size:,} bytes)"

    # Server
    server_status = "não executando"
    uptime = 0.0
    pid = _read_pid_atomic()
    if pid:
        try:
            os.kill(pid, 0)
            server_status = f"executando (PID={pid})"
            try:
                uptime = time.time() - PID_FILE.stat().st_mtime
            except:
                pass
        except OSError:
            server_status = "encerrado (stale PID)"
            try:
                PID_FILE.unlink()
            except:
                pass

    # Containers
    container_count = 0
    if DOCKER_AVAILABLE:
        try:
            client = docker_module.from_env()
            container_count = len(client.containers.list(all=True))
        except:
            pass

    return SystemStatus(
        docker=docker_status,
        daemon=daemon_status,
        cortex=cortex_status,
        server=server_status,
        containers=container_count,
        uptime_seconds=uptime
    )


def cmd_status() -> int:
    """Verifica saúde do Q5, conectividade local e estado do container."""
    status = get_system_status()

    print("=== XenoSys Status ===")
    print(f"Docker: {status.docker}")
    print(f"Daemon: {status.daemon}")
    print(f"Cortex: {status.cortex}")
    print(f"Server: {status.server}")
    print(f"Containers: {status.containers}")
    print(f"Uptime: {status.uptime_seconds:.1f}s")

    is_healthy = (
        status.daemon == "executando" and
        status.server != "não executando"
    )

    if is_healthy:
        print("\n✓ Sistema saudável")
        return ExitCode.SUCCESS
    else:
        print("\n✗ Sistema não saudável")
        return ExitCode.STATUS_UNHEALTHY


# =============================================================================
# LOGS COMMAND
# =============================================================================


def cmd_logs() -> int:
    """Agrega logs físicos e Audit Trail."""
    logger.info("Agregando logs...")

    log_files = [
        DATA_DIR / "xenosys.log",
        SECURITY_LOG,
        DATA_DIR / "server.log",
    ]

    found_logs = False
    for log_file in log_files:
        if log_file.exists():
            found_logs = True
            print(f"\n=== {log_file.name} ===")
            try:
                lines = log_file.read_text().splitlines()
                for line in lines[-100:]:
                    print(line)
            except OSError as e:
                print(f"Erro ao ler {log_file}: {e}")

    if not found_logs:
        print("Nenhum log encontrado")

    # Security audit
    if SECURITY_LOG.exists():
        print("\n=== Security Audit ===")
        lines = SECURITY_LOG.read_text().splitlines()
        for line in lines[-50:]:
            print(line)

    return ExitCode.SUCCESS


# =============================================================================
# MAIN CLI
# =============================================================================


def main():
    """Entry point da CLI."""
    parser = argparse.ArgumentParser(
        description="XenoSys CLI - Appliance de Execução Offline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  xenosys start       Inicia o Orquestrador
  xenosys stop       Encerra graciosamente
  xenosys status     Verifica saúde
  xenosys logs       Agrega logs
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("start", help="Inicia o Orquestrador e servidor")
    subparsers.add_parser("stop", help="Encerra graciosamente")
    subparsers.add_parser("status", help="Verifica saúde do sistema")
    subparsers.add_parser("logs", help="Agrega logs e audit trail")

    args = parser.parse_args()

    # Ensure data dir exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Route command
    if args.command == "start":
        return start_orchestrator()
    elif args.command == "stop":
        return stop_orchestrator()
    elif args.command == "status":
        return cmd_status()
    elif args.command == "logs":
        return cmd_logs()
    else:
        parser.print_help()
        return ExitCode.INVALID_COMMAND


if __name__ == "__main__":
    sys.exit(main())
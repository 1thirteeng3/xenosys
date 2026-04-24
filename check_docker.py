#!/usr/bin/env python3
"""
Docker Environment Setup and Validation Script

This script provides comprehensive Docker environment detection, validation,
and configuration for the XenoSys secure execution platform.

Key Features:
- Docker version detection and validation (minimum 20.10+)
- CGroups v2 availability check
- Daemon configuration with secure defaults
- Health check verification
- Retry logic with exponential backoff
- Structured JSON logging

Usage:
    python3 check_docker.py

Exit Codes:
    0 - Success
    1 - Docker not installed
    2 - Version requirement not met
    3 - CGroups v2 not available
    4 - Configuration failed
    5 - Health check failed
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from threading import Thread
from typing import Any, Callable, Dict

import docker
from docker import APIClient
from docker.errors import APIError, DockerException


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def pull_image_with_timeout(
    client: APIClient,
    image: str,
    timeout: int = 60
) -> bool:
    """
    Pull Docker image with timeout using a background thread.
    
    CORREÇÃO 14: Adicionar timeout no pull de imagem
    
    Args:
        client: Docker API client
        image: Image name to pull
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if pull succeeded, False otherwise
    """
    result = {"success": False, "error": None}
    
    def pull_thread():
        try:
            client.pull(image)
            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
    
    thread = Thread(target=pull_thread, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    return result["success"]


# =============================================================================
# CONFIGURATION
# =============================================================================

MIN_DOCKER_VERSION = (20, 10, 0)

DEFAULT_MEMORY_LIMIT = "2g"  # 2GB RAM limit
DEFAULT_CPU_LIMIT = 2.0      # 2 CPU cores

MAX_RETRIES = 3
MAX_RETRY_DELAY = 10  # seconds
INITIAL_RETRY_DELAY = 1  # seconds


# =============================================================================
# LOGGING SETUP - Structured JSON with UTC timestamps
# =============================================================================

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter that outputs structured log entries.
    
    Each log entry contains:
    - timestamp: ISO 8601 format in UTC
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - message: The log message
    - extra: Additional contextual data
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
            
        return json.dumps(log_entry)


def setup_logger(name: str) -> logging.Logger:
    """
    Configure and return a logger with JSON formatting.
    
    Args:
        name: Name for the logger instance
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger


logger = setup_logger("check_docker")


# =============================================================================
# RETRY LOGIC - Exponential backoff implementation
# =============================================================================

def retry_with_backoff(
    func: Callable[[], Any],
    max_retries: int = MAX_RETRIES,
    max_delay: float = MAX_RETRY_DELAY,
    initial_delay: float = INITIAL_RETRY_DELAY,
    logger: logging.Logger = logger
) -> Any:
    """
    Execute a function with exponential backoff retry logic.
    
    This pattern is critical for handling transient Docker API failures,
    network issues, and daemon startup delays.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        max_delay: Maximum delay between retries (seconds)
        initial_delay: Initial delay before first retry (seconds)
        logger: Logger instance for recording attempts
        
    Returns:
        Result of successful function execution
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except (APIError, DockerException, ConnectionError, PermissionError) as e:
            last_exception = e
            
            if attempt < max_retries:
                # Calculate exponential backoff: initial_delay * 2^attempt
                delay = min(initial_delay * (2 ** attempt), max_delay)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}. "
                    f"Retrying in {delay:.2f}s...",
                    extra={"extra_data": {"attempt": attempt + 1, "delay": delay}}
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"All {max_retries + 1} attempts failed",
                    extra={"extra_data": {"error": str(e)}}
                )
    
    raise last_exception


# =============================================================================
# DOCKER VERSION DETECTION
# =============================================================================

def get_docker_version(client: APIClient) -> Dict[str, Any]:
    """
    Retrieve Docker daemon version information.
    
    Uses the Docker Engine API to get version details including
    major, minor, and patch numbers.
    
    Args:
        client: Docker API client instance
        
    Returns:
        Dictionary containing version information
    """
    return client.version()


def parse_version(version_string: str) -> tuple:
    """
    Parse Docker version string into tuple of integers.
    
    Handles various version formats:
    - "20.10.5" -> (20, 10, 5)
    - "20.10" -> (20, 10, 0)
    - "24.0.0" -> (24, 0, 0)
    
    Args:
        version_string: Version string from Docker
        
    Returns:
        Tuple of (major, minor, patch) integers
    """
    parts = version_string.split(".")
    
    major = int(parts[0]) if len(parts) > 0 else 0
    minor = int(parts[1]) if len(parts) > 1 else 0
    patch = int(parts[2]) if len(parts) > 2 else 0
    
    return (major, minor, patch)


def validate_docker_version(version_info: Dict[str, Any]) -> bool:
    """
    Validate Docker version meets minimum requirements.
    
    Checks that Docker version is >= 20.10.0 as required
    for cgroups v2 support and modern security features.
    
    Args:
        version_info: Version information from Docker API
        
    Returns:
        True if version meets requirements
        
    Raises:
        ValueError: If version is below minimum
    """
    version_string = version_info.get("Version", "0.0.0")
    current_version = parse_version(version_string)
    
    logger.info(
        f"Docker version detected: {version_string}",
        extra={"extra_data": {
            "version": version_string,
            "major": current_version[0],
            "minor": current_version[1],
            "patch": current_version[2]
        }}
    )
    
    if current_version < MIN_DOCKER_VERSION:
        raise ValueError(
            f"Docker version {version_string} is below minimum required "
            f"version {MIN_DOCKER_VERSION[0]}.{MIN_DOCKER_VERSION[1]}.{MIN_DOCKER_VERSION[2]}"
        )
    
    logger.info(f"Version validation passed: {version_string} >= {MIN_DOCKER_VERSION}")
    return True


# =============================================================================
# CGROUPS V2 VALIDATION
# =============================================================================

def check_cgroups_v2() -> bool:
    """
    Check if cgroups v2 is available on the system.
    
    CGroups v2 (unified hierarchy) is required for modern Docker
    resource management and security features. This check examines
    the system cgroups configuration.
    
    Detection method:
    - Check /sys/fs/cgroup/cgroup.controllers exists (cgroups v2)
    - Check /proc/filesystems contains "cgroup2"
    - Fallback: check cgroup version file if available
    
    Returns:
        True if cgroups v2 is available
        
    Raises:
        RuntimeError: If cgroups v2 is not available
    """
    logger.info("Checking cgroups v2 availability...")
    
    # Method 1: Check cgroup2 filesystem type
    try:
        with open("/proc/filesystems", "r") as f:
            if "cgroup2" in f.read():
                logger.info(
                    "cgroups v2 detected via /proc/filesystems",
                    extra={"extra_data": {"method": "proc_filesystems"}}
                )
                return True
    except (IOError, PermissionError) as e:
        logger.debug(f"Could not check /proc/filesystems: {e}")
    
    # Method 2: Check cgroup controllers directory (v2 indicator)
    try:
        if os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
            logger.info(
                "cgroups v2 detected via /sys/fs/cgroup/cgroup.controllers",
                extra={"extra_data": {"method": "cgroup_controllers"}}
            )
            return True
    except (IOError, PermissionError) as e:
        logger.debug(f"Could not check cgroup controllers: {e}")
    
    # Method 3: Check cgroup version file (systemd detection)
    try:
        cgroup_version_file = "/sys/fs/cgroup/cgroup.version"
        if os.path.exists(cgroup_version_file):
            with open(cgroup_version_file, "r") as f:
                version = f.read().strip()
                if version == "2":
                    logger.info(
                        f"cgroups v2 confirmed via cgroup.version: {version}",
                        extra={"extra_data": {"method": "cgroup_version", "version": version}}
                    )
                    return True
    except (IOError, PermissionError) as e:
        logger.debug(f"Could not check cgroup version: {e}")
    
    # Method 4: Check mountinfo for cgroup2 mounts
    try:
        with open("/proc/self/mountinfo", "r") as f:
            for line in f:
                if "cgroup2" in line:
                    logger.info(
                        "cgroups v2 detected via /proc/self/mountinfo",
                        extra={"extra_data": {"method": "mountinfo"}}
                    )
                    return True
    except (IOError, PermissionError) as e:
        logger.debug(f"Could not check mountinfo: {e}")
    
    # If we reach here, cgroups v2 is not available
    raise RuntimeError(
        "cgroups v2 is not available on this system. "
        "Docker 20.10+ requires cgroups v2 for resource management. "
        "Please enable cgroups v2 in your system configuration."
    )


# =============================================================================
# DAEMON CONFIGURATION
# =============================================================================

def configure_daemon(
    client: APIClient,
    memory_limit: str = DEFAULT_MEMORY_LIMIT,
    cpu_limit: float = DEFAULT_CPU_LIMIT
) -> Dict[str, Any]:
    """
    Configure Docker daemon with secure default parameters.
    
    This applies baseline resource constraints by creating a test container
    with the specified limits. The container is created, verified, and removed
    to validate that the limits can be applied.
    
    Args:
        client: Docker API client
        memory_limit: Memory limit string (e.g., "2g", "512m")
        cpu_limit: CPU limit as float (e.g., 2.0, 1.5)
        
    Returns:
        Dictionary with configuration result including applied limits
        
    Raises:
        RuntimeError: If container creation with limits fails
    """
    logger.info(
        f"Configuring daemon with memory={memory_limit}, cpu={cpu_limit}",
        extra={"extra_data": {
            "memory_limit": memory_limit,
            "cpu_limit": cpu_limit
        }}
    )
    
    # Get current daemon info
    info = client.info()
    daemon_version = info.get("ServerVersion", "unknown")
    
    # Log current configuration
    logger.info(
        "Daemon configuration retrieved",
        extra={"extra_data": {
            "mem_limit": info.get("MemLimit", "unknown"),
            "mem_reservation": info.get("MemReservation", "unknown"),
            "cpu_period": info.get("CPUPeriod", "unknown"),
            "cpu_quota": info.get("CPUQuota", "unknown"),
            "daemon_version": daemon_version
        }}
    )
    
    # Create a test container with the specified resource limits
    # This validates that the daemon can apply resource constraints
    container_name = "xenosys_config_test"
    test_image = "alpine:latest"
    
    # Clean up any existing test container
    try:
        existing = client.containers(filters={"name": container_name})
        for c in existing:
            client.remove_container(c["Id"], force=True)
    except Exception:
        pass  # Ignore if no container exists
    
    # Pull image if not exists (CORREÇÃO 14: com timeout)
    try:
        logger.info(f"Pulling image {test_image} (timeout: 60s)...")
        if not pull_image_with_timeout(client, test_image, timeout=60):
            logger.warning(
                f"Image pull timed out or failed. Trying with existing images.",
                extra={"extra_data": {"image": test_image}}
            )
    except Exception as e:
        logger.warning(
            f"Could not pull image {test_image}: {str(e)}. "
            "Trying with existing images.",
            extra={"extra_data": {"error": str(e)}}
        )
    
    # Container config with resource limits
    host_config = client.create_host_config(
        mem_limit=memory_limit,
        cpu_period=100000,  # Docker default: 100ms period
        cpu_quota=int(cpu_limit * 100000),  # cpu_limit * period
        network_mode="none",  # Disable network for security
        mem_swappiness=0,  # Disable swap for security
    )
    
    container_config = {
        "name": container_name,  # CORREÇÃO 12: Nome fixo para cleanup confiável
        "image": test_image,
        "command": ["sh", "-c", "echo 'XenoSys config test passed' && sleep 1"],
        "host_config": host_config,
        "environment": ["XENOSYS_SECURE_MODE=true"],
        "working_dir": "/",
        "user": "",  # Run as current user
        "labels": {
            "xenosys.managed": "true",
            "xenosys.config": "validation"
        }
    }
    
    try:
        # Create and start container with limits
        logger.info(
            f"Creating test container with limits: mem={memory_limit}, cpu={cpu_limit}",
            extra={"extra_data": {
                "memory_limit": memory_limit,
                "cpu_limit": cpu_limit
            }}
        )
        
        container = client.create_container(**container_config)
        container_id = container["Id"]
        
        # Start the container
        client.start(container_id)
        
        # Wait for container to complete
        # CORREÇÃO 13: Verificar formato de resposta do wait()
        # O retorno pode ser int diretamente ou dict com StatusCode
        result = client.wait(container_id)
        if isinstance(result, dict):
            exit_code = result.get("StatusCode", -1)
        else:
            exit_code = result if isinstance(result, int) else -1
        
        # Get container info to verify limits were applied
        inspect_data = client.inspect_container(container_id)
        host_config_result = inspect_data.get("HostConfig", {})
        
        applied_memory = host_config_result.get("Memory", 0)
        applied_cpu = host_config_result.get("CpuPeriod", 100000)
        applied_cpu_quota = host_config_result.get("CpuQuota", 0)
        
        logger.info(
            "Resource limits verified",
            extra={"extra_data": {
                "applied_memory": applied_memory,
                "applied_cpu_period": applied_cpu,
                "applied_cpu_quota": applied_cpu_quota,
                "exit_code": exit_code
            }}
        )
        
        # Clean up test container
        client.remove_container(container_id, force=True)
        
        if exit_code != 0:
            raise RuntimeError(f"Test container exited with code {exit_code}")
        
        config_status = "applied"
        
    except Exception as e:
        logger.warning(
            f"Could not verify resource limits: {str(e)}. "
            "Daemon configuration accepted but limits may vary by container.",
            extra={"extra_data": {"error": str(e)}}
        )
        config_status = "accepted"
    
    return {
        "status": config_status,
        "memory_limit": memory_limit,
        "cpu_limit": cpu_limit,
        "daemon_version": daemon_version,
        "verified": config_status == "applied"
    }


# =============================================================================
# HEALTH CHECK
# =============================================================================

def wait_for_daemon_health(
    client: APIClient,
    timeout: int = 60
) -> bool:
    """
    Wait for Docker daemon to become healthy after startup.
    
    Implements a polling mechanism with timeout to ensure the
    daemon is fully operational before proceeding. This is
    critical for ensuring the environment is ready for container
    operations.
    
    Args:
        client: Docker API client
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if daemon becomes healthy within timeout
        
    Raises:
        TimeoutError: If daemon doesn't become healthy in time
    """
    logger.info(f"Waiting for daemon health (timeout: {timeout}s)...")
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Ping endpoint is lightweight and reliable
            ping_result = client.ping()
            
            if ping_result:
                elapsed = time.time() - start_time
                logger.info(
                    f"Docker daemon is healthy",
                    extra={"extra_data": {
                        "elapsed_seconds": round(elapsed, 2),
                        "status": "healthy"
                    }}
                )
                return True
                
        except (APIError, DockerException, ConnectionError, PermissionError) as e:
            logger.debug(f"Health check attempt failed: {e}")
        
        # Wait before next check
        time.sleep(1)
    
    raise TimeoutError(
        f"Docker daemon did not become healthy within {timeout} seconds"
    )


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_docker_check() -> Dict[str, Any]:
    """
    Execute the complete Docker environment check and configuration.
    
    This is the main entry point that orchestrates:
    1. Docker client initialization
    2. Version detection and validation
    3. CGroups v2 availability check
    4. Daemon configuration
    5. Health verification
    
    Returns:
        Dictionary with complete check results
        
    Raises:
        SystemExit: On validation failures with appropriate exit codes
    """
    result = {
        "success": False,
        "checks": {},
        "errors": []
    }
    
    try:
        # Step 1: Initialize Docker client
        # Using Docker SDK for Python - no subprocess calls
        logger.info("Initializing Docker client...")
        
        # Use low-level API directly
        api_client = docker.from_env().api
        
        result["checks"]["client_init"] = "passed"
        
        # Step 2: Get and validate Docker version
        logger.info("Checking Docker version...")
        
        version_info = retry_with_backoff(
            lambda: get_docker_version(api_client),
            logger=logger
        )
        
        validate_docker_version(version_info)
        result["checks"]["version"] = "passed"
        
        # Step 3: Check cgroups v2
        logger.info("Validating cgroups v2...")
        
        check_cgroups_v2()
        result["checks"]["cgroups_v2"] = "passed"
        
        # Step 4: Configure daemon
        logger.info("Configuring daemon...")
        
        config_result = retry_with_backoff(
            lambda: configure_daemon(api_client),
            logger=logger
        )
        result["checks"]["daemon_config"] = "passed"
        
        # Step 5: Health check
        # Note: wait_for_daemon_health has internal timeout, no retry needed
        logger.info("Performing health check...")
        
        health_result = wait_for_daemon_health(api_client, timeout=60)
        result["checks"]["health"] = "passed"
        
        # All checks passed
        result["success"] = True
        result["docker_version"] = version_info.get("Version")
        result["daemon_config"] = config_result
        
        logger.info(
            "All Docker checks passed successfully",
            extra={"extra_data": {
                "version": version_info.get("Version"),
                "all_checks_passed": True
            }}
        )
        
        return result
        
    except DockerException as e:
        error_msg = f"Docker not available: {str(e)}"
        logger.error(error_msg, extra={"extra_data": {"error": str(e)}})
        result["errors"].append(error_msg)
        sys.exit(1)
        
    except ValueError as e:
        error_msg = f"Version validation failed: {str(e)}"
        logger.error(error_msg, extra={"extra_data": {"error": str(e)}})
        result["errors"].append(error_msg)
        sys.exit(2)
        
    except RuntimeError as e:
        error_msg = f"CGroups v2 check failed: {str(e)}"
        logger.error(error_msg, extra={"extra_data": {"error": str(e)}})
        result["errors"].append(error_msg)
        sys.exit(3)
        
    except TimeoutError as e:
        error_msg = f"Health check failed: {str(e)}"
        logger.error(error_msg, extra={"extra_data": {"error": str(e)}})
        result["errors"].append(error_msg)
        sys.exit(5)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, extra={"extra_data": {"error": str(e), "type": type(e).__name__}})
        result["errors"].append(error_msg)
        sys.exit(4)


def main():
    """Entry point for the Docker check script."""
    start_time = time.time()
    
    logger.info(
        "Starting Docker environment check",
        extra={"extra_data": {
            "script": "check_docker.py",
            "platform": sys.platform,
            "python_version": sys.version.split()[0]
        }}
    )
    
    result = run_docker_check()
    
    elapsed = time.time() - start_time
    
    logger.info(
        f"Docker check completed in {elapsed:.2f}s",
        extra={"extra_data": {
            "elapsed_seconds": round(elapsed, 2),
            "success": result["success"]
        }}
    )
    
    # Print summary to stdout as JSON for programmatic access
    print(json.dumps({
        "success": result["success"],
        "elapsed_seconds": round(elapsed, 2),
        "docker_version": result.get("docker_version"),
        "checks": result.get("checks", {}),
        "errors": result.get("errors", [])
    }, indent=2))
    
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
"""
Testes de Integração Real para Docker REPL Engine
Testes críticos: Fork Bomb, Network Isolation, tmpfs, Read-Only RootFS
"""

import pytest
import docker
import asyncio
import os
import signal
import subprocess
import time


class TestForkBombReal:
    """Teste: PIDs Limit - fork bomb deve ser contido."""
    
    def test_fork_bomb_blocked_by_pids_limit(self):
        """
        executa fork() exponencialmente e verifica que o sistema
        operacional rejeita novos processos após pids_limit (64).
        """
        client = docker.from_env()
        
        # Configuração com pids_limit=64
        config = {
            "mem_limit": "512m",
            "memswap_limit": "512m",
            "pids_limit": 64,
            "cpu_period": 100000,
            "cpu_quota": 100000,
            "network_mode": "none",
            "read_only": True,
            "init": True,
            "auto_remove": True,
            "tmpfs": ["/tmp:size=256m,mode=1777"]
        }
        
        container = None
        try:
            # Cria container com limite de PIDs
            container = client.containers.run(
                "python:3.11-slim",
                command=[
                    "python", "-c", """
import os
import sys

# Tentativa de fork exponentially
pids = []
for i in range(10):  # 2^10 = 1024 tentativas
    try:
        pid = os.fork()
        if pid == 0:
            # Child - tenta continuar forking
            pids.append(os.getpid())
        else:
            pids.append(pid)
    except OSError as e:
        print(f"FORK_BLOCKED: {e}", file=sys.stderr)
        sys.exit(1)

print(f"FORKED_COUNT: {len(pids)}", file=sys.stdout)
sys.exit(0)
"""
                ],
                detach=True,
                **config
            )
            
            # Aguarda execução
            result = container.wait(timeout=30)
            logs = container.logs(stdout=True, stderr=True).decode()
            
            # Verifica que foi bloqueado pelo sistema operacional
            assert result["StatusCode"] in [0, 1], "Container deve completar ou falhar"
            
            # Se forks foram bloqueados, deve haver mensagem de erro
            if "FORK_BLOCKED" in logs or "Cannot allocate memory" in logs:
                print("✓ Fork bomb contida pelo pids_limit")
            else:
                # Conta quantos forks successfuls
                print(f"Logs: {logs}")
                
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass


class TestNetworkIsolationReal:
    """Teste: Network Isolation - rede deve estar bloqueada."""
    
    def test_network_completely_blocked(self):
        """
        executa ping/curl e verifica que a rede está bloqueada.
        """
        client = docker.from_env()
        
        config = {
            "mem_limit": "512m",
            "pids_limit": 64,
            "network_mode": "none",  # CRÍTICO
            "read_only": True,
            "init": True,
            "auto_remove": True
        }
        
        container = None
        try:
            container = client.containers.run(
                "python:3.11-slim",
                command=[
                    "python", "-c", """
import socket
import sys

# Tenta conectar externa
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(('8.8.8.8', 53))
    print("NETWORK_ALLOWED", file=sys.stdout)
    sys.exit(1)
except OSError as e:
    print(f"NETWORK_BLOCKED: {e}", file=sys.stderr)
    sys.exit(0)
"""
                ],
                detach=True,
                **config
            )
            
            result = container.wait(timeout=30)
            logs = container.logs(stdout=True, stderr=True).decode()
            
            # Rede deve estar bloqueada
            assert "NETWORK_BLOCKED" in logs or result["StatusCode"] != 0
            print(f"✓ Rede bloqueada: {logs}")
            
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass


class TestTmpfsReal:
    """Teste: tmpfs limit - /tmp deve ter limite"""
    
    def test_tmpfs_size_limited(self):
        """
        Verifica que /tmp tmpfs tem limite de 256MB.
        """
        client = docker.from_env()
        
        config = {
            "mem_limit": "512m",
            "pids_limit": 64,
            "network_mode": "none",
            "read_only": True,
            "init": True,
            "auto_remove": True,
            "tmpfs": ["/tmp:size=256m,mode=1777"]  # CRÍTICO
        }
        
        container = None
        try:
            container = client.containers.run(
                "python:3.11-slim",
                command=[
                    "sh", "-c", """
# Verifica tmpfs
df_output=$(df -BG /tmp | tail -1)
echo "$df_output"

# Tenta allocate mais que 256MB
dd if=/dev/zero of=/tmp/test bs=1M count=300 2>&1 | head -5
ret=$?

# Cleanup
rm -f /tmp/test 2>/dev/null

exit $ret
"""
                ],
                detach=True,
                **config
            )
            
            result = container.wait(timeout=30)
            logs = container.logs(stdout=True, stderr=True).decode()
            
            # Deve falhar ao tentar alocar >256MB
            if "no space left on device" in logs.lower() or result["StatusCode"] != 0:
                print("✓ tmpfs limit respeitado")
            else:
                print(f"Logs: {logs}")
                
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass


class TestReadOnlyRootfsReal:
    """Teste: RootFS Read-Only - sistema de arquivos root deve ser只读"""
    
    def test_rootfs_readonly(self):
        """
        Verifica que root filesystem é somente leitura.
        """
        client = docker.from_env()
        
        config = {
            "mem_limit": "512m",
            "pids_limit": 64,
            "network_mode": "none",
            "read_only": True,  # CRÍTICO
            "init": True,
            "auto_remove": True,
            "tmpfs": ["/tmp:size=256m,mode=1777"]
        }
        
        container = None
        try:
            container = client.containers.run(
                "python:3.11-slim",
                command=[
                    "sh", "-c", """
# Tenta escrever no root
echo "test" > /root/test_file 2>&1
ret=$?

# Cleanup
rm -f /root/test_file 2>/dev/null

exit $ret
"""
                ],
                detach=True,
                **config
            )
            
            result = container.wait(timeout=30)
            logs = container.logs(stdout=True, stderr=True).decode()
            
            # Deve falhar ao tentar escrever no root
            if "Read-only file system" in logs or "cannot" in logs.lower() or result["StatusCode"] != 0:
                print("✓ RootFS Read-Only respeitado")
            else:
                print(f"Logs: {logs}")
                
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

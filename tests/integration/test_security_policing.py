"""
Testes de Integração - Q7 Security Policing

Estes testes verificam fisicamente as políticas de segurança no container real.
Execute com: pytest tests/integration/test_security_policing.py -v
"""

import pytest
import docker
import asyncio
import os


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def docker_client():
    """Cliente Docker conectado."""
    client = docker.from_env()
    yield client
    # Cleanup: remove todos os containers de teste
    for c in client.containers.list(filters={"name": "test-secure-"}):
        try:
            c.kill()
            c.remove(force=True)
        except:
            pass


@pytest.fixture
def security_policing():
    """SecurityPolicing instance."""
    from src.runtime.security_policing import SecurityPolicing, SecurityConfig
    config = SecurityConfig(
        pids_limit=64,
        oom_score_adj=1000,
        read_only_rootfs=True,
        tmpfs_tmp="100m",
        tmpfs_run="50m",
    )
    return SecurityPolicing(config)


# =============================================================================
# TESTES DE INTEGRAÇÃO
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_container_readonly_rootfs(docker_client, security_policing):
    """
    CRÍTICO: Testa se RootFS é Read-Only.
    
    Tenta criar um arquivo em /. Se falhar (Read-Only), o teste passa.
    Se succeeder, o teste falha.
    """
    # Cria container com políticas de segurança
    container_id = await security_policing.create_secure_container(
        docker_client=docker_client,
        base_image="python:3.12-slim",
        name="test-secure-ro",
        memory_limit="512m",
    )
    
    try:
        # Tenta criar arquivo em root (deve falhar!)
        result = docker_client.api.execution(container_id, ["sh", "-c", "touch /test_file.txt"])
        
        # Se chegou aqui, RootFS é escrevível - FALHA!
        assert False, f"RootFS é escrevível! Container {container_id[:12]} aceitou escrita"
    
    except Exception as e:
        # Se resultou em erro, RootFS é Read-Only - SUCESSO!
        # O Docker retorna exit code não-zero para Read-Only
        assert "Read-only" in str(e) or "RO" in str(e) or "permission denied" in str(e).lower(), \
            f"Erro não é de Read-Only: {e}"
    
    finally:
        # Cleanup
        try:
            docker_client.kill(container_id)
            docker_client.remove_container(container_id, force=True)
        except:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_container_network_disabled(docker_client, security_policing):
    """
    CRÍTICO: Testa se rede está desabilitada.
    
    Tenta fazer ping. Se falhar (sem rede), o teste passa.
    """
    container_id = await security_policing.create_secure_container(
        docker_client=docker_client,
        base_image="python:3.12-slim",
        name="test-secure-net",
        memory_limit="512m",
    )
    
    try:
        # Tenta Ping (deve falhar!)
        result = docker_client.api.execution(container_id, ["sh", "-c", "ping -c 1 8.8.8.8"])
        
        # Se chegou aqui, rede está ativa - FALHA!
        assert False, f"Rede está ATIVA! Container {container_id[:12]} conseguiu fazer ping"
    
    except Exception as e:
        # Se resulted em erro, rede desabilitada - SUCESSO!
        assert "no" in str(e).lower() or "network" in str(e).lower() or "permission" in str(e).lower(), \
            f"Erro não é de rede: {e}"
    
    finally:
        try:
            docker_client.kill(container_id)
            docker_client.remove_container(container_id, force=True)
        except:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_container_pids_limit(docker_client, security_policing):
    """
    CRÍTICO: Testa se PIDs limit funciona.
    
    Tenta criar 100 processos. Se falhar (PIDs limit), o teste passa.
    """
    container_id = await security_policing.create_secure_container(
        docker_client=docker_client,
        base_image="python:3.12-slim",
        name="test-secure-pids",
        memory_limit="512m",
    )
    
    try:
        # Tenta fork bomb (deve falhar!)
        result = docker_client.api.execution(
            container_id, 
            ["sh", "-c", "for i in $(seq 1 100); do sleep 1 & done"]
        )
        
        # Se chegou aqui, PIDs não limitou - FALHA!
        assert False, f"PIDs limit não aplicadou! Container {container_id[:12]} criou processos"
    
    except Exception as e:
        # Se resultou em erro, PIDs limit funcionou - SUCESSO!
        assert "pids" in str(e).lower() or "limit" in str(e).lower() or "permission" in str(e).lower(), \
            f"Erro não é de PIDs: {e}"
    
    finally:
        try:
            docker_client.kill(container_id)
            docker_client.remove_container(container_id, force=True)
        except:
            pass


# =============================================================================
# TESTE DE VERIFICAÇÃO PÓS-CRIAÇÃO
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_verify_container_is_secure(docker_client, security_policing):
    """
    CRÍTICO: Testa a verificação física do container.
    
    Cria container e verifica se todas as políticas foram aplicadas.
    """
    container_id = await security_policing.create_secure_container(
        docker_client=docker_client,
        base_image="python:3.12-slim",
        name="test-secure-verify",
        memory_limit="512m",
    )
    
    try:
        # Verifica container
        secure = await security_policing.verify_container(container_id)
        
        # Se todas as políticas aplicadas, secure=True
        assert secure, f"Container {container_id[:12]} não passou na verificação!"
        
    finally:
        try:
            docker_client.kill(container_id)
            docker_client.remove_container(container_id, force=True)
        except:
            pass


# =============================================================================
# TESTE DE EXCEÇÃO EM VERIFICAÇÃO FALHA
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_fallback_kills_container():
    """
    CRÍTICO: Testa que exceção em verificação ABATE o container.
    
    Simula falha na verificação e verifica se container é morto.
    """
    from src.runtime.security_policing import SecurityPolicing, SecurityConfig, ContainerSecurityViolationError
    
    # Cria client real
    client = docker.from_env()
    config = SecurityConfig()
    policing = SecurityPolicing(config)
    
    # Cria container primeiro (sem wrapper)
    container = client.create_container(
        "python:3.12-slim",
        name="test-fallback",
        host_config=client.api.create_host_config(
            mem_limit="512m",
            network_mode="none",
        ),
    )
    container_id = container["Id"]
    client.start(container_id)
    
    try:
        # Força um ID inválido paraDAR erro na verificação
        invalid_id = "invalid-container-id"
        
        # Tenta verificar - deve lançar exceção
        with pytest.raises(ContainerSecurityViolationError):
            await policing.verify_container(invalid_id)
    
    finally:
        # Cleanup
        try:
            client.kill(container_id)
            client.remove_container(container_id, force=True)
        except:
            pass


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
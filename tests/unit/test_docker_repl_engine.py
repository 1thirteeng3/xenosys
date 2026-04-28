"""
Testes para docker_repl_engine.py (ContainmentConfig)
"""

import pytest
from runtime.docker_repl_engine import ContainmentConfig


class TestMemoryLimit:
    def test_default_memory_is_512mb(self):
        config = ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace")
        assert config.memory_limit == "512m"
    
    def test_memory_validation_range(self):
        # 512MB válido
        config = ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace", memory_limit="512m")
        
        # 1GB válido
        config = ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace", memory_limit="1g")
        
        # 256MB inválido
        with pytest.raises(ValueError):
            ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace", memory_limit="256m")


class TestPIDsLimit:
    def test_default_pids_limit_is_64(self):
        config = ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace")
        assert config.pids_limit == 64
    
    def test_pids_validation_range(self):
        # 1 válido
        config = ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace", pids_limit=1)
        
        # 0 inválido
        with pytest.raises(ValueError):
            ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace", pids_limit=0)


class TestWorkspacePathValidation:
    def test_canonical_path_is_set(self):
        config = ContainmentConfig(workspace_path="/tmp/xenosys_test_workspace")
        assert config.canonical_workspace_path != ""
    
    def test_relative_path_rejected(self):
        with pytest.raises(ValueError):
            ContainmentConfig(workspace_path="workspace")


class TestLifecycleHooks:
    @pytest.mark.asyncio
    async def test_hooks_fire_on_create(self):
        from core.hooks import LifecycleHooks
        from core.models import ContainerSession
        from datetime import datetime, timezone
        
        hooks = LifecycleHooks()
        fired = False
        
        async def on_create(session):
            nonlocal fired
            fired = True
        
        hooks.on_create(on_create)
        
        session = ContainerSession(
            container_id="test123",
            name="test",
            created_at=datetime.now(timezone.utc),
            config=None,
            status="created"
        )
        
        await hooks.trigger_create(session)
        assert fired


class TestHostConfigBuilder:
    def test_all_security_options(self):
        config = ContainmentConfig(
            workspace_path="/tmp/xenosys_test_workspace",
            memory_limit="512m",
            pids_limit=64,
            network_disabled=True,
            readonly_rootfs=True
        )
        
        kwargs = config.to_host_config_kwargs()
        
        assert "mem_limit" in kwargs
        assert kwargs["network_mode"] == "none"

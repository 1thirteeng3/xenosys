"""
XenoSys - Main Application Entry Point
"""

import asyncio
import logging
import os
import signal
from typing import Optional

import grpc
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .agents.registry import agent_registry
from .memory.orchestrator import get_memory_orchestrator
from .orchestration.event_bus import event_bus
from .llmops.telemetry import get_telemetry_exporter
from .messaging import get_message_broker, initialize_broker, shutdown_broker

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration - Network Binding Security
# ============================================================================

def get_grpc_bind_address() -> str:
    """
    Get the gRPC server bind address based on execution context.
    
    Desktop mode (Tauri): Bind to 127.0.0.1 to prevent agent hijacking.
    Docker/VPS mode: Bind to 0.0.0.0 (or GRPC_HOST env) for reverse proxy.
    """
    port = os.environ.get("GRPC_PORT", "50051")
    is_desktop = os.environ.get("TAURI_ENV") == "true"
    
    if is_desktop:
        # Desktop mode: Bind to localhost only - secure
        host = "127.0.0.1"
        logger.info("gRPC binding to localhost only (Desktop mode - secure)")
    else:
        # Docker/VPS mode: Allow external binding
        host = os.environ.get("GRPC_HOST", "0.0.0.0")
        if host == "0.0.0.0":
            logger.warning(
                "WARNING: gRPC server binding to all interfaces (0.0.0.0). "
                "Confirm this is an isolated Docker/VPS environment."
            )
    
    return f"{host}:{port}"


def get_http_bind_host() -> str:
    """
    Get the HTTP server bind host based on execution context.
    
    Desktop mode: Bind to 127.0.0.1.
    Docker/VPS mode: Bind to 0.0.0.0.
    """
    is_desktop = os.environ.get("TAURI_ENV") == "true"
    
    if is_desktop:
        return "127.0.0.1"  # Desktop: localhost only - secure
    else:
        return os.environ.get("HOST", "0.0.0.0")  # Docker/VPS: allow external


# ============================================================================
# Application
# ============================================================================


class XenoSysApp:
    """
    Main application class for XenoSys.
    
    Coordinates initialization of all subsystems.
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._grpc_server: Optional[grpc.aio.Server] = None
    
    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda rs: logger.warning(f"Waiting for memory subsystems... Attempt {rs.attempt_number}/7")
    )
    async def _initialize_memory_with_retry(self):
        """Initialize the memory orchestrator with Exponential Backoff."""
        memory = get_memory_orchestrator()
        await memory.initialize()
    
    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting XenoSys...")
        
        # Initialize event bus
        await event_bus.start()
        
        # Initialize message broker
        broker_config = self.config.get("messaging", {})
        broker_backend = broker_config.get("backend", "memory")
        await initialize_broker(broker_backend, **broker_config)
        
        # Initialize memory orchestrator with retry
        try:
            await self._initialize_memory_with_retry()
        except Exception as e:
            logger.error(f"Critical failure: Could not connect to memory modules after 7 attempts. {e}")
            raise
        
        # Initialize telemetry
        telemetry = get_telemetry_exporter(self.config.get("telemetry"))
        
        # Start the gRPC Asynchronous Server
        self._grpc_server = grpc.aio.server()
        
        # Associate your gRPC Servicer here:
        # from .api.grpc_servicer import RuntimeService, add_RuntimeServicer_to_server
        # add_RuntimeServicer_to_server(RuntimeService(), self._grpc_server)
        
        bind_address = get_grpc_bind_address()
        self._grpc_server.add_insecure_port(bind_address)
        await self._grpc_server.start()
        logger.info(f"gRPC Server actively listening on {bind_address}")
        
        self._running = True
        logger.info("XenoSys started successfully")
    
    async def stop(self) -> None:
        """Stop the application with graceful shutdown."""
        logger.info("Initiating graceful shutdown...")
        
        self._running = False
        
        # 1. Stop gRPC server
        if self._grpc_server:
            logger.info("Shutting down gRPC server...")
            await self._grpc_server.stop(grace=5.0)
        
        # 2. Disconnect Event Bus
        logger.info("Disconnecting Event Bus (Redis connections)...")
        await event_bus.stop()
        
        # 3. Stop message broker
        logger.info("Stopping message broker...")
        await shutdown_broker()
        
        # 4. Cancel pending tasks
        logger.info("Canceling pending tasks...")
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info("XenoSys safely shut down.")
    
    def run(self) -> None:
        """Run the application."""
        async def main():
            await self.start()
            
            # Wait for shutdown signal
            while self._running:
                await asyncio.sleep(1)
            
            await self.stop()
        
        asyncio.run(main())


# Application instance
_app: Optional[XenoSysApp] = None


def get_app(config: Optional[dict] = None) -> XenoSysApp:
    """Get or create the application instance."""
    global _app
    if _app is None:
        _app = XenoSysApp(config)
    return _app


async def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    app = get_app()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def shutdown(sig):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(app.stop())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: shutdown(s))
    
    await app.start()
    
    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())

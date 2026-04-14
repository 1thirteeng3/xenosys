"""
XenoSys - Main Application Entry Point
"""

import asyncio
import logging
import signal
from typing import Optional

from .agents.registry import agent_registry
from .memory.orchestrator import get_memory_orchestrator
from .orchestration.event_bus import event_bus
from .llmops.telemetry import get_telemetry_exporter
from .messaging import get_message_broker, initialize_broker, shutdown_broker

logger = logging.getLogger(__name__)


class XenoSysApp:
    """
    Main application class for XenoSys.
    
    Coordinates initialization of all subsystems.
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._running = False
        self._tasks: list[asyncio.Task] = []
    
    async def start(self) -> None:
        """Start the application."""
        logger.info("Starting XenoSys...")
        
        # Initialize event bus
        await event_bus.start()
        
        # Initialize message broker
        broker_config = self.config.get("messaging", {})
        broker_backend = broker_config.get("backend", "memory")
        await initialize_broker(broker_backend, **broker_config)
        
        # Initialize memory orchestrator
        memory = get_memory_orchestrator()
        await memory.initialize()
        
        # Initialize telemetry
        telemetry = get_telemetry_exporter(self.config.get("telemetry"))
        
        self._running = True
        logger.info("XenoSys started successfully")
    
    async def stop(self) -> None:
        """Stop the application with graceful shutdown."""
        logger.info("Initiating graceful shutdown...")
        
        self._running = False
        
        # 1. Stop new requests - Close HTTP clients and gRPC connections
        logger.info("Closing HTTP clients and gRPC connections...")
        
        # 2. Disconnect Event Bus, clearing Redis connections
        logger.info("Disconnecting Event Bus (Redis connections)...")
        await event_bus.stop()
        
        # 3. Stop message broker (includes Redis cleanup if using Redis backend)
        logger.info("Stopping message broker...")
        await shutdown_broker()
        
        # 4. Cancel pending tasks
        logger.info("Canceling pending tasks...")
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete cancellation
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
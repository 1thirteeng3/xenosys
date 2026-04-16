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
    """Configura o endereço de escuta do gRPC de forma dinâmica e segura."""
    port = os.environ.get("GRPC_PORT", "50051")
    is_desktop = os.environ.get("TAURI_ENV") == "true"

    if is_desktop:
        host = "127.0.0.1"
        logger.info("gRPC binding to localhost only (Desktop mode - secure)")
    else:
        host = os.environ.get("GRPC_HOST", "0.0.0.0")
        if host == "0.0.0.0":
            logger.warning("WARNING: gRPC server binding to all interfaces (0.0.0.0).")

    return f"{host}:{port}"

# ============================================================================
# Application Core
# ============================================================================

class XenoSysApp:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._grpc_server: Optional[grpc.aio.Server] = None

    @retry(
        stop=stop_after_attempt(7),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda rs: logger.warning(f"Aguardando boot dos subsistemas de IA... Tentativa {rs.attempt_number}/7")
    )
    async def _initialize_memory_with_retry(self):
        """Inicializa a memória utilizando Backoff Exponencial para tolerância a falhas."""
        logger.info("Tentando conectar à malha de memória...")
        memory = get_memory_orchestrator()
        await memory.initialize()

        # Validação agressiva: força o erro se as memórias não estiverem prontas
        if not hasattr(memory, 'stores') or len(memory.stores) == 0:
            raise ConnectionError("A inicialização da memória retornou vazia. Retentando...")

    async def start(self) -> None:
        """Inicia a aplicação orquestrando as conexões assíncronas."""
        logger.info("Starting XenoSys Core...")

        # 1. Start Infraestrutura Base (Eventos e Mensageria)
        await event_bus.start()
        
        broker_config = self.config.get("messaging", {})
        broker_backend = broker_config.get("backend", "memory")
        await initialize_broker(broker_backend, **broker_config)
        
        # Telemetria
        get_telemetry_exporter(self.config.get("telemetry"))

        # 2. Start Infraestrutura de IA (Blindado com Tenacity)
        try:
            await self._initialize_memory_with_retry()
        except Exception as e:
            logger.error(f"Degradação aceitável: Executando sem memórias remotas devido a TimeOut. Erro: {e}")

        # 3. Start Servidor gRPC
        logger.info("Instanciando servidor gRPC.aio...")
        self._grpc_server = grpc.aio.server()

        # NOTA DE ENGENHARIA: Adicione Servicers aqui quando os handlers (.proto) forem gerados
        # ex: add_RuntimeServicer_to_server(RuntimeService(), self._grpc_server)

        bind_address = get_grpc_bind_address()
        self._grpc_server.add_insecure_port(bind_address)
        await self._grpc_server.start()
        
        logger.info(f"====== Servidor gRPC ESCUTANDO ATIVAMENTE em {bind_address} ======")

        self._running = True
        logger.info("XenoSys started successfully")

    async def stop(self) -> None:
        """Encerra a aplicação desligando as portas graciosamente."""
        logger.info("Initiating graceful shutdown...")
        self._running = False

        if self._grpc_server:
            logger.info("Encerrando servidor gRPC...")
            await self._grpc_server.stop(grace=5.0)

        logger.info("Desconectando Event Bus e Message Broker...")
        await event_bus.stop()
        await shutdown_broker()

        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        logger.info("XenoSys safely shut down.")

    def run(self) -> None:
        """Mantém o Loop de Eventos ativo."""
        async def main():
            await self.start()
            while self._running:
                await asyncio.sleep(1)
            await self.stop()
        asyncio.run(main())

# Singleton management
_app: Optional[XenoSysApp] = None

def get_app(config: Optional[dict] = None) -> XenoSysApp:
    global _app
    if _app is None:
        _app = XenoSysApp(config)
    return _app

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    app = get_app()
    loop = asyncio.get_event_loop()

    def shutdown(sig):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(app.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: shutdown(s))

    await app.start()

    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        pass
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())

# nexus/core/memory/l4_contextual/graph_integration.py
import contextlib
import logging
import asyncio
from typing import List, Dict, Any
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

class ContextualMemoryClient:
    def __init__(self, mcp_server_url: str):
        self.server_url = mcp_server_url
        self._exit_stack = contextlib.AsyncExitStack()
        self.session: ClientSession | None = None

    async def connect(self):
        """Estabelece a conexão SSE com o mcp-memory-service."""
        try:
            transport = await self._exit_stack.enter_async_context(sse_client(self.server_url))
            self.session = await self._exit_stack.enter_async_context(ClientSession(transport[0], transport[1]))
            await self.session.initialize()
            logger.info("🟢 Conectado ao L4 Knowledge Graph (MCP Memory Service)")
        except Exception as e:
            logger.error(f"🔴 Falha crítica ao conectar no L4: {e}")
            raise

    async def disconnect(self):
        await self._exit_stack.aclose()

    # --- WRAPPERS DE SEGURANÇA PARA AS TOOLS DO MCP ---
    # Envelopamos as chamadas em asyncio.wait_for para evitar travamento do Event Loop

    async def read_graph(self, query: str) -> str:
        """Lê o contexto atual do grafo (Pre-hook)."""
        if not self.session: return ""
        try:
            # O timeout de 3 segundos garante que a UX do chat não engasgue se o L4 lentificar
            result = await asyncio.wait_for(
                self.session.call_tool("read_graph", arguments={"query": query}),
                timeout=3.0
            )
            return result.content[0].text if result.content else ""
        except Exception as e:
            logger.warning(f"L4 Read Timeout/Error: {e}")
            return ""

    async def create_relations(self, entities: List[Dict[str, str]], relations: List[Dict[str, str]]):
        """Escreve novas entidades e relações no grafo (Post-hook)."""
        if not self.session: return
        try:
            await asyncio.wait_for(
                self.session.call_tool("create_relations", arguments={
                    "entities": entities,
                    "relations": relations
                }),
                timeout=5.0
            )
        except Exception as e:
            logger.error(f"L4 Write Error: {e}")

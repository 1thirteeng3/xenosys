"""
XenoSys Memory System - L4 Contextual Memory (BrainSys)
Built on Membase for AI's second brain via MCP SSE transport.

Membase: https://membase.so
The AI's own second brain - context captured, processed, and analyzed.
Note: Uses MCP (Model Context Protocol) with SSE for remote HTTP transport.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ============================================================================
# MCP SSE Client for BrainSys/Membase
# ============================================================================

class BrainSysMCPClient:
    """
    MCP Client for BrainSys operations via SSE transport.
    
    Uses Server-Sent Events (SSE) for stateless remote communication.
    This replaces the old Stdio-based transport with HTTP-based SSE.
    """

    def __init__(self, mcp_server_url: str):
        """
        Initialize MCP client with SSE transport.
        
        Args:
            mcp_server_url: URL of the MCP server (e.g., http://localhost:9000/sse)
        """
        self.server_url = mcp_server_url
        self._exit_stack: Optional[Any] = None
        self.session: Optional[Any] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """
        Establishes a stateless connection via Server-Sent Events (SSE).
        """
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            import contextlib
            
            # Manages the transport and session lifecycle
            self._exit_stack = contextlib.AsyncExitStack()
            
            # Create SSE transport
            sse_transport = await self._exit_stack.enter_async_context(
                sse_client(self.server_url)
            )
            
            # Create client session
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(sse_transport[0], sse_transport[1])
            )
            
            await self.session.initialize()
            self._connected = True
            
            logger.info(f"Connected to BrainSys MCP via SSE: {self.server_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect via SSE to MCP Server: {e}")
            raise ConnectionError(f"Failed to connect via SSE to MCP Server: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self.session = None
            self._connected = False
            logger.info("Disconnected from BrainSys MCP")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools."""
        if not self.session:
            return []
        
        try:
            result = await self.session.list_tools()
            return result.tools if hasattr(result, 'tools') else []
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Any:
        """Call an MCP tool with timeout protection.
        
        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments
            timeout: Maximum time to wait for response (default 30s)
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            # Wrap with asyncio.wait_for to prevent infinite wait on network drop
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"MCP tool {tool_name} timed out after {timeout}s")
            raise RuntimeError(f"MCP tool call timed out: {tool_name}")
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise


# ============================================================================
# BrainSys Types
# ============================================================================

@dataclass
class ContextEntry:
    """A context entry in BrainSys."""
    id: UUID = field(default_factory=uuid4)
    content: str = ""
    context_type: str = "general"  # analysis, summary, insight, pattern
    source_session_id: Optional[str] = None
    source_interaction_id: Optional[str] = None
    embedding: Optional[List[float]] = None
    importance: float = 0.7  # Higher default than L1
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextAnalysis:
    """Analysis result from processing context."""
    entry_id: UUID
    summary: str
    key_points: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    confidence: float = 0.5


@dataclass
class PatternRecord:
    """A recurring pattern detected in context."""
    id: UUID = field(default_factory=uuid4)
    pattern_type: str = ""  # behavioral, linguistic, technical
    description: str = ""
    frequency: int = 0
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# BrainSys Store (Contextual Memory) with MCP SSE
# ============================================================================

class BrainSysStore:
    """
    L4 Contextual Memory store using Membase via MCP SSE.
    
    Provides:
    - AI's own second brain for context analysis via MCP protocol
    - Pattern detection and learning
    - Context importance scoring
    - Semantic context search
    - Real-time analysis
    """

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:9000/sse",
    ):
        self.mcp_client = BrainSysMCPClient(mcp_server_url)
    
    async def initialize(self) -> bool:
        """Initialize BrainSys store."""
        return await self.mcp_client.connect()
    
    async def close(self) -> None:
        """Close the store."""
        await self.mcp_client.disconnect()
    
    async def capture_context(
        self,
        content: str,
        context_type: str = "general",
        source_session_id: Optional[str] = None,
        source_interaction_id: Optional[str] = None,
        importance: float = 0.7,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextEntry:
        """Capture new context from interaction via MCP."""
        args = {
            "content": content,
            "context_type": context_type,
            "importance": importance,
            "tags": tags or [],
        }
        
        if source_session_id:
            args["source_session_id"] = source_session_id
        if source_interaction_id:
            args["source_interaction_id"] = source_interaction_id
        if metadata:
            args["metadata"] = metadata
        
        try:
            result = await self.mcp_client.call_tool("store_context", args)
            
            return ContextEntry(
                content=content,
                context_type=context_type,
                source_session_id=source_session_id,
                source_interaction_id=source_interaction_id,
                importance=importance,
                tags=tags or [],
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Failed to capture context: {e}")
            raise
    
    async def analyze_and_capture(
        self,
        session_id: str,
        interaction_content: str,
        context_type: str = "analysis",
    ) -> ContextEntry:
        """Capture and analyze context from interaction via MCP."""
        entry = await self.capture_context(
            content=interaction_content,
            context_type=context_type,
            source_session_id=session_id,
            importance=0.8,
            tags=[context_type],
        )
        
        # Analyze via MCP tool
        try:
            analysis_result = await self.mcp_client.call_tool(
                "analyze_context",
                {"entry_id": str(entry.id)}
            )
            
            if analysis_result and hasattr(analysis_result, 'analysis'):
                analysis = analysis_result.analysis
                entry.importance = analysis.get("confidence", entry.importance)
        except Exception as e:
            logger.warning(f"Context analysis failed: {e}")
        
        return entry
    
    async def retrieve_context(
        self,
        query: str,
        context_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        top_k: int = 10,
    ) -> List[ContextEntry]:
        """Retrieve relevant context via MCP."""
        args = {
            "query": query,
            "top_k": top_k,
        }
        
        if context_type:
            args["context_type"] = context_type
        if tags:
            args["tags"] = tags
        
        try:
            result = await self.mcp_client.call_tool("search_contexts", args)
            
            entries = []
            if result and hasattr(result, 'results'):
                for item in result.results:
                    entries.append(ContextEntry(
                        id=UUID(item.get("id", str(uuid4()))),
                        content=item.get("content", ""),
                        context_type=item.get("context_type", "general"),
                        importance=item.get("importance", 0.7),
                        tags=item.get("tags", []),
                    ))
            
            return entries
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def get_patterns(
        self,
        pattern_type: Optional[str] = None,
    ) -> List[PatternRecord]:
        """Get learned patterns via MCP."""
        args = {}
        if pattern_type:
            args["pattern_type"] = pattern_type
        
        try:
            result = await self.mcp_client.call_tool("get_patterns", args)
            
            patterns = []
            if result and hasattr(result, 'patterns'):
                for item in result.patterns:
                    patterns.append(PatternRecord(
                        pattern_type=item.get("pattern_type", ""),
                        description=item.get("description", ""),
                        frequency=item.get("frequency", 0),
                        evidence=item.get("evidence", []),
                    ))
            
            return patterns
        except Exception as e:
            logger.error(f"Failed to get patterns: {e}")
            return []
    
    async def get_session_context(
        self,
        session_id: str,
    ) -> List[ContextEntry]:
        """Get all context for a session via MCP."""
        return await self.retrieve_context(
            query="",
            tags=[session_id],
            top_k=100,
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get BrainSys statistics."""
        return {
            "mcp_url": self.mcp_client.server_url,
            "connected": self.mcp_client._connected,
        }


# Global BrainSys store instance
_global_brainsys_store: Optional[BrainSysStore] = None


def get_brainsys_store(
    mcp_server_url: str = "http://localhost:9000/sse",
) -> BrainSysStore:
    """Get or create global BrainSys store."""
    global _global_brainsys_store
    if _global_brainsys_store is None:
        _global_brainsys_store = BrainSysStore(mcp_server_url=mcp_server_url)
    return _global_brainsys_store
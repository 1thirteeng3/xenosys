"""
XenoSys Memory System - L2 Long-term Memory (2ndBrain)
Built on Obsidian for user materials and notes via MCP SSE transport.

Obsidian: https://obsidian.md
The user's second brain - personal knowledge management.
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
# MCP SSE Client for Obsidian
# ============================================================================

class ObsidianMCPClient:
    """
    MCP Client for Obsidian vault operations via SSE transport.
    
    Uses Server-Sent Events (SSE) for stateless remote communication.
    This replaces the old Stdio-based transport with HTTP-based SSE.
    """

    def __init__(self, mcp_server_url: str):
        """
        Initialize MCP client with SSE transport.
        
        Args:
            mcp_server_url: URL of the MCP server (e.g., http://localhost:3000/sse)
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
            
            logger.info(f"Connected to Obsidian MCP via SSE: {self.server_url}")
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
            logger.info("Disconnected from Obsidian MCP")
    
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
# 2ndBrain Types
# ============================================================================

@dataclass
class Note:
    """A note in 2ndBrain (Obsidian vault)."""
    id: UUID = field(default_factory=uuid4)
    title: str = ""
    content: str = ""
    path: str = ""  # Relative path in vault
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)  # Linked notes
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    modified_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NoteSearchResult:
    """Result from note search."""
    note: Note
    score: float


# ============================================================================
# 2ndBrain Store with MCP SSE
# ============================================================================

class SecondBrainStore:
    """
    L2 Long-term Memory store using Obsidian via MCP SSE.
    
    Provides:
    - Personal knowledge management via MCP protocol
    - Note-taking with wiki-links
    - Tag-based organization
    - Full-text search
    """

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:3000/sse",
    ):
        self.mcp_client = ObsidianMCPClient(mcp_server_url)
    
    async def initialize(self) -> bool:
        """Initialize the 2ndBrain store."""
        return await self.mcp_client.connect()
    
    async def close(self) -> None:
        """Close the store."""
        await self.mcp_client.disconnect()
    
    async def store(
        self,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store a note via MCP."""
        title = title or self._generate_title(content)
        
        # Build arguments for MCP tool
        args = {
            "title": title,
            "content": content,
            "folder": folder or "notes",
            "tags": tags or [],
        }
        
        if metadata:
            args["metadata"] = metadata
        
        # Call MCP tool
        try:
            result = await self.mcp_client.call_tool("create_note", args)
            note_id = uuid4()
            logger.info(f"Stored note in 2ndBrain via MCP: {note_id}")
            return note_id
        except Exception as e:
            logger.error(f"Failed to store note: {e}")
            raise
    
    async def retrieve(self, path: str) -> Optional[Note]:
        """Retrieve a note by path via MCP."""
        try:
            result = await self.mcp_client.call_tool("read_note", {"path": path})
            
            # Parse result into Note
            if result and hasattr(result, 'content'):
                # Convert MCP result to Note
                return Note(
                    id=uuid4(),
                    title=result.get("title", path.split("/")[-1].replace(".md", "")),
                    content=result.get("content", ""),
                    path=path,
                )
        except Exception as e:
            logger.error(f"Failed to retrieve note: {e}")
        
        return None
    
    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[NoteSearchResult]:
        """Search notes via MCP."""
        args = {
            "query": query,
            "limit": limit,
        }
        
        if tags:
            args["tags"] = tags
        
        try:
            result = await self.mcp_client.call_tool("search_notes", args)
            
            results = []
            if result and hasattr(result, 'results'):
                for item in result.results:
                    note = Note(
                        id=uuid4(),
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        path=item.get("path", ""),
                        tags=item.get("tags", []),
                    )
                    results.append(NoteSearchResult(
                        note=note,
                        score=item.get("score", 0.0)
                    ))
            
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def get_user_notes(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[Note]:
        """Get all notes for a specific user."""
        results = await self.search(
            query="",
            tags=[f"user:{user_id}"],
            limit=limit,
        )
        return [r.note for r in results]
    
    async def update(
        self,
        path: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Note]:
        """Update a note via MCP."""
        args = {"path": path}
        
        if content is not None:
            args["content"] = content
        if title is not None:
            args["title"] = title
        if tags is not None:
            args["tags"] = tags
        
        try:
            result = await self.mcp_client.call_tool("update_note", args)
            return await self.retrieve(path)
        except Exception as e:
            logger.error(f"Failed to update note: {e}")
            return None
    
    def _generate_title(self, content: str) -> str:
        """Generate a title from content."""
        first_line = content.split('\n')[0].strip()
        if first_line:
            return first_line[:100]
        return f"Note {datetime.utcnow().isoformat()}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get 2ndBrain statistics."""
        return {
            "mcp_url": self.mcp_client.server_url,
            "connected": self.mcp_client._connected,
        }


# Global 2ndBrain store instance
_global_secondbrain_store: Optional[SecondBrainStore] = None


def get_secondbrain_store(
    mcp_server_url: str = "http://localhost:3000/sse",
) -> SecondBrainStore:
    """Get or create global 2ndBrain store."""
    global _global_secondbrain_store
    if _global_secondbrain_store is None:
        _global_secondbrain_store = SecondBrainStore(mcp_server_url=mcp_server_url)
    return _global_secondbrain_store
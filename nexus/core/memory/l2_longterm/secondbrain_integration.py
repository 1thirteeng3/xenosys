from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# ============================================================================
# Domínio e Modelos de Dados
# ============================================================================

@dataclass
class Note:
     """Representação universal de uma nota no sistema XenoSys."""
     title: str
     content: str
     path: str  # Caminho relativo no vault
     id: UUID = field(default_factory=uuid4)
     tags: List[str] = field(default_factory=list)
     metadata: Dict[str, Any] = field(default_factory=dict)
     modified_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class NoteSearchResult:
     note: Note
     score: float = 1.0

# ============================================================================
# Interfaces de Transporte (Strategy Pattern)
# ============================================================================

class ObsidianTransport(ABC):
     """Interface abstrata para comunicação com o Obsidian."""
     
     @abstractmethod
     async def initialize(self) -> bool: ...
     
     @abstractmethod
     async def read(self, path: str) -> Optional[Note]: ...
     
     @abstractmethod
     async def write(self, note: Note) -> bool: ...
     
     @abstractmethod
     async def search(self, query: str, limit: int = 10) -> List[NoteSearchResult]: ...

# ============================================================================
# Implementação 1: Sistema de Arquivos (Local/CLI)
# ============================================================================

class LocalFileSystemTransport(ObsidianTransport):
     """Acesso direto ao Vault via File System para máxima performance."""
     
     def __init__(self, vault_path: Optional[str] = None):
         self.vault_path = Path(vault_path or os.environ.get("OBSIDIAN_VAULT_PATH", "/app/obsidian_vault"))

     async def initialize(self) -> bool:
         try:
             self.vault_path.mkdir(parents=True, exist_ok=True)
             # Healthcheck
             test_file = self.vault_path / ".xenosys_test"
             test_file.write_text("connection_test")
             test_file.unlink()
             return True
         except Exception as e:
             logger.error(f"Erro ao acessar Vault Local: {e}")
             return False

     async def read(self, path: str) -> Optional[Note]:
         file_path = self.vault_path / (path if path.endswith('.md') else f"{path}.md")
         if not file_path.exists():
             return None
         
         content = file_path.read_text(encoding="utf-8")
         return Note(
             title=file_path.stem,
             content=content,
             path=str(file_path.relative_to(self.vault_path)),
             modified_at=datetime.fromtimestamp(file_path.stat().st_mtime)
         )

     async def write(self, note: Note) -> bool:
         file_path = self.vault_path / (note.path if note.path.endswith('.md') else f"{note.path}.md")
         try:
             file_path.parent.mkdir(parents=True, exist_ok=True)
             file_path.write_text(note.content, encoding="utf-8")
             return True
         except Exception as e:
             logger.error(f"Erro na escrita local: {e}")
             return False

     async def search(self, query: str, limit: int = 10) -> List[NoteSearchResult]:
         results = []
         query = query.lower()
         for file in self.vault_path.rglob("*.md"):
             if len(results) >= limit: break
             
             content = file.read_text(encoding="utf-8", errors="ignore")
             if query in file.name.lower() or query in content.lower():
                 note = Note(title=file.stem, content=content, path=str(file.relative_to(self.vault_path)))
                 results.append(NoteSearchResult(note=note))
         return results

# ============================================================================
# Implementação 2: MCP SSE (Remoto)
# ============================================================================

class MCPRemoteTransport(ObsidianTransport):
     """Acesso via Protocolo MCP (Model Context Protocol) sobre SSE."""
     
     def __init__(self, url: str):
         self.url = url
         self.session = None
         self._exit_stack = None

     async def initialize(self) -> bool:
         from mcp import ClientSession
         from mcp.client.sse import sse_client
         import contextlib
         
         try:
             self._exit_stack = contextlib.AsyncExitStack()
             sse_transport = await self._exit_stack.enter_async_context(sse_client(self.url))
             self.session = await self._exit_stack.enter_async_context(
                 ClientSession(sse_transport[0], sse_transport[1])
             )
             await self.session.initialize()
             return True
         except Exception as e:
             logger.error(f"Falha na conexão MCP SSE: {e}")
             return False

     async def read(self, path: str) -> Optional[Note]:
         try:
             res = await self.session.call_tool("read_note", {"path": path})
             return Note(title=res.get("title", path), content=res.get("content", ""), path=path)
         except Exception: return None

     async def write(self, note: Note) -> bool:
         try:
             await self.session.call_tool("create_note", {
                 "title": note.title, "content": note.content, "path": note.path
             })
             return True
         except Exception: return False

     async def search(self, query: str, limit: int = 10) -> List[NoteSearchResult]:
         # Implementação similar à original chamando a tool 'search_notes'
         return [] 

# ============================================================================
# Gerenciador do SecondBrain (Orquestrador)
# ============================================================================

class SecondBrainStore:
     """
     L2 Long-term Memory.
     Pode operar em modo LOCAL (Filesystem) ou REMOTO (MCP).
     """

     def __init__(self, transport: ObsidianTransport):
         self.transport = transport

     async def initialize(self):
         return await self.transport.initialize()

     async def store_note(self, content: str, title: str, folder: str = "notes"):
         path = f"{folder}/{title}.md"
         note = Note(title=title, content=content, path=path)
         success = await self.transport.write(note)
         if success:
             logger.info(f"Nota salva com sucesso: {path}")
             return note.id
         raise IOError("Falha ao salvar nota no 2ndBrain")

     async def find(self, query: str) -> List[NoteSearchResult]:
         return await self.transport.search(query)

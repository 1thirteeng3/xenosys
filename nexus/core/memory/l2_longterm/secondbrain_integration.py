"""
XenoSys Memory System - L2 Long-term Memory (2ndBrain)
Built on Obsidian for user materials and notes via REST API.

Obsidian: https://obsidian.md
The user's second brain - personal knowledge management.
Note: Uses Obsidian Local REST API plugin for HTTP access.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger(__name__)


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
# Obsidian REST API Client
# ============================================================================

class ObsidianClient:
    """
    Client for Obsidian vault operations via REST API.
    
    Requires Obsidian Local REST API plugin running on a server.
    Provides:
    - Note CRUD operations via HTTP
    - Folder management
    - YAML frontmatter parsing
    - Wiki-link resolution
    - Tag-based organization
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.endpoint = self.config.get("endpoint", "http://localhost:8080")
        self.api_key = self.config.get("api_key", "")
        self.vault_name = self.config.get("vault_name", "xenosys")
        self.timeout = httpx.Timeout(self.config.get("timeout", 30.0))
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            self._client = httpx.AsyncClient(
                base_url=self.endpoint,
                timeout=self.timeout,
                headers=headers,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def connect(self) -> bool:
        """Verify connection to Obsidian API."""
        try:
            client = await self._get_client()
            response = await client.get(f"/vaults/{self.vault_name}/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to Obsidian: {e}")
            return False
    
    async def create_note(
        self,
        title: str,
        content: str = "",
        folder: str = "notes",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Note:
        """Create a new note via HTTP."""
        import yaml
        
        # Build frontmatter
        frontmatter = {
            "title": title,
            "created": datetime.utcnow().isoformat(),
            "modified": datetime.utcnow().isoformat(),
            "tags": tags or [],
        }
        if metadata:
            frontmatter.update(metadata)
        
        fm_yaml = yaml.dump(frontmatter, default_flow_style=False)
        full_content = f"---\n{fm_yaml}---\n\n{content}"
        
        # Generate filename
        filename = self._sanitize_filename(title) + ".md"
        file_path = f"{folder}/{filename}"
        
        try:
            client = await self._get_client()
            response = await client.put(
                f"/vaults/{self.vault_name}/files/{file_path}",
                json={"content": full_content}
            )
            
            if response.status_code in (200, 201):
                return Note(
                    id=uuid4(),
                    title=title,
                    content=content,
                    path=file_path,
                    tags=tags or [],
                    frontmatter=frontmatter,
                )
            raise Exception(f"Failed to create note: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to create note: {e}")
            raise
    
    async def get_note(self, path: str) -> Optional[Note]:
        """Read a note from the vault via HTTP."""
        try:
            client = await self._get_client()
            response = await client.get(f"/vaults/{self.vault_name}/files/{path}")
            
            if response.status_code != 200:
                return None
            
            content = response.json().get("content", "")
            frontmatter, body = self._parse_frontmatter(content)
            
            title = frontmatter.get("title", path.split("/")[-1].replace(".md", ""))
            tags = frontmatter.get("tags", [])
            
            return Note(
                id=uuid4(),
                title=title,
                content=body,
                path=path,
                tags=tags,
                frontmatter=frontmatter,
            )
            
        except Exception as e:
            logger.error(f"Failed to get note: {e}")
            return None
    
    async def update_note(
        self,
        path: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Note]:
        """Update an existing note."""
        note = await self.get_note(path)
        if not note:
            return None
        
        if content is not None:
            note.content = content
        if title is not None:
            note.title = title
        if tags is not None:
            note.tags = tags
        
        note.modified_at = datetime.utcnow()
        note.frontmatter["modified"] = note.modified_at.isoformat()
        
        return await self.create_note(
            title=note.title,
            content=note.content,
            folder=path.split("/")[0] if "/" in path else "notes",
            tags=note.tags,
            metadata=note.frontmatter,
        )
    
    async def delete_note(self, path: str) -> bool:
        """Delete a note via HTTP."""
        try:
            client = await self._get_client()
            response = await client.delete(f"/vaults/{self.vault_name}/files/{path}")
            return response.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Failed to delete note: {e}")
            return False
    
    async def search_notes(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        limit: int = 50,
    ) -> List[NoteSearchResult]:
        """Search notes via HTTP."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"/vaults/{self.vault_name}/search",
                json={
                    "query": query,
                    "tags": tags,
                    "folder": folder,
                    "limit": limit
                }
            )
            
            if response.status_code != 200:
                return []
            
            results = []
            for item in response.json().get("results", []):
                note = Note(
                    id=uuid4(),
                    title=item.get("title", ""),
                    content=item.get("content", ""),
                    path=item.get("path", ""),
                    tags=item.get("tags", []),
                )
                results.append(NoteSearchResult(note=note, score=item.get("score", 0.0)))
            
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def list_notes(
        self,
        folder: str = "notes",
    ) -> List[str]:
        """List note paths in a folder."""
        try:
            client = await self._get_client()
            response = await client.get(f"/vaults/{self.vault_name}/files/{folder}")
            
            if response.status_code != 200:
                return []
            
            return response.json().get("files", [])
            
        except Exception as e:
            logger.error(f"Failed to list notes: {e}")
            return []
    
    async def get_tags(self) -> List[str]:
        """Get all unique tags in the vault."""
        try:
            client = await self._get_client()
            response = await client.get(f"/vaults/{self.vault_name}/tags")
            
            if response.status_code == 200:
                return response.json().get("tags", [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get tags: {e}")
            return []
    
    def _sanitize_filename(self, title: str) -> str:
        """Convert title to safe filename."""
        import re
        filename = re.sub(r'[<>:"/\\|?*]', '', title)
        filename = filename.replace(' ', '_')
        return filename[:200]
    
    def _parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from note."""
        import yaml
        
        if not content.startswith("---"):
            return {}, content
        
        try:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return frontmatter, body
        except Exception as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
        
        return {}, content


# ============================================================================
# 2ndBrain Long-term Memory Store
# ============================================================================

class SecondBrainStore:
    """
    L2 Long-term Memory store using Obsidian via HTTP.
    
    Provides:
    - Personal knowledge management via REST API
    - Note-taking with wiki-links
    - Tag-based organization
    - Full-text search
    """
    
    def __init__(
        self,
        obsidian_client: Optional[ObsidianClient] = None,
    ):
        self.obsidian = obsidian_client or ObsidianClient()
    
    async def initialize(self) -> bool:
        """Initialize the 2ndBrain store."""
        return await self.obsidian.connect()
    
    async def close(self) -> None:
        """Close the store."""
        await self.obsidian.close()
    
    async def store(
        self,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store a note in 2ndBrain via HTTP."""
        title = title or self._generate_title(content)
        
        if user_id:
            tags = tags or []
            tags.append(f"user:{user_id}")
        
        note_metadata = metadata or {}
        if user_id:
            note_metadata["user_id"] = user_id
        
        note = await self.obsidian.create_note(
            title=title,
            content=content,
            folder=folder or "notes",
            tags=tags,
            metadata=note_metadata,
        )
        
        logger.info(f"Stored note in 2ndBrain: {note.id}")
        return note.id
    
    async def retrieve(self, path: str) -> Optional[Note]:
        """Retrieve a note by path."""
        return await self.obsidian.get_note(path)
    
    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[NoteSearchResult]:
        """Search notes in 2ndBrain."""
        if user_id:
            tags = tags or []
            tags.append(f"user:{user_id}")
        
        return await self.obsidian.search_notes(
            query=query,
            tags=tags,
            limit=limit,
        )
    
    async def get_user_notes(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[Note]:
        """Get all notes for a specific user."""
        results = await self.obsidian.search_notes(
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
        """Update a note."""
        return await self.obsidian.update_note(path, content, title, tags)
    
    def _generate_title(self, content: str) -> str:
        """Generate a title from content."""
        first_line = content.split('\n')[0].strip()
        if first_line:
            return first_line[:100]
        return f"Note {datetime.utcnow().isoformat()}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get 2ndBrain statistics."""
        return {
            "endpoint": self.obsidian.endpoint,
            "vault": self.obsidian.vault_name,
        }


# Global 2ndBrain store instance
_global_secondbrain_store: Optional[SecondBrainStore] = None


def get_secondbrain_store(
    config: Optional[Dict[str, Any]] = None,
) -> SecondBrainStore:
    """Get or create global 2ndBrain store."""
    global _global_secondbrain_store
    if _global_secondbrain_store is None:
        _global_secondbrain_store = SecondBrainStore(
            obsidian_client=ObsidianClient(config) if config else None
        )
    return _global_secondbrain_store
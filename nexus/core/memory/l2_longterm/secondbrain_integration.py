"""
XenoSys Memory System - L2 Long-term Memory (2ndBrain)
Built on Obsidian for user materials and notes.

Obsidian: https://obsidian.md
The user's second brain - personal knowledge management.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

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


@dataclass
class Folder:
    """A folder in the Obsidian vault."""
    path: str
    name: str
    parent: Optional[str] = None


# ============================================================================
# Obsidian Integration
# ============================================================================

class ObsidianClient:
    """
    Client for Obsidian vault operations.
    
    Provides:
    - Note CRUD operations
    - Folder management
    - YAML frontmatter parsing
    - Wiki-link resolution
    - Tag-based organization
    """
    
    def __init__(self, vault_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.vault_path = Path(vault_path or self.config.get("vault_path", "./2ndbrain"))
        self._ensure_vault()
    
    def _ensure_vault(self) -> None:
        """Ensure vault directory exists."""
        self.vault_path.mkdir(parents=True, exist_ok=True)
        
        # Create default folders
        (self.vault_path / "inbox").mkdir(exist_ok=True)
        (self.vault_path / "notes").mkdir(exist_ok=True)
        (self.vault_path / "archives").mkdir(exist_ok=True)
    
    async def create_note(
        self,
        title: str,
        content: str = "",
        folder: str = "notes",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Note:
        """Create a new note in the vault."""
        # Generate filename from title
        filename = self._sanitize_filename(title) + ".md"
        
        # Build path
        note_path = self.vault_path / folder / filename
        note_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build frontmatter
        frontmatter = {
            "title": title,
            "created": datetime.utcnow().isoformat(),
            "modified": datetime.utcnow().isoformat(),
            "tags": tags or [],
        }
        if metadata:
            frontmatter.update(metadata)
        
        # Write note
        note_content = self._build_note_content(frontmatter, content)
        note_path.write_text(note_content, encoding="utf-8")
        
        note = Note(
            id=uuid4(),
            title=title,
            content=content,
            path=str(note_path.relative_to(self.vault_path)),
            tags=tags or [],
            frontmatter=frontmatter,
        )
        
        logger.info(f"Created note: {note.path}")
        return note
    
    async def get_note(self, path: str) -> Optional[Note]:
        """Read a note from the vault."""
        note_path = self.vault_path / path
        
        if not note_path.exists():
            return None
        
        content = note_path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(content)
        
        # Extract title from frontmatter or filename
        title = frontmatter.get("title", note_path.stem)
        tags = frontmatter.get("tags", [])
        links = self._extract_links(body)
        
        stat = note_path.stat()
        
        return Note(
            id=uuid4(),
            title=title,
            content=body,
            path=path,
            tags=tags,
            links=links,
            frontmatter=frontmatter,
            created_at=datetime.fromisoformat(frontmatter.get("created", datetime.utcnow().isoformat())),
            modified_at=datetime.fromisoformat(frontmatter.get("modified", datetime.utcnow().isoformat())),
        )
    
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
        
        # Update fields
        if content is not None:
            note.content = content
        if title is not None:
            note.title = title
        if tags is not None:
            note.tags = tags
        
        note.modified_at = datetime.utcnow()
        note.frontmatter["modified"] = note.modified_at.isoformat()
        
        # Write back
        note_path = self.vault_path / path
        note_content = self._build_note_content(note.frontmatter, note.content)
        note_path.write_text(note_content, encoding="utf-8")
        
        return note
    
    async def delete_note(self, path: str) -> bool:
        """Delete a note (move to archives)."""
        note_path = self.vault_path / path
        
        if not note_path.exists():
            return False
        
        # Move to archives instead of deleting
        archive_path = self.vault_path / "archives" / note_path.name
        note_path.rename(archive_path)
        
        logger.info(f"Archived note: {path} -> {archive_path}")
        return True
    
    async def search_notes(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        limit: int = 50,
    ) -> List[NoteSearchResult]:
        """Search notes by content and tags."""
        results = []
        
        # Determine search folder
        search_path = self.vault_path / (folder or "notes")
        
        # Walk through notes
        for note_path in search_path.rglob("*.md"):
            try:
                note = await self.get_note(str(note_path.relative_to(self.vault_path)))
                if not note:
                    continue
                
                # Filter by tags if specified
                if tags and not any(tag in note.tags for tag in tags):
                    continue
                
                # Simple content search
                if query.lower() in note.content.lower() or query.lower() in note.title.lower():
                    score = self._calculate_score(query, note)
                    results.append(NoteSearchResult(note=note, score=score))
                
            except Exception as e:
                logger.warning(f"Error processing note {note_path}: {e}")
        
        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
    
    async def list_notes(
        self,
        folder: str = "notes",
        recursive: bool = True,
    ) -> List[str]:
        """List note paths in a folder."""
        folder_path = self.vault_path / folder
        
        if not folder_path.exists():
            return []
        
        pattern = "**/*.md" if recursive else "*.md"
        return [str(p.relative_to(self.vault_path)) for p in folder_path.glob(pattern)]
    
    async def get_tags(self) -> List[str]:
        """Get all unique tags in the vault."""
        tags = set()
        
        for note_path in self.vault_path.rglob("*.md"):
            try:
                note = await self.get_note(str(note_path.relative_to(self.vault_path)))
                if note:
                    tags.update(note.tags)
            except Exception:
                pass
        
        return sorted(list(tags))
    
    def _sanitize_filename(self, title: str) -> str:
        """Convert title to safe filename."""
        # Remove special characters
        filename = re.sub(r'[<>:"/\\|?*]', '', title)
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        return filename[:200]  # Limit length
    
    def _build_note_content(
        self,
        frontmatter: Dict[str, Any],
        body: str,
    ) -> str:
        """Build note content with YAML frontmatter."""
        import yaml
        
        fm_yaml = yaml.dump(frontmatter, default_flow_style=False)
        return f"---\n{fm_yaml}---\n\n{body}"
    
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
    
    def _extract_links(self, content: str) -> List[str]:
        """Extract wiki-style links from content."""
        # Match [[link]] pattern
        links = re.findall(r'\[\[([^\]]+)\]\]', content)
        return links
    
    def _calculate_score(self, query: str, note: Note) -> float:
        """Calculate relevance score for search."""
        score = 0.0
        query_lower = query.lower()
        
        # Title match is worth more
        if query_lower in note.title.lower():
            score += 10.0
        
        # Tag match
        for tag in note.tags:
            if query_lower in tag.lower():
                score += 5.0
        
        # Content match
        if query_lower in note.content.lower():
            score += 1.0
        
        # Recency bonus
        hours_old = (datetime.utcnow() - note.modified_at).total_seconds() / 3600
        score += max(0, 1 - hours_old / 24)  # Decay over 24 hours
        
        return score


# ============================================================================
# 2ndBrain Long-term Memory Store
# ============================================================================

class SecondBrainStore:
    """
    L2 Long-term Memory store using Obsidian.
    
    Provides:
    - Personal knowledge management
    - Note-taking with wiki-links
    - Tag-based organization
    - Versioning through git (external)
    - Full-text search
    """
    
    def __init__(
        self,
        obsidian_client: Optional[ObsidianClient] = None,
        default_folder: str = "notes",
    ):
        self.obsidian = obsidian_client or ObsidianClient()
        self.default_folder = default_folder
        self._cache: Dict[str, Note] = {}
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the 2ndBrain store."""
        logger.info("Initialized 2ndBrain (Obsidian) store")
    
    async def store(
        self,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """Store a note in 2ndBrain."""
        # Generate title if not provided
        title = title or self._generate_title(content)
        
        # Add user tag if provided
        if user_id:
            tags = tags or []
            tags.append(f"user:{user_id}")
        
        # Build metadata
        note_metadata = metadata or {}
        if user_id:
            note_metadata["user_id"] = user_id
        
        note = await self.obsidian.create_note(
            title=title,
            content=content,
            folder=folder or self.default_folder,
            tags=tags,
            metadata=note_metadata,
        )
        
        # Update cache
        async with self._lock:
            self._cache[note.path] = note
        
        logger.info(f"Stored note in 2ndBrain: {note.id}")
        return note.id
    
    async def retrieve(self, path: str) -> Optional[Note]:
        """Retrieve a note by path."""
        # Check cache
        async with self._lock:
            note = self._cache.get(path)
        
        if note:
            return note
        
        # Fetch from Obsidian
        return await self.obsidian.get_note(path)
    
    async def search(
        self,
        query: str,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[NoteSearchResult]:
        """Search notes in 2ndBrain."""
        # Add user filter if provided
        if user_id:
            tags = tags or []
            tags.append(f"user:{user_id}")
        
        results = await self.obsidian.search_notes(
            query=query,
            tags=tags,
            limit=limit,
        )
        
        logger.info(f"2ndBrain search returned {len(results)} results")
        return results
    
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
        note = await self.obsidian.update_note(path, content, title, tags)
        
        if note:
            async with self._lock:
                self._cache[path] = note
        
        return note
    
    async def link_notes(
        self,
        source_path: str,
        target_title: str,
    ) -> bool:
        """Add a wiki-link from one note to another."""
        source = await self.retrieve(source_path)
        if not source:
            return False
        
        # Add link to content
        link = f"[[{target_title}]]"
        new_content = source.content + f"\n{link}"
        
        await self.update(source_path, content=new_content)
        return True
    
    async def get_related_notes(
        self,
        note_path: str,
        limit: int = 10,
    ) -> List[Note]:
        """Get notes related through links and tags."""
        note = await self.retrieve(note_path)
        if not note:
            return []
        
        related = []
        
        # Get linked notes
        for link_title in note.links:
            # Search for the linked note
            results = await self.search(link_title, limit=1)
            if results:
                related.append(results[0].note)
        
        # Get notes with same tags
        for tag in note.tags:
            results = await self.search("", tags=[tag], limit=limit)
            for r in results:
                if r.note.path != note_path and r.note not in related:
                    related.append(r.note)
        
        return related[:limit]
    
    def _generate_title(self, content: str) -> str:
        """Generate a title from content."""
        # Use first line or first 50 chars
        first_line = content.split('\n')[0].strip()
        if first_line:
            return first_line[:100]
        return f"Note {datetime.utcnow().isoformat()}"
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get 2ndBrain statistics."""
        notes = await self.obsidian.list_notes()
        tags = await self.obsidian.get_tags()
        
        return {
            "total_notes": len(notes),
            "total_tags": len(tags),
            "vault_path": str(self.obsidian.vault_path),
        }


# Global 2ndBrain store instance
_global_secondbrain_store: Optional[SecondBrainStore] = None


def get_secondbrain_store(
    vault_path: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> SecondBrainStore:
    """Get or create global 2ndBrain store."""
    global _global_secondbrain_store
    if _global_secondbrain_store is None:
        obsidian_config = config or {}
        if vault_path:
            obsidian_config["vault_path"] = vault_path
        _global_secondbrain_store = SecondBrainStore(
            obsidian_client=ObsidianClient(config=obsidian_config)
        )
    return _global_secondbrain_store
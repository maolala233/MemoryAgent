"""Convert parsed document chunks into structured memory files."""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.markdown import build_frontmatter, compose_markdown
from .chunking_service import Chunk


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len] or "chunk"


def _detect_track(text: str) -> str:
    low = text.lower()
    if any(w in low for w in ("decide", "decision", "tradeoff", "chose")):
        return "decision"
    if any(w in low for w in ("workflow", "process", "pipeline", "step")):
        return "workflow"
    if any(w in low for w in ("project", "roadmap", "milestone", "release")):
        return "project"
    if any(w in low for w in ("reference", "doc", "spec", "manual")):
        return "reference"
    return "note"


def _extract_keywords(text: str, limit: int = 6) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    freq: Dict[str, int] = {}
    stopwords = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "have", "has"}
    for w in words:
        if w in stopwords:
            continue
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _extract_action_items(text: str) -> List[str]:
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        for marker in ("- [ ]", "- []", "TODO:", "ACTION:"):
            if stripped.startswith(marker):
                items.append(stripped[len(marker):].strip())
                break
    return items


class DocToMemoryConverter:
    def convert_chunks(self, chunks: List[Chunk],
                       doc_metadata: Dict[str, Any],
                       project_id: Optional[str] = None,
                       memory_type: str = "imported_document") -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        title_base = doc_metadata.get("title", "imported_document")
        for chunk in chunks:
            track = _detect_track(chunk.text)
            keywords = _extract_keywords(chunk.text)
            action_items = _extract_action_items(chunk.text)
            summary = chunk.text[:160].replace("\n", " ").strip()
            slug = _slugify(chunk.section or title_base)
            filename = f"{slug}.md"
            rel_path = f"imports/{_slugify(title_base)}/{filename}"
            frontmatter = {
                "memory_type": memory_type,
                "track": track,
                "project_id": project_id or doc_metadata.get("title", ""),
                "summary": summary,
                "keywords": keywords,
                "source_doc": doc_metadata.get("filename", ""),
                "section": chunk.section,
                "imported_at": datetime.utcnow().isoformat(timespec="seconds"),
                "status": "active",
            }
            body = f"# {chunk.section or title_base}\n\n{chunk.text}"
            if action_items:
                body += "\n\n## Action items\n\n"
                for item in action_items:
                    body += f"- [ ] {item}\n"
            files.append(
                {
                    "rel_path": rel_path,
                    "frontmatter": frontmatter,
                    "content": body,
                }
            )
        return files


doc_to_memory = DocToMemoryConverter()

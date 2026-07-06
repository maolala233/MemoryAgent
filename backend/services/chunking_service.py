"""Document chunking strategies."""
from __future__ import annotations

import re
from typing import List, Optional


class Chunk:
    __slots__ = ("text", "section", "tokens", "index")

    def __init__(self, text: str, section: str, tokens: int, index: int) -> None:
        self.text = text
        self.section = section
        self.tokens = tokens
        self.index = index

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "section": self.section,
            "tokens": self.tokens,
            "index": self.index,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


class ChunkingService:
    def chunk_by_section(self, text: str, headings: Optional[List[str]] = None) -> List[Chunk]:
        sections = self._split_by_headings(text)
        chunks: List[Chunk] = []
        idx = 0
        for section_title, body in sections:
            if not body.strip():
                continue
            chunks.append(Chunk(body, section_title, _estimate_tokens(body), idx))
            idx += 1
        return chunks

    def chunk_by_size(self, text: str, max_tokens: int = 400, overlap: int = 40) -> List[Chunk]:
        words = text.split()
        if not words:
            return []
        chunks: List[Chunk] = []
        idx = 0
        i = 0
        while i < len(words):
            end = min(i + max_tokens, len(words))
            chunk_text = " ".join(words[i:end])
            chunks.append(Chunk(chunk_text, "Body", _estimate_tokens(chunk_text), idx))
            idx += 1
            if end >= len(words):
                break
            i = end - overlap
        return chunks

    def chunk_document(self, text: str, max_tokens: int = 400,
                       overlap: int = 40) -> List[Chunk]:
        """Section-aware chunking that falls back to size-based for big sections."""
        sections = self._split_by_headings(text)
        chunks: List[Chunk] = []
        idx = 0
        for section_title, body in sections:
            if not body.strip():
                continue
            tokens = _estimate_tokens(body)
            if tokens <= max_tokens * 1.5:
                chunks.append(Chunk(body, section_title, tokens, idx))
                idx += 1
            else:
                for sub in self.chunk_by_size(body, max_tokens=max_tokens, overlap=overlap):
                    sub.index = idx
                    sub.section = section_title
                    chunks.append(sub)
                    idx += 1
        if not chunks:
            chunks = self.chunk_by_size(text, max_tokens=max_tokens, overlap=overlap)
        return self._merge_short_chunks(chunks, min_tokens=40)

    def _merge_short_chunks(self, chunks: List[Chunk], min_tokens: int = 40) -> List[Chunk]:
        merged: List[Chunk] = []
        for c in chunks:
            if merged and c.tokens < min_tokens:
                prev = merged[-1]
                prev.text = prev.text + "\n\n" + c.text
                prev.tokens = _estimate_tokens(prev.text)
            else:
                merged.append(Chunk(c.text, c.section, c.tokens, len(merged)))
        for i, c in enumerate(merged):
            c.index = i
        return merged

    @staticmethod
    def _split_by_headings(text: str) -> List[tuple]:
        sections: List[tuple] = []
        current_title = "Introduction"
        buffer: List[str] = []
        for line in text.splitlines():
            if re.match(r"^#{1,6}\s+\S", line):
                if buffer:
                    sections.append((current_title, "\n".join(buffer).strip()))
                    buffer = []
                current_title = re.sub(r"^#{1,6}\s+", "", line).strip() or current_title
            else:
                buffer.append(line)
        if buffer:
            sections.append((current_title, "\n".join(buffer).strip()))
        if not sections:
            sections = [("Document", text)]
        return sections


chunking_service = ChunkingService()

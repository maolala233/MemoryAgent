"""Pydantic schemas for API request/response payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------- Memory ----------
class MemoryDocBase(BaseModel):
    rel_path: str
    title: Optional[str] = None
    memory_type: str = "note"
    track: str = "note"
    project_id: Optional[str] = None
    status: str = "active"
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    open_loops: List[Dict[str, Any]] = Field(default_factory=list)


class MemoryDoc(MemoryDocBase):
    content: str = ""
    frontmatter: Dict[str, Any] = Field(default_factory=dict)
    size_bytes: int = 0
    indexed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class MemoryDocResponse(MemoryDoc):
    pass


class MemoryListResponse(BaseModel):
    total: int
    items: List[MemoryDoc]


class MemoryCreateRequest(BaseModel):
    rel_path: str
    content: str = ""
    memory_type: str = "note"
    track: str = "note"
    project_id: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    track: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None


# ---------- Search ----------
class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    strategy: str = "hybrid"
    track: Optional[str] = None
    memory_type: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[str] = None
    min_score: float = 0.0


class MemoryResult(BaseModel):
    rel_path: str
    title: str
    snippet: str
    score: float
    memory_type: Optional[str] = None
    track: Optional[str] = None
    updated_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    query: str
    strategy: str
    total: int
    results: List[MemoryResult]


class SearchFilters(BaseModel):
    tracks: List[str]
    memory_types: List[str]
    projects: List[str]


# ---------- Stats ----------
class StatsOverview(BaseModel):
    total_docs: int
    total_size: int
    open_loops_count: int
    last_updated: Optional[datetime] = None


class StatsDistribution(BaseModel):
    by_type: Dict[str, int]
    by_track: Dict[str, int]
    by_status: Dict[str, int]


class TimelinePoint(BaseModel):
    date: str
    doc_count: int
    update_count: int


class OpenLoopItem(BaseModel):
    path: str
    title: str
    kind: str
    item: str
    priority: str = "medium"


# ---------- Agents ----------
class AgentInfo(BaseModel):
    id: str
    name: str
    role: str
    description: str
    llm_provider: str
    llm_model: str
    memory_strategy: str
    memory_limit: int
    tools: List[str]


class AgentTestRequest(BaseModel):
    test_prompt: str


class AgentTestResponse(BaseModel):
    response: str
    latency_ms: int
    status: str


# ---------- Chat ----------
class ChatMessage(BaseModel):
    role: str
    content: str
    memories: Optional[List[MemoryResult]] = None
    thinking: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    agent: str = "codex-architect"
    context: List[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    response: str
    memories_used: List[MemoryResult] = Field(default_factory=list)
    thinking: Optional[str] = None
    status: str = "ok"


# ---------- Documents ----------
class ParsedChunk(BaseModel):
    index: int
    section: str
    text: str
    tokens: int


class ParseResponse(BaseModel):
    file_id: str
    filename: str
    total_chunks: int
    metadata: Dict[str, Any]
    chunks: List[ParsedChunk]


class ConvertRequest(BaseModel):
    project_id: Optional[str] = None
    memory_type: str = "imported_document"
    strategy: str = "auto"


class MemoryFilePreview(BaseModel):
    rel_path: str
    frontmatter: Dict[str, Any]
    content: str


class ConvertResponse(BaseModel):
    file_id: str
    memory_files: List[MemoryFilePreview]


class SaveRequest(BaseModel):
    memory_files: List[MemoryFilePreview]


class SaveResponse(BaseModel):
    saved_count: int
    paths: List[str]


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    file_size: int
    page_count: Optional[int] = None


# ---------- Generic ----------
class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None


class RescanResponse(BaseModel):
    docs_indexed: int
    duration_seconds: float

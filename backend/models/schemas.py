"""Pydantic 数据模型：API 请求/响应结构。

涵盖记忆文档、搜索、统计、Agent、聊天、文档导入，
以及 Mandol 的空间管理、单元 CRUD、关系管理、图谱遍历、
多视图检索、智能问答、高阶记忆构建与持久化等模型。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =====================================================================
# 记忆文档（Markdown Vault，兼容旧逻辑）
# =====================================================================
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
    sync_to_mandol: bool = True


class MemoryUpdateRequest(BaseModel):
    content: Optional[str] = None
    memory_type: Optional[str] = None
    track: Optional[str] = None
    status: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None


# =====================================================================
# 搜索
# =====================================================================
class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    strategy: str = "hybrid"  # hybrid|keyword|semantic|mandol|holistic|view|space|graph|text
    track: Optional[str] = None
    memory_type: Optional[str] = None
    status: Optional[str] = None
    project_id: Optional[str] = None
    min_score: float = 0.0
    # Mandol 专属
    view: Optional[str] = None  # base_memory|knowledge|entity_relation|event_causal...
    space_name: Optional[str] = None
    use_rerank: bool = True
    skip_views: Optional[List[str]] = None


class MemoryResult(BaseModel):
    rel_path: str = ""
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    memory_type: Optional[str] = None
    track: Optional[str] = None
    updated_at: Optional[datetime] = None
    # Mandol 专属
    uid: Optional[str] = None
    text: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    scores: Optional[Dict[str, float]] = None
    ranks: Optional[Dict[str, int]] = None


class SearchResponse(BaseModel):
    query: str
    strategy: str
    total: int
    results: List[MemoryResult]


class SearchFilters(BaseModel):
    tracks: List[str]
    memory_types: List[str]
    projects: List[str]


# =====================================================================
# 统计
# =====================================================================
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


# =====================================================================
# Agent
# =====================================================================
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


# =====================================================================
# 聊天
# =====================================================================
class ChatMessage(BaseModel):
    role: str
    content: str
    memories: Optional[List[MemoryResult]] = None
    thinking: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    agent: str = "codex-architect"
    context: List[ChatMessage] = Field(default_factory=list)
    top_k: int = 5
    use_rerank: bool = True
    system_prompt: Optional[str] = None
    temperature: float = 0.3
    max_tokens: Optional[int] = None


class ChatResponse(BaseModel):
    response: str
    memories_used: List[MemoryResult] = Field(default_factory=list)
    thinking: Optional[str] = None
    status: str = "ok"


# =====================================================================
# 文档导入
# =====================================================================
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
    build_mandol: bool = True  # 是否同步构建 Mandol 记忆
    project_id: Optional[str] = None  # 项目 ID（与 convert 一致，便于整链路关联）


class SaveResponse(BaseModel):
    saved_count: int
    paths: List[str]
    mandol_synced: int = 0
    original_path: Optional[str] = None
    summary_path: Optional[str] = None
    summary_text: Optional[str] = None
    extraction: Optional[Dict[str, Any]] = None


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    file_size: int
    page_count: Optional[int] = None


# =====================================================================
# 通用
# =====================================================================
class StatusResponse(BaseModel):
    status: str
    message: Optional[str] = None


class RescanResponse(BaseModel):
    docs_indexed: int
    duration_seconds: float


# =====================================================================
# Mandol 记忆单元
# =====================================================================
class MandolUnitInfo(BaseModel):
    uid: str
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    text: str = ""
    space_name: Optional[str] = None


class MandolUnitCreateRequest(BaseModel):
    uid: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    space_name: Optional[str] = None


class MandolUnitBatchCreateRequest(BaseModel):
    items: List[MandolUnitCreateRequest]


class MandolUnitListResponse(BaseModel):
    total: int
    items: List[MandolUnitInfo]


# =====================================================================
# Mandol 空间管理
# =====================================================================
class SpaceInfo(BaseModel):
    name: str
    unit_count: int = 0
    child_spaces: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpaceListResponse(BaseModel):
    total: int
    items: List[SpaceInfo]


class SpaceCreateRequest(BaseModel):
    name: str


class SpaceAttachRequest(BaseModel):
    parent: str
    child: str


class UnitSpaceRequest(BaseModel):
    uid: str
    space_name: str


# =====================================================================
# Mandol 关系管理
# =====================================================================
class RelationshipCreateRequest(BaseModel):
    source: str
    target: str
    rel_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class RelationshipInfo(BaseModel):
    source: str
    target: str
    rel_type: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class RelationshipListResponse(BaseModel):
    uid: str
    direction: str
    relationships: List[RelationshipInfo]


class RelationshipDeleteRequest(BaseModel):
    source: str
    target: str
    rel_type: Optional[str] = None


# =====================================================================
# Mandol 图谱遍历
# =====================================================================
class BFSExpandRequest(BaseModel):
    seed_uids: List[str]
    per_seed: int = 3
    hops: int = 1
    rel_type: Optional[str] = None


class NeighborsRequest(BaseModel):
    uid: str
    rel_type: Optional[str] = None
    direction: str = "out"  # out|in|all
    top_k: int = 10


class EntitySubgraphRequest(BaseModel):
    query: str
    max_depth: int = 2
    top_k: int = 10


class TraceRequest(BaseModel):
    uid: str
    max_depth: int = 2
    top_k: int = 10


class GraphNode(BaseModel):
    uid: str
    type: str = ""
    name: str = ""
    text: str = ""


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship: str
    confidence: float = 1.0
    properties: Dict[str, Any] = Field(default_factory=dict)


class SubgraphResponse(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)


class TraceResponse(BaseModel):
    chain: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None
    corefs: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


# =====================================================================
# Mandol 检索
# =====================================================================
class MandolRetrieveRequest(BaseModel):
    query: str
    top_k: int = 10
    use_rerank: bool = True
    skip_views: Optional[List[str]] = None
    view: Optional[str] = None  # 按视图检索时指定
    space_name: Optional[str] = None  # 按空间检索时指定


class MandolSearchHit(BaseModel):
    uid: str
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    scores: Dict[str, float] = Field(default_factory=dict)
    ranks: Dict[str, int] = Field(default_factory=dict)


class MandolRetrieveResponse(BaseModel):
    query: str
    mode: str  # holistic|view|space|text
    total: int
    results: List[MandolSearchHit]


# =====================================================================
# Mandol 智能问答
# =====================================================================
class MandolAskRequest(BaseModel):
    query: str
    top_k: int = 5
    use_rerank: bool = True
    system_prompt: Optional[str] = None
    temperature: float = 0.3
    max_tokens: Optional[int] = 4096  # 默认 4096 兼容 thinking 模式 LLM


class MandolAskResponse(BaseModel):
    answer: str
    hits: List[MandolSearchHit] = Field(default_factory=list)
    status: str = "ok"


# =====================================================================
# Mandol 构建 & 合并
# =====================================================================
class BuildRequest(BaseModel):
    mode: str = "auto"  # auto|force
    skip_summary: bool = True  # 跳过 summary 生成，直接用原文切片


class BuildReportResponse(BaseModel):
    status: str
    mode: str = ""
    sessions_processed: int = 0
    units_processed: int = 0
    duration_seconds: float = 0.0
    token_usage: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class MergeResponse(BaseModel):
    status: str
    duration_seconds: float = 0.0


# =====================================================================
# Mandol 统计 & 监控
# =====================================================================
class MandolStatsResponse(BaseModel):
    enabled: bool
    total_units: int = 0
    total_spaces: int = 0
    base_memory_count: int = 0
    entity_count: int = 0
    event_count: int = 0
    summary_count: int = 0
    token_usage: Dict[str, int] = Field(default_factory=dict)
    dirty: bool = False
    error: Optional[str] = None


class MandolMonitorResponse(BaseModel):
    enabled: bool
    monitor: str = ""
    error: Optional[str] = None


# =====================================================================
# Mandol 持久化
# =====================================================================
class SaveSnapshotRequest(BaseModel):
    storage_path: Optional[str] = None
    wait: bool = False


class LoadSnapshotRequest(BaseModel):
    storage_path: str


class SnapshotResponse(BaseModel):
    status: str
    path: str
    units: int = 0
    spaces: int = 0
    duration_seconds: Optional[float] = None
    saved_at: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None

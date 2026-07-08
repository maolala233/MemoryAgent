// 共享 TypeScript 类型，匹配后端 schemas。

// =============== 记忆文档 ===============
export interface MemoryDoc {
  rel_path: string;
  title?: string | null;
  memory_type: string;
  track: string;
  project_id?: string | null;
  status: string;
  summary?: string | null;
  keywords: string[];
  open_loops: OpenLoop[];
  frontmatter: Record<string, unknown>;
  content: string;
  size_bytes: number;
  indexed_at?: string | null;
  verified_at?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
}

export interface OpenLoop {
  kind: string;
  item: string;
  priority?: string;
}

export interface MemoryListResponse {
  total: number;
  items: MemoryDoc[];
}

export interface MemoryResult {
  rel_path: string;
  title: string;
  snippet: string;
  score: number;
  memory_type?: string | null;
  track?: string | null;
  updated_at?: string | null;
  // Mandol 专属
  uid?: string | null;
  text?: string | null;
  raw_data?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  scores?: Record<string, number> | null;
  ranks?: Record<string, number> | null;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  strategy?: string;
  track?: string;
  memory_type?: string;
  status?: string;
  project_id?: string;
  min_score?: number;
  view?: string;
  space_name?: string;
  use_rerank?: boolean;
  skip_views?: string[];
}

export interface SearchResponse {
  query: string;
  strategy: string;
  total: number;
  results: MemoryResult[];
}

export interface SearchFilters {
  tracks: string[];
  memory_types: string[];
  projects: string[];
}

// =============== 统计 ===============
export interface StatsOverview {
  total_docs: number;
  total_size: number;
  open_loops_count: number;
  last_updated?: string | null;
}

export interface StatsDistribution {
  by_type: Record<string, number>;
  by_track: Record<string, number>;
  by_status: Record<string, number>;
}

export interface TimelinePoint {
  date: string;
  doc_count: number;
  update_count: number;
}

export interface OpenLoopItem {
  path: string;
  title: string;
  kind: string;
  item: string;
  priority: string;
}

// =============== Agent ===============
export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  description: string;
  llm_provider: string;
  llm_model: string;
  memory_strategy: string;
  memory_limit: number;
  tools: string[];
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  memories?: MemoryResult[] | null;
  thinking?: string | null;
  streaming?: boolean;
}

// =============== 文档导入 ===============
export interface ParsedChunk {
  index: number;
  section: string;
  text: string;
  tokens: number;
}

export interface MemoryFilePreview {
  rel_path: string;
  frontmatter: Record<string, unknown>;
  content: string;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  status: string;
  file_size: number;
  page_count?: number | null;
}

export interface ParseResponse {
  file_id: string;
  filename: string;
  total_chunks: number;
  metadata: Record<string, unknown>;
  chunks: ParsedChunk[];
}

export interface ConvertResponse {
  file_id: string;
  memory_files: MemoryFilePreview[];
}

export interface SaveResponse {
  saved_count: number;
  paths: string[];
  mandol_synced?: number;
}

export interface TreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  children?: TreeNode[];
}

// =============== Mandol 记忆单元 ===============
export interface MandolUnitInfo {
  uid: string;
  raw_data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  text: string;
}

export interface MandolUnitListResponse {
  total: number;
  items: MandolUnitInfo[];
}

export interface MandolUnitCreateRequest {
  uid: string;
  text: string;
  metadata?: Record<string, unknown>;
  space_name?: string;
}

// =============== Mandol 空间管理 ===============
export interface SpaceInfo {
  name: string;
  unit_count: number;
  child_spaces: string[];
  summary?: string | null;
  metadata: Record<string, unknown>;
}

export interface SpaceListResponse {
  total: number;
  items: SpaceInfo[];
}

// =============== Mandol 关系管理 ===============
export interface RelationshipInfo {
  source: string;
  target: string;
  rel_type: string;
  properties: Record<string, unknown>;
}

export interface RelationshipListResponse {
  uid: string;
  direction: string;
  relationships: RelationshipInfo[];
}

// =============== Mandol 图谱 ===============
export interface GraphNode {
  uid: string;
  type: string;
  name: string;
  text: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  confidence: number;
  properties?: Record<string, unknown>;
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  entities: Record<string, unknown>[];
  events: Record<string, unknown>[];
}

export interface TraceResponse {
  chain: Record<string, unknown>[];
  summary?: Record<string, unknown> | null;
  corefs: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
}

// =============== Mandol 检索 ===============
export interface MandolSearchHit {
  uid: string;
  text: string;
  score: number;
  metadata: Record<string, unknown>;
  raw_data: Record<string, unknown>;
  scores: Record<string, number>;
  ranks: Record<string, number>;
}

export interface MandolRetrieveResponse {
  query: string;
  mode: string;
  total: number;
  results: MandolSearchHit[];
}

// =============== Mandol 问答 ===============
export interface MandolAskResponse {
  answer: string;
  hits: MandolSearchHit[];
  status: string;
}

// =============== Mandol 构建 ===============
export interface BuildReportResponse {
  status: string;
  mode: string;
  sessions_processed: number;
  units_processed: number;
  duration_seconds: number;
  token_usage: Record<string, number>;
  warnings: string[];
  error?: string | null;
}

// =============== Mandol 统计 ===============
export interface MandolStatsResponse {
  enabled: boolean;
  total_units?: number;
  total_spaces?: number;
  base_memory_count?: number;
  entity_count?: number;
  event_count?: number;
  summary_count?: number;
  token_usage?: Record<string, number>;
  dirty?: boolean;
  error?: string | null;
}

export interface SnapshotResponse {
  status: string;
  path: string;
  units: number;
  spaces: number;
}

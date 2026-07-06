// Shared TypeScript types matching backend schemas.

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
}

export interface SearchRequest {
  query: string;
  limit?: number;
  strategy?: "keyword" | "semantic" | "hybrid" | "none";
  track?: string;
  memory_type?: string;
  status?: string;
  project_id?: string;
  min_score?: number;
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
}

export interface TreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  children?: TreeNode[];
}

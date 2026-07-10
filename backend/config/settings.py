"""应用配置：从环境变量加载，提供合理默认值。

整合了 Mandol MemorySystem 所需的全部配置字段，支持前端动态配置：
- LLM（OpenAI 兼容接口，支持 ollama/vllm/云服务）
- Embedder（本地 sentence-transformers 或远程 OpenAI 兼容接口）
- Reranker（本地 CrossEncoder 或远程接口）
- 系统参数（分块、会话、相似度、BFS 扩展等）
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

# 设置 HuggingFace 镜像，解决国内网络无法下载模型的问题
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """后端运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- 路径 ----------------
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    vault_dir: Path = Field(default_factory=lambda: Path("data/vault"))
    db_path: Path = Field(default_factory=lambda: Path("data/codex_memory.db"))
    upload_dir: Path = Field(default_factory=lambda: Path("data/uploads"))
    llm_profiles_path: Path = Field(default_factory=lambda: Path("data/llm_profiles.json"))

    # ---------------- 服务器 ----------------
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # ---------------- 传统 LLM（兼容旧逻辑）----------------
    default_llm_provider: str = "mock"  # mock | ollama | openai
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # ---------------- 传统 Embedding（兼容旧逻辑）----------------
    embedding_provider: str = "mock"  # mock | ollama | openai
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 384

    # ---------------- 缓存 ----------------
    enable_cache: bool = True
    cache_ttl_search: int = 300
    cache_ttl_stats: int = 1800

    # ---------------- 鉴权（可选）----------------
    api_key: Optional[str] = None

    # ================ Mandol 集成 ================
    mandol_enabled: bool = True
    mandol_storage_dir: Path = Field(default_factory=lambda: Path("data/mandol"))
    mandol_enable_persistence: bool = True
    mandol_auto_save_interval: int = 300

    # ---- Mandol LLM（OpenAI 兼容）----
    mandol_llm_model: str = "qwen3.5:9b"
    mandol_llm_base_url: str = "http://localhost:11434/v1"
    mandol_llm_api_key: str = "ollama"

    # ---- Mandol Embedder ----
    mandol_embedder_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    mandol_embedder_device: str = "cpu"  # cpu | cuda | cuda:0
    mandol_embedder_dim: int = 384
    mandol_use_remote_embedder: bool = False
    mandol_embedder_remote_base_url: str = ""
    mandol_embedder_remote_api_path: str = "/v1/embeddings"
    mandol_embedder_remote_timeout: int = 60
    # 本地嵌入模型目录（离线模式优先使用此路径加载）
    mandol_embedder_local_path: str = ""
    mandol_embedder_offline_only: bool = False

    # ---- Mandol Reranker ----
    mandol_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    mandol_reranker_device: str = "cpu"
    mandol_use_remote_reranker: bool = False
    mandol_reranker_remote_base_url: str = ""
    mandol_reranker_remote_api_path: str = "/v1/rerank"
    mandol_reranker_remote_timeout: int = 60
    # 本地 reranker 模型目录（离线模式优先使用此路径加载）
    mandol_reranker_local_path: str = ""
    mandol_reranker_offline_only: bool = False

    # ---- HuggingFace 缓存 ----
    hf_home: str = ""  # 为空则使用默认 ~/.cache/huggingface
    hf_endpoint: str = "https://hf-mirror.com"
    hf_offline: bool = False  # 开启后只使用本地缓存模型

    # ---- Mandol 外部存储：Neo4j 图数据库 ----
    mandol_neo4j_uri: str = "bolt://localhost:7687"
    mandol_neo4j_user: str = "neo4j"
    mandol_neo4j_password: str = "mandol123"
    mandol_neo4j_database: str = "neo4j"

    # ---- Mandol 外部存储：Milvus 向量数据库 ----
    # 远程模式：uri 形如 "http://milvus-host:19530"
    # 本地嵌入式：uri 形如本地 db 文件路径（data/mandol/milvus.db）
    mandol_milvus_uri: str = "http://localhost:19530"
    mandol_milvus_user: str = ""
    mandol_milvus_password: str = ""
    mandol_milvus_db: str = ""
    mandol_milvus_collection: str = "mandol_memory_units"
    mandol_milvus_token: str = ""  # 用于 Milvus 的鉴权 token
    mandol_milvus_secure: bool = False  # https
    # 远程 Milvus 是否启用，关闭时回退到嵌入式
    mandol_milvus_remote_enabled: bool = True

    # ---- 远程 Milvus 用于配置/缓存存储 ----
    # 专门用于存储应用配置项和缓存 KV 数据（与 mandol_milvus_* 同库，但不同 collection）
    app_milvus_uri: str = "http://localhost:19530"
    app_milvus_user: str = ""
    app_milvus_password: str = ""
    app_milvus_db: str = ""
    app_milvus_token: str = ""
    app_milvus_secure: bool = False
    app_milvus_config_collection: str = "codex_config"
    app_milvus_cache_collection: str = "codex_cache"
    app_milvus_remote_enabled: bool = True

    # ---- Mandol 系统参数 ----
    mandol_chunk_max_tokens: int = 512
    mandol_session_time_gap_seconds: int = 1800
    mandol_session_check_interval: int = 20
    mandol_session_max_pending: int = 100
    mandol_similarity_top_k: int = 5
    mandol_similarity_threshold: float = 0.7
    mandol_similarity_recent_window: int = 20
    mandol_bfs_expansion_per_seed: int = 3
    mandol_bfs_expansion_hops: int = 1
    mandol_max_context_units: int = 20
    mandol_max_entities_per_llm: int = 50
    mandol_max_events_per_llm: int = 50
    mandol_promote_threshold: int = 100
    mandol_use_unified_pipeline: bool = True

    def ensure_directories(self) -> None:
        """创建所有必需的目录。"""
        for path in (self.vault_dir, self.upload_dir, self.db_path.parent, self.mandol_storage_dir):
            path.mkdir(parents=True, exist_ok=True)
        # HuggingFace 缓存目录
        if self.hf_home:
            os.environ["HF_HOME"] = self.hf_home
            Path(self.hf_home).mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_ENDPOINT", self.hf_endpoint or "https://hf-mirror.com")
        if self.hf_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


def apply_env_overrides(settings: Settings) -> Settings:
    """允许通过环境变量临时覆盖配置。"""
    if os.getenv("VAULT_DIR"):
        settings.vault_dir = Path(os.getenv("VAULT_DIR"))
    if os.getenv("DB_PATH"):
        settings.db_path = Path(os.getenv("DB_PATH"))
    return settings


settings = Settings()

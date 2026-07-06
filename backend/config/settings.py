"""Application settings loaded from environment with sane defaults."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Codex Memory backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    vault_dir: Path = Field(default_factory=lambda: Path("data/vault"))
    db_path: Path = Field(default_factory=lambda: Path("data/codex_memory.db"))
    upload_dir: Path = Field(default_factory=lambda: Path("data/uploads"))

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # CORS
    cors_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # LLM defaults
    default_llm_provider: str = "mock"  # mock | ollama | openai
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"

    # Embeddings
    embedding_provider: str = "mock"  # mock | ollama | openai
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 384

    # Cache
    enable_cache: bool = True
    cache_ttl_search: int = 300
    cache_ttl_stats: int = 1800

    # Auth (very basic, optional)
    api_key: Optional[str] = None

    def ensure_directories(self) -> None:
        """Create all required directories if missing."""
        for path in (self.vault_dir, self.upload_dir, self.db_path.parent):
            path.mkdir(parents=True, exist_ok=True)

    @property
    def sqlite_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


def apply_env_overrides(settings: Settings) -> Settings:
    """Allow ad-hoc env vars to override settings (already handled by pydantic-settings)."""
    if os.getenv("VAULT_DIR"):
        settings.vault_dir = Path(os.getenv("VAULT_DIR"))
    if os.getenv("DB_PATH"):
        settings.db_path = Path(os.getenv("DB_PATH"))
    return settings


settings = Settings()

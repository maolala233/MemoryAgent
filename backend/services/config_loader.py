"""YAML configuration loader with env-var interpolation."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..config.settings import settings

_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _interpolate(value: Any) -> Any:
    if isinstance(value, str):
        def repl(match: re.Match) -> str:
            name, default = match.group(1), match.group(2)
            return os.environ.get(name, default if default is not None else match.group(0))
        return _ENV_RE.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


class ConfigLoader:
    """Loads YAML configs from the backend/config directory."""

    def __init__(self, config_dir: Optional[Path] = None) -> None:
        self.config_dir = config_dir or (Path(__file__).resolve().parents[1] / "config")

    def load(self, name: str) -> Dict[str, Any]:
        path = self.config_dir / f"{name}.yaml"
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return _interpolate(data)

    def load_models(self) -> Dict[str, Any]:
        return self.load("models")

    def load_agents(self) -> Dict[str, Any]:
        return self.load("agents")

    def load_retrieval(self) -> Dict[str, Any]:
        return self.load("retrieval")

    def load_external_stores(self) -> Dict[str, Any]:
        """加载外部存储（Milvus / Neo4j）持久化配置。"""
        return self.load("external_stores")

    def save_external_stores(self, data: Dict[str, Any]) -> None:
        """写入外部存储配置到 external_stores.yaml。"""
        path = self.config_dir / "external_stores.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)

    def load_model_store(self) -> Dict[str, Any]:
        """加载本地模型（embedder / reranker）持久化配置。"""
        return self.load("model_store")

    def save_model_store(self, data: Dict[str, Any]) -> None:
        """写入本地模型配置到 model_store.yaml。"""
        path = self.config_dir / "model_store.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)


config_loader = ConfigLoader()


def get_models_config() -> Dict[str, Any]:
    cfg = config_loader.load_models()
    # Apply settings overrides if env was set after YAML interpolation
    providers = cfg.get("providers", {})
    if settings.openai_api_key and "openai" in providers:
        providers["openai"]["api_key"] = settings.openai_api_key
    if settings.ollama_base_url and "ollama" in providers:
        providers["ollama"]["base_url"] = settings.ollama_base_url
    return cfg


def get_agents_config() -> Dict[str, Any]:
    return config_loader.load_agents()


def get_retrieval_config() -> Dict[str, Any]:
    return config_loader.load_retrieval()


def save_models_config(data: Dict[str, Any]) -> None:
    """Persist model configuration to models.yaml."""
    path = config_loader.config_dir / "models.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)


def get_external_stores_config() -> Dict[str, Any]:
    """获取外部存储（Milvus / Neo4j）的持久化配置。"""
    return config_loader.load_external_stores()


def save_external_stores_config(data: Dict[str, Any]) -> None:
    """写入外部存储（Milvus / Neo4j）配置。"""
    config_loader.save_external_stores(data)


def get_model_store_config() -> Dict[str, Any]:
    """获取本地模型（embedder / reranker）持久化配置。"""
    return config_loader.load_model_store()


def save_model_store_config(data: Dict[str, Any]) -> None:
    """写入本地模型（embedder / reranker）配置。"""
    config_loader.save_model_store(data)


def apply_model_store_config(target=None) -> None:
    """启动时把 model_store.yaml 中的值写入 settings.mandol_embedder_local_path 等。

    优先级：YAML 持久化配置 > settings 类默认值 > 环境变量。
    """
    cfg = get_model_store_config()
    if not cfg:
        return
    target = target or settings

    for kind in ("embedder", "reranker"):
        block = cfg.get(kind, {}) or {}
        if not isinstance(block, dict):
            continue
        if kind == "embedder":
            local_attr = "mandol_embedder_local_path"
            offline_attr = "mandol_embedder_offline_only"
        else:
            local_attr = "mandol_reranker_local_path"
            offline_attr = "mandol_reranker_offline_only"
        lp = block.get("local_path")
        if lp not in (None, ""):
            setattr(target, local_attr, str(lp))
        if "offline_only" in block:
            setattr(target, offline_attr, bool(block["offline_only"]))


def apply_external_stores_config(target=None) -> None:
    """启动时把 external_stores.yaml 中的值写入 settings.mandol_milvus_* / mandol_neo4j_*。

    优先级：YAML 持久化配置 > settings 类默认值 > 环境变量。
    仅在目标字段为非空时才覆盖，避免空字符串误清空。
    """
    cfg = get_external_stores_config()
    if not cfg:
        return
    target = target or settings

    milvus = cfg.get("milvus", {}) or {}
    if isinstance(milvus, dict):
        mapping = {
            "uri": "mandol_milvus_uri",
            "user": "mandol_milvus_user",
            "password": "mandol_milvus_password",
            "db_name": "mandol_milvus_db",
            "collection": "mandol_milvus_collection",
            "token": "mandol_milvus_token",
        }
        for k, attr in mapping.items():
            v = milvus.get(k)
            if v not in (None, ""):
                setattr(target, attr, v)
        if "secure" in milvus:
            target.mandol_milvus_secure = bool(milvus["secure"])
        if "remote_enabled" in milvus:
            target.mandol_milvus_remote_enabled = bool(milvus["remote_enabled"])

    neo4j = cfg.get("neo4j", {}) or {}
    if isinstance(neo4j, dict):
        mapping = {
            "uri": "mandol_neo4j_uri",
            "user": "mandol_neo4j_user",
            "password": "mandol_neo4j_password",
            "database": "mandol_neo4j_database",
        }
        for k, attr in mapping.items():
            v = neo4j.get(k)
            if v not in (None, ""):
                setattr(target, attr, v)

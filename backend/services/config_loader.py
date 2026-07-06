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

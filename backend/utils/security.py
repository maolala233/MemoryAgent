"""Path safety and basic input validation helpers."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from ..config.settings import settings


def sanitize_rel_path(rel_path: str) -> str:
    """Strip leading slashes, decode URL escapes, block traversal."""
    if not rel_path:
        raise ValueError("Empty path")
    rel_path = unquote(rel_path)
    rel_path = rel_path.lstrip("/\\").replace("\\", "/")
    parts = [p for p in rel_path.split("/") if p not in ("", ".", "..")]
    if not parts:
        raise ValueError("Invalid path")
    return "/".join(parts)


def resolve_vault_path(rel_path: str) -> Path:
    """Return absolute path inside vault, refusing traversal escapes."""
    safe = sanitize_rel_path(rel_path)
    root = settings.vault_dir.resolve()
    full = (root / safe).resolve()
    try:
        full.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes vault: {rel_path}") from exc
    return full


def validate_file_type(filename: str, allowed: tuple = (".md", ".txt", ".pdf", ".docx")) -> bool:
    return filename.lower().endswith(allowed)


def validate_file_size(size: int, max_bytes: int = 50 * 1024 * 1024) -> bool:
    return 0 < size <= max_bytes

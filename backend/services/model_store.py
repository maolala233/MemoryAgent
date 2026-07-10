"""管理本地模型目录与已下载的 HuggingFace 模型列表。

当 `mandol_embedder_offline_only` / `mandol_reranker_offline_only` 开启时，
初始化会从本地目录或 HF 缓存中加载模型，不再访问远端。

提供能力：
- list_local_models(root_dir): 扫描本地候选模型目录
- list_cached_hf_models(): 读取 HF 缓存下的已下载模型
- select_local_model(kind, path): 把指定路径记入 settings
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.settings import settings
from ..utils.logger import info, warn

DEFAULT_HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"


def _candidate_roots() -> List[Path]:
    """返回本地模型候选根目录列表。"""
    roots: List[Path] = []
    if settings.hf_home:
        roots.append(Path(settings.hf_home) / "hub")
    roots.append(DEFAULT_HF_CACHE)
    extra = Path("data/models")
    if extra.exists():
        roots.append(extra)
    return [r for r in roots if r.exists()]


def _looks_like_model_dir(p: Path) -> bool:
    """判断目录是否像一个模型目录。"""
    if not p.is_dir():
        return False
    has_config = (p / "config.json").exists()
    has_weights = any(p.glob("*.safetensors")) or any(p.glob("*.bin")) or any(p.glob("*.pt"))
    has_tokenizer = (p / "tokenizer.json").exists() or (p / "tokenizer_config.json").exists()
    return has_config and (has_weights or has_tokenizer)


def _scan_dir(root: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not root.exists():
        return out
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            # HF 缓存目录通常形如 models--<org>--<name>
            match = re.match(r"^models--(.+)$", child.name)
            if match:
                snapshots = child / "snapshots"
                if snapshots.exists():
                    for snap in snapshots.iterdir():
                        if _looks_like_model_dir(snap):
                            out.append({
                                "id": match.group(1).replace("--", "/"),
                                "path": str(snap),
                                "root": str(child),
                            })
                            break
                continue
            # 普通模型目录
            if _looks_like_model_dir(child):
                out.append({
                    "id": child.name,
                    "path": str(child),
                    "root": str(child.parent),
                })
    except Exception as exc:
        warn(f"扫描模型目录失败 {root}: {exc}")
    return out


def list_local_models() -> Dict[str, Any]:
    """列出所有可用的本地模型（候选 embedder/reranker）。"""
    roots = _candidate_roots()
    models: List[Dict[str, Any]] = []
    seen = set()
    for r in roots:
        for m in _scan_dir(r):
            key = m["path"]
            if key in seen:
                continue
            seen.add(key)
            models.append(m)
    return {
        "roots": [str(r) for r in roots],
        "models": models,
        "hf_home": settings.hf_home or str(DEFAULT_HF_CACHE.parent),
    }


def select_local_model(kind: str, path: str) -> Dict[str, Any]:
    """把指定本地路径设置为 embedder 或 reranker 的模型。

    kind: "embedder" | "reranker"
    """
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return {"ok": False, "error": f"路径不存在: {path}"}
    if not _looks_like_model_dir(p):
        return {"ok": False, "error": f"目录不是有效的模型目录: {path}"}
    if kind == "embedder":
        settings.mandol_embedder_local_path = str(p)
        settings.mandol_embedder_offline_only = True
    elif kind == "reranker":
        settings.mandol_reranker_local_path = str(p)
        settings.mandol_reranker_offline_only = True
    else:
        return {"ok": False, "error": f"未知的 kind: {kind}"}
    info(f"已选择本地 {kind} 模型: {p}")
    return {
        "ok": True,
        "kind": kind,
        "path": str(p),
        "offline_only": True,
    }


def clear_local_model(kind: str) -> Dict[str, Any]:
    """清除本地模型选择，回退到远端/默认。"""
    if kind == "embedder":
        settings.mandol_embedder_local_path = ""
        settings.mandol_embedder_offline_only = False
    elif kind == "reranker":
        settings.mandol_reranker_local_path = ""
        settings.mandol_reranker_offline_only = False
    else:
        return {"ok": False, "error": f"未知的 kind: {kind}"}
    return {"ok": True, "kind": kind}


def set_offline_mode(enabled: bool) -> Dict[str, Any]:
    """开启/关闭全局 HuggingFace 离线模式。"""
    settings.hf_offline = bool(enabled)
    os.environ["HF_HUB_OFFLINE"] = "1" if enabled else "0"
    os.environ["TRANSFORMERS_OFFLINE"] = "1" if enabled else "0"
    return {"ok": True, "offline": bool(enabled)}


def current_models() -> Dict[str, Any]:
    """返回当前生效的 embedder / reranker 配置。"""
    return {
        "embedder": {
            "model": settings.mandol_embedder_model,
            "local_path": settings.mandol_embedder_local_path,
            "offline_only": settings.mandol_embedder_offline_only,
            "device": settings.mandol_embedder_device,
            "use_remote": settings.mandol_use_remote_embedder,
        },
        "reranker": {
            "model": settings.mandol_reranker_model,
            "local_path": settings.mandol_reranker_local_path,
            "offline_only": settings.mandol_reranker_offline_only,
            "device": settings.mandol_reranker_device,
            "use_remote": settings.mandol_use_remote_reranker,
        },
        "hf_offline": settings.hf_offline,
        "hf_home": settings.hf_home,
    }

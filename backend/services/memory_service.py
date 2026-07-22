"""Memory vault CRUD + indexing service.

Files are stored on disk as Markdown with YAML frontmatter; metadata and a
full-text index live in SQLite. Vector embeddings are persisted in
`memory_vectors` for semantic retrieval.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config.settings import settings
from ..database import db
from ..utils.logger import info, warn
from ..utils.markdown import (
    compose_markdown,
    extract_open_loops,
    extract_title,
    split_frontmatter,
)
from ..utils.security import resolve_vault_path, sanitize_rel_path
from .cache_service import cache
from .llm_adapter import get_embedding_provider


def _run_async(coro):
    """Run a coroutine from sync code, even inside a running event loop."""
    try:
        asyncio.get_running_loop()
        # We're inside a running loop — run in a separate thread.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        # No running loop — safe to use asyncio.run directly.
        return asyncio.run(coro)


class MemoryService:
    """High-level operations over the memory vault."""

    def __init__(self) -> None:
        self._embedding = get_embedding_provider()

    # ---------------- Read ----------------
    def get_document(self, rel_path: str) -> Optional[Dict[str, Any]]:
        safe = sanitize_rel_path(rel_path)
        meta = db.get_doc(safe)
        path = resolve_vault_path(safe)
        if not path.exists():
            if meta:
                meta["content"] = meta.get("summary", "") or ""
            return meta
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(raw)
        if meta is None:
            meta = {
                "rel_path": safe,
                "title": extract_title(body, safe),
                "memory_type": frontmatter.get("memory_type", "note"),
                "track": frontmatter.get("track", "note"),
                "project_id": frontmatter.get("project_id"),
                "status": frontmatter.get("status", "active"),
                "summary": frontmatter.get("summary"),
                "keywords": frontmatter.get("keywords", []),
                "open_loops": extract_open_loops(body),
                "frontmatter": frontmatter,
                "size_bytes": path.stat().st_size,
                "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
            }
        meta["content"] = body
        meta.setdefault("frontmatter", frontmatter)
        meta.setdefault("size_bytes", path.stat().st_size)
        return meta

    def list_documents(
        self,
        skip: int = 0,
        limit: int = 50,
        track: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = None,
        project_id: Optional[str] = None,
        has_open_loop: Optional[bool] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        return db.list_docs(
            skip=skip, limit=limit, track=track, memory_type=memory_type,
            status=status, project_id=project_id, has_open_loop=has_open_loop,
        )

    def get_stats(self) -> Dict[str, Any]:
        cached = cache.get("stats:overview")
        if cached:
            return cached
        stats = db.stats_overview()
        cache.set("stats:overview", stats, ttl=settings.cache_ttl_stats)
        return stats

    def get_open_loops(self) -> List[Dict[str, Any]]:
        return db.stats_open_loops()

    # ---------------- Write ----------------
    def create_document(self, rel_path: str, content: str,
                        memory_type: str = "note", track: str = "note",
                        project_id: Optional[str] = None,
                        summary: Optional[str] = None,
                        keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        safe = sanitize_rel_path(rel_path)
        if not safe.endswith(".md"):
            safe = safe + ".md"
        path = resolve_vault_path(safe)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = content
        frontmatter = {
            "memory_type": memory_type,
            "track": track,
            "project_id": project_id or "",
            "summary": summary or "",
            "keywords": keywords or [],
            "status": "active",
            "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        }
        path.write_text(compose_markdown(frontmatter, body), encoding="utf-8")
        doc = self._index_file(safe, frontmatter, body)
        cache.invalidate_prefix("stats:")
        cache.invalidate_prefix("search:")
        db.audit("create", safe)
        
        # Sync to Mandol if enabled
        self._sync_to_mandol(safe, body, frontmatter)
        
        return doc

    def update_document(self, rel_path: str, content: Optional[str] = None,
                        memory_type: Optional[str] = None,
                        track: Optional[str] = None,
                        status: Optional[str] = None,
                        summary: Optional[str] = None,
                        keywords: Optional[List[str]] = None) -> Dict[str, Any]:
        safe = sanitize_rel_path(rel_path)
        path = resolve_vault_path(safe)
        if not path.exists():
            raise FileNotFoundError(f"Memory not found: {safe}")
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = split_frontmatter(raw)
        if content is not None:
            body = content
        if memory_type:
            frontmatter["memory_type"] = memory_type
        if track:
            frontmatter["track"] = track
        if status:
            frontmatter["status"] = status
        if summary is not None:
            frontmatter["summary"] = summary
        if keywords is not None:
            frontmatter["keywords"] = keywords
        frontmatter["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
        path.write_text(compose_markdown(frontmatter, body), encoding="utf-8")
        doc = self._index_file(safe, frontmatter, body)
        cache.invalidate_prefix("stats:")
        cache.invalidate_prefix("search:")
        db.audit("update", safe)
        # 同步更新到 Mandol
        self._sync_to_mandol(safe, body, frontmatter)
        return doc

    def delete_document(self, rel_path: str, soft: bool = True) -> None:
        safe = sanitize_rel_path(rel_path)
        path = resolve_vault_path(safe)
        if path.exists() and not soft:
            path.unlink()
        elif path.exists() and soft:
            raw = path.read_text(encoding="utf-8")
            frontmatter, body = split_frontmatter(raw)
            frontmatter["status"] = "deleted"
            frontmatter["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
            path.write_text(compose_markdown(frontmatter, body), encoding="utf-8")
        db.delete_doc(safe, soft=soft)
        cache.invalidate_prefix("stats:")
        cache.invalidate_prefix("search:")
        db.audit("delete", safe)

    # ---------------- Indexing ----------------
    def rescan_vault(self, skip_embed_if_exists: bool = True) -> Dict[str, Any]:
        """重扫描 vault 文件，更新 SQLite 索引。

        Args:
            skip_embed_if_exists: 若为 True（默认），跳过已有向量的文档，
                                   避免启动时对所有文档重新 embedding 拖慢速度。
                                   只有没有向量的文档（新文档）才会计算向量。
        """
        start = datetime.utcnow()
        root = settings.vault_dir
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        count = 0
        embed_count = 0
        skip_count = 0
        for path in root.rglob("*.md"):
            if any(part.startswith(".") for part in path.parts):
                continue
            rel = path.relative_to(root).as_posix()
            try:
                raw = path.read_text(encoding="utf-8")
                frontmatter, body = split_frontmatter(raw)
                
                # 判断是否已有向量（含 chunk 向量），跳过 re-embedding
                should_embed = True
                if skip_embed_if_exists:
                    existing = db.get_vector(rel)
                    if existing is not None:
                        should_embed = False
                        skip_count += 1
                if should_embed:
                    embed_count += 1
                self._index_file(rel, frontmatter, body, embed=should_embed)
                count += 1
            except Exception as exc:
                warn(f"Failed to index {rel}", exc=exc)
        elapsed = (datetime.utcnow() - start).total_seconds()
        cache.invalidate_prefix("stats:")
        cache.invalidate_prefix("search:")
        info(f"Rescan complete: {count} docs in {elapsed:.2f}s (embedded={embed_count}, skipped={skip_count})")
        return {"docs_indexed": count, "duration_seconds": elapsed, "embedded": embed_count, "skipped": skip_count}

    def _index_file(self, rel_path: str, frontmatter: Dict[str, Any],
                    body: str, embed: bool = True) -> Dict[str, Any]:
        title = frontmatter.get("title") or extract_title(body, rel_path)
        loops = extract_open_loops(body)
        doc = {
            "rel_path": rel_path,
            "title": title,
            "memory_type": frontmatter.get("memory_type", "note"),
            "track": frontmatter.get("track", "note"),
            "project_id": frontmatter.get("project_id"),
            "status": frontmatter.get("status", "active"),
            "summary": frontmatter.get("summary"),
            "keywords": frontmatter.get("keywords", []),
            "open_loops": loops,
            "frontmatter": frontmatter,
            "body": body,  # 关键: 存到 memory_docs.body 供 LIKE 检索
            "size_bytes": len(body.encode("utf-8")),
            "updated_at": frontmatter.get("updated_at") or datetime.utcnow().isoformat(timespec="seconds"),
            "created_at": frontmatter.get("created_at"),
            "verified_at": frontmatter.get("verified_at"),
        }
        db.upsert_doc(doc)
        db.upsert_fts(rel_path, title, body, doc.get("summary") or "")
        if embed:
            # 改进: 对大文档按 chunk 切分,每个 chunk 独立 embedding 并入库
            # 避免 body[:2000] 截断导致的中后段内容无法被语义检索命中
            try:
                from .chunking_service import chunking_service
                chunks = chunking_service.chunk_document(body, max_tokens=250, overlap=40)
                if not chunks:
                    vector = _run_async(self._embedding.embed(f"{title}\n{body[:2000]}"))
                    db.upsert_vector(rel_path, vector, self._embedding.__class__.__name__)
                elif len(chunks) == 1:
                    vector = _run_async(self._embedding.embed(f"{title}\n{chunks[0].text[:2000]}"))
                    db.upsert_vector(rel_path, vector, self._embedding.__class__.__name__)
                else:
                    # 多个 chunk: 每个 chunk 独立 embedding,子 chunk 用于精确召回
                    chunk_vectors = []
                    for c in chunks:
                        text = f"[{c.section}] {c.text}"
                        try:
                            vec = _run_async(self._embedding.embed(text))
                            chunk_vectors.append((c.index, vec, c.section, c.text[:200]))
                        except Exception as exc:
                            warn(f"Chunk embedding failed for {rel_path}#{c.index}: {exc}")
                    if chunk_vectors:
                        # 主向量用所有 chunk 的平均,保证整文档语义可检索
                        dim = len(chunk_vectors[0][1])
                        avg = [0.0] * dim
                        for _, v, _, _ in chunk_vectors:
                            for i, x in enumerate(v):
                                avg[i] += x
                        avg = [x / len(chunk_vectors) for x in avg]
                        db.upsert_vector(rel_path, avg, self._embedding.__class__.__name__)
                        # 子 chunk 向量(用于精确命中某段)
                        for idx, vec, sec, snippet in chunk_vectors:
                            db.upsert_vector(
                                f"{rel_path}#chunk{idx}",
                                vec,
                                self._embedding.__class__.__name__,
                            )
                            db.upsert_fts(
                                f"{rel_path}#chunk{idx}",
                                f"{title} - {sec}",
                                snippet,
                                snippet[:80],
                            )
            except Exception as exc:
                warn(f"Embedding failed for {rel_path}: {exc}")
        return doc

    def ensure_seed_data(self) -> None:
        """Seed the vault with example memories on first run."""
        root = settings.vault_dir
        if any(root.glob("*.md")) or db.stats_overview()["total_docs"] > 0:
            return
        seeds = [
            ("projects/project_aether_spec.md", "Project Aether Spec",
             "project", "project", "Project Aether is a distributed memory platform."),
            ("workflows/workflow_refinement_v4.md", "Workflow Refinement v4",
             "workflow", "workflow", "Refined ingestion workflow with chunk deduplication."),
            ("decisions/decision_matrix_q3.md", "Decision Matrix Q3",
             "decision", "decision", "Q3 architecture decisions and tradeoffs."),
            ("notes/api_documentation_draft.md", "API Documentation Draft",
             "note", "note", "Draft for the public REST API documentation."),
            ("notes/onboarding_checklist.md", "Onboarding Checklist",
             "note", "note", "Checklist for new team members."),
        ]
        for rel, title, mtype, track, summary in seeds:
            body = f"# {title}\n\n{summary}\n\n- [ ] Confirm scope\n- [ ] Schedule kickoff\n"
            self.create_document(rel, body, memory_type=mtype, track=track,
                                 summary=summary, keywords=[track, mtype])
        info(f"Seeded {len(seeds)} example memories")

    def _sync_to_mandol(self, rel_path: str, body: str, frontmatter: Dict[str, Any]) -> None:
        """Sync document to Mandol if enabled."""
        try:
            from .mandol_service import mandol_service
            if mandol_service.is_enabled:
                mandol_service.sync_document(rel_path, body, frontmatter)
        except Exception as exc:
            warn(f"Failed to sync {rel_path} to Mandol: {exc}")


memory_service = MemoryService()

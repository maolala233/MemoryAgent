"""Document upload + parse + convert + save router."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config.settings import settings
from ..database import db
from ..models.schemas import (
    ConvertRequest,
    ConvertResponse,
    MemoryFilePreview,
    ParseResponse,
    ParsedChunk,
    SaveRequest,
    SaveResponse,
    StatusResponse,
    UploadResponse,
)
from ..services.chunking_service import chunking_service, Chunk
from ..services.doc_to_memory import doc_to_memory
from ..services.document_parser import document_parser
from ..services.memory_service import memory_service
from ..services.summary_service import summary_generator
from ..utils.logger import warn
from ..utils.security import validate_file_type, validate_file_size

router = APIRouter(prefix="/api/documents", tags=["documents"])

_FILE_REGISTRY: Dict[str, dict] = {}


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    if not validate_file_type(file.filename or ""):
        raise HTTPException(status_code=400, detail="Unsupported file type")
    contents = await file.read()
    if not validate_file_size(len(contents)):
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    file_id = uuid.uuid4().hex[:12]
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.upload_dir / f"{file_id}_{file.filename}"
    out_path.write_bytes(contents)
    _FILE_REGISTRY[file_id] = {
        "filename": file.filename,
        "path": str(out_path),
        "size": len(contents),
    }
    db.audit("upload", file.filename, f"file_id={file_id}")
    return UploadResponse(
        file_id=file_id,
        filename=file.filename or "unknown",
        status="uploaded",
        file_size=len(contents),
    )


@router.post("/{file_id}/parse", response_model=ParseResponse)
def parse(file_id: str) -> ParseResponse:
    info = _FILE_REGISTRY.get(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
    parsed = document_parser.parse(Path(info["path"]))
    text = parsed.get("text", "")
    metadata = document_parser.extract_metadata(text, info["filename"])
    metadata["pages"] = parsed.get("pages", 1)
    metadata["format"] = parsed.get("metadata", {}).get("format")
    chunks = chunking_service.chunk_document(text)
    info["text"] = text
    info["metadata"] = metadata
    info["chunks"] = [c.to_dict() for c in chunks]
    return ParseResponse(
        file_id=file_id,
        filename=info["filename"],
        total_chunks=len(chunks),
        metadata=metadata,
        chunks=[ParsedChunk(**c) for c in info["chunks"]],
    )


@router.post("/{file_id}/convert-to-memory", response_model=ConvertResponse)
def convert_to_memory(file_id: str, req: ConvertRequest) -> ConvertResponse:
    info = _FILE_REGISTRY.get(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
    if "chunks" not in info:
        parse(file_id)
        info = _FILE_REGISTRY[file_id]
    chunks = [Chunk(c["text"], c["section"], c["tokens"], c["index"])
              for c in info["chunks"]]
    files = doc_to_memory.convert_chunks(
        chunks, info["metadata"],
        project_id=req.project_id, memory_type=req.memory_type,
    )
    info["memory_files"] = files
    return ConvertResponse(
        file_id=file_id,
        memory_files=[MemoryFilePreview(**f) for f in files],
    )


@router.post("/{file_id}/save", response_model=SaveResponse)
def save(file_id: str, req: SaveRequest) -> SaveResponse:
    info = _FILE_REGISTRY.get(file_id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
    files = req.memory_files or info.get("memory_files", [])
    saved_paths: list[str] = []
    mandol_synced = 0
    # 1) 自动写一份原始 markdown 入库
    original_path: str | None = None
    try:
        title_base = info["metadata"].get("title") or info.get("filename", "imported_document")
        original = summary_generator.generate_original_markdown(
            title=title_base,
            raw_text=info.get("text", ""),
            source_doc=info.get("filename", ""),
            project_id=req.project_id,
        )
        if original:
            original_path = original["rel_path"]
            saved_paths.append(original_path)
            # 同步到 Mandol
            if req.build_mandol:
                from ..services.mandol_service import mandol_service
                if mandol_service.is_enabled and mandol_service.sync_document(
                    original_path, original["content"],
                    metadata={"memory_type": "imported_original", "track": "source"},
                ):
                    mandol_synced += 1
    except Exception as exc:
        warn(f"自动生成原始 markdown 失败: {exc}")
    # 2) LLM 摘要
    summary_path: str | None = None
    summary_text: str | None = None
    if req.build_mandol:
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                summary = loop.run_until_complete(
                    summary_generator.generate_for_document(
                        title=info["metadata"].get("title") or info.get("filename", "imported_document"),
                        raw_text=info.get("text", ""),
                        source_doc=info.get("filename", ""),
                        project_id=req.project_id,
                    )
                )
            finally:
                loop.close()
            if summary:
                summary_path = summary["rel_path"]
                summary_text = summary.get("summary")
                saved_paths.append(summary_path)
                from ..services.mandol_service import mandol_service
                if mandol_service.is_enabled and mandol_service.sync_document(
                    summary_path, summary["content"],
                    metadata={"memory_type": "imported_summary", "track": "summary"},
                ):
                    mandol_synced += 1
        except Exception as exc:
            warn(f"LLM 摘要生成失败: {exc}")
    # 3) 保存 chunked 记忆文件
    for f in files:
        try:
            doc = memory_service.create_document(
                f.rel_path, f.content,
                memory_type=f.frontmatter.get("memory_type", "imported_document"),
                track=f.frontmatter.get("track", "note"),
                project_id=f.frontmatter.get("project_id"),
                summary=f.frontmatter.get("summary"),
                keywords=f.frontmatter.get("keywords", []),
            )
            saved_paths.append(doc["rel_path"])
            # 同步到 Mandol
            if req.build_mandol:
                from ..services.mandol_service import mandol_service
                if mandol_service.is_enabled:
                    if mandol_service.sync_document(
                        doc["rel_path"], f.content,
                        metadata={
                            "memory_type": f.frontmatter.get("memory_type", "imported_document"),
                            "track": f.frontmatter.get("track", "note"),
                            "title": doc.get("title"),
                        },
                    ):
                        mandol_synced += 1
        except Exception as exc:
            warn(f"Save failed for {f.rel_path}: {exc}")
    # 4) 触发高阶记忆构建
    if req.build_mandol and mandol_synced > 0:
        from ..services.mandol_service import mandol_service
        if mandol_service.is_enabled:
            try:
                mandol_service.build_high_level(mode="auto")
            except Exception as exc:
                warn(f"Build high level after import failed: {exc}")
            # 5) 自动后台保存 snapshot（避免阻塞）
            try:
                mandol_service.save()
            except Exception as exc:
                warn(f"自动 save snapshot 失败: {exc}")
    db.audit("import", file_id, f"saved={len(saved_paths)}, mandol_synced={mandol_synced}")
    return SaveResponse(
        saved_count=len(saved_paths),
        paths=saved_paths,
        mandol_synced=mandol_synced,
        original_path=original_path,
        summary_path=summary_path,
        summary_text=summary_text,
    )


@router.delete("/{file_id}", response_model=StatusResponse)
def delete_temp(file_id: str) -> StatusResponse:
    info = _FILE_REGISTRY.pop(file_id, None)
    if info and info.get("path"):
        try:
            Path(info["path"]).unlink(missing_ok=True)
        except Exception as exc:
            warn(f"Failed to delete temp file: {exc}")
    return StatusResponse(status="deleted", message=file_id)


@router.get("/status/{file_id}")
def status(file_id: str) -> dict:
    info = _FILE_REGISTRY.get(file_id)
    if not info:
        return {"status": "missing", "progress": 0}
    progress = 100 if info.get("memory_files") else (50 if info.get("chunks") else 25)
    return {"status": "uploaded" if progress < 50 else "ready", "progress": progress}

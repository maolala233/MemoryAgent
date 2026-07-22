"""Convert parsed document chunks into structured memory files."""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.markdown import build_frontmatter, compose_markdown
from .chunking_service import Chunk


def _slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len] or "chunk"


def _detect_track(text: str) -> str:
    low = text.lower()
    if any(w in low for w in ("decide", "decision", "tradeoff", "chose")):
        return "decision"
    if any(w in low for w in ("workflow", "process", "pipeline", "step")):
        return "workflow"
    if any(w in low for w in ("project", "roadmap", "milestone", "release")):
        return "project"
    if any(w in low for w in ("reference", "doc", "spec", "manual")):
        return "reference"
    return "note"


def _extract_keywords(text: str, limit: int = 6) -> List[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    freq: Dict[str, int] = {}
    stopwords = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "have", "has"}
    for w in words:
        if w in stopwords:
            continue
        freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:limit]]


def _extract_action_items(text: str) -> List[str]:
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        for marker in ("- [ ]", "- []", "TODO:", "ACTION:"):
            if stripped.startswith(marker):
                items.append(stripped[len(marker):].strip())
                break
    return items


class DocToMemoryConverter:
    # 摘要改写 Prompt: 用 LLM 把 chunk 改写成 1-2 句中文摘要
    # 强调: 摘要必须包含"标题"+"核心事实", 用于 embedding 检索 + LLM 召回后上下文重建
    _SUMMARY_PROMPT = """你是企业知识管理助手。请基于以下文档片段生成一段中文摘要 (80-150 字), 用于语义检索。

要求:
1. 必须包含章节标题作为前缀
2. 突出该片段的核心事实/规则/流程/数值
3. 保留所有产品名称、专有名词、关键数字
4. 1-2 句话, 不超过 150 字

章节标题: {section}

文档片段:
{content}

只输出摘要文本本身, 不要任何前缀/解释。"""

    async def _rewrite_summary(self, section: str, text: str) -> Optional[str]:
        """用 mandol LLM 改写 summary。失败时返回 None, 调用方应回退到默认截断。"""
        try:
            from .mandol_service import mandol_service
            if not mandol_service.is_enabled:
                return None
            system = mandol_service._require()
            llm = (
                getattr(system, "_llm_provider", None)
                or getattr(system, "llm_provider", None)
            )
            if llm is None or not hasattr(llm, "chat"):
                return None
            content = text[:2000]  # 限长
            prompt = self._SUMMARY_PROMPT.format(
                section=section or "正文",
                content=content,
            )

            def _do_call() -> Optional[str]:
                try:
                    resp = llm.chat(
                        messages=[
                            {
                                "role": "system",
                                "content": "你是企业知识管理专家。",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.2,
                        max_tokens=300,
                    )
                except Exception:
                    return None
                out = getattr(resp, "content", None)
                if out is None and isinstance(resp, dict):
                    out = resp.get("content", "")
                if not out:
                    return None
                # 清理 qwen3 类模型的 <think> 块
                import re as _re
                out = _re.sub(r"<think>.*?</think>", "", out, flags=_re.DOTALL).strip()
                # 限长到 180 字
                if len(out) > 180:
                    out = out[:178] + "…"
                return out

            import asyncio
            return await asyncio.get_event_loop().run_in_executor(None, _do_call)
        except Exception:
            return None

    def _rewrite_summary_sync(self, section: str, text: str) -> str:
        """同步入口: 跑 LLM 改写 summary, 失败回退到首 160 字截断。"""
        import asyncio
        try:
            coro = self._rewrite_summary(section, text)
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                # 无运行中的 loop, 直接 run
                result = asyncio.run(coro)
            else:
                # 在 loop 中 (FastAPI), 退化为同步截断, 避免阻塞事件循环
                # 调用方应在导入阶段批量跑; 此处不强制同步等待
                result = None
        except Exception:
            result = None

        if result:
            return result
        return text[:160].replace("\n", " ").strip()

    def convert_chunks(self, chunks: List[Chunk],
                       doc_metadata: Dict[str, Any],
                       project_id: Optional[str] = None,
                       memory_type: str = "imported_document",
                       use_llm_summary: bool = True) -> List[Dict[str, Any]]:
        files: List[Dict[str, Any]] = []
        title_base = doc_metadata.get("title", "imported_document")
        for chunk in chunks:
            track = _detect_track(chunk.text)
            keywords = _extract_keywords(chunk.text)
            action_items = _extract_action_items(chunk.text)
            # 摘要改写: 用 LLM 生成结构化摘要, 包含标题 + 关键事实
            # (失败时回退到首 160 字截断, 保留可用性)
            if use_llm_summary:
                summary = self._rewrite_summary_sync(chunk.section, chunk.text)
            else:
                summary = chunk.text[:160].replace("\n", " ").strip()
            slug = _slugify(chunk.section or title_base)
            # 加入 chunk_index 保证每个 chunk 生成独立文件
            filename = f"{slug}_p{chunk.index:02d}.md"
            rel_path = f"imports/{_slugify(title_base)}/{filename}"
            frontmatter = {
                "memory_type": memory_type,
                "track": track,
                "project_id": project_id or doc_metadata.get("title", ""),
                "summary": summary,
                "keywords": keywords,
                "source_doc": doc_metadata.get("filename", ""),
                "section": chunk.section,
                "imported_at": datetime.utcnow().isoformat(timespec="seconds"),
                "status": "active",
            }
            body = f"# {chunk.section or title_base}\n\n{chunk.text}"
            if action_items:
                body += "\n\n## Action items\n\n"
                for item in action_items:
                    body += f"- [ ] {item}\n"
            files.append(
                {
                    "rel_path": rel_path,
                    "frontmatter": frontmatter,
                    "content": body,
                }
            )
        return files


doc_to_memory = DocToMemoryConverter()

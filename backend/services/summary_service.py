"""LLM-driven summary generator.

为已上传的文档/记忆生成关键信息摘要，输出 Markdown 格式，
可与原始 markdown 并存于 vault 目录中。
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Dict, Optional

from ..config.settings import settings
from ..utils.logger import warn
from ..utils.markdown import compose_markdown

_SUMMARY_PROMPT = """你是一名专业的企业知识管理助手。请基于以下内容生成"关键信息摘要"。

要求：
1. 用 Markdown 格式输出，结构清晰：使用 ## 二级标题组织主题
2. 突出"定义/规则/流程/数值/例外"等关键事实
3. 保留所有具体数字、百分比、日期、产品名称
4. 长度控制在原文的 15%-30%
5. 末尾用 bullet 列出 3-6 个核心要点（key_takeaways）

原文标题：{title}

原文内容：
{content}
"""


def _truncate_for_prompt(text: str, limit: int = 12000) -> str:
    """限制 prompt 输入长度，避免超出 LLM 上下文。"""
    if len(text) <= limit:
        return text
    return text[: limit - 200] + "\n\n...(以下内容已截断)..."


def _strip_think_blocks(text: str) -> str:
    """清理部分 LLM（如 qwen3.5）输出的 <think>...</think> 块。"""
    if not text:
        return text
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


async def _call_llm_summary(title: str, content: str) -> Optional[str]:
    """调用 mandol LLM provider 生成摘要。"""
    try:
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return None
        # 直接调底层 LLM provider，跳过 retrieve
        system = mandol_service._require()
        llm = getattr(system, "_llm_provider", None) or getattr(system, "llm_provider", None)
        if llm is None:
            return None
        prompt = _SUMMARY_PROMPT.format(title=title, content=_truncate_for_prompt(content))
        # mandol LLMProvider.chat 是同步方法（OpenAI 兼容），在线程中跑
        def _do_call() -> Optional[str]:
            if hasattr(llm, "chat"):
                resp = llm.chat(
                    messages=[
                        {"role": "system", "content": "你是企业知识管理专家。"},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=2048,
                )
                if hasattr(resp, "content"):
                    return resp.content
                if isinstance(resp, dict):
                    return resp.get("content", "")
                return str(resp)
            elif hasattr(llm, "generate"):
                return llm.generate(prompt, max_tokens=2048, temperature=0.2)
            return None

        text = await asyncio.get_event_loop().run_in_executor(None, _do_call)
        return _strip_think_blocks(text or "")
    except Exception as exc:
        warn(f"LLM 摘要生成失败: {exc}")
        return None


def _build_summary_markdown(title: str, summary: str, source_doc: str) -> str:
    """拼装摘要 markdown 文档（含 frontmatter）。"""
    frontmatter = {
        "title": f"{title} - 摘要",
        "memory_type": "imported_summary",
        "track": "summary",
        "summary": (summary[:160] + "...") if len(summary) > 160 else summary,
        "keywords": [],
        "source_doc": source_doc,
        "generated_at": _now_iso(),
        "status": "active",
    }
    body = f"# {title} - 关键信息摘要\n\n{summary}\n"
    return compose_markdown(frontmatter, body)


def _now_iso() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat(timespec="seconds")


class SummaryGenerator:
    """为已上传文档生成关键信息摘要。"""

    def __init__(self) -> None:
        self._vault_dir: Optional[Path] = None
        self._lock = asyncio.Lock()

    def _resolve_vault(self) -> Path:
        if self._vault_dir is None:
            self._vault_dir = Path(settings.vault_dir)
        return self._vault_dir

    async def generate_for_document(
        self,
        title: str,
        raw_text: str,
        source_doc: str = "",
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """为一份原始文档生成摘要并写入 vault 目录。

        Returns:
            dict { rel_path, content, summary, status } 或 None（LLM 未启用/失败时）
        """
        if not raw_text or not raw_text.strip():
            return None
        summary = await _call_llm_summary(title, raw_text)
        if not summary:
            return None
        # 写入 vault/imports/<title>/_summary.md
        from .doc_to_memory import _slugify
        slug = _slugify(title)
        rel_path = f"imports/{slug}/_summary.md"
        full_path = self._resolve_vault() / rel_path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            content = _build_summary_markdown(title, summary, source_doc)
            full_path.write_text(content, encoding="utf-8")
            return {
                "rel_path": rel_path,
                "content": content,
                "summary": summary,
                "status": "generated",
            }
        except Exception as exc:
            warn(f"写入摘要文件失败: {exc}")
            return None

    def generate_original_markdown(
        self,
        title: str,
        raw_text: str,
        source_doc: str = "",
        project_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """把原始解析文本固化为原始 markdown 入库。"""
        if not raw_text or not raw_text.strip():
            return None
        from .doc_to_memory import _slugify
        slug = _slugify(title)
        rel_path = f"imports/{slug}/_original.md"
        full_path = self._resolve_vault() / rel_path
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            frontmatter = {
                "title": title,
                "memory_type": "imported_original",
                "track": "source",
                "summary": (raw_text[:160] + "...") if len(raw_text) > 160 else raw_text,
                "keywords": [],
                "source_doc": source_doc,
                "generated_at": _now_iso(),
                "status": "active",
            }
            body = f"# {title} (原文)\n\n{raw_text}\n"
            content = compose_markdown(frontmatter, body)
            full_path.write_text(content, encoding="utf-8")
            return {
                "rel_path": rel_path,
                "content": content,
                "status": "generated",
            }
        except Exception as exc:
            warn(f"写入原始 markdown 失败: {exc}")
            return None


summary_generator = SummaryGenerator()

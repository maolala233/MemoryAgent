"""LLM 驱动的实体/事件抽取。

当 Mandol 的 build_high_level 不可用或返回 0 实体时，可使用本服务作为
降级方案，从文本中直接调用 LLM 抽取结构化 (实体, 关系, 事件) 三元组，
并写入 Mandol 记忆单元与 Neo4j 图谱。

主要 API：
- extract_entities_events(text, ...) -> dict
- extract_and_store(text, doc_id, ...) -> dict
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from ..config.settings import settings
from ..utils.logger import info, warn


_EXTRACT_PROMPT = """你是一名企业知识图谱专家。请从以下文本中抽取结构化信息，用于构建知识图谱。

要求：
1. 抽取实体（entities）：包括人名、产品名、机构名、概念、流程、数字、日期等
2. 抽取实体间关系（relations）：使用"主语-谓语-宾语"形式，谓语尽量简短（如 "包含"、"提供"、"属于"）
3. 抽取事件（events）：以时间为线索的关键动作/状态变化
4. 仅输出严格 JSON，结构如下：
{{
  "entities": [
    {{"name": "实体名", "type": "Person|Product|Organization|Concept|Process|Number|Date|Location|Rule", "description": "简要描述"}}
  ],
  "relations": [
    {{"source": "实体名1", "target": "实体名2", "relation": "关系类型", "evidence": "原文证据"}}
  ],
  "events": [
    {{"title": "事件标题", "time": "时间（如有）", "actors": ["参与实体"], "description": "事件描述"}}
  ]
}}

注意事项：
- 只输出 JSON，不要任何解释或 Markdown 代码块包裹
- 实体名尽量使用原文用语，避免同义改写
- 如果文本过短或没有可用信息，返回 {{"entities": [], "relations": [], "events": []}}
- 最多抽取 20 个实体、30 条关系、10 个事件

文本：
{text}
"""


def _strip_think_blocks(text: str) -> str:
    if not text:
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_block(text: str) -> Optional[str]:
    """从 LLM 响应中提取第一个完整 JSON 对象。"""
    if not text:
        return None
    text = _strip_think_blocks(text)
    # 去除 Markdown 代码块
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    # 找到最外层 { ... }
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start: i + 1]
    return None


def _call_llm(prompt: str, max_tokens: int = 2048) -> Optional[str]:
    """通过 mandol LLM provider 调用底层 LLM。"""
    try:
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return None
        system = mandol_service._require()
        llm = getattr(system, "_llm_provider", None) or getattr(system, "llm_provider", None)
        if llm is None:
            return None
        if hasattr(llm, "chat"):
            resp = llm.chat(
                messages=[
                    {"role": "system", "content": "你是企业知识图谱专家，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            if hasattr(resp, "content"):
                return resp.content
            if isinstance(resp, dict):
                return resp.get("content", "")
            return str(resp)
        elif hasattr(llm, "generate"):
            return llm.generate(prompt, max_tokens=max_tokens, temperature=0.1)
        return None
    except Exception as exc:
        warn(f"LLM 抽取调用失败: {exc}")
        return None


def _parse_extraction(raw: str) -> Dict[str, List[Dict[str, Any]]]:
    if not raw:
        return {"entities": [], "relations": [], "events": []}
    block = _extract_json_block(raw)
    if not block:
        warn("LLM 抽取响应中未找到 JSON 块")
        return {"entities": [], "relations": [], "events": []}
    try:
        data = json.loads(block)
    except Exception as exc:
        warn(f"LLM 抽取 JSON 解析失败: {exc}")
        return {"entities": [], "relations": [], "events": []}
    return {
        "entities": list(data.get("entities", []) or []),
        "relations": list(data.get("relations", []) or []),
        "events": list(data.get("events", []) or []),
    }


class EntityExtractor:
    """LLM 实体/关系/事件抽取器。"""

    def __init__(self) -> None:
        self._last_stats: Dict[str, int] = {"entities": 0, "relations": 0, "events": 0}

    @property
    def last_stats(self) -> Dict[str, int]:
        return self._last_stats

    def extract(self, text: str, max_chars: int = 6000) -> Dict[str, List[Dict[str, Any]]]:
        """从文本抽取实体/关系/事件。返回 dict 含 entities/relations/events 三个数组。"""
        if not text or not text.strip():
            return {"entities": [], "relations": [], "events": []}
        truncated = text[:max_chars]
        prompt = _EXTRACT_PROMPT.format(text=truncated)
        raw = _call_llm(prompt, max_tokens=2048)
        result = _parse_extraction(raw or "")
        self._last_stats = {
            "entities": len(result["entities"]),
            "relations": len(result["relations"]),
            "events": len(result["events"]),
        }
        info(f"LLM 实体抽取: 实体={self._last_stats['entities']}, "
             f"关系={self._last_stats['relations']}, 事件={self._last_stats['events']}")
        return result

    def extract_and_store(
        self,
        text: str,
        source_doc: str = "",
        project_id: Optional[str] = None,
        space_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """抽取并写入 Mandol 记忆单元。返回统计。"""
        from .mandol_service import mandol_service
        if not mandol_service.is_enabled:
            return {
                "status": "skipped",
                "reason": "mandol_disabled",
                "entities": 0,
                "relations": 0,
                "events": 0,
            }
        try:
            mandol_service._ensure_initialized()
        except Exception as exc:
            warn(f"无法初始化 Mandol: {exc}")
            return {"status": "error", "reason": str(exc), "entities": 0, "relations": 0, "events": 0}

        extraction = self.extract(text)
        if not any([extraction["entities"], extraction["relations"], extraction["events"]]):
            return {
                "status": "empty",
                "entities": 0,
                "relations": 0,
                "events": 0,
            }

        # 写入 Mandol
        stored = 0
        try:
            from Mandol.src.mandol import MemoryUnit, Uid
            system = mandol_service._require()
            base_tag = uuid.uuid4().hex[:8]

            for ent in extraction["entities"]:
                name = (ent.get("name") or "").strip()
                if not name:
                    continue
                uid = f"ent:{base_tag}:{_slug(name)}"
                unit = MemoryUnit(
                    uid=Uid(uid),
                    raw_data={
                        "text_content": (
                            f"实体: {name}\n类型: {ent.get('type', 'Concept')}\n"
                            f"描述: {ent.get('description', '')}"
                        ),
                        "entity_name": name,
                        "entity_type": ent.get("type", "Concept"),
                        "entity_description": ent.get("description", ""),
                    },
                    metadata={
                        "type": "entity",
                        "source_doc": source_doc,
                        "project_id": project_id or "",
                    },
                )
                if space_name:
                    system.semantic_map.create_space(space_name)
                    system.semantic_map.add_unit(
                        unit, space_names=[space_name], ensure_embedding=True,
                    )
                else:
                    system.add(unit)
                stored += 1

            for ev in extraction["events"]:
                title = (ev.get("title") or "").strip()
                if not title:
                    continue
                uid = f"evt:{base_tag}:{_slug(title)}"
                actors = ev.get("actors", []) or []
                unit = MemoryUnit(
                    uid=Uid(uid),
                    raw_data={
                        "text_content": (
                            f"事件: {title}\n时间: {ev.get('time', '')}\n"
                            f"参与方: {', '.join(actors) if isinstance(actors, list) else str(actors)}\n"
                            f"描述: {ev.get('description', '')}"
                        ),
                        "event_title": title,
                        "event_time": ev.get("time", ""),
                        "event_actors": actors if isinstance(actors, list) else [str(actors)],
                        "event_description": ev.get("description", ""),
                    },
                    metadata={
                        "type": "event",
                        "source_doc": source_doc,
                        "project_id": project_id or "",
                    },
                )
                if space_name:
                    system.semantic_map.create_space(space_name)
                    system.semantic_map.add_unit(
                        unit, space_names=[space_name], ensure_embedding=True,
                    )
                else:
                    system.add(unit)
                stored += 1

            # 触发高阶构建，使关系被抽取进图谱
            try:
                mandol_service.build_high_level(mode="auto")
            except Exception as exc:
                warn(f"抽取后 build_high_level 失败: {exc}")
        except Exception as exc:
            warn(f"写入 Mandol 失败: {exc}")
            return {
                "status": "partial",
                "error": str(exc),
                "entities": len(extraction["entities"]),
                "relations": len(extraction["relations"]),
                "events": len(extraction["events"]),
                "stored": stored,
            }
        return {
            "status": "ok",
            "entities": len(extraction["entities"]),
            "relations": len(extraction["relations"]),
            "events": len(extraction["events"]),
            "stored": stored,
        }


def _slug(s: str, max_len: int = 48) -> str:
    """生成 URL/UID 安全的 slug。"""
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", (s or "").lower()).strip("_")
    return (s or "x")[:max_len]


entity_extractor = EntityExtractor()

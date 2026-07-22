"""Insight map reducer for extracting cross-session global insights.

Reduces accumulated memory across all sessions into high-level insights
using chunked LLM-based reduction.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Dict, List

from ...domain.memory_unit import MemoryUnit
from ...domain.types import Uid
from ...ports.llm_provider import ChatMessage, LLMProvider
from .._llm_retry import retry_llm_json_call, strip_json_fences
from ..session_manager import Session

logger = logging.getLogger(__name__)

INSIGHT_MAP_SYSTEM_PROMPT = """你是一名深度分析专家。请基于以下会话摘要进行反思、分析、推理，生成高层级洞察。
并识别形成该洞察的最核心摘要 UID。

摘要信息：
{summaries_text}

**第 1 步：思考过程（最终输出无需反映）**
1. 分析每个摘要类别：情节性、程序性、知识性、情感性
2. 识别跨类别的模式与关联
3. 推导事件或行为之间的因果关系
4. 基于模式生成可操作的洞察

**第 2 步：最终输出**

请按以下 JSON 格式返回洞察分析：
{{
    "key_source_uids": ["最核心的源摘要 UID 列表"],
    "insights": {{
        "pattern_recognition": ["识别出的跨摘要模式与趋势"],
        "causal_relationships": ["发现的因果关系链"],
        "predictive_insights": ["基于模式的预测与趋势判断"],
        "behavioral_characteristics": ["用户或系统的深层行为特征"],
        "optimization_recommendations": ["基于洞察的具体改进建议"],
        "risk_warnings": ["潜在问题与风险点"]
    }}
}}

洞察要求：
1. 超越单个摘要的表面信息
2. 发现隐藏的模式与关联
3. 提供可操作的建议
4. 推理基于证据
5. 具有预测价值
6. 准确识别最重要的源 UID

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""

INSIGHT_REDUCE_SYSTEM_PROMPT = """你是一名洞察整合专家。请将多个会话洞察合并为全局洞察，以保持连贯、不冗余的全局理解。

**第 1 步：思考过程（最终输出无需反映）**
1. 比较各会话的洞察，寻找共同主题
2. 识别哪些洞察是真正的模式，哪些是一次性观察
3. 优先保留置信度最高、应用面最广的洞察
4. 保持洞察类型的多样性

**第 2 步：最终输出**

合并原则：
1. 即使是旧会话中真正重要的洞察也要保留
2. 将重叠或冗余的洞察合并为更全面的洞察
3. 加入新会话中真正新增的洞察
4. 保持多样性，不要把所有内容都合并为少数几点
5. 洞察文本要简洁但信息丰富

请按以下 JSON 格式返回合并后的全局洞察：
{{
    "key_source_session_ids": ["贡献此全局洞察的会话 ID 列表"],
    "insights": {{
        "pattern_recognition": ["识别出的跨会话模式与趋势"],
        "causal_relationships": ["发现的因果关系链"],
        "predictive_insights": ["基于模式的预测与趋势判断"],
        "behavioral_characteristics": ["深层行为特征"],
        "optimization_recommendations": ["具体改进建议"],
        "risk_warnings": ["潜在问题与风险点"]
    }}
}}

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""

INSIGHT_TYPES = [
    "pattern_recognition",
    "causal_relationships",
    "predictive_insights",
    "behavioral_characteristics",
    "optimization_recommendations",
    "risk_warnings",
]


@dataclass
class InsightResult:
    """Structured insight produced by the insight map-reduce pipeline.

    Attributes:
        key_source_uids: UIDs of the most important source summaries.
        insights: Dict mapping insight type to a list of insight strings.
            Keys are from INSIGHT_TYPES: pattern_recognition,
            causal_relationships, predictive_insights,
            behavioral_characteristics, optimization_recommendations,
            risk_warnings.
        level: Granularity — 'session' or 'global'.
        session_id: Owning session identifier (empty for global insights).
    """
    key_source_uids: List[str]
    insights: Dict[str, List[str]]
    level: str = "session"
    session_id: str = ""


class InsightMapReducer:
    """Reduces memory into cross-session global insights via LLM.

    Accumulates MemoryUnits (typically from the insight space) into
    token-budgeted chunks and calls the LLM to extract high-level insights.

    Args:
        llm: LLM provider for insight generation.
        embedder: Optional embedding provider for insight units.
        chunk_max_tokens: Max tokens per LLM prompt chunk.
        default_text_key: Key for extracting text from raw_data.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        text_key: str = "text_content",
    ):
        self._llm = llm_provider
        self._text_key = str(text_key)

    def process_session(
        self,
        session: Session,
        summary_units: Dict[str, List[MemoryUnit]],
    ) -> List[MemoryUnit]:
        """Generate session-level insights from summary units.

        Accumulates all summary texts, calls the LLM to extract high-level
        insights, and wraps the result as a single MemoryUnit.

        Args:
            session: The session to analyse.
            summary_units: Dict mapping category name to summary MemoryUnits.

        Returns:
            List containing one insight MemoryUnit for the session.
        """
        summary_texts = []
        source_summary_uids = []

        for category, units in summary_units.items():
            for unit in units:
                text = unit.raw_data.get(self._text_key, "")
                if text:
                    uid = str(unit.uid)
                    summary_texts.append(f"[{category.upper()}] (UID: {uid})\n{text}")
                    source_summary_uids.append(uid)

        if not summary_texts:
            return []

        content = "\n\n".join(summary_texts)
        insight = self._map_phase(content, session.session_id, source_summary_uids)

        if not insight.key_source_uids:
            insight.key_source_uids = source_summary_uids[:5]

        uid = f"{session.session_id}:insight:session"
        raw_data = {
            self._text_key: json.dumps(insight.insights, ensure_ascii=False),
            "insights": insight.insights,
        }
        metadata = {
            "type": "insight",
            "category": "insights",
            "level": insight.level,
            "session_id": session.session_id,
            "key_source_uids": insight.key_source_uids,
        }
        unit = MemoryUnit(
            uid=Uid(uid),
            raw_data=raw_data,
            metadata=metadata,
        )

        return [unit]

    def _map_phase(
        self,
        content: str,
        session_id: str,
        source_summary_uids: List[str],
    ) -> InsightResult:
        summaries_text = f"Summaries to analyze:\n{content[:8000]}"
        prompt = INSIGHT_MAP_SYSTEM_PROMPT.format(summaries_text=summaries_text)

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            insight = retry_llm_json_call(
                self._llm,
                messages,
                lambda resp: self._parse_insight_response(resp, session_id, source_summary_uids),
                temperature=0.1,
                max_tokens=8192,
                context_label="insight_map",
            )
        except json.JSONDecodeError:
            insight = self._create_fallback_insight(session_id, source_summary_uids)
        except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError, AttributeError) as e:
            logger.error("Insight map phase failed: %s", e)
            insight = self._create_fallback_insight(session_id, source_summary_uids)

        return insight

    def _parse_insight_response(
        self,
        response: str,
        session_id: str,
        source_summary_uids: List[str],
    ) -> InsightResult:
        data = json.loads(strip_json_fences(response))

        # 防御:LLM 偶尔返回 list,统一规整为 dict
        if isinstance(data, list):
            # 列表里可能直接是 insights dict 列表,尝试取第一条
            if data and isinstance(data[0], dict):
                data = data[0]
            else:
                data = {"insights": {}}
        if not isinstance(data, dict):
            data = {"insights": {}}

        key_source_uids = data.get("key_source_uids", [])
        if not isinstance(key_source_uids, list):
            key_source_uids = source_summary_uids[:5]

        insights_raw = data.get("insights", {})
        if not isinstance(insights_raw, dict):
            insights_raw = {}
        insights: Dict[str, List[str]] = {}

        for insight_type in INSIGHT_TYPES:
            items = insights_raw.get(insight_type, [])
            if isinstance(items, list):
                insights[insight_type] = [str(item) for item in items if item]
            else:
                insights[insight_type] = []

        for insight_type in INSIGHT_TYPES:
            if not insights.get(insight_type):
                insights[insight_type] = []

        return InsightResult(
            key_source_uids=[str(uid) for uid in key_source_uids if isinstance(uid, str)],
            insights=insights,
            level="session",
            session_id=session_id,
        )

    def _create_fallback_insight(
        self,
        session_id: str,
        source_summary_uids: List[str],
    ) -> InsightResult:
        return InsightResult(
            key_source_uids=source_summary_uids[:5] if source_summary_uids else [],
            insights={insight_type: [] for insight_type in INSIGHT_TYPES},
            level="session",
            session_id=session_id,
        )

    def reduce_insights(
        self,
        session_insights: List[MemoryUnit],
        all_session_ids: List[str],
    ) -> InsightResult:
        """Merge multiple session-level insights into a global insight.

        When only one session insight exists, its data is returned directly
        with level promoted to 'global'. Otherwise, the LLM is called to
        intelligently merge all session insights.

        Args:
            session_insights: Insight MemoryUnits from all sessions.
            all_session_ids: All session IDs contributing to the global insight.

        Returns:
            A global-level InsightResult with merged insight data.
        """
        if not session_insights:
            return InsightResult(
                key_source_uids=[],
                insights={insight_type: [] for insight_type in INSIGHT_TYPES},
                level="global",
            )

        if len(session_insights) == 1:
            unit = session_insights[0]
            insights = unit.raw_data.get("insights", {})
            if isinstance(insights, str):
                try:
                    insights = json.loads(insights)
                except json.JSONDecodeError:
                    insights = {}
            return InsightResult(
                key_source_uids=unit.metadata.get("key_source_uids", []),
                insights=insights if isinstance(insights, dict) else {},
                level="global",
            )

        existing_insights_texts = []
        for i, unit in enumerate(session_insights):
            insights = unit.raw_data.get("insights", {})
            if isinstance(insights, str):
                try:
                    insights = json.loads(insights)
                except json.JSONDecodeError:
                    insights = {}
            session_id_insight = unit.metadata.get("session_id", f"session_{i}")
            existing_insights_texts.append(
                f"Session {session_id_insight} insights:\n{json.dumps(insights, ensure_ascii=False, indent=2)}"
            )

        prompt = f"""Existing Session Insights:
{chr(10).join(existing_insights_texts)}

All session IDs: {all_session_ids}"""

        combined = INSIGHT_REDUCE_SYSTEM_PROMPT + "\n\n" + prompt
        messages: List[ChatMessage] = [
            {"role": "user", "content": combined},
        ]

        try:
            result = retry_llm_json_call(
                self._llm,
                messages,
                lambda resp: self._parse_reduce_response(resp, all_session_ids),
                temperature=0.1,
                max_tokens=2048,
                context_label="insight_reduce",
            )
            return result
        except json.JSONDecodeError:
            return self._merge_insights_fallback(session_insights, all_session_ids)
        except (ConnectionError, TimeoutError, OSError, RuntimeError, ValueError, AttributeError) as e:
            logger.error("Insight reduce failed: %s", e)
            return self._merge_insights_fallback(session_insights, all_session_ids)

    def _parse_reduce_response(
        self,
        response: str,
        session_ids: List[str],
    ) -> InsightResult:
        data = json.loads(strip_json_fences(response))

        # 防御:LLM 偶尔返回 list,统一规整为 dict
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                data = data[0]
            else:
                data = {"insights": {}}
        if not isinstance(data, dict):
            data = {"insights": {}}

        key_source_sessions = data.get("key_source_session_ids", session_ids)
        if not isinstance(key_source_sessions, list):
            key_source_sessions = session_ids

        insights_raw = data.get("insights", {})
        insights: Dict[str, List[str]] = {}

        for insight_type in INSIGHT_TYPES:
            items = insights_raw.get(insight_type, [])
            if isinstance(items, list):
                insights[insight_type] = [str(item) for item in items if item]
            else:
                insights[insight_type] = []

        return InsightResult(
            key_source_uids=list(key_source_sessions),
            insights=insights,
            level="global",
        )

    def _merge_insights_fallback(
        self,
        session_insights: List[MemoryUnit],
        session_ids: List[str],
    ) -> InsightResult:
        merged: Dict[str, List[str]] = {t: [] for t in INSIGHT_TYPES}

        for unit in session_insights:
            insights = unit.raw_data.get("insights", {})
            if isinstance(insights, str):
                try:
                    insights = json.loads(insights)
                except json.JSONDecodeError:
                    continue
            if not isinstance(insights, dict):
                continue
            for insight_type in INSIGHT_TYPES:
                items = insights.get(insight_type, [])
                if isinstance(items, list):
                    for item in items:
                        if item and item not in merged[insight_type]:
                            merged[insight_type].append(str(item))

        return InsightResult(
            key_source_uids=session_ids,
            insights=merged,
            level="global",
        )
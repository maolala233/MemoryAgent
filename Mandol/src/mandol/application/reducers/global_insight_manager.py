"""Global insight manager for accumulating and updating cross-session insights.

Merges new insights from each session into a persistent global insight store.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .._llm_retry import strip_json_fences
from ...domain.memory_unit import MemoryUnit
from ...domain.types import Uid
from ...ports.llm_provider import ChatMessage, LLMProvider

if TYPE_CHECKING:
    from ..session_manager import Session

logger = logging.getLogger(__name__)

INSIGHT_TYPES = [
    "pattern_recognition",
    "causal_relationships",
    "predictive_insights",
    "behavioral_characteristics",
    "optimization_recommendations",
    "risk_warnings",
]

GLOBAL_INSIGHT_MERGE_PROMPT = """你是一名洞察整合专家。请将新会话的洞察合并到现有全局洞察中，以保持连贯、不冗余的全局理解。

**第 1 步：思考过程（最终输出无需反映）**
1. 比较现有全局洞察与新会话洞察
2. 识别哪些洞察是真正新增的，哪些是重叠的
3. 合并相似洞察，同时保留多样性
4. 在所有类型中优先保留高价值洞察

**第 2 步：最终输出**

合并规则：
1. 即使是旧的全局洞察中真正重要的也要保留
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

仅输出合法 JSON，不要 markdown 代码块。所有 JSON 内的文本内容请使用中文。"""


@dataclass
class GlobalInsightResult:
    """Global insight accumulated across all sessions.

    Attributes:
        key_source_session_ids: Session IDs that contributed to this insight.
        insights: Dict mapping insight type to a list of insight strings.
        level: Always 'global' for this result type.
    """
    key_source_session_ids: List[str]
    insights: Dict[str, List[str]]
    level: str = "global"


class GlobalInsightManager:
    """Accumulates and updates global insights across all sessions.

    Each session's insights are appended to a persistent list, with
    periodic deduplication via InsightMapReducer. Supports retrieving
    formatted insight texts for use in LLM prompts.

    Args:
        llm_provider: LLM provider for insight reduction.
        text_key: Key in raw_data for extracting text content.
    """

    GLOBAL_INSIGHT_UID = "global_insight_v1"

    def __init__(
        self,
        llm_provider: LLMProvider,
        text_key: str = "text_content",
    ):
        """Initialize the global insight manager.

        Args:
            llm_provider: LLM provider for insight reduction calls.
            text_key: Key in raw_data for extracting text content.
        """
        self._llm = llm_provider
        self._text_key = str(text_key)

        self._lock = threading.Lock()
        self._global_insight: Optional[GlobalInsightResult] = None
        self._is_initialized = False
        self._version = 0

    def merge_and_update(
        self,
        session: "Session",
        session_insights: List[MemoryUnit],
        semantic_map: Any,
        graph: Any,
        naming: Any,
        root_space: str = "default",
    ) -> None:
        """Thread-safe merge of session insights into the global insight.

        Args:
            session: The current session object.
            session_insights: Sub-insights from the current session (not persisted).
            semantic_map: SemanticMapService instance.
            graph: SemanticGraphService instance.
            naming: SpaceNamingPolicy instance.
            root_space: Root space name.
        """
        if not session_insights:
            logger.debug(f"Session {session.session_id} has no insights to merge")
            return

        session_insight = self._extract_session_insight(session_insights)
        if not session_insight or not session_insight.insights:
            logger.debug(f"Session {session.session_id} has empty insights")
            return

        with self._lock:
            if not self._is_initialized:
                self._global_insight = GlobalInsightResult(
                    key_source_session_ids=[session.session_id],
                    insights=session_insight.insights,
                    level="global",
                )
                self._is_initialized = True
            else:
                self._incremental_merge(session.session_id, session_insight)

            self._version += 1
            self._persist_global_insight(semantic_map, graph, naming, root_space)

    def _extract_session_insight(self, session_insights: List[MemoryUnit]) -> Optional[GlobalInsightResult]:
        if not session_insights:
            return None
        unit = session_insights[0]
        insights = unit.raw_data.get("insights", {})
        if isinstance(insights, str):
            try:
                insights = json.loads(insights)
            except json.JSONDecodeError:
                insights = {}
        if not isinstance(insights, dict):
            return None
        key_source_uids = unit.metadata.get("key_source_uids", [])
        return GlobalInsightResult(
            key_source_session_ids=key_source_uids,
            insights=insights,
            level="session",
        )

    def _incremental_merge(
        self,
        session_id: str,
        session_insight: GlobalInsightResult,
    ) -> None:
        """Incrementally merge session insights into global insights (lock already held)."""
        if not self._global_insight:
            self._global_insight = GlobalInsightResult(
                key_source_session_ids=[session_id],
                insights=session_insight.insights,
                level="global",
            )
            return

        prompt = f"""Existing Global Insights:
{json.dumps(self._global_insight.insights, ensure_ascii=False, indent=2)}

New Session Insights (from session {session_id}):
{json.dumps(session_insight.insights, ensure_ascii=False, indent=2)}

All contributing session IDs: {self._global_insight.key_source_session_ids + [session_id]}"""

        combined = GLOBAL_INSIGHT_MERGE_PROMPT + "\n\n" + prompt
        messages: List[ChatMessage] = [
            {"role": "user", "content": combined},
        ]

        try:
            response = self._llm.chat(messages, temperature=0.1, max_tokens=2048)
            self._global_insight = self._parse_merge_response(
                response.content, session_id
            )
        except (json.JSONDecodeError, ValueError, ConnectionError, TimeoutError, OSError, RuntimeError, AttributeError) as e:
            logger.error("Global insight merge failed: %s, using fallback merge", e)
            self._merge_insights_fallback(session_id, session_insight)

    def _parse_merge_response(
        self,
        response: str,
        session_id: str,
    ) -> GlobalInsightResult:
        """Parse the LLM merge response and update the global insight."""
        data = json.loads(strip_json_fences(response))

        # 兜底：若 LLM 返回的不是 dict（例如返回 list），视为解析失败，
        # 抛出 ValueError 让上层 except 走到 fallback 路径。
        if not isinstance(data, dict):
            raise ValueError(
                f"merge response is not a dict (got {type(data).__name__}): "
                f"{str(data)[:200]}"
            )

        key_source_sessions = data.get("key_source_session_ids", [])
        if not isinstance(key_source_sessions, list):
            key_source_sessions = []

        insights_raw = data.get("insights", {})
        insights: Dict[str, List[str]] = {}

        for insight_type in INSIGHT_TYPES:
            items = insights_raw.get(insight_type, [])
            if isinstance(items, list):
                insights[insight_type] = [str(item) for item in items if item]
            else:
                insights[insight_type] = []

        return GlobalInsightResult(
            key_source_session_ids=key_source_sessions,
            insights=insights,
            level="global",
        )

    def _merge_insights_fallback(
        self,
        session_id: str,
        session_insight: GlobalInsightResult,
    ) -> None:
        """Fallback merge when LLM fails: simple concatenation of insights."""
        if not self._global_insight:
            return

        merged: Dict[str, List[str]] = dict(self._global_insight.insights)

        for insight_type in INSIGHT_TYPES:
            existing = set(merged.get(insight_type, []))
            new_items = session_insight.insights.get(insight_type, [])
            merged[insight_type] = list(existing.union(set(new_items)))

        self._global_insight = GlobalInsightResult(
            key_source_session_ids=self._global_insight.key_source_session_ids + [session_id],
            insights=merged,
            level="global",
        )

    def _persist_global_insight(
        self,
        semantic_map: Any,
        graph: Any,
        naming: Any,
        root_space: str,
    ) -> None:
        """Persist the global insight into the semantic map."""
        if not self._global_insight:
            return

        insights_text = json.dumps(self._global_insight.insights, ensure_ascii=False, indent=2)

        embedding_text_parts: List[str] = []
        for itype in INSIGHT_TYPES:
            items = self._global_insight.insights.get(itype, [])
            if items:
                embedding_text_parts.append(f"{itype}: " + "; ".join(str(i) for i in items))
        embedding_text = "\n".join(embedding_text_parts) if embedding_text_parts else insights_text

        insight_unit = MemoryUnit(
            uid=Uid(self.GLOBAL_INSIGHT_UID),
            raw_data={
                self._text_key: insights_text,
                "embedding_text": embedding_text,
                "insights": self._global_insight.insights,
            },
            metadata={
                "type": "global_insight",
                "category": "insights",
                "level": "global",
                "key_source_session_ids": self._global_insight.key_source_session_ids,
                "version": self._version,
            },
        )

        insight_space = naming.insights(root_space)

        semantic_map.add_unit(
            insight_unit,
            space_names=[insight_space],
            ensure_embedding=True,
            embedding_text=embedding_text,
        )

        logger.info(f"Persisted global insight v{self._version} with sessions: {self._global_insight.key_source_session_ids}")

    @property
    def global_insight(self) -> Optional[GlobalInsightResult]:
        """Return the current global insight (for debugging)."""
        with self._lock:
            return self._global_insight

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def version(self) -> int:
        return self._version
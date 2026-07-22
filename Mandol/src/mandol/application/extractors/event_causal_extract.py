"""Event and causal relationship extraction from conversational memory.

Uses LLM prompts to extract events and identify cause-effect relationships
between them within a given session context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from ...domain.memory_unit import MemoryUnit
from ...ports.llm_provider import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)

# 推断事件之间因果关系的提示词
EVENT_CAUSAL_EXTRACT_PROMPT = """你是一名因果关系分析专家。给定一个会话中的事件列表，识别其中存在因果关系的事件对（一个事件导致或影响另一个事件）。

**关键指令：**
- 仅输出合法 JSON，不要任何其他文字
- 聚焦清晰的因果关系
- 因必须按时间顺序发生在果之前
- 置信度分数：0.0（弱）到 1.0（强）
- 仅保留置信度 >= 0.6 的关系
- 事件签名必须与原始事件描述完全一致
- 每个事件有 UID —— 使用 UID 进行来源追踪

**考虑的因果关系类型：**
- direct_causal：A 直接导致 B（例如『导致了』、『引起了』、『触发了』）
- indirect_causal：A 间接促成或影响 B（例如『有助于』、『推动了』、『使……成为可能』）
- conditional_causal：A 在特定条件下导致 B（例如『当 X 发生时，A 导致 B』）
- temporal_causal：A 在时间上先于并导致 B（例如『之后』、『随后』）
- emotional_causal：情感状态导致行为或决策（例如『恐惧导致』、『兴奋引发』）
- behavioral_causal：决策或行动导致结果（例如『决定……』、『选择……』、『行动结果』）

**待分析事件：**
{events_json}

**要求的输出格式：**
{{
  "causal_relationships": [
    {{
      "cause_event": "字符串 - 因事件的描述原文",
      "effect_event": "字符串 - 果事件的描述原文",
      "causal_type": "字符串 - 只能是：direct_causal, indirect_causal, conditional_causal, temporal_causal, emotional_causal, behavioral_causal",
      "confidence_score": "浮点数",
      "rationale": "字符串 - 简要说明（中文）",
      "source_uids": ["字符串 - 因事件 UID", "字符串 - 果事件 UID"]
    }}
  ]
}}

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""

# 从对话记录中抽取事件描述的提示词
EVENT_EXTRACTION_PROMPT = """你是一名事件抽取专家。给定一组记忆记录，识别并抽取其中提到的所有有意义的事件。

**待抽取的事件类型：**
- action_event：具体的动作或决策（例如『决定迁移数据库』、『取消了会议』）
- state_change：状态、情况的变化（例如『服务器宕机』、『状态变更为激活』）
- communication_event：信息交换（例如『给团队发邮件』、『收到反馈』）
- temporal_event：有时间边界的事件（例如『每周一』、『Q3 期间』、『发布后』）
- relationship_event：涉及关系的事件（例如『加入团队』、『离职』）

**关键指令：**
- 仅输出合法 JSON，不要任何其他文字
- 抽取要具体到有意义的实体
- 尽量提供时间戳
- 每个事件必须有唯一的 UID 用于追踪
- 置信度分数：0.0（弱）到 1.0（强）

**待分析记录：**
{records_json}

**要求的输出格式：**
{{
  "events": [
    {{
      "signature": "字符串 - 简明的事件描述（不超过 100 字）",
      "text": "字符串 - 完整的事件描述",
      "event_type": "字符串 - 只能是：action_event, state_change, communication_event, temporal_event, relationship_event",
      "timestamp": "字符串 - 事件发生时间（若已知）",
      "confidence": "浮点数",
      "uid": "字符串 - 该事件的唯一标识"
    }}
  ]
}}

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""

CAUSAL_TYPES = [
    "direct_causal",
    "indirect_causal",
    "conditional_causal",
    "temporal_causal",
    "emotional_causal",
    "behavioral_causal",
]


@dataclass
class ExtractedEvent:
    """An event extracted from conversational data.

    Attributes:
        signature: Concise event description (max 100 chars).
        text: Full event description.
        event_type: Category (action_event, state_change, etc.).
        timestamp: When the event occurred, if known.
        confidence: Extraction confidence in [0.0, 1.0].
        uid: Unique identifier for this event.
    """
    signature: str
    text: str
    event_type: str
    timestamp: str
    confidence: float
    uid: str


@dataclass
class CausalRelation:
    """A cause-effect relationship between two events.

    Attributes:
        cause_event: The cause event description.
        effect_event: The effect event description.
        causal_type: Type of causality (direct_causal, indirect_causal, etc.).
        confidence: Confidence score in [0.0, 1.0].
        rationale: Human-readable explanation.
        source_uids: UIDs of the events involved.
    """
    cause_event: str
    effect_event: str
    causal_type: str
    confidence: float
    rationale: str = ""
    source_uids: List[str] = field(default_factory=list)


class EventCausalExtractor:
    """Extracts events and causal relationships from conversations.

    Wraps an LLM provider with two tasks:
    1. Event extraction: identify events from raw records.
    2. Causal extraction: infer cause-effect chains between events.

    Args:
        llm_provider: LLM provider for extraction calls.
        confidence_threshold: Minimum confidence to include (default 0.6).
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        confidence_threshold: float = 0.6,
    ):
        self._llm = llm_provider
        self._threshold = float(confidence_threshold)

    def extract_events(
        self,
        records: Sequence[MemoryUnit],
    ) -> List[ExtractedEvent]:
        """Extract events from raw conversation records.

        Args:
            records: MemoryUnits with conversation text.

        Returns:
            List of ExtractedEvent objects.
        """
        if not records:
            return []

        record_list = []
        for i, r in enumerate(records):
            text = r.raw_data.get("text_content", "") or r.raw_data.get("text", "")
            if not text:
                continue
            ts = r.metadata.get("timestamp", "")
            speaker = r.metadata.get("speaker", "Unknown")
            record_list.append({
                "index": i,
                "text": text,
                "timestamp": ts,
                "speaker": speaker,
                "uid": str(r.uid),
            })

        if not record_list:
            return []

        content = json.dumps(record_list, ensure_ascii=False, indent=2)
        prompt = EVENT_EXTRACTION_PROMPT.format(records_json=content)

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._llm.chat(
                messages,
                temperature=0.1,
                max_tokens=8192,
            )
            return self._parse_event_response(response.content)
        except (json.JSONDecodeError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            logger.error("Event extraction failed: %s", e)
            return []

    def extract_causal_relations(
        self,
        events: Sequence[MemoryUnit],
        session_id: str,
    ) -> List[CausalRelation]:
        """Extract causal relationships between events.

        Args:
            events: Event MemoryUnits to analyze.
            session_id: Session identifier for context tracking.

        Returns:
            List of CausalRelation objects above the confidence threshold.
        """
        if not events or len(events) < 2:
            return []

        event_list = []
        for e in events:
            text = e.raw_data.get("text_content", "") or e.raw_data.get("text", "")
            if not text:
                continue
            signature = e.raw_data.get("signature", text[:100])
            event_list.append({
                "text": text,
                "signature": signature,
                "uid": str(e.uid),
                "timestamp": e.metadata.get("timestamp", ""),
            })

        if len(event_list) < 2:
            return []

        content = json.dumps(event_list, ensure_ascii=False, indent=2)
        prompt = EVENT_CAUSAL_EXTRACT_PROMPT.format(events_json=content)

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._llm.chat(
                messages,
                temperature=0.1,
                max_tokens=2048,
            )
            return self._parse_response(response.content, event_list)
        except (json.JSONDecodeError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            logger.error("Event causal extraction failed: %s", e)
            return []

    def _parse_event_response(
        self,
        response: str,
    ) -> List[ExtractedEvent]:
        """Parse the LLM JSON response for event extraction.

        Args:
            response: Raw LLM response string (JSON).

        Returns:
            List of ExtractedEvent objects, or empty on parse failure.
        """
        try:
            data = json.loads(response)
            events_data = data.get("events", [])

            results = []
            for item in events_data:
                signature = str(item.get("signature", "")).strip()
                text = str(item.get("text", "")).strip()
                if not signature and not text:
                    continue
                results.append(ExtractedEvent(
                    signature=signature or text[:100],
                    text=text or signature,
                    event_type=str(item.get("event_type", "action_event")),
                    timestamp=str(item.get("timestamp", "")),
                    confidence=float(item.get("confidence", 0.8)),
                    uid=str(item.get("uid", f"event_{len(results)}")),
                ))

            return results
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse event extraction response: {response[:200]}")
            return []

    def _parse_response(
        self,
        response: str,
        event_list: List[Dict[str, Any]],
    ) -> List[CausalRelation]:
        """Parse the LLM JSON response for causal relationship extraction.

        Validates that both cause and effect events exist in the event
        list and that confidence exceeds the threshold.

        Args:
            response: Raw LLM response string (JSON).
            event_list: Original event dicts for validation.

        Returns:
            List of validated CausalRelation objects.
        """
        try:
            data = json.loads(response)
            relations_data = data.get("causal_relationships", [])

            event_signatures = {e["signature"] for e in event_list}
            event_texts = {e["text"] for e in event_list}
            event_uids = {e["signature"]: e["uid"] for e in event_list}
            event_uids.update({e["text"]: e["uid"] for e in event_list})
            results = []

            for r in relations_data:
                cause = str(r.get("cause_event", ""))
                effect = str(r.get("effect_event", ""))
                causal_type = str(r.get("causal_type", "direct_causal"))
                conf = float(r.get("confidence_score", 0.0))

                if cause not in event_signatures and cause not in event_texts:
                    continue
                if effect not in event_signatures and effect not in event_texts:
                    continue
                if conf < self._threshold:
                    continue
                if causal_type not in CAUSAL_TYPES:
                    causal_type = "direct_causal"

                source_uids = []
                if cause in event_uids:
                    source_uids.append(event_uids[cause])
                if effect in event_uids:
                    source_uids.append(event_uids[effect])

                results.append(CausalRelation(
                    cause_event=cause,
                    effect_event=effect,
                    causal_type=causal_type,
                    confidence=conf,
                    rationale=str(r.get("rationale", "")),
                    source_uids=source_uids,
                ))

            return results
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse causal relation response: {response[:200]}")
            return []
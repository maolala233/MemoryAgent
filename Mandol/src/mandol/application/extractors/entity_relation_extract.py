"""Entity and relationship extraction from conversational memory.

Uses LLM prompts to identify entities (person, organization, location, etc.)
and infer semantic relationships between them within a given session context.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from ...domain.memory_unit import MemoryUnit
from ...ports.llm_provider import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)

# 提取已知实体之间关系的提示词
ENTITY_RELATION_EXTRACT_PROMPT = """你是一名专业的实体关系抽取专家。给定一个会话中出现的实体列表，识别它们之间有意义的关系。

**关键指令：**
- 仅输出合法 JSON，不要任何其他文字
- 关系应是上下文中有意义的语义连接
- 置信度分数：0.0（弱）到 1.0（强）
- 仅保留置信度 >= 0.6 的关系
- 实体文本必须与原始实体名完全一致
- 每个实体有 UID —— 使用 UID 进行来源追踪

**考虑的关系类型：**
- 身份类：is_a、works_as、role_is（属于 / 担任 / 角色是）
- 归属类：owns、belongs_to、contains（拥有 / 属于 / 包含）
- 位置类：located_at、lives_in、works_at、from（位于 / 居住 / 工作于 / 来自）
- 时间类：happened_at、lasted、before、after（发生于 / 持续 / 之前 / 之后）
- 参与类：participated_in、experienced、completed（参与 / 经历 / 完成）
- 情感类：likes、loves、hates、worries_about、supports（喜欢 / 爱 / 厌恶 / 担心 / 支持）
- 因果类：caused、because、therefore、affected、resulted_in（导致 / 因为 / 因此 / 影响 / 引致）
- 社交类：friend_of、family_of、colleague_of、neighbor_of、partner_of（朋友 / 家人 / 同事 / 邻居 / 伙伴）
- 学习/工作类：studies、works_at、teaches、guides、collaborates_with（学习 / 工作于 / 教授 / 指导 / 协作）

**待分析实体：**
{entities_json}

**要求的输出格式：**
{{
  "relationships": [
    {{
      "head_entity": "字符串 - 实体原文",
      "tail_entity": "字符串 - 实体原文",
      "relation_type": "字符串 - 使用上述关系类型（如 works_as、located_at、likes）",
      "confidence_score": "浮点数",
      "rationale": "字符串 - 简要说明（中文）",
      "source_uids": ["字符串 - 头实体的 UID", "字符串 - 尾实体的 UID"]
    }}
  ]
}}

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""

# 从原始对话记录中抽取实体的提示词
ENTITY_TYPES_EXTRACTION_PROMPT = """你是一名专业的实体抽取专家。给定一组记忆记录，识别并抽取其中提到的所有有意义的实体。

**待抽取的实体类型：**
- person：具体的个人（按姓名或明确指代，例如『张三』、『医生』、『我的经理』）
- organization：公司、机构、团队、群组（例如『Google』、『工程团队』）
- location：地点、场所、地理指代（例如『旧金山』、『办公室』、『会议室』）
- concept：抽象概念、理论、原则（例如『机器学习』、『敏捷方法论』）
- object：物理或数字对象、工具、产品（例如『笔记本电脑』、『新 API』）
- event：具体发生的事、会议、事件（例如『发布会』、『Q3 会议』）
- activity：动作、流程、工作流（例如『代码评审』、『数据迁移』）

**关键指令：**
- 仅输出合法 JSON，不要任何其他文字
- 抽取要具体到有意义的实体
- 尽量提供上下文/描述
- 每个实体必须有唯一的 UID 用于追踪
- 置信度分数：0.0（弱）到 1.0（强）

**待分析记录：**
{records_json}

**要求的输出格式：**
{{
  "entities": [
    {{
      "text": "字符串 - 实体原文（按出现形式）",
      "entity_type": "字符串 - 只能是：person, organization, location, concept, object, event, activity",
      "description": "字符串 - 实体的简要上下文或描述（中文）",
      "confidence": "浮点数",
      "uid": "字符串 - 该实体的唯一标识（格式：entity_{{index}}）"
    }}
  ]
}}

输出 JSON 格式。所有 JSON 内的文本内容请使用中文。"""

RELATION_TYPES = [
    "is_a", "works_as", "role_is",
    "owns", "belongs_to", "contains",
    "located_at", "lives_in", "works_at", "from",
    "happened_at", "before", "after", "during",
    "participated_in", "experienced", "completed",
    "likes", "loves", "hates", "worries_about", "supports",
    "caused", "because", "therefore", "affected", "resulted_in",
    "friend_of", "family_of", "colleague_of", "neighbor_of", "partner_of",
    "studies", "teaches", "guides", "collaborates_with",
]

RELATION_CATEGORIES = {
    "identity": ["is_a", "works_as", "role_is"],
    "ownership": ["owns", "belongs_to", "contains"],
    "location": ["located_at", "lives_in", "works_at", "from"],
    "temporal": ["happened_at", "before", "after", "during"],
    "participation": ["participated_in", "experienced", "completed"],
    "emotional": ["likes", "loves", "hates", "worries_about", "supports"],
    "causal": ["caused", "because", "therefore", "affected", "resulted_in"],
    "social": ["friend_of", "family_of", "colleague_of", "neighbor_of", "partner_of"],
    "learning_work": ["studies", "teaches", "guides", "collaborates_with"],
}


@dataclass
class ExtractedEntity:
    """A single entity extracted from conversation data.

    Attributes:
        text: The entity text as it appears in the source.
        entity_type: Category (person, organization, location, etc.).
        description: Brief contextual description or empty string.
        confidence: Extraction confidence in [0.0, 1.0].
        uid: Unique identifier for this entity.
    """

    text: str
    entity_type: str
    description: str
    confidence: float
    uid: str


@dataclass
class ExtractedRelation:
    """A semantic relationship between two entities.

    Attributes:
        head_entity: Source entity text.
        tail_entity: Target entity text.
        relation_type: Type of relationship (e.g. works_as, located_at).
        confidence: Confidence score in [0.0, 1.0].
        rationale: Human-readable explanation of the relationship.
        source_uids: UIDs of the entities involved.
    """

    head_entity: str
    tail_entity: str
    relation_type: str
    confidence: float
    rationale: str = ""
    source_uids: List[str] = field(default_factory=list)


class EntityRelationExtractor:
    """Extracts entities and relationships from conversational memory.

    Wraps an LLM provider with pre-defined prompts for two tasks:
    1. Entity extraction: identify entities from raw conversation records.
    2. Relationship extraction: infer semantic links between entities.

    Args:
        llm_provider: LLM provider for extraction calls.
        confidence_threshold: Minimum confidence to include a result (default 0.6).
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        confidence_threshold: float = 0.6,
    ):
        self._llm = llm_provider
        self._threshold = float(confidence_threshold)

    def extract_entities(
        self,
        records: Sequence[MemoryUnit],
    ) -> List[ExtractedEntity]:
        """Extract entities from raw conversation records.

        Args:
            records: MemoryUnits containing conversation text.

        Returns:
            List of ExtractedEntity objects.
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
        prompt = ENTITY_TYPES_EXTRACTION_PROMPT.format(records_json=content)

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._llm.chat(
                messages,
                temperature=0.1,
                max_tokens=8192,
            )
            return self._parse_entity_response(response.content)
        except (json.JSONDecodeError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            logger.error("Entity extraction failed: %s", e)
            return []

    def extract_relations(
        self,
        entities: Sequence[MemoryUnit],
        session_id: str,
    ) -> List[ExtractedRelation]:
        """Extract relationships between a set of entity units.

        Args:
            entities: Entity MemoryUnits to analyze.
            session_id: Session identifier for context tracking.

        Returns:
            List of ExtractedRelation objects above the confidence threshold.
        """
        if not entities or len(entities) < 2:
            return []

        entity_list = []
        for e in entities:
            text = e.raw_data.get("text_content", "") or e.raw_data.get("text", "")
            if not text:
                continue
            entity_type = e.metadata.get("entity_type", "unknown")
            entity_list.append({
                "text": text,
                "type": entity_type,
                "uid": str(e.uid),
            })

        if len(entity_list) < 2:
            return []

        content = json.dumps(entity_list, ensure_ascii=False, indent=2)
        prompt = ENTITY_RELATION_EXTRACT_PROMPT.format(entities_json=content)

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._llm.chat(
                messages,
                temperature=0.1,
                max_tokens=8192,
            )
            return self._parse_response(response.content, entity_list)
        except (json.JSONDecodeError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            logger.error("Entity relation extraction failed: %s", e)
            return []

    def _parse_entity_response(
        self,
        response: str,
    ) -> List[ExtractedEntity]:
        """Parse the LLM JSON response for entity extraction.

        Args:
            response: Raw LLM response string (JSON).

        Returns:
            List of ExtractedEntity objects, or empty on parse failure.
        """
        try:
            data = json.loads(response)
            entities_data = data.get("entities", [])

            results = []
            for item in entities_data:
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                results.append(ExtractedEntity(
                    text=text,
                    entity_type=str(item.get("entity_type", "unknown")),
                    description=str(item.get("description", "")),
                    confidence=float(item.get("confidence", 0.8)),
                    uid=str(item.get("uid", f"entity_{len(results)}")),
                ))

            return results
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse entity extraction response: {response[:200]}")
            return []

    def _parse_response(
        self,
        response: str,
        entity_list: List[Dict[str, Any]],
    ) -> List[ExtractedRelation]:
        """Parse the LLM JSON response for relationship extraction.

        Validates that both head and tail entities exist in the entity
        list and that confidence exceeds the threshold.

        Args:
            response: Raw LLM response string (JSON).
            entity_list: Original entity dicts for validation.

        Returns:
            List of validated ExtractedRelation objects.
        """
        try:
            data = json.loads(response)
            relations_data = data.get("relationships", [])

            entity_texts = {e["text"] for e in entity_list}
            entity_uids = {e["text"]: e["uid"] for e in entity_list}
            results = []

            for r in relations_data:
                head = str(r.get("head_entity", ""))
                tail = str(r.get("tail_entity", ""))
                rel_type = str(r.get("relation_type", ""))
                conf = float(r.get("confidence_score", 0.0))

                if head not in entity_texts or tail not in entity_texts:
                    continue
                if conf < self._threshold:
                    continue

                source_uids = []
                if head in entity_uids:
                    source_uids.append(entity_uids[head])
                if tail in entity_uids:
                    source_uids.append(entity_uids[tail])

                results.append(ExtractedRelation(
                    head_entity=head,
                    tail_entity=tail,
                    relation_type=rel_type,
                    confidence=conf,
                    rationale=str(r.get("rationale", "")),
                    source_uids=source_uids,
                ))

            return results
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse entity relation response: {response[:200]}")
            return []
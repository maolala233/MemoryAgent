"""Event deduplication using signature-based matching and LLM confirmation.

Compares event signatures (participants + action + date) and uses LLM
prompts to decide whether two events describe the same real-world occurrence.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from ...domain.memory_unit import MemoryUnit
from ...domain.types import Uid
from ...ports.llm_provider import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)

# 快速预筛选：判断新事件是否与已有事件签名重复
EVENT_QUICK_MATCH_PROMPT = """你是一名事件去重助手。请快速判断新事件是否与现有列表中的某个事件重复。

输入：
- 现有事件签名列表：{signatures}
- 新事件详情：{new_event}

仅输出 JSON：
{{
    "is_duplicate": true/false,
    "matched_signatures": ["sig1", "sig2"],
    "decision_confidence": 0.92
}}

注意通用语言现象：
- 同一事件用不同表述（缩写、别名、详写/简写）描述，应判定为重复
- 时间表达差异（如『今天』与具体日期）若指向同一日，应视为同一事件
- 主体/客体的称谓变化（如『客户』与具体客户名）不影响事件同一性"""

# 详细成对比较：判断两个事件是否描述同一真实发生的事
EVENT_DETAILED_CONFIRM_PROMPT = """你是一名事件去重助手。请比较两个事件，判断它们是否描述同一真实发生的事。

已有事件：
{existing_event}

新批次事件：
{new_event}

仅输出 JSON：
{{
    "is_same_event": true/false,
    "merged_event": {{
        "participants": ["合并后的参与方列表"],
        "event_description": "合并后的描述",
        "absolute_time": "ISO 8601 格式",
        "signature": "规范化后的签名"
    }},
    "decision_confidence": 0.95
}}

注意通用语言现象：
- 同一事件用不同表述（缩写、别名、详写/简写）描述，应判定为同一
- 否定/肯定/反问等不同语气若描述同一事实，仍视为同一事件
- 时间表达差异（相对时间/绝对日期）若指向同一时间点，视为同一事件
- 枚举/列举的不同项目不算同一事件，必须为同一具体发生的事"""


def _generate_signature(event: MemoryUnit) -> str:
    """Generate a normalized signature string for an event.

    Format: \"participants-action-YYYYMMDD\" using the first action word
    and up to 3 participants.

    Args:
        event: The event MemoryUnit.

    Returns:
        A signature string suitable for fuzzy matching.
    """
    text = event.raw_data.get("text_content", "") or event.raw_data.get("text", "")
    participants = event.metadata.get("participants", [])
    if isinstance(participants, str):
        participants = [p.strip() for p in participants.split(",") if p.strip()]
    if not participants:
        participants = ["unknown"]
    action = text.lower().strip().split()[0] if text.strip() else "event"
    participants_str = ",".join(sorted(p.lower().strip() for p in participants[:3]))
    timestamp = event.metadata.get("timestamp", "") or event.metadata.get("inferred_time", "")
    date_str = ""
    if timestamp:
        try:
            date_str = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y%m%d")
        except (ValueError, TypeError, KeyError):
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", timestamp)
            if m:
                date_str = f"{m.group(1)}{m.group(2)}{m.group(3)}"
    return f"{participants_str}-{action}-{date_str}"


def _iso_to_yyyymmdd(iso_string: str) -> Optional[str]:
    """Convert an ISO-8601 timestamp string to YYYYMMDD.

    Args:
        iso_string: An ISO-8601 datetime string.

    Returns:
        YYYYMMDD string, or None if parsing fails.
    """
    if not iso_string:
        return None
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y%m%d")
    except (ValueError, TypeError):
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", iso_string)
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"
        return None


@dataclass
class EventCandidate:
    """A candidate event with signature and inferred date.

    Attributes:
        unit: The source MemoryUnit.
        signature: Normalized signature from _generate_signature.
        inferred_date: YYYYMMDD date string derived from the timestamp.
    """
    unit: MemoryUnit
    signature: str
    inferred_date: str


class EventDeduplicator:
    """Deduplicates events using signature matching and LLM confirmation.

    Two-stage pipeline:
    1. Quick match: scan existing signatures for potential duplicates.
    2. Detailed confirm: LLM compares matched pairs and produces a merged
       canonical event with confidence score.

    Args:
        llm_provider: LLM provider for detailed confirmation calls.
        similarity_threshold: Minimum confidence to accept a merge (default 0.85).
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        similarity_threshold: float = 0.85,
    ):
        self._llm = llm_provider
        self._threshold = float(similarity_threshold)

    def deduplicate(
        self,
        events: Sequence[MemoryUnit],
    ) -> List[MemoryUnit]:
        """Deduplicate a batch of event memory units.

        Args:
            events: Event MemoryUnits to deduplicate.

        Returns:
            List of unique event MemoryUnits after merging duplicates.
        """
        if not events:
            return []

        candidates = self._extract_candidates(events)
        if not candidates:
            return []

        date_buckets: Dict[str, List[EventCandidate]] = {}
        for c in candidates:
            if c.inferred_date:
                date_buckets.setdefault(c.inferred_date, []).append(c)
            else:
                date_buckets.setdefault("unknown", []).append(c)

        merged_events: List[Dict[str, Any]] = []
        existing_signatures: List[str] = []

        for date, bucket in date_buckets.items():
            for candidate in bucket:
                is_dup, matched_sigs, conf = self._quick_match(
                    candidate, existing_signatures
                )

                if not is_dup:
                    merged_events.append({
                        "unit": candidate.unit,
                        "signature": candidate.signature,
                        "confidence": conf,
                    })
                    existing_signatures.append(candidate.signature)
                else:
                    matched = next(
                        (me for me in merged_events if me["signature"] in matched_sigs),
                        None
                    )
                    if matched:
                        is_same, merged, conf = self._detailed_merge(matched["unit"], candidate.unit)
                        if is_same and merged:
                            new_sig = merged.get("signature", candidate.signature)
                            merged_events = [
                                me for me in merged_events if me["signature"] != matched["signature"]
                            ]
                            merged_events.append({
                                "unit": MemoryUnit(
                                    uid=Uid(f"event:{new_sig[:50]}"),
                                    raw_data={
                                        "text_content": merged.get("event_description", ""),
                                        "participants": merged.get("participants", []),
                                    },
                                    metadata={
                                        "type": "event",
                                        "signature": new_sig,
                                        "merged_from_signatures": [matched["signature"], candidate.signature],
                                    },
                                ),
                                "signature": new_sig,
                                "confidence": conf,
                            })
                            existing_signatures = [
                                s if s != matched["signature"] else new_sig for s in existing_signatures
                            ]
                        else:
                            merged_events.append({
                                "unit": candidate.unit,
                                "signature": candidate.signature,
                                "confidence": conf,
                            })
                            existing_signatures.append(candidate.signature)

        return [me["unit"] for me in merged_events]

    def _extract_candidates(self, events: Sequence[MemoryUnit]) -> List[EventCandidate]:
        candidates = []
        for event in events:
            sig = _generate_signature(event)
            inferred_time = event.metadata.get("inferred_time", "")
            inferred_date = _iso_to_yyyymmdd(inferred_time) or ""
            candidates.append(EventCandidate(
                unit=event,
                signature=sig,
                inferred_date=inferred_date,
            ))
        return candidates

    def _quick_match(
        self,
        candidate: EventCandidate,
        existing_signatures: List[str],
    ) -> tuple[bool, List[str], float]:
        if not existing_signatures:
            return False, [], 0.0

        filtered = [
            sig for sig in existing_signatures
            if sig.split("-")[-1] == candidate.inferred_date
        ] if candidate.inferred_date else list(existing_signatures)

        if not filtered:
            return False, [], 0.0

        prompt = EVENT_QUICK_MATCH_PROMPT.format(
            signatures=json.dumps(filtered, ensure_ascii=False),
            new_event=json.dumps({
                "signature": candidate.signature,
                "text": candidate.unit.raw_data.get("text_content", ""),
                "participants": candidate.unit.metadata.get("participants", []),
            }, ensure_ascii=False),
        )

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._llm.chat(messages, temperature=0.1, max_tokens=512)
            data = json.loads(response.content)
            return (
                bool(data.get("is_duplicate", False)),
                list(data.get("matched_signatures", [])),
                float(data.get("decision_confidence", 0.5)),
            )
        except (json.JSONDecodeError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            logger.error("Event quick match failed: %s", e)
            return False, [], 0.5

    def _detailed_merge(
        self,
        existing: MemoryUnit,
        new: MemoryUnit,
    ) -> tuple[bool, Optional[Dict[str, Any]], float]:
        prompt = EVENT_DETAILED_CONFIRM_PROMPT.format(
            existing_event=json.dumps({
                "text": existing.raw_data.get("text_content", ""),
                "participants": existing.metadata.get("participants", []),
                "signature": _generate_signature(existing),
            }, ensure_ascii=False),
            new_event=json.dumps({
                "text": new.raw_data.get("text_content", ""),
                "participants": new.metadata.get("participants", []),
                "signature": _generate_signature(new),
            }, ensure_ascii=False),
        )

        messages: List[ChatMessage] = [
            {"role": "user", "content": prompt},
        ]

        try:
            response = self._llm.chat(messages, temperature=0.1, max_tokens=32768)
            data = json.loads(response.content)
            is_same = bool(data.get("is_same_event", False))
            merged = data.get("merged_event") if is_same else None
            return is_same, merged, float(data.get("decision_confidence", 0.5))
        except (json.JSONDecodeError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            logger.error("Event detailed merge failed: %s", e)
            return False, None, 0.5

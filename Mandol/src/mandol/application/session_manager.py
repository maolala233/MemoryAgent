"""Session detection and segmentation for conversational memory.

Uses LLM-based analysis to identify topic boundaries in continuous dialogue
streams, splitting long conversations into discrete sessions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..domain.types import Uid
from ..ports.llm_provider import ChatMessage, LLMProvider
from ._llm_retry import retry_llm_json_call, strip_json_fences

logger = logging.getLogger(__name__)


# System prompt: semantic-first session boundaries, flat JSON
# (reasoning + boundaries + should_wait) for reliable parsing.
SESSION_SYSTEM_PROMPT = """你是一名会话边界识别专家，专门负责把连续对话流切分成独立的会话（MemCells / 记忆单元）。

**重要语言规则**：`reasoning` 字段必须与下方对话片段的语言保持一致。片段主要为中文就用中文写 reasoning；主要为英文就用英文。不要混合语言。

**核心原则**：默认合并不分割；只有出现明确语义 / 主题中断时才切分。优先看主题与话语流转，而不是单纯看时间间隔：单纯的长静默不足以触发分割，必须配合明显的新主题。

### 会话（情节）定义
一个会话 = 参与者可以视为同一情节的连贯主线（同一具体目标、问题、计划，或紧密相关的子主题）。

### 何时添加边界（基于 1-based 消息索引，见输出说明）
仅在出现以下**明确信号**时添加边界：
- **强烈主题转换**：对话进入明显不相关的话题（例如：部署调试 → 周末出行）。
- **显式情节切换**：类似"对了"、"换个话题"、"我们聊聊……"等开启新主题的表达（非短暂旁注）。
- **任务收尾 + 不相关后续**：任务收尾的最后一行归入该情节；只有当**之后**的消息开启全新独立情节时才切分。
- **时间作为弱提示**：较大的时间间隔只能作为辅助证据，必须同时存在**明确**新主题；绝不能仅因时间戳远就切分。

### 不要因以下情况切分
- 问候、感谢、简短确认（"好的"、"知道了"）—— 归入它们依附的情节。
- 仍与同一主线相关的轻量旁注或"顺便一提"。
- 同一会议或同一持续问题内部的自然漂移。
- **系统/占位尾段**：若末尾仅含 `[图片]`/`[视频]` 等无文本占位，或仅有无主题的"ok"/表情，应使用 `should_wait` 而非硬造边界。

### `should_wait`
当本批次**末尾**过薄、不足以负责任地确定边界时，设为 true：
- 末尾仅含非文本占位或极简回复。
- 系统性语句不携带会话主题。
- 末尾模糊，无法判断是否延续同一情节。

`should_wait` 为 true 时，`boundaries` 设为 []（本批不切分；后续会获得更多上下文）。

### 多个边界
仅当本批次存在**两处或以上**明确断裂时使用。完全以语义主题变更作为切分准则；不强制最小段长。

### 输出格式（仅单个 JSON 对象）
不要 markdown 代码块，JSON 前后无任何文本。所有字符串放一行（`reasoning` 内不要有原始换行）。

Schema:
{
  "reasoning": "<用一句话概括所有边界决策>",
  "boundaries": [<int>, ...],
  "should_wait": <boolean>
}

**boundaries**：每个整数是日志中带 `[k]` 前缀的**1-based 行索引**。含义：在该消息**之后**切分——下一行开启**新**会话。例如 boundaries [4] 表示第 [1]–[4] 行留在当前会话；第 [5] 行起开启新会话。空数组 [] 表示本批不切分。

### 示例 A（中文）
输入行（节选）：
[1] ... 小李: 帮我看看登录问题
[2] ... 小王: 我查一下日志
[3] ... 小王: AuthService 里有空指针
[4] ... 小李: 改好了，谢谢！
[5] ... 小李: 中午一起吃饭？
[6] ... 小王: 12:30 可以

输出：
{"reasoning": "消息 1-4 完成了一次 bug 修复；消息 5 开启了新的吃饭话题。", "boundaries": [4], "should_wait": false}

### 示例 B（无边界）
输出：
{"reasoning": "所有行都围绕同一产品演进讨论，没有出现新的独立主题。", "boundaries": [], "should_wait": false}

### 示例 C（非中文）
若输入行主要是关于同一项目的非中文需求澄清：
{"reasoning": "整段对话都围绕同一需求澄清，没有新独立主题，因此不切分。", "boundaries": [], "should_wait": false}"""


SESSION_USER_PROMPT = """当前会话 ID：{session_id}

{previous_reasoning_block}
### 记忆片段（按时间顺序，同一发言者）
每行格式：[1-based 索引] 时间戳: 文本

{content}

严格按系统消息中定义的 JSON 格式返回单个对象（不要 markdown，JSON 之外不要有任何文字）。"""


def estimate_tokens(text: str) -> int:
    """Estimate token count using a heuristic character-based model.

    Chinese characters: 0.6 tokens each.
    ASCII alphabetic: 0.3 tokens each.
    Other characters: 0.4 tokens each.

    Args:
        text: The input text to estimate.

    Returns:
        Estimated token count as an integer.
    """
    chinese_chars = len([c for c in text if "一" <= c <= "鿿"])
    english_chars = len([c for c in text if c.isalpha() and ord(c) < 128])
    other_chars = len(text) - chinese_chars - english_chars
    return int(chinese_chars * 0.6 + english_chars * 0.3 + other_chars * 0.4)


def _format_previous_reasoning_block(previous_reasoning: str, max_tokens: int = 300) -> str:
    """Format the previous reasoning for injection into the user prompt.

    Truncates from the tail if it exceeds max_tokens.

    Args:
        previous_reasoning: The reasoning string from the previous batch.
        max_tokens: Maximum token budget for the block.

    Returns:
        Empty string if previous_reasoning is empty, or a formatted block.
    """
    if not previous_reasoning.strip():
        return ""
    if estimate_tokens(previous_reasoning) > max_tokens:
        # Truncate from tail: keep last ~(max_tokens - overhead) tokens
        # Simple approach: keep last N chars proportional to max_tokens
        chars_per_token = len(previous_reasoning) / max(1, estimate_tokens(previous_reasoning))
        keep_chars = int((max_tokens - 20) * chars_per_token)
        previous_reasoning = "…(truncated) " + previous_reasoning[-keep_chars:]
    return f"### 上一批次的推理（仅作参考）\n上一批次的分析结论是：{previous_reasoning}\n"


@dataclass
class Session:
    """A discrete conversational session.

    Attributes:
        session_id: Unique identifier for the session.
        unit_uids: Ordered list of MemoryUnit UIDs in this session.
        start_time: ISO-format timestamp of the first unit.
        end_time: ISO-format timestamp of the last unit.
        topic: Human-readable topic label for the session.
    """

    session_id: str
    unit_uids: List[Uid] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    topic: str = ""

    @property
    def unit_count(self) -> int:
        return len(self.unit_uids)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the session to a plain dict."""
        return {
            "session_id": self.session_id,
            "unit_uids": [str(u) for u in self.unit_uids],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "topic": self.topic,
        }


@dataclass
class SessionSplitPoint:
    """A single split boundary within a session.

    Attributes:
        split_at_index: The fragment index where the new session starts (0-indexed).
        topic: Topic label for the new session.
        reason: Explanation for why this split was chosen.
    """

    split_at_index: int
    topic: str = ""
    reason: str = ""


@dataclass
class SessionSplitDecision:
    """Result of a session boundary analysis.

    Attributes:
        should_split: Whether the content should be split.
        split_at_index: Index of the first split point (for backwards compatibility).
        topic: Topic of the first new session (often inferred downstream).
        split_points: All split points when multiple splits are detected.
        reasoning: One-sentence LLM rationale (new JSON schema); may be empty.
        should_wait: When True, the tail was ambiguous — no split was applied for this batch.
    """

    should_split: bool
    split_at_index: Optional[int] = None
    topic: str = ""
    split_points: List[SessionSplitPoint] = field(default_factory=list)
    reasoning: str = ""
    should_wait: bool = False


class SessionManager:
    """Detects and manages conversational session boundaries.

    Provides a single-entry LLM-based batch analysis method (analyze_batch)
    and session storage/query methods. Does NOT manage cross-batch state
    (reasoning chain, session assignment filtering, batch sizing) — that is the
    caller's responsibility (MemorySystem).

    Args:
        llm_provider: The LLM provider used for split decision analysis.
        max_unit_count: Maximum units per batch before forced analysis (default 20).
        time_gap_threshold_seconds: Time gap hint injected into the session
            detection prompt for LLM reference only. Not used for hard splitting.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_unit_count: int = 20,
        time_gap_threshold_seconds: int = 1800,
    ):
        self._llm = llm_provider
        self._max_unit_count = int(max_unit_count)
        self._time_gap_threshold = int(time_gap_threshold_seconds)  # Unused. Retained for backward compatibility.
        self._sessions: List[Session] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_batch(
        self,
        content_lines: List[str],
        session_id: str,
        previous_reasoning: str = "",
        on_warning: Optional[Callable[[str], None]] = None,
    ) -> SessionSplitDecision:
        """Analyze a single batch of formatted content lines for session boundaries.

        This is the single entry point for LLM-based session boundary detection.
        It assembles the system + user prompts, calls the LLM with retry, and
        parses the V2 JSON response.

        On LLM failure (retries exhausted): returns a no-split decision with a
        warning log. The caller is responsible for merging the batch into the
        current session without splitting.

        Args:
            content_lines: Formatted lines, each "[idx] timestamp: text".
            session_id: Current session ID for context.
            previous_reasoning: Reasoning from the previous batch (already
                truncated to ~300 tokens by the caller).
            on_warning: Optional callback for warning accumulation.

        Returns:
            SessionSplitDecision with boundaries, reasoning, and should_wait.
        """
        previous_block = _format_previous_reasoning_block(previous_reasoning)
        content = "\n".join(content_lines)

        combined = SESSION_SYSTEM_PROMPT + "\n\n" + SESSION_USER_PROMPT.format(
            session_id=session_id,
            previous_reasoning_block=previous_block,
            content=content,
        )
        messages: List[ChatMessage] = [
            {"role": "user", "content": combined},
        ]

        try:
            decision = retry_llm_json_call(
                self._llm,
                messages,
                lambda resp: self._parse_v2_response(resp, len(content_lines)),
                temperature=0.1,
                max_tokens=32768,
                context_label=f"session_split_{session_id}",
            )
            split_info = (
                ", ".join(
                    [
                        f"idx={sp.split_at_index}({sp.topic})"
                        for sp in decision.split_points
                    ]
                )
                if decision.split_points
                else "none"
            )
            logger.info(
                "SessionManager analyze_batch: should_split=%s should_wait=%s splits=[%s] reasoning=%.200s",
                decision.should_split,
                decision.should_wait,
                split_info,
                decision.reasoning or "",
            )
            return decision
        except json.JSONDecodeError:
            # retry_llm_json_call exhausted all retries — LLM persistently
            # returned unparseable output.
            msg = (
                f"[FALLBACK] Session split LLM returned unparseable JSON "
                f"for session {session_id} after all retries. "
                f"Returning no-split — {len(content_lines)} units "
                f"will be merged without boundary detection."
            )
            logger.error(msg)
            if on_warning:
                on_warning(msg)
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Network, timeout, or provider-level API errors.
            msg = (
                f"[FALLBACK] Session split LLM call FAILED for session {session_id}: {e}. "
                f"Returning no-split — {len(content_lines)} units "
                f"will be merged without boundary detection."
            )
            logger.error(msg)
            if on_warning:
                on_warning(msg)
        return SessionSplitDecision(
            should_split=False,
            split_at_index=None,
            topic="",
            split_points=[],
            reasoning="",
            should_wait=False,
        )

    # ------------------------------------------------------------------
    # Session storage / query
    # ------------------------------------------------------------------

    def add_session(
        self,
        session_id: str,
        unit_uids: List[str],
    ) -> Session:
        """Manually register a session with the given units.

        Args:
            session_id: Unique session identifier.
            unit_uids: List of Unit UID strings.

        Returns:
            The newly created Session object.
        """
        session = Session(
            session_id=session_id,
            unit_uids=[Uid(u) for u in unit_uids],
        )
        self._sessions.append(session)
        return session

    def get_sessions(self) -> List[Session]:
        """Return all tracked sessions.

        Returns:
            Copy of the internal session list.
        """
        return list(self._sessions)

    def reset(self) -> None:
        """Clear all tracked sessions."""
        self._sessions.clear()

    # ------------------------------------------------------------------
    # Internal: V2 JSON parsing
    # ------------------------------------------------------------------

    def _parse_v2_response(
        self,
        response: str,
        content_count: int,
    ) -> SessionSplitDecision:
        """Parse flat JSON: reasoning, boundaries (1-based after-index), should_wait."""
        data = json.loads(strip_json_fences(response))
        reasoning = str(data.get("reasoning", "")).replace("\n", " ").strip()
        should_wait = bool(data.get("should_wait", False))

        if should_wait:
            logger.info(
                "Session split deferred (should_wait): %.200s",
                reasoning or "(no reasoning)",
            )
            return SessionSplitDecision(
                should_split=False,
                split_at_index=None,
                topic="",
                split_points=[],
                reasoning=reasoning,
                should_wait=True,
            )

        raw_bounds = data.get("boundaries", [])
        if not isinstance(raw_bounds, list):
            raw_bounds = []

        boundaries: List[int] = []
        for b in raw_bounds:
            try:
                boundaries.append(int(b))
            except (ValueError, TypeError):
                continue

        boundaries = sorted(set(boundaries))
        split_points: List[SessionSplitPoint] = []

        # 1-based "after line b" => 0-based first index of new session == b
        max_b = content_count - 1
        for b in boundaries:
            if 1 <= b <= max_b:
                split_points.append(
                    SessionSplitPoint(
                        split_at_index=b,
                        topic="",
                        reason=reasoning,
                    ),
                )
            else:
                logger.warning(
                    "boundary %s invalid for batch size %s (valid 1..%s), skipping",
                    b,
                    content_count,
                    max_b,
                )

        should_split = len(split_points) > 0
        return SessionSplitDecision(
            should_split=should_split,
            split_at_index=split_points[0].split_at_index if split_points else None,
            topic="",
            split_points=split_points,
            reasoning=reasoning,
            should_wait=False,
        )

    # ------------------------------------------------------------------
    # Helpers (used by MemorySystem)
    # ------------------------------------------------------------------

    def build_session(
        self,
        session_id: str,
        unit_uids: List[str],
        topic: str = "",
        start_time: str = "",
        end_time: str = "",
    ) -> Session:
        """Build a Session object with the given parameters.

        Args:
            session_id: Unique session identifier.
            unit_uids: List of unit UID strings.
            topic: Human-readable topic label.
            start_time: ISO-format start timestamp.
            end_time: ISO-format end timestamp.

        Returns:
            The newly created Session.
        """
        session = Session(
            session_id=session_id,
            unit_uids=[Uid(u) for u in unit_uids],
            topic=topic,
            start_time=start_time,
            end_time=end_time,
        )
        self._sessions.append(session)
        return session

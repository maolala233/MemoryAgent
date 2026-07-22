"""Prompt for LLM-based event match judging.

Determines whether a newly extracted event refers to the same real-world
occurrence as a known canonical event candidate.
"""

# LLM prompt for pairwise event matching with confidence scoring.
# Inputs: new event details and list of candidate canonical events.
# Output: JSON with matched boolean, canonical_id, confidence, reasoning.
EVENT_MATCH_JUDGE_PROMPT = """你是核心指代消解与事件匹配专家。

给定一个新抽取的事件和一组候选规范事件，判断新事件是否指代与某候选相同的现实世界事件。

## 新事件
名称: {new_event_name}
描述: {new_event_description}
参与者: {new_participants}
时间: {new_time}
事实: {new_facts}

## 候选规范事件
{candidates}

## 任务说明
1. 将新事件与每个候选仔细对比。
2. 综合考虑：事件名称相似度、描述重叠度、参与者重叠度、时间邻近性、地点一致性。
3. 若新事件明显指代与某候选相同的现实事件，选出该候选。
4. 若新事件与所有候选均不同，输出无匹配。
5. 不同会话可能从不同视角描述同一现实事件。
6. 名称比较时注意中英文别名/简称差异。

## 输出格式
返回 JSON 对象：
```json
{{
    "matched_index": <整数或 null>,
    "confidence": <0.0~1.0 之间的浮点数>,
    "canonical_name_suggestion": <字符串或 null>,
    "reasoning": "<简要说明>"
}}
```

字段说明：
- `matched_index`：匹配候选的 0-based 索引，无匹配则为 null
- `confidence`：对该匹配决策的置信度（0.0 = 无信心，1.0 = 绝对确定）
- `canonical_name_suggestion`：若合并，建议的规范名称（或 null 保持原名）
- `reasoning`：决策的简要说明
"""
